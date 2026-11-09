#!/usr/bin/env python3
"""Comparaison DNS/ADB : commandes fixes, sans sudo ni écriture téléphone.

Exécuter le même fichier dans Codex puis dans le terminal Ubuntu normal.
Aucun profil de navigateur, clé ADB, cookie ou jeton n'est lu.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
HOSTS = ('accounts.google.com', 'support.google.com', 'www.samsung.com',
         'support.bell.ca', 'doc.samsungmobile.com', 'fota-cloud-dn.ospserver.net')
URLS = ('https://doc.samsungmobile.com/SM-G990W2/BMC/doc.html',
        'https://doc.samsungmobile.com/SM-G990W2/023358220727/eng.html',
        'https://fota-cloud-dn.ospserver.net/firmware/BMC/SM-G990W2/version.xml')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def run_command(test_id, argv, timeout=20):
    """Capture le code réel du processus ; absent = None, timeout tué = code réel."""
    start = time.monotonic()
    result = {'id': test_id, 'argv': argv, 'command': shlex.join(argv), 'started_at': utc(),
              'returncode': None, 'timed_out': False, 'stdout': '', 'stderr': ''}
    try:
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, errors='replace')
        try:
            stdout, stderr = child.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            result['timed_out'] = True
            child.kill()
            stdout, stderr = child.communicate()
        result.update(returncode=child.returncode, stdout=stdout, stderr=stderr,
                      status='timeout' if result['timed_out'] else 'executed')
    except OSError as exc:
        result.update(status='not_started', stderr=f'{type(exc).__name__}: {exc}')
    result.update(finished_at=utc(), duration_seconds=round(time.monotonic() - start, 3))
    return result


def commands():
    items = [('python_version', [sys.executable, '--version']),
             ('kernel', ['uname', '-srm']),
             ('localhost', ['getent', 'hosts', 'localhost']),
             ('resolver_status', ['resolvectl', 'status']),
             ('resolver_service', ['systemctl', 'is-active', 'systemd-resolved']),
             ('adb_version', ['adb', 'version']),
             ('usb_samsung', ['lsusb', '-d', '04e8:']),
             ('adb_devices', ['adb', 'devices', '-l'])]
    for host in HOSTS:
        items.append(('dns_' + host, ['getent', 'ahosts', host]))
    items.append(('resolver_query', ['resolvectl', 'query', 'doc.samsungmobile.com']))
    # Test de permission locale uniquement, sans envoi de données et sans autre DNS.
    probe = '''import socket,sys,json
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.settimeout(2)
try:
 s.connect((sys.argv[1],int(sys.argv[2])))
 print(json.dumps({'result':'connected'}))
except OSError as e:
 print(json.dumps({'result':type(e).__name__,'errno':e.errno,'message':str(e)}))
 sys.exit(1)
finally:
 s.close()
'''
    for test_id, host, port in [('socket_dns_local', '127.0.0.53', '53'),
                                ('socket_adb_local', '127.0.0.1', '5037')]:
        items.append((test_id, [sys.executable, '-c', probe, host, port]))
    for n, url in enumerate(URLS):
        # -q en première option ignore ~/.curlrc ; aucune authentification ou cookie.
        # Pas de proxy hérité : aucun identifiant de proxy n'est transmis.
        # HEAD seulement : aucune image firmware ni corps de page téléchargé.
        items.append(('http_metadata_' + str(n + 1), ['curl', '-q', '--noproxy', '*',
                      '--head', '--silent', '--show-error', '--connect-timeout', '5',
                      '--max-time', '15', '--proto', '=https', url]))
    return items


def context():
    result = {'platform': platform.platform(), 'python': sys.version.split()[0],
              'label_is_user_declared': True,
              'proxy_variables_present_only': {key: bool(os.environ.get(key)) for key in
                ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')},
              'limits': 'Une étiquette ubuntu ne prouve pas à elle seule une exécution hors sandbox. '
                        'Aucune valeur de proxy, clé ADB, session ou donnée de navigateur collectée.'}
    for name in ('/etc/resolv.conf', '/etc/nsswitch.conf'):
        try:
            result[name] = Path(name).read_text(errors='replace')
        except OSError as exc:
            result[name] = type(exc).__name__
    try:
        result['process_restrictions'] = [line for line in Path('/proc/self/status').read_text().splitlines()
                                          if line.startswith(('NoNewPrivs:', 'Seccomp:', 'Seccomp_filters:'))]
    except OSError:
        result['process_restrictions'] = 'inaccessible'
    for name in ('net', 'pid', 'user'):
        try:
            result['namespace_' + name] = os.readlink('/proc/self/ns/' + name)
        except OSError as exc:
            result['namespace_' + name] = type(exc).__name__
    return result


def inventory(root):
    return {str(p.relative_to(root)): digest(p) for p in (root / 'rapports').rglob('*')
            if p.is_file() and not p.is_symlink()}


def verify_inventory(root, before):
    changed = []
    for name, old in before.items():
        p = root / name
        if not p.is_file() or digest(p) != old:
            changed.append(name)
    return {'files_checked': len(before), 'changed_or_missing': changed,
            'note': 'Une autre instance qui écrit simultanément peut faire varier un journal.'}


def classify(records):
    by_id = {r['id']: r for r in records}
    findings = []
    adb = by_id.get('adb_devices', {})
    error = adb.get('stderr', '')
    if 'Operation not permitted' in error or 'Permission denied' in error:
        findings.append('ADB : erreur de permission observée ; voir stderr exact. '
                        'Cela ne prouve pas un refus de débogage du téléphone.')
    elif adb.get('returncode') == 0:
        findings.append('ADB : commande devices exécutée avec succès ; vérifier la présence et l’état d’un appareil.')
    if any(r['id'].startswith('dns_') and r.get('returncode') not in (0, None) for r in records):
        findings.append('Au moins une résolution DNS getent a échoué dans cet environnement.')
    if any(r['id'].startswith('http_metadata_') and r.get('returncode') == 6 for r in records):
        findings.append('curl code 6 : nom d’hôte non résolu, aucun statut HTTP du serveur obtenu.')
    if any(r['id'].startswith('socket_') and '"errno": 1' in r.get('stdout', '') for r in records):
        findings.append('Une connexion locale a renvoyé EPERM : restriction de permission observée ; '
                        'la règle exacte nécessite la configuration de l’environnement.')
    findings.append('HEAD 200 ne valide ni un firmware binaire ni son authenticité. HEAD 403 ne prouve pas un refus FRP.')
    return findings


def compare(report, other):
    left = {r['id']: r for r in report['tests']}
    right = {r['id']: r for r in other['tests']}
    return {'labels': [report['label'], other['label']], 'other_time': other['started_at'],
            'script_hashes_equal': report['script_sha256'] == other['script_sha256'],
            'rows': [{'id': key, report['label']: left[key]['returncode'],
                      other['label']: right[key]['returncode']} for key in left if key in right],
            'limits': 'Comparer aussi stdout/stderr et l’heure. Un code ADB 0 ne signifie pas un téléphone autorisé.'}


def save_report(report, folder):
    folder.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix='environnement-' + report['label'] + '-' +
                                    datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-',
                                    suffix='.json', dir=folder)
    path = Path(filename)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    lines = ['PRÉVOST V17 — DIAGNOSTIC ENVIRONNEMENT', 'Étiquette : ' + report['label'],
             'Date UTC : ' + report['started_at'], '', 'CONSTATS'] + report['findings']
    lines += ['', 'CONTEXTE', json.dumps(report['context'], ensure_ascii=False, indent=2)]
    for row in report['tests']:
        lines += ['', '$ ' + row['command'], 'Code de retour : ' + str(row['returncode']),
                  'Statut : ' + row['status'], 'Timeout : ' + str(row['timed_out']),
                  'STDOUT:', row['stdout'], 'STDERR:', row['stderr']]
    lines += ['', 'CONSERVATION', json.dumps(report['preservation'], ensure_ascii=False, indent=2)]
    if report.get('comparison'):
        lines += ['', 'COMPARAISON', json.dumps(report['comparison'], ensure_ascii=False, indent=2)]
    with path.with_suffix('.txt').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(lines) + '\n')
    with path.with_suffix('.json.sha256').open('x', encoding='utf-8') as stream:
        stream.write(digest(path) + '  ' + path.name + '\n')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True, choices=('codex', 'ubuntu'))
    args = parser.parse_args(argv)
    before = inventory(ROOT)
    report = {'label': args.label, 'started_at': utc(), 'script_sha256': digest(Path(__file__)),
              'actions': 'Aucun sudo, redémarrage, reset, flash, modification DNS ou formulaire soumis. '
                         'adb devices peut démarrer le serveur ADB sur le PC et utiliser ses clés habituelles.',
              'context': context(), 'tests': []}
    try:
        for test_id, command in commands():
            row = run_command(test_id, command)
            report['tests'].append(row)
            print(f'{test_id}: code={row["returncode"]} statut={row["status"]}', flush=True)
    except KeyboardInterrupt:
        print('Interruption : sauvegarde des tests terminés.', file=sys.stderr)
    report['finished_at'] = utc()
    report['findings'] = classify(report['tests'])
    report['preservation'] = verify_inventory(ROOT, before)
    folder = ROOT / 'rapports' / 'v17'
    other_label = 'ubuntu' if args.label == 'codex' else 'codex'
    previous = sorted(folder.glob('environnement-' + other_label + '-*.json'))
    if previous:
        try:
            report['comparison'] = compare(report, json.loads(previous[-1].read_text(encoding='utf-8')))
        except (OSError, ValueError, KeyError) as exc:
            report['comparison_error'] = type(exc).__name__
    path = save_report(report, folder)
    print('Rapport JSON :', path)
    print('Rapport TXT :', path.with_suffix('.txt'))
    print('SHA256 :', path.with_suffix('.json.sha256'))
    print('Code 0 du script = collecte terminée ; consulter les codes individuels pour chaque test.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
