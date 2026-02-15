#!/bin/bash

set -e

echo "╔════════════════════════════════════════════╗"
echo "║   Serial Server Installer Builder v1.3    ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Cleanup
echo "🧹 Cleanup alter Builds..."
rm -rf build SerialServer-*.dmg SerialServer-*.pkg

# Verzeichnisse erstellen
echo "📁 Erstelle Build-Verzeichnisse..."
mkdir -p build/pkg-root/usr/local/serialserver
mkdir -p build/scripts
mkdir -p build/resources
mkdir -p build/dmg

# Dateien kopieren
echo "📦 Kopiere Programm-Dateien..."
cp -r serialserver/* build/pkg-root/usr/local/serialserver/
chmod +x build/pkg-root/usr/local/serialserver/server.py

# Resources kopieren
echo "📄 Kopiere Installer-Resources..."
if [ -d resources ]; then
    cp resources/*.html build/resources/ 2>/dev/null || true
fi

# ── Post-Install Script ─────────────────────────────────────────────────────
echo "📝 Erstelle Post-Install Script..."
cat > build/scripts/postinstall << 'EOFPOST'
#!/bin/bash

LOG="/tmp/serialserver-install.log"
exec > >(tee -a "$LOG") 2>&1

echo "========================================"
echo "Serial Server Post-Installation"
echo "Zeit: $(date)"
echo "========================================"

cd /usr/local/serialserver

# Python Check
if ! command -v python3 &> /dev/null; then
    echo "❌ FEHLER: Python 3 nicht gefunden!"
    echo "Bitte installieren Sie Python 3 von https://www.python.org"
    echo "oder via: xcode-select --install"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo "✓ Python gefunden: $PYTHON_VERSION"

# Virtual Environment erstellen
echo "Erstelle Virtual Environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "❌ FEHLER: Konnte venv nicht erstellen"
    echo "Versuche: xcode-select --install"
    exit 1
fi
echo "✓ Virtual Environment erstellt"

# Dependencies installieren
echo "Installiere Dependencies..."
./venv/bin/pip install --upgrade pip > /dev/null 2>&1

./venv/bin/pip install flask flask-sock flask-cors pyserial 2>&1 | tail -5
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "❌ FEHLER: Konnte Pakete nicht installieren"
    echo "Bitte prüfen Sie Ihre Internetverbindung"
    exit 1
fi
echo "✓ Pakete installiert"

# Verzeichnisse und Permissions
echo "Setze Berechtigungen..."
mkdir -p logs
chown -R root:wheel /usr/local/serialserver
chmod +x server.py

# LaunchDaemon installieren
echo "Installiere LaunchDaemon..."
cp com.serialserver.plist /Library/LaunchDaemons/
chown root:wheel /Library/LaunchDaemons/com.serialserver.plist
chmod 644 /Library/LaunchDaemons/com.serialserver.plist

# Alte Installation stoppen (falls vorhanden)
launchctl unload /Library/LaunchDaemons/com.serialserver.plist 2>/dev/null || true

# Service starten
echo "Starte Service..."
launchctl load /Library/LaunchDaemons/com.serialserver.plist
sleep 3

# Verifikation
if curl -s --max-time 5 http://localhost:8765/health > /dev/null 2>&1; then
    echo "✓ Service läuft erfolgreich!"
else
    echo "⚠ Service gestartet, aber Health-Check noch nicht erreichbar"
    echo "  Das kann bei erster Installation normal sein."
    echo "  Prüfe Logs: tail -f /usr/local/serialserver/logs/server.log"
fi

echo "========================================"
echo "✅ Installation abgeschlossen!"
echo "========================================"

exit 0
EOFPOST

chmod +x build/scripts/postinstall

# ── Pre-Install Script ───────────────────────────────────────────────────────
echo "📝 Erstelle Pre-Install Script..."
cat > build/scripts/preinstall << 'EOFPRE'
#!/bin/bash

# Alte Installation stoppen falls vorhanden
if [ -f /Library/LaunchDaemons/com.serialserver.plist ]; then
    echo "Stoppe bestehenden Service..."
    launchctl unload /Library/LaunchDaemons/com.serialserver.plist 2>/dev/null || true
fi

exit 0
EOFPRE

chmod +x build/scripts/preinstall

# ── Distribution XML (korrigiert: kein doppeltes <options>) ──────────────
echo "📝 Erstelle Distribution XML..."
cat > build/distribution.xml << 'EOFDIST'
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
    <title>Serial WebSocket Server</title>
    <organization>com.serialserver</organization>
    <domains enable_localSystem="true"/>
    <options customize="never" require-scripts="true" rootVolumeOnly="true" hostArchitectures="x86_64,arm64"/>

    <welcome file="welcome.html" mime-type="text/html"/>
    <readme file="readme.html" mime-type="text/html"/>
    <conclusion file="conclusion.html" mime-type="text/html"/>

    <choices-outline>
        <line choice="default">
            <line choice="com.serialserver.pkg"/>
        </line>
    </choices-outline>

    <choice id="default"/>
    <choice id="com.serialserver.pkg" visible="false">
        <pkg-ref id="com.serialserver.pkg"/>
    </choice>

    <pkg-ref id="com.serialserver.pkg" version="1.3" onConclusion="none">SerialServer-component.pkg</pkg-ref>

    <installation-check script="pm_install_check();"/>
    <script>
    <![CDATA[
        function pm_install_check() {
            if(system.compareVersions(system.version.ProductVersion, '10.15') < 0) {
                my.result.title = 'Nicht kompatibel';
                my.result.message = 'Dieses Paket ben\u00f6tigt macOS 10.15 (Catalina) oder neuer.';
                my.result.type = 'Fatal';
                return false;
            }
            return true;
        }
    ]]>
    </script>
</installer-gui-script>
EOFDIST

# ── Component Package bauen ──────────────────────────────────────────────────
echo "🔨 Baue Component Package..."
pkgbuild --root build/pkg-root \
         --scripts build/scripts \
         --identifier com.serialserver \
         --version 1.3 \
         --install-location / \
         build/SerialServer-component.pkg

if [ $? -ne 0 ]; then
    echo "❌ pkgbuild fehlgeschlagen"
    exit 1
fi
echo "✓ Component Package erstellt"

# ── Product Package bauen ────────────────────────────────────────────────────
echo "🔨 Baue Product Package..."
productbuild --distribution build/distribution.xml \
             --resources build/resources \
             --package-path build \
             build/SerialServer.pkg

if [ $? -ne 0 ]; then
    echo "❌ productbuild fehlgeschlagen"
    exit 1
fi
echo "✓ Product Package erstellt"

# ── Uninstall Script für DMG ─────────────────────────────────────────────────
echo "📝 Erstelle Uninstall Script..."
cat > build/dmg/uninstall.sh << 'EOFUNINSTALL'
#!/bin/bash

echo "Serial WebSocket Server - Deinstallation"
echo "========================================="
echo ""

# Root-Check
if [ "$EUID" -ne 0 ]; then
    echo "Bitte mit sudo ausführen:"
    echo "  sudo bash uninstall.sh"
    exit 1
fi

echo "⚠  Dies entfernt den Serial WebSocket Server vollständig."
read -p "Fortfahren? (j/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[JjYy]$ ]]; then
    echo "Abgebrochen."
    exit 0
fi

echo ""
echo "Stoppe Service..."
launchctl unload /Library/LaunchDaemons/com.serialserver.plist 2>/dev/null || true

echo "Entferne LaunchDaemon..."
rm -f /Library/LaunchDaemons/com.serialserver.plist

echo "Entferne Programmdateien..."
rm -rf /usr/local/serialserver

echo "Entferne Installer-Receipt..."
pkgutil --forget com.serialserver 2>/dev/null || true

echo ""
echo "✅ Deinstallation abgeschlossen!"
echo ""
EOFUNINSTALL

chmod +x build/dmg/uninstall.sh

# ── README für DMG ─────────────────────────────────────────────────────────
cat > build/dmg/README.txt << 'EOFREADME'
Serial WebSocket Server v1.3
=============================

Installation:
  1. Doppelklick auf "SerialServer.pkg"
  2. Installer folgen
  3. Administrator-Passwort eingeben
  4. Fertig!

Der Service läuft automatisch im Hintergrund
und startet bei jedem Neustart.

  Server:    http://localhost:8765
  WebSocket: ws://localhost:8765/ws
  Health:    http://localhost:8765/health

Konfiguration: /usr/local/serialserver/config.json
Logs:           /usr/local/serialserver/logs/

Deinstallation:
  sudo bash uninstall.sh
  (Datei liegt in diesem DMG)
EOFREADME

# PKG ins DMG kopieren
cp build/SerialServer.pkg build/dmg/

# ── DMG erstellen ──────────────────────────────────────────────────────────
echo "💿 Erstelle DMG..."
hdiutil create -volname "Serial Server 1.3" \
               -srcfolder build/dmg \
               -ov -format UDZO \
               SerialServer-1.3.dmg

if [ $? -ne 0 ]; then
    echo "❌ DMG-Erstellung fehlgeschlagen"
    exit 1
fi

# Ergebnis
SIZE=$(du -h SerialServer-1.3.dmg | cut -f1)

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║          ✅ BUILD ERFOLGREICH!            ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "📦 Datei:  SerialServer-1.3.dmg"
echo "📊 Größe:  $SIZE"
echo ""
echo "Inhalt des DMG:"
echo "  • SerialServer.pkg  (Installer)"
echo "  • uninstall.sh      (Deinstallation)"
echo "  • README.txt        (Anleitung)"
echo ""
echo "Zum Testen:"
echo "  1. open SerialServer-1.3.dmg"
echo "  2. SerialServer.pkg doppelklicken"
echo "  3. Installer durchlaufen"
echo ""
echo "Nach Installation prüfen:"
echo "  curl http://localhost:8765/health"
echo ""
