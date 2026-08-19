# -*- coding: utf-8 -*-
"""
Fuellt das Wiki mit einem IT-Nachschlagewerk (Startinhalt).
Idempotent: vorhandene Bereiche/Seiten (per slug) werden uebersprungen.

Aufruf auf dem Server:
    sudo -u wiki /opt/wiki/venv/bin/python /opt/wiki/seed_content.py
"""
from app import create_app
from app.extensions import db
from app.models import User, Space, Page, PageRevision, Tag
from app.textutils import slugify

# (slug, name, beschreibung, parent_slug, default_access)
SPACES = [
    ('wissen', 'IT-Wissensdatenbank', 'Anleitungen & Nachschlagewerk fuer den IT-Alltag.', None, 'read'),
    ('windows', 'Windows', 'Clients & Server, Active Directory, Troubleshooting.', 'wissen', 'read'),
    ('linux', 'Linux', 'Shell, Dienste, Server-Administration.', 'wissen', 'read'),
    ('macos', 'macOS', 'Apple-Clients im Support.', 'wissen', 'read'),
    ('netzwerk', 'Netzwerk', 'IP, DNS, DHCP, VPN, WLAN, Diagnose.', 'wissen', 'read'),
    ('email-office', 'E-Mail & Office', 'Outlook, Microsoft 365.', 'wissen', 'read'),
    ('hardware', 'Hardware', 'Arbeitsplaetze, Drucker, Diagnose.', 'wissen', 'read'),
    ('sicherheit', 'Sicherheit', 'Passwoerter, Phishing, Backups, Malware.', 'wissen', 'read'),
    ('ablaeufe', 'Standard-Ablaeufe', 'Prozesse & Checklisten fuers Team.', None, 'read'),
    ('kunden', 'Kunden', 'Kundendokumentation - Zugriff je Kunde einzeln.', None, 'none'),
    ('kunde-muster', 'Kunde Mustermann GmbH (Beispiel)', 'BEISPIEL - kopiere diese Struktur je Kunde.', 'kunden', 'none'),
    ('infos', 'Interne Infos', 'Kontakte, Lizenzen, Notfallplan, Glossar.', None, 'read'),
]

# (space_slug, titel, [tags], markdown-inhalt)
PAGES = [

# ---------------- WINDOWS ----------------
('windows', 'Windows: Standardreparaturen', ['Windows', 'Troubleshooting'], """\
# Windows: Standardreparaturen

Erste Hilfe bei instabilen oder langsamen Windows-Systemen. Reihenfolge von harmlos nach tiefgreifend.

## Systemdateien pruefen und reparieren
In einer **Eingabeaufforderung als Administrator**:

```
sfc /scannow
```

Findet und ersetzt beschaedigte Systemdateien. Danach ggf. das Komponentenabbild reparieren:

```
DISM /Online /Cleanup-Image /RestoreHealth
```

> Reihenfolge: erst `DISM`, dann `sfc /scannow`, wenn `sfc` allein nicht durchlaeuft.

## Datentraeger pruefen
```
chkdsk C: /f /r
```
`/f` behebt Fehler, `/r` sucht defekte Sektoren. Bei der Systempartition Neustart noetig (mit `J` bestaetigen).

## Autostart aufraeumen
`Task-Manager` (Strg+Umschalt+Esc) -> Reiter **Autostart** -> unnoetige Eintraege deaktivieren.

## Abgesicherter Modus
`msconfig` -> Reiter **Start** -> *Abgesicherter Start*, oder beim Neustart Umschalt gedrueckt halten -> Problembehandlung -> Erweiterte Optionen.

## Windows-Update zuruecksetzen
Dienste stoppen, Cache leeren, Dienste starten:
```
net stop wuauserv
net stop bits
ren %windir%\\SoftwareDistribution SoftwareDistribution.old
net start wuauserv
net start bits
```

## Checkliste
- [ ] `sfc` / `DISM` gelaufen
- [ ] Datentraeger geprueft
- [ ] Autostart bereinigt
- [ ] Treiber/Updates aktuell
""" ),

('windows', 'Windows: Netzwerk-Diagnose', ['Windows', 'Netzwerk', 'Troubleshooting'], """\
# Windows: Netzwerk-Diagnose

Wichtigste Befehle in der Eingabeaufforderung / PowerShell.

## IP-Konfiguration
```
ipconfig /all
```
Zeigt IP, Subnetz, Gateway, DNS, MAC. DHCP erneuern:
```
ipconfig /release
ipconfig /renew
```

## DNS-Cache leeren
```
ipconfig /flushdns
```

## Erreichbarkeit testen
```
ping 8.8.8.8          (Internet erreichbar?)
ping google.de        (Namensaufloesung ok?)
tracert google.de     (Weg / wo haengt es?)
```
Tipp: Erst die IP (8.8.8.8) pingen, dann den Namen. Geht IP aber nicht Name -> **DNS-Problem**.

## Namensaufloesung pruefen
```
nslookup firmenserver.local
```

## Offene Verbindungen / Ports
```
netstat -ano
```
Die letzte Spalte ist die PID -> im Task-Manager zuordnen.

## Schnelltest-Reihenfolge
1. `ipconfig /all` - hat der PC ueberhaupt eine sinnvolle IP?
2. Gateway anpingen (Router erreichbar?)
3. `8.8.8.8` anpingen (Internet?)
4. Namen anpingen (DNS?)
""" ),

('windows', 'Windows: Benutzerprofil & Netzlaufwerke', ['Windows'], """\
# Windows: Benutzerprofil & Netzlaufwerke

## Beschaedigtes Benutzerprofil neu anlegen
1. Daten des alten Profils sichern (`C:\\Users\\<Name>`).
2. Neuen lokalen/Domaenen-Login anlegen bzw. anmelden -> neues Profil entsteht.
3. Daten (Desktop, Dokumente, Favoriten) ins neue Profil kopieren - **nicht** `NTUSER.DAT`.

## Netzlaufwerk verbinden
```
net use Z: \\\\server\\freigabe /persistent:yes
```
Mit anderem Benutzer:
```
net use Z: \\\\server\\freigabe /user:DOMAENE\\benutzer
```
Trennen:
```
net use Z: /delete
```

## Verbundene Laufwerke anzeigen
```
net use
```
""" ),

('windows', 'Active Directory: Alltag', ['Windows', 'Active-Directory'], """\
# Active Directory: taeglicher Support

## Passwort zuruecksetzen
**ADUC** (`dsa.msc`) -> Benutzer suchen -> Rechtsklick -> *Kennwort zuruecksetzen*.
Haken *Benutzer muss Kennwort bei naechster Anmeldung aendern* setzen.

Per PowerShell (RSAT):
```
Set-ADAccountPassword -Identity mmuster -Reset
Unlock-ADAccount -Identity mmuster
```

## Konto entsperren
```
Search-ADAccount -LockedOut | Unlock-ADAccount
```

## Gruppenmitgliedschaft
```
Get-ADPrincipalGroupMembership mmuster | Select name
Add-ADGroupMember -Identity "VPN-Nutzer" -Members mmuster
```

## Gruppenrichtlinien aktualisieren (am Client)
```
gpupdate /force
gpresult /r
```

## Haeufige Fehlerbilder
- **Konto gesperrt** nach mehreren Fehlversuchen -> entsperren, alte gespeicherte Passwoerter/WLAN pruefen (Handy!).
- **Zeitabweichung > 5 min** -> Kerberos scheitert -> Uhrzeit/Zeitserver pruefen.
""" ),

('windows', 'Windows: Drucker-Probleme beheben', ['Windows', 'Drucker', 'Troubleshooting'], """\
# Windows: Drucker-Probleme beheben

## Druckwarteschlange haengt / Spooler
```
net stop spooler
del /Q /F %systemroot%\\System32\\spool\\PRINTERS\\*
net start spooler
```

## Netzwerkdrucker per IP hinzufuegen
Einstellungen -> Drucker -> *Der gewuenschte Drucker ist nicht aufgefuehrt* -> *Drucker mit TCP/IP-Adresse hinzufuegen* -> IP eingeben -> passenden Treiber waehlen.

## Checkliste bei "druckt nicht"
- [ ] Drucker an, Papier, kein Stau, Toner ok?
- [ ] Drucker per `ping <Drucker-IP>` erreichbar?
- [ ] Richtiger Drucker als Standard?
- [ ] Warteschlange leer / Spooler neu gestartet?
- [ ] Treiber aktuell (Hersteller-Seite)?

## Testseite
Drucker-Eigenschaften -> *Testseite drucken* grenzt Treiber- vs. Anwendungsproblem ein.
""" ),

('windows', 'PowerShell: Schnellreferenz', ['Windows', 'PowerShell', 'Referenz'], """\
# PowerShell: Schnellreferenz

## Grundlagen
```
Get-Help <cmdlet> -Examples     # Hilfe mit Beispielen
Get-Command *service*           # Cmdlets finden
Get-Process | Sort CPU -desc    # Prozesse nach CPU
```

## Dienste
```
Get-Service | Where Status -eq 'Running'
Restart-Service -Name Spooler
```

## Dateien
```
Get-ChildItem C:\\Logs -Recurse -Filter *.log
Get-Content .\\app.log -Tail 50 -Wait
```

## System-Infos
```
Get-ComputerInfo | Select CsName, OsName, OsVersion
Get-Volume
```

## Netzwerk
```
Test-NetConnection google.de -Port 443
Get-NetIPAddress | Select IPAddress, InterfaceAlias
```

> Ausfuehrungsrichtlinie fuer Skripte (nur wenn noetig, bewusst):
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
""" ),

# ---------------- LINUX ----------------
('linux', 'Linux: Grundbefehle', ['Linux', 'Shell', 'Referenz'], """\
# Linux: Grundbefehle

## Navigation & Dateien
```
pwd                 # wo bin ich
ls -lah             # auflisten (inkl. versteckt, Groessen)
cd /pfad            # wechseln
cp -r quelle ziel   # kopieren (rekursiv)
mv alt neu          # verschieben/umbenennen
rm -i datei         # loeschen (mit Rueckfrage)
mkdir -p a/b/c      # Verzeichnisse anlegen
```

## Anzeigen & Suchen
```
cat datei           # ganze Datei
less datei          # blaettern (q zum Beenden)
tail -f datei.log   # live mitlesen
grep -ri "text" .   # rekursiv suchen (ohne Gross/Klein)
find / -name "*.conf" 2>/dev/null
```

## Editor
`nano datei` (einfach) oder `vim datei` (maechtig; `:wq` speichern+beenden, `:q!` verwerfen).

## Hilfe
```
man <befehl>
<befehl> --help
```
""" ),

('linux', 'Linux: Benutzer & Rechte', ['Linux', 'Rechte'], """\
# Linux: Benutzer & Rechte

## Rechte lesen
`ls -l` zeigt z.B. `-rwxr-xr--`:
- Position 1: Typ (`-` Datei, `d` Verzeichnis)
- 3er-Bloecke: **Besitzer**, **Gruppe**, **Andere** (r=lesen, w=schreiben, x=ausfuehren)

## Rechte setzen
```
chmod 640 datei       # rw- r-- ---
chmod +x script.sh    # ausfuehrbar machen
chown user:gruppe datei
chmod -R 755 /var/www # rekursiv
```
Merkhilfe Oktal: r=4, w=2, x=1 (also 7=rwx, 6=rw-, 5=r-x).

## Benutzer
```
sudo useradd -m -s /bin/bash mmuster
sudo passwd mmuster
sudo usermod -aG sudo mmuster   # Gruppe hinzufuegen
id mmuster
```

## sudo
```
sudo <befehl>         # einzelner Befehl als root
sudo -i               # root-Shell (bewusst einsetzen!)
```
""" ),

('linux', 'Linux: Dienste mit systemd', ['Linux', 'systemd'], """\
# Linux: Dienste mit systemd

## Status & Steuern
```
systemctl status nginx
sudo systemctl start nginx
sudo systemctl stop nginx
sudo systemctl restart nginx
sudo systemctl reload nginx     # Konfig neu laden (ohne Neustart)
```

## Autostart
```
sudo systemctl enable nginx     # beim Boot starten
sudo systemctl disable nginx
systemctl is-enabled nginx
```

## Logs eines Dienstes
```
journalctl -u nginx -n 50 --no-pager
journalctl -u nginx -f          # live
journalctl -p err -b            # Fehler seit letztem Boot
```

## Fehlersuche bei "startet nicht"
1. `systemctl status <dienst>` - letzte Zeilen lesen.
2. `journalctl -u <dienst> -n 50` - konkrete Fehlermeldung.
3. Konfiguration testen (z.B. `nginx -t`).
""" ),

('linux', 'Linux: Netzwerk-Diagnose', ['Linux', 'Netzwerk', 'Troubleshooting'], """\
# Linux: Netzwerk-Diagnose

## Adressen & Routen
```
ip a                # Schnittstellen & IPs
ip r                # Routing / Standardgateway
```

## Erreichbarkeit
```
ping -c4 8.8.8.8
ping -c4 google.de
traceroute google.de
```

## DNS
```
dig google.de +short
nslookup firmenserver.local
cat /etc/resolv.conf
```

## Ports & Verbindungen
```
ss -tulpen          # lauschende Ports + Prozesse
ss -tn state established
```

## Firewall (ufw)
```
sudo ufw status
sudo ufw allow 22/tcp
```

> Merksatz wie bei Windows: erst IP pingen, dann Namen. Name scheitert, IP klappt -> DNS.
""" ),

('linux', 'Linux: Paketverwaltung', ['Linux', 'Referenz'], """\
# Linux: Paketverwaltung

## Debian/Ubuntu (apt)
```
sudo apt update              # Paketlisten aktualisieren
sudo apt upgrade             # Updates einspielen
sudo apt install htop
sudo apt remove htop
apt search begriff
```

## RHEL/Fedora (dnf)
```
sudo dnf check-update
sudo dnf upgrade
sudo dnf install htop
sudo dnf remove htop
```

## Was ist installiert?
```
dpkg -l | grep name      # Debian/Ubuntu
rpm -qa | grep name      # RHEL/Fedora
```
""" ),

('linux', 'SSH: Verbindung & Schluessel', ['Linux', 'SSH', 'Sicherheit'], """\
# SSH: Verbindung & Schluessel

## Verbinden
```
ssh benutzer@server
ssh -p 2222 benutzer@server      # anderer Port
```

## Schluesselpaar erstellen (empfohlen statt Passwort)
```
ssh-keygen -t ed25519 -C "mmuster@intrabit"
```
Oeffentlichen Schluessel auf den Server bringen:
```
ssh-copy-id benutzer@server
```

## Dateien kopieren
```
scp datei.txt benutzer@server:/tmp/
scp -r ordner/ benutzer@server:/opt/
```

## Sicherheits-Basics
- Passwort-Login deaktivieren, sobald Key funktioniert (`/etc/ssh/sshd_config`: `PasswordAuthentication no`).
- Root-Login vermeiden (`PermitRootLogin no`).
- Nach Aenderung: `sudo systemctl reload ssh`.
""" ),

# ---------------- MACOS ----------------
('macos', 'macOS: Support-Grundlagen', ['macOS', 'Referenz'], """\
# macOS: Support-Grundlagen

## Wichtige Tastenkuerzel
| Aktion | Kuerzel |
|---|---|
| Kopieren / Einfuegen | Cmd+C / Cmd+V |
| Spotlight-Suche | Cmd+Leertaste |
| Screenshot (Auswahl) | Cmd+Umschalt+4 |
| Screenshot (ganzer Bildschirm) | Cmd+Umschalt+3 |
| App wechseln | Cmd+Tab |
| App erzwingen zu beenden | Cmd+Alt+Esc |

## System-Infos
Apple-Menue -> *Ueber diesen Mac* -> *Systembericht* (Hardware, Seriennummer).

## Programme verwalten
- Deinstallieren: App aus *Programme* in den Papierkorb, Reste in `~/Library`.
- Autostart: Systemeinstellungen -> *Allgemein* -> *Anmeldeobjekte*.

## Updates
Systemeinstellungen -> *Allgemein* -> *Softwareupdate*.
""" ),

('macos', 'macOS: Netzwerk & Terminal', ['macOS', 'Netzwerk'], """\
# macOS: Netzwerk & Terminal

## Netzwerk-Infos (Terminal)
```
ifconfig en0            # IP der Schnittstelle
networksetup -listallnetworkservices
ping -c4 8.8.8.8
dig google.de +short
```

## DNS-Cache leeren
```
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
```

## Nuetzliche Terminal-Basics
```
ls -lah
cd ~/Downloads
open .                  # aktuellen Ordner im Finder oeffnen
sudo <befehl>
```

## WLAN zuruecksetzen
Systemeinstellungen -> *WLAN* -> Netzwerk *Ignorieren*, dann neu verbinden.
""" ),

('macos', 'macOS: Haeufige Probleme', ['macOS', 'Troubleshooting'], """\
# macOS: Haeufige Probleme

## Sicherer Modus (Safe Mode)
- **Apple Silicon (M1/M2/...):** Ausschalten -> Ein-/Aus-Taste halten bis Startoptionen -> Volume waehlen -> Umschalt halten -> *Im sicheren Modus starten*.
- **Intel:** Beim Start Umschalt halten.

## NVRAM zuruecksetzen (nur Intel)
Beim Start `Cmd+Alt+P+R` ca. 20 Sek. halten. Setzt Ton, Aufloesung, Startvolume-Auswahl zurueck.

## Festplatte pruefen
*Festplattendienstprogramm* -> Volume waehlen -> *Erste Hilfe*.

## Haengende App beenden
`Cmd+Alt+Esc` -> App auswaehlen -> *Sofort beenden*.

## Wiederherstellungsmodus
- **Apple Silicon:** Ein-/Aus-Taste halten -> *Optionen*.
- **Intel:** `Cmd+R` beim Start.
""" ),

# ---------------- NETZWERK ----------------
('netzwerk', 'Netzwerk-Grundlagen', ['Netzwerk', 'Referenz'], """\
# Netzwerk-Grundlagen

## Bausteine
- **IP-Adresse** - eindeutige Adresse im Netz (z.B. 192.168.1.20).
- **Subnetzmaske** - trennt Netz- von Geraeteanteil (z.B. 255.255.255.0 = /24).
- **Standardgateway** - Weg nach "draussen" (meist der Router, z.B. 192.168.1.1).
- **DNS** - uebersetzt Namen in IPs.
- **DHCP** - vergibt IPs automatisch.

## Private Adressbereiche (nicht im Internet geroutet)
| Bereich | CIDR |
|---|---|
| 10.0.0.0 - 10.255.255.255 | 10.0.0.0/8 |
| 172.16.0.0 - 172.31.255.255 | 172.16.0.0/12 |
| 192.168.0.0 - 192.168.255.255 | 192.168.0.0/16 |

## /24 kurz erklaert
`/24` = 256 Adressen (254 nutzbar), Maske 255.255.255.0. Beispielnetz 192.168.1.0/24: nutzbar .1 bis .254, .255 ist Broadcast.

## Typischer Fehler
Zwei Geraete mit **gleicher IP** -> Konflikt. Symptom: sporadische Verbindungsabbrueche. Loesung: DHCP nutzen oder feste IPs sauber vergeben.
""" ),

('netzwerk', 'VPN einrichten (allgemein)', ['Netzwerk', 'VPN'], """\
# VPN einrichten (allgemein)

Ein VPN verbindet einen Client sicher (verschluesselt) mit dem Firmennetz.

## Was du brauchst
- VPN-Typ/Client (z.B. OpenVPN, WireGuard, IPsec, Hersteller-Client).
- Server-Adresse (Hostname/IP) und Port.
- Zugangsdaten bzw. Konfig-/Zertifikatsdatei.
- Ggf. Freigabe des Benutzers in der passenden Gruppe (siehe Active Directory).

## Ablauf (generisch)
1. Client installieren.
2. Konfigurationsdatei/Profil importieren.
3. Anmelden, Verbindung testen.
4. Erreichbarkeit eines internen Servers pruefen (`ping <interne-IP>`).

## Troubleshooting
- **Verbindet nicht:** Internet am Client ok? Firewall/Port offen? Uhrzeit korrekt (Zertifikate)?
- **Verbunden, aber kein Zugriff:** Route/Split-Tunnel? DNS des VPN aktiv? Benutzer in richtiger Gruppe?
- **Nach Passwortwechsel:** neues Passwort im Client hinterlegen.

> Zugangsdaten/Konfigs gehoeren in den **Passwortmanager**, nicht ins Wiki.
""" ),

('netzwerk', 'WLAN-Probleme beheben', ['Netzwerk', 'WLAN', 'Troubleshooting'], """\
# WLAN-Probleme beheben

## Schnelldiagnose
1. Fliegt nur **ein** Geraet raus oder alle? (Geraet vs. Accesspoint)
2. WLAN aus/an, richtiges Netz gewaehlt?
3. Signal ausreichend? (Naeher an den Accesspoint)
4. Anderes Geraet am selben Netz -> Internet ok?

## Haeufige Ursachen
- **Falsches/altes Passwort** gespeichert -> Netz "vergessen" und neu verbinden.
- **IP-Konflikt / kein DHCP** -> `ipconfig /all` (Windows), gibt es eine 169.254.x.x? Dann kein DHCP.
- **Kanalstoerung** in dichten Umgebungen -> Accesspoint-Kanal wechseln.
- **Treiber** des WLAN-Adapters veraltet.

## Windows-Reset (letzte Stufe)
```
netsh winsock reset
netsh int ip reset
ipconfig /flushdns
```
Danach Neustart.
""" ),

('netzwerk', 'Ports & Protokolle (Referenz)', ['Netzwerk', 'Referenz'], """\
# Ports & Protokolle (Referenz)

| Port | Protokoll | Wofuer |
|---|---|---|
| 20/21 | FTP | Dateiuebertragung (unverschluesselt) |
| 22 | SSH/SFTP | Sichere Fernwartung/Uebertragung |
| 25 | SMTP | Mailversand (Server-zu-Server) |
| 53 | DNS | Namensaufloesung |
| 67/68 | DHCP | IP-Vergabe |
| 80 | HTTP | Web (unverschluesselt) |
| 110 | POP3 | Mailabruf (alt) |
| 143 | IMAP | Mailabruf |
| 389 | LDAP | Verzeichnisdienst (AD) |
| 443 | HTTPS | Web (verschluesselt) |
| 445 | SMB | Windows-Dateifreigaben |
| 587 | SMTP (Submission) | Mailversand vom Client |
| 636 | LDAPS | LDAP verschluesselt |
| 993 | IMAPS | IMAP verschluesselt |
| 995 | POP3S | POP3 verschluesselt |
| 3389 | RDP | Windows-Remotedesktop |

> Nur Ports oeffnen, die wirklich gebraucht werden. Im Zweifel `Test-NetConnection host -Port <n>` (Windows) bzw. `ss -tulpen` (Linux).
""" ),

# ---------------- E-MAIL & OFFICE ----------------
('email-office', 'Outlook: Profil neu anlegen', ['Outlook', 'Office', 'Troubleshooting'], """\
# Outlook: Profil neu anlegen

Hilft bei vielen Outlook-Problemen (Synchronisation, Abstuerze, Passwortschleifen).

## Neues Profil anlegen
1. Outlook schliessen.
2. *Systemsteuerung* -> *Mail (Microsoft Outlook)* -> **Profile anzeigen**.
3. *Hinzufuegen* -> Namen vergeben -> Konto einrichten (meist automatisch per Autodiscover).
4. Unten **Immer dieses Profil verwenden** oder **Zu verwendendes Profil bestaetigen** waehlen.

## OST-Datei zuruecksetzen (Cache neu aufbauen)
Konto ist server-seitig (Exchange/M365)? Dann kann die lokale `.ost` gefahrlos neu erzeugt werden:
1. Outlook schliessen.
2. `.ost` finden: `%localappdata%\\Microsoft\\Outlook`.
3. Datei umbenennen (z.B. `.ost.old`).
4. Outlook starten -> Cache wird neu geladen.

> **PST** (POP3/Archiv) enthaelt lokale Daten - **nicht** einfach loeschen, erst sichern!
""" ),

('email-office', 'Outlook: haeufige Probleme', ['Outlook', 'Office', 'Troubleshooting'], """\
# Outlook: haeufige Probleme

## Fragt staendig nach Passwort
- Gespeicherte Anmeldedaten pruefen: *Anmeldeinformationsverwaltung* (Windows) -> alte Outlook-Eintraege entfernen.
- Passwort nach Wechsel neu eingeben; MFA/App-Passwort noetig?
- Profil neu anlegen (siehe eigene Seite).

## Startet nicht / haengt
```
outlook.exe /safe        # abgesicherter Modus (ohne Add-ins)
```
Startet es so -> Add-ins einzeln deaktivieren (*Datei -> Optionen -> Add-Ins*).

## Suche findet nichts
*Datei -> Optionen -> Suchen -> Indizierungsoptionen* -> Neu aufbauen.

## Kalender/Mails synchronisieren nicht
- Onlinestatus pruefen (*Senden/Empfangen*).
- OST zuruecksetzen.
- Autodiscover testen (Strg+Rechtsklick auf Outlook-Symbol in der Taskleiste -> *E-Mail-AutoKonfiguration testen*).
""" ),

('email-office', 'Microsoft 365: Basics', ['Office', 'M365'], """\
# Microsoft 365: Basics

## Admin Center
`admin.microsoft.com` - Benutzer, Lizenzen, Gruppen, Passwoerter.

## Haeufige Aufgaben
- **Passwort zuruecksetzen:** Benutzer -> Aktive Benutzer -> Person -> *Passwort zuruecksetzen*.
- **Lizenz zuweisen:** Benutzer -> *Lizenzen und Apps*.
- **Postfach-Weiterleitung:** Benutzer -> *E-Mail* -> Weiterleitung (bewusst und dokumentiert!).
- **Gemeinsames Postfach:** Exchange Admin Center -> *Empfaenger -> Postfaecher*.

## Wichtige Portale
| Zweck | URL |
|---|---|
| Admin Center | admin.microsoft.com |
| Exchange | admin.exchange.microsoft.com |
| Entra ID (Azure AD) | entra.microsoft.com |
| Self-Service Passwort | passwordreset.microsoftonline.com |

> MFA moeglichst fuer alle aktiv. Weiterleitungen nach aussen sind ein haeufiger Angriffsweg - immer hinterfragen.
""" ),

# ---------------- HARDWARE ----------------
('hardware', 'Arbeitsplatz einrichten (Standard)', ['Hardware', 'Checkliste'], """\
# Arbeitsplatz einrichten (Standard)

Checkliste fuer einen neuen/aufgesetzten Arbeitsplatz.

## Hardware
- [ ] PC/Notebook, Netzteil, Dock
- [ ] Monitor(e), Kabel (HDMI/DP/USB-C)
- [ ] Tastatur, Maus, Headset
- [ ] Netzwerk (LAN/WLAN) verbunden

## System
- [ ] Windows aktiviert, aktuelle Updates
- [ ] Rechnername nach Namensschema gesetzt
- [ ] In Domaene/Entra aufgenommen
- [ ] Standardsoftware installiert (siehe *Interne Infos -> Software & Lizenzen*)
- [ ] Drucker verbunden
- [ ] Virenschutz aktiv & aktuell
- [ ] Backup/Sync (OneDrive o.ae.) eingerichtet

## Benutzer
- [ ] Anmeldung getestet
- [ ] E-Mail-Profil eingerichtet
- [ ] Netzlaufwerke verbunden
- [ ] Kurz-Einweisung / Uebergabe dokumentiert (Ticket)
""" ),

('hardware', 'Drucker: Grundlagen & Fehler', ['Hardware', 'Drucker', 'Troubleshooting'], """\
# Drucker: Grundlagen & Fehler

## Anbindungsarten
- **USB** - direkt am PC.
- **Netzwerk (IP)** - im LAN, mehrere Nutzer. IP am Drucker-Display ablesbar.
- **Druckserver** - zentrale Warteschlange, Freigabe per `\\\\server\\drucker`.

## Erste Schritte bei Fehlern
1. Physisch: Papier, Toner/Tinte, Stau, Displaymeldung.
2. Erreichbarkeit: `ping <Drucker-IP>`.
3. Warteschlange leeren / Spooler neu starten (siehe Windows-Seite).
4. Testseite ueber Treiber drucken.
5. Treiber vom Hersteller neu installieren.

## Schlechtes Druckbild
- Laser: Trommel/Toner pruefen, Reinigungsroutine.
- Tinte: Duesenreinigung, Patronen pruefen.

## Scannen geht nicht
Firewall/Netzwerk pruefen, "Scan-to-Folder"-Ziel (Freigabe + Rechte + Zugangsdaten) kontrollieren.
""" ),

('hardware', 'Hardware-Diagnose', ['Hardware', 'Troubleshooting'], """\
# Hardware-Diagnose

## Symptome sinnvoll einordnen
- **Startet gar nicht:** Netzteil/Kabel, andere Steckdose, Ladeanzeige.
- **Zufaellige Abstuerze/Bluescreens:** oft RAM oder Ueberhitzung/Treiber.
- **Sehr langsam:** Datentraeger (HDD/SSD) am Ende? Zu wenig RAM? Malware?

## RAM testen
Windows: *Windows-Speicherdiagnose* (`mdsched.exe`) oder **MemTest86** (bootbar) fuer gruendliche Tests.

## Datentraeger (SSD/HDD)
- Windows: `chkdsk`, Hersteller-Tool (z.B. CrystalDiskInfo) fuer **SMART**-Werte.
- Warnzeichen: steigende *Reallocated Sectors*, Klackern (HDD).

## Temperaturen
Tools wie HWiNFO. Bei Ueberhitzung: Luefter/Staub, Waermeleitpaste, Belueftung.

## Vorgehen
1. Ein Teil nach dem anderen ausschliessen (RAM-Riegel einzeln, anderes Netzteil).
2. Ereignisanzeige (Windows) / `journalctl -p err` (Linux) auf Muster pruefen.
3. Befund + Ergebnis im Ticket dokumentieren.
""" ),

# ---------------- SICHERHEIT ----------------
('sicherheit', 'Passwoerter & Passwortmanager', ['Sicherheit', 'Passwoerter'], """\
# Passwoerter & Passwortmanager

## Regeln
- **Lang statt kompliziert:** Passphrasen (4+ Woerter) sind stark und merkbar.
- **Einzigartig pro Dienst** - niemals wiederverwenden.
- **Passwortmanager** nutzen (zentral & sicher), nicht Zettel/Excel.
- **MFA** (2. Faktor) ueberall wo moeglich.

## Kundendaten
- Zugaenge **immer im Passwortmanager**, nie im Wiki oder in E-Mails.
- Im Wiki nur **Verweise** ("liegt im Passwortmanager unter <Eintrag>").

## Bei Verdacht auf Kompromittierung
1. Betroffenes Passwort sofort aendern.
2. Sessions/Tokens invalidieren (Abmelden ueberall).
3. MFA pruefen/neu einrichten.
4. Vorgang dokumentieren, ggf. eskalieren.
""" ),

('sicherheit', 'Phishing erkennen', ['Sicherheit', 'Phishing'], """\
# Phishing erkennen

## Typische Merkmale
- **Dringlichkeit/Drohung** ("Konto wird gesperrt!").
- **Unerwarteter Anhang** oder Link.
- **Absender stimmt nicht** mit angezeigtem Namen ueberein (echte Adresse pruefen!).
- **Links fuehren woanders hin** (Mauszeiger drueberhalten, Ziel pruefen - nicht klicken).
- Ungewoehnliche Sprache, Rechtschreibfehler, generische Anrede.

## Im Zweifel
- **Nicht klicken, nicht antworten, nichts oeffnen.**
- Ueber bekannten Weg gegenpruefen (Telefon, offizielle Seite - **nicht** die Nummer/Links aus der Mail).
- Verdacht melden (siehe *Notfall- & Eskalationsplan*).

## Wenn schon geklickt/Daten eingegeben
1. Netzwerk trennen (bei Datei/Anhang).
2. Passwoerter aendern (von einem sauberen Geraet).
3. Eskalieren & dokumentieren.
""" ),

('sicherheit', 'Backup-Strategie (3-2-1)', ['Sicherheit', 'Backup'], """\
# Backup-Strategie (3-2-1)

## Die Regel
- **3** Kopien der Daten
- auf **2** verschiedenen Medien
- **1** davon ausser Haus (offsite) bzw. offline

## Wichtig
- **Wiederherstellung regelmaessig testen** - ein Backup, das nicht zurueckspielbar ist, ist keins.
- **Offline/Immutable-Kopie** gegen Ransomware (verschluesselt sonst auch die Backups).
- **Aufbewahrung/Versionen** definieren (taeglich/woechentlich/monatlich).
- **Protokolle pruefen** (siehe *Standard-Ablaeufe -> Backup-Kontrolle*).

## Was gehoert gesichert?
Serverdaten, Datenbanken, Konfigurationen, Mail, wichtige Clients/Home-Verzeichnisse, Doku (auch dieses Wiki!).
""" ),

('sicherheit', 'Malware-Verdacht: Vorgehen', ['Sicherheit', 'Malware', 'Troubleshooting'], """\
# Malware-Verdacht: Vorgehen

> Ziel: Ausbreitung stoppen, Beweise sichern, sauber wiederherstellen.

## Sofortmassnahmen
1. **Geraet vom Netz trennen** (LAN-Kabel ziehen / WLAN aus). **Nicht** herunterfahren, wenn Beweissicherung wichtig ist - erst Ruecksprache.
2. Betroffenen Benutzer/Umfang eingrenzen.
3. **Eskalieren** (siehe Notfallplan) - nicht allein wursteln.

## Analyse
- Was ist passiert (Anhang, Link, USB)? Wann?
- Vollstaendiger Virenscan (offline/Rescue-Medium).
- Weitere Geraete/Freigaben betroffen?

## Wiederherstellung
- Im Zweifel **neu aufsetzen** statt "bereinigen".
- Passwoerter der betroffenen Konten aendern.
- Aus sauberem Backup zuruueck.

## Nachbereitung
- Ursache dokumentieren, Luecke schliessen, Team informieren.
""" ),

# ---------------- ABLAEUFE ----------------
('ablaeufe', 'Onboarding neuer Mitarbeiter', ['Ablauf', 'Checkliste', 'Onboarding'], """\
# Onboarding neuer Mitarbeiter

## Vor dem ersten Tag
- [ ] Benutzerkonto (AD/Entra) anlegen, Gruppen zuweisen
- [ ] E-Mail-Postfach einrichten, ggf. Verteiler
- [ ] Hardware bereitstellen & aufsetzen (siehe Arbeitsplatz-Checkliste)
- [ ] Standardsoftware & Lizenzen zuweisen
- [ ] Telefon/Nebenstelle, Zutritt (falls zustaendig)

## Am ersten Tag
- [ ] Anmeldung testen, Passwort-Erstwechsel
- [ ] E-Mail, Netzlaufwerke, Drucker pruefen
- [ ] MFA einrichten
- [ ] Kurz-Einweisung (Passwortmanager, Wiki, Ticketsystem)

## Nachbereitung
- [ ] Uebergabe/Do­kumentation im Ticket
- [ ] Konto & Rechte final kontrollieren
""" ),

('ablaeufe', 'Offboarding (Austritt)', ['Ablauf', 'Checkliste', 'Offboarding'], """\
# Offboarding (Austritt)

> Zeitpunkt mit HR/Vorgesetzten abstimmen (genau zum Austritt).

## Konten & Zugriff
- [ ] Anmeldung deaktivieren (nicht sofort loeschen)
- [ ] Sessions/Tokens invalidieren, MFA-Geraete entfernen
- [ ] VPN-/Remote-Zugaenge sperren
- [ ] Weiterleitungen/Vertretung fuer Mail einrichten (mit Fachbereich)

## Daten & Hardware
- [ ] Postfach/Daten sichern bzw. uebergeben
- [ ] Hardware einsammeln (PC, Handy, Token, Schluessel/Karte)
- [ ] Lizenzen freigeben/neu zuweisen

## Abschluss
- [ ] Nach Aufbewahrungsfrist Konto endgueltig loeschen
- [ ] Alles im Ticket dokumentieren
""" ),

('ablaeufe', 'Ticket-Bearbeitung', ['Ablauf', 'Ticket'], """\
# Ticket-Bearbeitung

## Guter Ticket-Ablauf
1. **Aufnehmen:** Wer, was, seit wann, Fehlermeldung woertlich, Betroffene.
2. **Priorisieren** (siehe unten).
3. **Bearbeiten:** Schritte + Ergebnisse dokumentieren (nachvollziehbar!).
4. **Loesung + Rueckmeldung** an den Nutzer.
5. **Schliessen** mit kurzer Zusammenfassung.

## Priorisierung (Beispiel)
| Prio | Bedeutung | Beispiel |
|---|---|---|
| Hoch | Arbeit steht (viele/kritisch) | Server aus, Standort ohne Netz |
| Mittel | Einzelne blockiert | PC startet nicht |
| Niedrig | Stoerend, Workaround da | Drucker-Randproblem, Wunsch |

## Gute Doku-Gewohnheit
- Immer **was probiert** und **was rauskam** festhalten.
- Loesung ins Wiki, wenn sie wiederkehrt (Wissen sichern!).
""" ),

('ablaeufe', 'Backup-Kontrolle (Routine)', ['Ablauf', 'Backup', 'Checkliste'], """\
# Backup-Kontrolle (Routine)

> Regelmaessig (z.B. taeglich morgens) - ein unbemerkt kaputtes Backup ist der Klassiker.

## Taeglich
- [ ] Backup-Jobs der letzten Nacht: **alle erfolgreich?**
- [ ] Fehler/Warnungen pruefen und nachverfolgen
- [ ] Freier Speicher auf dem Backup-Ziel ok?

## Regelmaessig (z.B. monatlich)
- [ ] **Test-Wiederherstellung** einer Datei/VM
- [ ] Offsite/Offline-Kopie vorhanden & aktuell?
- [ ] Aufbewahrung/Versionen wie definiert?

## Bei Fehlern
1. Job-Log lesen, Ursache bestimmen.
2. Job manuell nachholen.
3. Wenn Muster: Ursache dauerhaft beheben, dokumentieren.
""" ),

('ablaeufe', 'Uebergabe & Rufbereitschaft', ['Ablauf', 'Checkliste'], """\
# Uebergabe & Rufbereitschaft

## Saubere Uebergabe
- Offene Tickets mit Stand ("was fehlt noch").
- Laufende/geplante Wartungen.
- Bekannte Stoerungen & Workarounds.
- Wichtige Termine/Fristen.

## In Rufbereitschaft
- Erreichbarkeit sicherstellen (Telefon geladen, VPN getestet).
- Zugriff auf Passwortmanager, Wiki, Ticketsystem, Monitoring.
- Eskalationswege kennen (siehe Notfallplan).

## Nach einem Einsatz
- Was war, was wurde getan, was ist offen -> Ticket + Uebergabe.
""" ),

# ---------------- KUNDEN ----------------
('kunden', 'Kundendokumentation: So funktioniert es', ['Kunden', 'Anleitung'], """\
# Kundendokumentation: So funktioniert es

Dieser Bereich buendelt die Doku pro Kunde. **Zugriff ist je Kunde einzeln geregelt.**

## Struktur
- Fuer **jeden Kunden** einen eigenen **Unterbereich** anlegen (Verwaltung -> Bereiche -> "+ Unterbereich" unter *Kunden*).
- Zugriff des Unterbereichs auf **kein Zugriff** lassen und gezielt Personen freischalten (Verwaltung -> Zugriffe).

## Was gehoert rein
- **Steckbrief** (Kontakte, Systeme, Besonderheiten) - Vorlage "Kunden-Steckbrief" nutzen.
- Netzplan/Standorte, wichtige Systeme, Wartungsfenster.
- Wiederkehrende Aufgaben & bekannte Eigenheiten.

## Was NICHT rein gehoert
- **Keine Passwoerter/Secrets** - nur Verweise auf den Passwortmanager.
- Keine personenbezogenen Daten ueber das Noetige hinaus (Datenschutz!).

> Siehe Beispiel-Unterbereich **"Kunde Mustermann GmbH"**.
""" ),

('kunde-muster', 'Steckbrief - Mustermann GmbH (BEISPIEL)', ['Kunden', 'Steckbrief', 'Beispiel'], """\
# Steckbrief - Mustermann GmbH  *(BEISPIEL - Platzhalter ersetzen)*

> Dies ist eine **Beispielseite**. Kopiere die Struktur je echtem Kunden und fuelle sie.

## Kontakt
- Ansprechpartner: *Max Mustermann (Geschaeftsfuehrung)*
- Telefon: *0000 / 000000*
- E-Mail: *it@mustermann-beispiel.de*
- IT-Verantwortlich intern: *N. N.*

## Vertrag / Service
- Betreuung: *z.B. Wartungsvertrag, Reaktionszeit 4h*
- Wartungsfenster: *z.B. Mi 18-20 Uhr*

## Systeme & Umgebung
| System | Details |
|---|---|
| Server | *z.B. 1x Windows Server 2022, Hyper-V* |
| Clients | *z.B. 12x Windows 11* |
| Netzwerk | *z.B. Firewall XY, VLANs* |
| Backup | *z.B. taeglich, offsite* |

## Zugaenge
> Alle Zugaenge liegen im **Passwortmanager** unter *Mustermann GmbH*. Hier stehen **keine** Passwoerter.

## Besonderheiten / Notizen
- *z.B. Branchensoftware XY, Eigenheiten, wiederkehrende Themen.*

## Verweise
- Tickets: *Verweis/Nummerkreis*
- Netzplan: *Anhang oder Link*
""" ),

# ---------------- INTERNE INFOS ----------------
('infos', 'Willkommen & Wiki-Spielregeln', ['Intern', 'Anleitung'], """\
# Willkommen im IT-Wiki

Dieses Wiki ist unser gemeinsames **Nachschlagewerk**. Ziel: Wissen einmal sauber festhalten, damit es alle wiederfinden.

## So arbeiten wir damit
- **Suchen zuerst** (oben) - vieles ist schon da.
- **Neues Wissen eintragen**, sobald ein Problem 2x auftaucht.
- **Schlagworte** vergeben (z.B. Windows, Netzwerk) - erleichtert das Finden.
- **Vorlagen** nutzen ("Aus Vorlage starten") fuer einheitliche Seiten.
- **Anhaenge** fuer Logs/PDFs, **PDF-Export** zum Weitergeben.

## Struktur
- **IT-Wissensdatenbank** - Anleitungen (Windows, Linux, macOS, Netzwerk, ...).
- **Standard-Ablaeufe** - Prozesse & Checklisten.
- **Kunden** - Doku je Kunde (Zugriff einzeln).
- **Interne Infos** - Kontakte, Lizenzen, Notfallplan, Glossar.

## Regeln
- **Keine Passwoerter** ins Wiki - nur Verweise auf den Passwortmanager.
- Kurz, korrekt, nachvollziehbar. Lieber knapp und richtig als lang und veraltet.
- Beim Aendern eine kurze **Aenderungsnotiz** hinterlassen.
""" ),

('infos', 'Wichtige Kontakte', ['Intern', 'Kontakte'], """\
# Wichtige Kontakte  *(Platzhalter - bitte ausfuellen)*

## Intern
| Rolle | Name | Kontakt |
|---|---|---|
| IT-Leitung | *N. N.* | *Tel / Mail* |
| Team IT | *N. N.* | *Tel / Mail* |
| Bereitschaft | *Plan/Nummer* | *...* |

## Dienstleister / Lieferanten
| Thema | Anbieter | Kontakt / Vertrag |
|---|---|---|
| Internet/WAN | *Provider* | *Hotline, Kundennr.* |
| Telefonanlage | *Anbieter* | *...* |
| Hardware | *Lieferant* | *...* |
| Software/Support | *Hersteller* | *...* |

## Notfall
- Eskalation & Rufnummern: siehe **Notfall- & Eskalationsplan**.
""" ),

('infos', 'Software & Lizenzen', ['Intern', 'Lizenzen', 'Software'], """\
# Software & Lizenzen  *(Platzhalter - bitte ausfuellen)*

## Standard-Arbeitsplatz (Software-Set)
- [ ] Betriebssystem: *Windows 11 ...*
- [ ] Office/M365: *Version/Plan*
- [ ] Browser: *...*
- [ ] PDF: *...*
- [ ] Virenschutz: *...*
- [ ] VPN-Client: *...*
- [ ] Branchensoftware: *...*

## Lizenzuebersicht
| Produkt | Typ | Anzahl | Ablauf | Ablage |
|---|---|---|---|---|
| *z.B. M365 Business* | Abo | *n* | *Datum* | *Passwortmanager/Portal* |
| *Virenschutz* | Abo | *n* | *Datum* | *...* |

> Lizenzschluessel/Zugaenge gehoeren in den **Passwortmanager**, nicht hierher.
""" ),

('infos', 'Notfall- & Eskalationsplan', ['Intern', 'Notfall', 'Sicherheit'], """\
# Notfall- & Eskalationsplan  *(Rahmen - an Intrabit anpassen)*

## Wann eskalieren?
- Sicherheitsvorfall (Malware, Datenabfluss, Phishing mit Klick).
- Ausfall kritischer Systeme (Server, Netz, Standort).
- Alles, was allein nicht sicher loesbar ist - lieber einmal zu viel.

## Sofort-Reihenfolge bei Sicherheitsvorfall
1. **Eindaemmen** - betroffenes Geraet vom Netz trennen.
2. **Melden/Eskalieren** - IT-Leitung/Verantwortliche informieren.
3. **Beweise sichern** - nichts vorschnell loeschen/neu aufsetzen (Ruecksprache).
4. **Dokumentieren** - Zeitpunkt, Umfang, Schritte.

## Kontakte (ausfuellen)
| Stufe | Wer | Erreichbarkeit |
|---|---|---|
| 1 | *Team/Bereitschaft* | *...* |
| 2 | *IT-Leitung* | *...* |
| 3 | *Externer Dienstleister/Hersteller* | *...* |

## Wichtige Ablagen
- Passwortmanager, Monitoring, Backup-Konsole, Ticketsystem, dieses Wiki.
""" ),

('infos', 'Glossar: IT-Abkuerzungen', ['Intern', 'Glossar', 'Referenz'], """\
# Glossar: IT-Abkuerzungen

| Abk. | Bedeutung | Kurz |
|---|---|---|
| AD | Active Directory | Windows-Verzeichnisdienst (Benutzer/Rechte) |
| DHCP | Dynamic Host Configuration Protocol | Vergibt IPs automatisch |
| DNS | Domain Name System | Name -> IP |
| GPO | Group Policy Object | Gruppenrichtlinie |
| IMAP | Internet Message Access Protocol | Mailabruf (serverseitig) |
| LAN/WAN | Local/Wide Area Network | lokales / weites Netz |
| MFA/2FA | (Multi/Zwei)-Faktor-Authentifizierung | 2. Faktor beim Login |
| OST/PST | Outlook-Datendateien | Cache (OST) / lokal (PST) |
| RDP | Remote Desktop Protocol | Windows-Fernsteuerung |
| SMB | Server Message Block | Windows-Dateifreigaben |
| SMTP | Simple Mail Transfer Protocol | Mailversand |
| SSD/HDD | Solid State / Hard Disk Drive | Datentraeger |
| SSH | Secure Shell | sichere Fernwartung (Linux) |
| VLAN | Virtual LAN | logisch getrennte Netze |
| VPN | Virtual Private Network | sichere Verbindung ins Firmennetz |
""" ),

]


def main():
    app = create_app()
    with app.app_context():
        admin = (User.query.filter_by(username='admin').first()
                 or User.query.filter_by(role='admin').first())
        aid = admin.id if admin else None

        slug_to_space = {s.slug: s for s in Space.query.all()}
        created_s = 0
        for slug, name, desc, parent_slug, acc in SPACES:
            if slug in slug_to_space:
                continue
            parent = slug_to_space.get(parent_slug)
            sp = Space(slug=slug, name=name, description=desc,
                       default_access=acc,
                       parent_id=(parent.id if parent else None))
            db.session.add(sp)
            db.session.flush()
            slug_to_space[slug] = sp
            created_s += 1

        def get_tag(tname):
            tslug = slugify(tname, fallback='tag')
            t = Tag.query.filter_by(slug=tslug).first()
            if not t:
                t = Tag(slug=tslug, name=tname)
                db.session.add(t)
            return t

        created_p = 0
        for space_slug, title, tags, content in PAGES:
            sp = slug_to_space.get(space_slug)
            if sp is None:
                continue
            pslug = slugify(title)
            if Page.query.filter_by(space_id=sp.id, slug=pslug).first():
                continue
            pg = Page(space_id=sp.id, slug=pslug, title=title, content=content,
                      created_by=aid, updated_by=aid)
            db.session.add(pg)
            db.session.flush()
            pg.tags = [get_tag(t) for t in tags]
            db.session.add(PageRevision(page_id=pg.id, title=title, content=content,
                                        comment='Angelegt (Startinhalt)', author_id=aid))
            created_p += 1

        db.session.commit()
        print(f'{created_s} Bereiche und {created_p} Seiten angelegt.')


if __name__ == '__main__':
    main()
