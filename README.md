# Serial WebSocket Server v1.2

macOS Installer für den Serial WebSocket Server - speziell für NIDEK RT-5100 Autorefraktometer.

## Features

- Automatische USB-Serial Erkennung (VID/PID-basiert)
- WebSocket Push-Benachrichtigungen in Echtzeit
- NIDEK RT-5100 Protokoll: 2400/7-O-2, DTR=True, RTS=False
- Timeout-basiertes Message Buffering (0.5s)
- Zeilenenden-Normalisierung (CR/CRLF → LF)
- macOS PKG Installer mit LaunchDaemon
- Autostart bei Systemstart, Auto-Reconnect

## Installation

```bash
# DMG bauen
bash build-installer.sh

# DMG öffnen und PKG installieren
open SerialServer-1.2.dmg
```

## Endpoints

| Endpoint | Beschreibung |
|----------|-------------|
| `http://localhost:8765/health` | Health Check |
| `http://localhost:8765/devices` | Geräte-Status |
| `ws://localhost:8765/ws` | WebSocket Live-Daten |

## Konfiguration

`/usr/local/serialserver/config.json`

## Deinstallation

```bash
sudo bash uninstall.sh
```
