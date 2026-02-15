# Serial WebSocket Server v1.3 – On-Demand Edition

macOS Installer für den NIDEK RT-5100 Autorefraktometer Serial-WebSocket-Bridge.

**On-Demand:** Serial Ports werden erst geöffnet wenn die PVS-App eine WebSocket-Verbindung herstellt, und automatisch geschlossen wenn die App beendet wird.

## Schnellstart

```bash
chmod +x build-installer.sh
./build-installer.sh
```

Erstellt: `SerialServer-1.3.dmg`

## User-Installation (per Doppelklick)

1. **DMG öffnen** – Doppelklick auf `SerialServer-1.3.dmg`
2. **PKG öffnen** – Doppelklick auf `SerialServer.pkg`
3. **Installer folgen** – Administrator-Passwort eingeben
4. **Fertig!**

### Was passiert automatisch

- Dateien nach `/usr/local/serialserver` kopiert
- Python Virtual Environment erstellt
- Dependencies installiert (Flask, PySerial, etc.)
- LaunchDaemon in `/Library/LaunchDaemons/` eingerichtet
- Service gestartet und läuft bei jedem Neustart

## Nach Installation

Server läuft automatisch auf:

- **HTTP:** `http://localhost:8765`
- **WebSocket:** `ws://localhost:8765/ws`
- **Health:** `http://localhost:8765/health`

## Konfiguration anpassen

```bash
sudo nano /usr/local/serialserver/config.json
sudo launchctl kickstart -k system/com.serialserver
```

## Service-Verwaltung

```bash
# Status
sudo launchctl list | grep serialserver

# Neu starten
sudo launchctl kickstart -k system/com.serialserver

# Logs
tail -f /usr/local/serialserver/logs/server.log

# Stoppen
sudo launchctl unload /Library/LaunchDaemons/com.serialserver.plist
```

## Deinstallation

Entweder das mitgelieferte Script im DMG nutzen:

```bash
sudo bash /Volumes/Serial\ Server\ 1.3/uninstall.sh
```

Oder manuell:

```bash
sudo launchctl unload /Library/LaunchDaemons/com.serialserver.plist
sudo rm -rf /usr/local/serialserver
sudo rm /Library/LaunchDaemons/com.serialserver.plist
sudo pkgutil --forget com.serialserver
```

## Build-Voraussetzungen

- macOS mit Xcode Command Line Tools
- `pkgbuild` und `productbuild` (auf macOS vorinstalliert)

## Verzeichnisstruktur

```
SerialServer-Build/
├── serialserver/              # Server-Dateien
│   ├── server.py              # Hauptprogramm
│   ├── config.json            # Geräte-Konfiguration
│   └── com.serialserver.plist # LaunchDaemon
├── resources/                 # Installer-UI
│   ├── welcome.html
│   ├── readme.html
│   └── conclusion.html
├── build-installer.sh         # Build-Script
├── quick-check.py             # Port-Diagnose-Tool
└── README.md
```
