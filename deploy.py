"""
MiniWiki – Vollautomatisches From-Scratch-Deployment
====================================================
Richtet das Wiki auf einem FRISCHEN Ubuntu/Debian-Server komplett ein:
  System-Pakete · MariaDB + DB/User · App-User · venv + Abhaengigkeiten ·
  Schema (alle Tabellen) + Admin-Login · systemd-Service (Autostart) · UFW

Zugangsdaten werden interaktiv abgefragt (mit Defaults) oder ueber
Umgebungsvariablen gesetzt – es stehen KEINE Passwoerter in dieser Datei.

Aufruf (bei dir lokal, nicht auf dem Server):
    venv\\Scripts\\python deploy.py

Nicht-interaktiv: Werte als ENV setzen (siehe env=... unten).
"""
import paramiko, os, sys, time, secrets, getpass


# ── Konfiguration einsammeln (ENV > Eingabe > Default) ──────────────────
def ask(label, default='', env=None, secret=False):
    if env and os.environ.get(env) not in (None, ''):
        return os.environ[env]
    if not sys.stdin.isatty():            # nicht-interaktiv -> Default
        return default
    suffix = f' [{default}]' if default and not secret else ''
    prompt = f'  {label}{suffix}: '
    val = (getpass.getpass(prompt) if secret else input(prompt)).strip()
    return val or default


def ask_yesno(label, default=True, env=None):
    raw = ask(label + ' (j/n)', 'j' if default else 'n', env=env)
    return str(raw).strip().lower() in ('j', 'ja', 'y', 'yes', 'true', '1')


def gather_config():
    print('\n=== MiniWiki Deployment – Konfiguration ===\n')
    c = {}
    print('— Ziel-Server (SSH) —')
    c['HOST']     = ask('Server-IP/Host', '', env='DEPLOY_HOST')
    c['USER']     = ask('SSH-Benutzer', 'root', env='DEPLOY_SSH_USER')
    c['PASSWORD'] = ask('SSH-Passwort', '', env='DEPLOY_SSH_PASS', secret=True)
    c['PORT']     = int(ask('App-Port', '5002', env='DEPLOY_PORT'))

    print('\n— Wiki —')
    c['WIKI_NAME'] = ask('Anzeigename des Wikis', 'MiniWiki', env='WIKI_NAME')

    print('\n— Datenbank (wird angelegt) —')
    c['DB_NAME']  = ask('DB-Name', 'wiki', env='DB_NAME')
    c['DB_USER']  = ask('DB-User', 'wiki', env='DB_USER')
    c['DB_PASS']  = ask('DB-Passwort', 'Wiki#' + secrets.token_hex(4), env='DB_PASS', secret=True)

    print('\n— Erster Admin-Login —')
    c['ADMIN_USER']  = ask('Admin-Benutzername', 'admin', env='ADMIN_USER')
    c['ADMIN_PASS']  = ask('Admin-Passwort', 'Admin#2026', env='ADMIN_PASS', secret=True)
    c['ADMIN_EMAIL'] = ask('Admin E-Mail (optional)', '', env='ADMIN_EMAIL')

    print('\n— Optionen —')
    c['SEED'] = ask_yesno('Beispiel-Bereiche + Startseite anlegen?', True, env='SEED_DEMO')
    c['COOKIE_SECURE'] = ask('Laeuft hinter HTTPS? cookie_secure (true/false)', 'false', env='COOKIE_SECURE')

    if not c['HOST'] or not c['PASSWORD']:
        print('\nFEHLER: HOST und SSH-Passwort sind erforderlich '
              '(per Eingabe oder ENV DEPLOY_HOST / DEPLOY_SSH_PASS).')
        sys.exit(1)
    return c


APP_DIR   = '/opt/wiki'
APP_USER  = 'wiki'
LOG_DIR   = '/var/log/wiki'
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

# Diese Dateien/Ordner NICHT auf den Server hochladen
SKIP = {
    '.git', '.github', 'venv', '.venv', '__pycache__', '.env', 'instance',
    'wiki.db', 'wiki_test.db', '.env.example', 'tests', '.idea', '.vscode',
    # Deploy-/Seed-Skripte – nicht Teil der App
    'deploy.py', 'deploy_update.py', 'seed_content.py',
}


def skip_item(name):
    return name in SKIP or name.endswith('.pyc') or name.endswith(('.db', '.log'))


def run(ssh, cmd, sudo=False):
    if sudo:
        cmd = "sudo -n bash -c '" + cmd.replace("'", "'\\''") + "'"
    print('  $ ' + (cmd[:90] + ('...' if len(cmd) > 90 else '')))
    chan = ssh.get_transport().open_session()
    chan.get_pty()
    chan.exec_command(cmd)
    out = b''
    while True:
        if chan.recv_ready():
            out += chan.recv(4096)
        elif chan.exit_status_ready():
            break
        else:
            time.sleep(0.05)
    code = chan.recv_exit_status()
    text = out.decode('utf-8', errors='replace').strip()
    if code != 0:
        print('    [WARN] exit=' + str(code) + ': ' + text[-300:])
    return text, code


def sftp_put_dir(sftp, local_path, remote_path):
    try:
        sftp.stat(remote_path)
    except FileNotFoundError:
        sftp.mkdir(remote_path)
    for item in os.listdir(local_path):
        if skip_item(item):
            continue
        l = os.path.join(local_path, item)
        r = remote_path + '/' + item
        if os.path.isdir(l):
            sftp_put_dir(sftp, l, r)
        else:
            sftp.put(l, r)


def main():
    c = gather_config()
    SECRET_KEY = secrets.token_hex(32)
    PORT = c['PORT']

    print('\n+--------------------------------------------------+')
    print('|   MiniWiki – Server Deployment                   |')
    print('+--------------------------------------------------+\n')

    print('[1/9] SSH-Verbindung aufbauen...')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(c['HOST'], username=c['USER'], password=c['PASSWORD'],
                timeout=30, banner_timeout=60, auth_timeout=30,
                look_for_keys=False, allow_agent=False)
    print('      Verbunden mit ' + c['HOST'])

    # passwortloses sudo fuer den Deploy-User (falls nicht root)
    if c['USER'] != 'root':
        run(ssh, 'echo "' + c['PASSWORD'] + '" | sudo -S bash -c "echo \'' + c['USER']
            + ' ALL=(ALL) NOPASSWD:ALL\' > /etc/sudoers.d/deploy-nopasswd && chmod 440 /etc/sudoers.d/deploy-nopasswd"')
        time.sleep(1)

    print('\n[2/9] System-Pakete installieren...')
    run(ssh, 'apt-get update -qq', sudo=True)
    run(ssh, 'DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3 python3-pip '
             'python3-venv python3-dev mariadb-server mariadb-client ufw build-essential rsync', sudo=True)
    run(ssh, 'systemctl enable --now mariadb', sudo=True)

    print('\n[3/9] Datenbank einrichten...')
    sql = ("CREATE DATABASE IF NOT EXISTS " + c['DB_NAME'] + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
           "CREATE USER IF NOT EXISTS '" + c['DB_USER'] + "'@'localhost' IDENTIFIED BY '" + c['DB_PASS'] + "';"
           "GRANT ALL PRIVILEGES ON " + c['DB_NAME'] + ".* TO '" + c['DB_USER'] + "'@'localhost';"
           "FLUSH PRIVILEGES;")
    run(ssh, 'mysql -u root -e "' + sql + '"', sudo=True)

    print('\n[4/9] App-Verzeichnis vorbereiten...')
    run(ssh, 'id ' + APP_USER + ' || useradd --system --no-create-home --shell /bin/false ' + APP_USER, sudo=True)
    run(ssh, 'mkdir -p ' + APP_DIR + ' ' + LOG_DIR, sudo=True)
    run(ssh, 'chown ' + c['USER'] + ':' + c['USER'] + ' ' + APP_DIR, sudo=True)

    print('\n[5/9] Dateien hochladen...')
    sftp = ssh.open_sftp()
    sftp_put_dir(sftp, LOCAL_DIR, APP_DIR)
    sftp.close()
    print('      App-Dateien kopiert')

    print('\n[6/9] .env erstellen...')
    env_lines = [
        'SECRET_KEY=' + SECRET_KEY,
        'DATABASE_URL=mysql+pymysql://' + c['DB_USER'] + ':' + c['DB_PASS'] + '@localhost/' + c['DB_NAME'],
        'WIKI_NAME=' + c['WIKI_NAME'],
        'INSTANCE_LABEL=',
        'COOKIE_SECURE=' + str(c.get('COOKIE_SECURE', 'false')).lower(),
    ]
    sftp = ssh.open_sftp()
    with sftp.open(APP_DIR + '/.env', 'w') as f:
        f.write('\n'.join(env_lines) + '\n')
    sftp.close()
    run(ssh, 'chown -R ' + APP_USER + ':' + APP_USER + ' ' + APP_DIR + ' ' + LOG_DIR, sudo=True)
    run(ssh, 'chmod 600 ' + APP_DIR + '/.env', sudo=True)

    print('\n[7/9] Python-Umgebung + Abhaengigkeiten...')
    run(ssh, 'sudo -u ' + APP_USER + ' python3 -m venv ' + APP_DIR + '/venv')
    run(ssh, 'sudo -u ' + APP_USER + ' ' + APP_DIR + '/venv/bin/pip install -q --upgrade pip wheel')
    run(ssh, 'sudo -u ' + APP_USER + ' ' + APP_DIR + '/venv/bin/pip install -q --no-cache-dir -r ' + APP_DIR + '/requirements.txt')

    print('\n[8/9] Schema anlegen + Admin-Login...')
    venv_flask = 'sudo -u ' + APP_USER + ' ' + APP_DIR + '/venv/bin/flask --app run'
    run(ssh, 'cd ' + APP_DIR + ' && ' + venv_flask + ' init-db')
    admin_cmd = (venv_flask + ' create-admin --username "' + c['ADMIN_USER']
                 + '" --password "' + c['ADMIN_PASS'] + '"')
    if c.get('ADMIN_EMAIL'):
        admin_cmd += ' --email "' + c['ADMIN_EMAIL'] + '"'
    run(ssh, 'cd ' + APP_DIR + ' && ' + admin_cmd)
    if c.get('SEED'):
        run(ssh, 'cd ' + APP_DIR + ' && ' + venv_flask + ' seed-demo')
    run(ssh, 'cd ' + APP_DIR + ' && ' + venv_flask + ' seed-templates')

    print('\n[9/9] systemd-Service + Firewall...')
    service_txt = ('[Unit]\n'
        'Description=MiniWiki\n'
        'After=network.target mariadb.service\n\n'
        '[Service]\n'
        'User=' + APP_USER + '\nGroup=' + APP_USER + '\n'
        'WorkingDirectory=' + APP_DIR + '\n'
        'Environment=PATH=' + APP_DIR + '/venv/bin\n'
        'EnvironmentFile=' + APP_DIR + '/.env\n'
        'ExecStart=' + APP_DIR + '/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:' + str(PORT)
        + ' --timeout 60 --access-logfile ' + LOG_DIR + '/access.log --error-logfile '
        + LOG_DIR + '/error.log run:app\n'
        'Restart=always\nRestartSec=5\n\n'
        '[Install]\nWantedBy=multi-user.target\n')
    sftp = ssh.open_sftp()
    with sftp.open('/tmp/wiki.service', 'w') as f:
        f.write(service_txt)
    sftp.close()
    run(ssh, 'cp /tmp/wiki.service /etc/systemd/system/wiki.service && rm -f /tmp/wiki.service', sudo=True)
    run(ssh, 'systemctl daemon-reload', sudo=True)
    run(ssh, 'systemctl enable --now wiki', sudo=True)
    time.sleep(3)
    status, _ = run(ssh, 'systemctl is-active wiki', sudo=True)

    run(ssh, 'ufw --force enable', sudo=True)
    run(ssh, 'ufw allow OpenSSH', sudo=True)
    run(ssh, 'ufw allow ' + str(PORT) + '/tcp', sudo=True)

    ssh.close()
    print('\n+--------------------------------------------------+')
    print('|   DEPLOYMENT ABGESCHLOSSEN                       |')
    print('+--------------------------------------------------+')
    print('  URL:      http://' + c['HOST'] + ':' + str(PORT))
    print('  Login:    ' + c['ADMIN_USER'])
    print('  Passwort: ' + c['ADMIN_PASS'] + '   <-- BITTE AENDERN!')
    print('  Service:  ' + status.strip())
    print('+--------------------------------------------------+')
    print('  Tipp: Fuer HTTPS einen nginx-Proxy davor setzen und')
    print('        in der .env COOKIE_SECURE=true setzen.')
    print('+--------------------------------------------------+')


if __name__ == '__main__':
    main()
