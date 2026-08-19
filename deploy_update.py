"""
MiniWiki – Update-Deployment (kein Neuaufbau!)
==============================================
Aktualisiert nur die App auf dem Server:
  - laedt app/ + requirements.txt/config.py/run.py neu hoch
  - installiert ggf. neue Abhaengigkeiten
  - fuehrt (falls Migrationen vorhanden) 'flask db upgrade' aus
  - startet den Wiki-Dienst neu

Die .env (SECRET_KEY, DATABASE_URL, ...) und die Datenbank bleiben UNVERAENDERT.
Zugangsdaten werden abgefragt oder per ENV gesetzt – keine Passwoerter im File.

Aufruf (lokal bei dir):
    venv\\Scripts\\python deploy_update.py
"""
import paramiko, os, sys, time, getpass


def ask(label, default='', env=None, secret=False):
    if env and os.environ.get(env) not in (None, ''):
        return os.environ[env]
    if not sys.stdin.isatty():
        return default
    suffix = f' [{default}]' if default and not secret else ''
    val = (getpass.getpass(f'  {label}: ') if secret else input(f'  {label}{suffix}: ')).strip()
    return val or default


HOST     = ask('Server-IP/Host', '', env='DEPLOY_HOST')
USER     = ask('SSH-Benutzer', 'root', env='DEPLOY_SSH_USER')
PASSWORD = ask('SSH-Passwort', '', env='DEPLOY_SSH_PASS', secret=True)

APP_DIR  = '/opt/wiki'
APP_USER = 'wiki'
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

# Diese Dateien/Ordner NICHT hochladen
SKIP = {'.git', 'venv', '.venv', '__pycache__', '.env', '.env.example', 'instance',
        'wiki.db', 'wiki_test.db', 'deploy.py', 'deploy_update.py', 'seed_content.py',
        'README.md', '.gitignore'}

# Einzeldateien im Projekt-Root, die mit aktualisiert werden
ROOT_FILES = ['requirements.txt', 'config.py', 'run.py']


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
    if text:
        print('    ' + text[-400:].replace('\n', '\n    '))
    if code != 0:
        print('    [WARN] exit=' + str(code))
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
            print('    upload: ' + r)


def main():
    if not PASSWORD:
        print('FEHLER: SSH-Passwort erforderlich (Eingabe oder ENV DEPLOY_SSH_PASS).')
        sys.exit(1)

    print('\n+-------------------------------------------+')
    print('|   MiniWiki – UPDATE Deployment            |')
    print('+-------------------------------------------+\n')

    print('[1/5] SSH-Verbindung...')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD,
                timeout=30, banner_timeout=60, auth_timeout=30,
                look_for_keys=False, allow_agent=False)
    print('      Verbunden mit ' + HOST)

    print('\n[2/5] Dateien hochladen...')
    # Zielverzeichnis kurzzeitig dem SSH-User uebergeben, damit der Upload klappt
    run(ssh, 'chown -R ' + USER + ':' + USER + ' ' + APP_DIR + '/app', sudo=True)
    root_targets = ' '.join(APP_DIR + '/' + f for f in ROOT_FILES)
    run(ssh, 'chown ' + USER + ':' + USER + ' ' + root_targets + ' 2>/dev/null || true', sudo=True)

    sftp = ssh.open_sftp()
    sftp_put_dir(sftp, os.path.join(LOCAL_DIR, 'app'), APP_DIR + '/app')
    for fname in ROOT_FILES:
        lp = os.path.join(LOCAL_DIR, fname)
        if os.path.exists(lp):
            sftp.put(lp, APP_DIR + '/' + fname)
            print('    upload: ' + APP_DIR + '/' + fname)
    sftp.close()

    # Besitz zurueck an den App-User
    run(ssh, 'chown -R ' + APP_USER + ':' + APP_USER + ' ' + APP_DIR + '/app', sudo=True)
    run(ssh, 'chown ' + APP_USER + ':' + APP_USER + ' ' + root_targets + ' 2>/dev/null || true', sudo=True)
    print('      Dateien aktualisiert')

    print('\n[3/5] Abhaengigkeiten installieren...')
    run(ssh, 'sudo -u ' + APP_USER + ' ' + APP_DIR + '/venv/bin/pip install -q --no-cache-dir -r ' + APP_DIR + '/requirements.txt')

    print('\n[4/5] Schema aktualisieren + Standardvorlagen...')
    run(ssh, 'cd ' + APP_DIR + ' && sudo -u ' + APP_USER + ' ' + APP_DIR
             + '/venv/bin/flask --app run ensure-schema')
    run(ssh, 'cd ' + APP_DIR + ' && sudo -u ' + APP_USER + ' ' + APP_DIR
             + '/venv/bin/flask --app run seed-templates')

    print('\n[5/5] Dienst neu starten...')
    run(ssh, 'systemctl restart wiki', sudo=True)
    time.sleep(3)
    status, _ = run(ssh, 'systemctl is-active wiki', sudo=True)
    run(ssh, 'journalctl -u wiki -n 6 --no-pager', sudo=True)

    ssh.close()
    print('\n+-------------------------------------------+')
    print('|   UPDATE ABGESCHLOSSEN                     |')
    print('+-------------------------------------------+')
    print('  Dienst:  ' + status.strip())
    print('  Host:    ' + HOST)
    print('+-------------------------------------------+')


if __name__ == '__main__':
    main()
