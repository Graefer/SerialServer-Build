#!/usr/bin/env python3
"""
Quick Port Check - Zeigt die Description des NIDEK-Ports
"""
import serial.tools.list_ports

print("Suche nach /dev/tty.usbserial-FTFO13HP...")
print()

for port in serial.tools.list_ports.comports():
    if "FTFO13HP" in port.device or "usbserial" in port.device:
        print(f"✅ GEFUNDEN: {port.device}")
        print(f"   Description: '{port.description}'")
        print(f"   Manufacturer: '{port.manufacturer}'")
        print(f"   VID: 0x{port.vid:04x}" if port.vid else "   VID: None")
        print(f"   PID: 0x{port.pid:04x}" if port.pid else "   PID: None")
        print()
        print("📋 Verwende diese Config:")
        print("{")
        print(f'  "description": "{port.description}",')
        print('  "baudrate": 2400,')
        print('  "databits": 7,')
        print('  "stopbits": 2,')
        print('  "parity": "O"')
        print("}")
        print()
        print("ODER mit VID/PID:")
        if port.vid:
            print("{")
            print(f'  "vid": "0x{port.vid:04x}",')
            if port.pid:
                print(f'  "pid": "0x{port.pid:04x}",')
            print('  "baudrate": 2400,')
            print('  "databits": 7,')
            print('  "stopbits": 2,')
            print('  "parity": "O"')
            print("}")
        break
else:
    print("❌ Port nicht gefunden!")
    print()
    print("Alle verfügbaren Ports:")
    for port in serial.tools.list_ports.comports():
        print(f"  • {port.device} - {port.description}")
