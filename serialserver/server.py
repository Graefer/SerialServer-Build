#!/usr/bin/env python3
"""Serial WebSocket Server v1.2 - Mit DTR/RTS Support für NIDEK RT-5100"""

from flask import Flask, jsonify
from flask_sock import Sock
from flask_cors import CORS
import serial
import serial.tools.list_ports
import threading
import time
import json
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(log_file, log_level):
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
    )
    return logging.getLogger(__name__)


# Konfiguration laden
config_path = Path(__file__).parent / 'config.json'
with open(config_path, 'r') as f:
    CONFIG = json.load(f)

logger = setup_logging(CONFIG['logging']['file'], CONFIG['logging']['level'])

app = Flask(__name__)
sock = Sock(app)
CORS(app)

# Globaler State
port_data = {}
active_serial_connections = {}
websocket_clients = []
data_lock = threading.Lock()
running = True


def find_port_by_config(config):
    """Findet einen seriellen Port anhand der Konfiguration (VID/PID/Serial/Description)."""
    ports = serial.tools.list_ports.comports()
    
    logger.debug(f"Suche Port mit Config: {config}")
    logger.debug(f"Verfügbare Ports: {len(ports)}")
    
    for port in ports:
        logger.debug(f"Prüfe Port: {port.device}")
        logger.debug(f"  VID: {hex(port.vid) if port.vid else 'None'}")
        logger.debug(f"  PID: {hex(port.pid) if port.pid else 'None'}")
        logger.debug(f"  Serial: {port.serial_number}")
        logger.debug(f"  Description: {port.description}")
        
        # VID Filter
        if config.get('vid'):
            expected_vid = int(config['vid'], 16) if isinstance(config['vid'], str) else config['vid']
            if port.vid != expected_vid:
                logger.debug(f"  VID mismatch: {hex(port.vid) if port.vid else 'None'} != {hex(expected_vid)}")
                continue
        
        # PID Filter
        if config.get('pid'):
            expected_pid = int(config['pid'], 16) if isinstance(config['pid'], str) else config['pid']
            if port.pid != expected_pid:
                logger.debug(f"  PID mismatch: {hex(port.pid) if port.pid else 'None'} != {hex(expected_pid)}")
                continue
        
        # Serial Number Filter
        if config.get('serial_number') and port.serial_number != config['serial_number']:
            logger.debug(f"  Serial mismatch: {port.serial_number} != {config['serial_number']}")
            continue
        
        # Description Filter
        if config.get('description'):
            if config['description'].lower() not in port.description.lower():
                logger.debug(f"  Description mismatch")
                continue
        
        # Wenn wir hier sind, passt der Port!
        logger.info(f"Port gefunden: {port.device}")
        return port.device
    
    logger.warning("Kein passender Port gefunden!")
    return None


def broadcast_to_clients(message):
    """Sendet eine Nachricht an alle verbundenen WebSocket-Clients."""
    with data_lock:
        dead_clients = []
        for ws in websocket_clients:
            try:
                ws.send(json.dumps(message))
            except Exception:
                dead_clients.append(ws)
        for ws in dead_clients:
            websocket_clients.remove(ws)


def read_serial_port(device_config):
    """Thread-Funktion: Liest kontinuierlich Daten von einem seriellen Port."""
    device_name = device_config['name']
    buffer_size = device_config.get('buffer_size', 1024)

    with data_lock:
        port_data[device_name] = {
            'data': None,
            'timestamp': None,
            'received': False,
            'connected': False,
            'port': None
        }

    ser = None
    message_buffer = b''  # Sammelt den gesamten NIDEK-Datenblock
    last_receive_time = None  # Zeitpunkt des letzten empfangenen Bytes
    MESSAGE_TIMEOUT = 0.5  # Sekunden ohne Daten = Block komplett
    port_path = None
    logger.info(f"[{device_name}] Thread gestartet")

    while running:
        try:
            # Verbindung herstellen falls nötig
            if ser is None or not ser.is_open:
                port_path = find_port_by_config(device_config)
                if port_path:
                    # Port öffnen
                    ser = serial.Serial(
                        port=port_path,
                        baudrate=device_config['baudrate'],
                        bytesize=device_config['databits'],
                        parity=device_config['parity'],
                        stopbits=device_config['stopbits'],
                        timeout=1
                    )

                    # DTR/RTS setzen (NIDEK RT-5100)
                    ser.dtr = True
                    ser.rts = False
                    logger.info(f"[{device_name}] DTR=True, RTS=False gesetzt")
                    time.sleep(0.2)
                    
                    with data_lock:
                        active_serial_connections[device_name] = ser
                        port_data[device_name]['connected'] = True
                        port_data[device_name]['port'] = port_path
                    
                    logger.info(f"[{device_name}] Verbunden: {port_path}")
                    logger.info(f"[{device_name}] Config: {device_config['baudrate']}/{device_config['databits']}-{device_config['parity']}-{device_config['stopbits']}")
                    
                    broadcast_to_clients({
                        'type': 'device_status',
                        'device': device_name,
                        'connected': True,
                        'port': port_path,
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    with data_lock:
                        port_data[device_name]['connected'] = False
                    time.sleep(2)
                    continue

            # Prüfen ob der Port noch physisch existiert
            if not Path(port_path).exists():
                logger.warning(f"[{device_name}] Port {port_path} nicht mehr vorhanden")
                raise serial.SerialException(f"Port {port_path} verschwunden")

            # Daten lesen und sammeln bis Sendepause
            if ser.in_waiting:
                chunk = ser.read(ser.in_waiting)
                message_buffer += chunk
                last_receive_time = time.time()
                logger.debug(f"[{device_name}] Empfangen: {len(chunk)} bytes (Gesamt: {len(message_buffer)})")

                # Buffer-Overflow-Schutz
                if len(message_buffer) >= buffer_size:
                    logger.warning(f"[{device_name}] Buffer overflow ({len(message_buffer)} bytes), sende Block")
                    last_receive_time = time.time() - MESSAGE_TIMEOUT  # Sofort senden

            # Prüfe ob gesammelter Block komplett ist (Sendepause erreicht)
            elif message_buffer and last_receive_time:
                if time.time() - last_receive_time >= MESSAGE_TIMEOUT:
                    # Decode und Zeilenenden normalisieren (NIDEK sendet \r als Trenner)
                    data_str = message_buffer.decode('utf-8', errors='ignore')
                    data_str = data_str.replace('\r\n', '\n').replace('\r', '\n').strip()
                    timestamp = datetime.now().isoformat()

                    data_payload = {
                        'data': data_str,
                        'timestamp': timestamp,
                        'received': True,
                        'connected': True,
                        'port': port_path,
                        'size': len(message_buffer)
                    }

                    with data_lock:
                        port_data[device_name] = data_payload

                    logger.info(f"[{device_name}] BLOCK KOMPLETT ({len(message_buffer)} bytes): {data_str[:100]}")
                    logger.debug(f"[{device_name}] HEX: {message_buffer.hex()}")

                    broadcast_to_clients({
                        'type': 'measurement',
                        'device': device_name,
                        'data': data_str,
                        'timestamp': timestamp
                    })

                    message_buffer = b''
                    last_receive_time = None
                else:
                    time.sleep(0.05)  # Kurz warten auf weitere Daten
            else:
                time.sleep(0.1)

        except serial.SerialException as e:
            logger.error(f"[{device_name}] Serial Error: {e}")
            if ser:
                try:
                    ser.close()
                except:
                    pass
                ser = None
            with data_lock:
                port_data[device_name]['connected'] = False
            broadcast_to_clients({
                'type': 'device_status',
                'device': device_name,
                'connected': False,
                'timestamp': datetime.now().isoformat()
            })
            time.sleep(2)
        
        except Exception as e:
            logger.error(f"[{device_name}] Unerwarteter Fehler: {e}")
            time.sleep(2)

    # Cleanup beim Beenden
    if ser and ser.is_open:
        ser.close()
    logger.info(f"[{device_name}] Thread beendet")


@app.route('/health')
def health():
    """Health Check Endpoint"""
    with data_lock:
        devices = {}
        for device_name, data in port_data.items():
            devices[device_name] = {
                'connected': data.get('connected', False),
                'port': data.get('port')
            }
    return jsonify({'status': 'healthy', 'devices': devices})


@app.route('/devices')
def devices():
    """Gibt Geräte-Status zurück"""
    with data_lock:
        return jsonify(port_data)


@sock.route('/ws')
def websocket(ws):
    """WebSocket Endpoint für Live-Daten"""
    logger.info("WebSocket Client verbunden")
    
    with data_lock:
        websocket_clients.append(ws)
    
    try:
        # Initial state sammeln (unter Lock) und senden (ohne Lock)
        with data_lock:
            initial_messages = []
            for device_name, data in port_data.items():
                initial_messages.append(json.dumps({
                    'type': 'device_status',
                    'device': device_name,
                    'connected': data.get('connected', False),
                    'port': data.get('port'),
                    'timestamp': datetime.now().isoformat()
                }))
        for msg in initial_messages:
            ws.send(msg)

        # Auf Nachrichten warten (keep-alive)
        while True:
            data = ws.receive()
            if data is None:
                break
    except Exception as e:
        logger.info(f"WebSocket Error: {e}")
    finally:
        with data_lock:
            if ws in websocket_clients:
                websocket_clients.remove(ws)
        logger.info("WebSocket Client getrennt")


def signal_handler(sig, frame):
    """Graceful Shutdown"""
    global running
    logger.info("Shutdown Signal empfangen...")
    running = False
    
    # Serielle Verbindungen schließen
    with data_lock:
        for ser in active_serial_connections.values():
            if ser and ser.is_open:
                ser.close()
    
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 60)
    logger.info("Serial WebSocket Server v1.2 - NIDEK RT-5100 Edition")
    logger.info("=" * 60)
    logger.info(f"Config: {config_path}")
    logger.info(f"Geräte: {len(CONFIG['devices'])}")
    
    # Device-Threads starten
    threads = []
    for device_config in CONFIG['devices']:
        logger.info(f"Starte Thread für: {device_config['name']}")
        t = threading.Thread(target=read_serial_port, args=(device_config,), daemon=True)
        t.start()
        threads.append(t)
    
    # Flask Server starten
    host = CONFIG['server']['host']
    port = CONFIG['server']['port']
    logger.info(f"Server startet auf {host}:{port}")
    logger.info("=" * 60)
    
    app.run(host=host, port=port, debug=False)
