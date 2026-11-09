"""Outil Samsung V20 : sondes fermées en lecture et dossier officiel local."""
import json
from pathlib import Path
import tempfile

from outils.v17.diagnostic_environnement import digest, inventory, run_command, utc, verify_inventory
from outils.v18.diagnostic_recovery import usb_interfaces
from outils.v19 import recuperation_google as google
from prevost_v16.core import Diagnostics, parse_adb, read

ROOT = Path(__file__).resolve().parents[2]
MTP_ATTRIBUTES = 'standard::type,filesystem::type,filesystem::readonly'
LIMITS = [
    'La vérification Google nécessite le compte antérieurement synchronisé ou une démarche officielle de propriété ; aucun déblocage garanti.',
    'USB et MTP ne lisent pas le drapeau FRP. Un montage MTP ne prouve pas que les données utilisateur sont déverrouillées.',
    'Aucun shell Android, acceptation automatique d’autorisation ADB, redémarrage, flash, reset ou sideload envoyé.',
    'Modèle exact, Android installé et bootloader restent inconnus si les seules annonces USB/MTP ne les fournissent pas.',
    'L’observation d’écran V19 est historique et déclarée par l’utilisateur ; elle n’est pas une nouvelle lecture de l’écran.',
]


def allowed(argv):
    """Liste fermée : toute nouvelle commande doit être revue et testée explicitement."""
    return argv in (['lsusb', '-d', '04e8:'], ['adb', 'devices', '-l'], ['gio', 'mount', '-li']) or (
        len(argv) == 5 and argv[:4] == ['gio', 'info', '-a', MTP_ATTRIBUTES]
        and argv[4].startswith('mtp://') and '\n' not in argv[4] and '\r' not in argv[4])


def mtp_attributes(output):
    result = {}
    for line in output.splitlines():
        key, separator, value = line.strip().partition(': ')
        if separator and key in MTP_ATTRIBUTES.split(',') and value.strip():
            result[key] = value.strip()
    return result


def collect(sysfs=Path('/sys/bus/usb/devices'), runner=run_command, timeout=15,
            probe_adb=True, probe_mtp=True):
    probes = []

    def command(key, argv):
        if not allowed(argv):
            raise ValueError('Commande hors périmètre V20')
        result = runner(key, argv, timeout=timeout)
        probes.append(result)
        return result

    def adapter(argv):
        result = command('mtp_mounts', argv)
        return {'status': 'ok' if result['returncode'] == 0 else 'indisponible',
                'code': result['returncode'], 'output': result['stdout']}

    usb = usb_interfaces(Path(sysfs))
    for d in usb['devices']:
        for i in d['interfaces']:
            path = Path(i['path'])
            i['endpoints'] = [{k: read(ep / k) for k in ('bEndpointAddress', 'bmAttributes',
                               'wMaxPacketSize', 'bInterval')} for ep in sorted(path.glob('ep_*'))]
    command('usb', ['lsusb', '-d', '04e8:'])
    adb = command('adb', ['adb', 'devices', '-l']) if probe_adb else {
        'id': 'adb', 'status': 'skipped', 'returncode': None, 'stdout': '', 'stderr': 'ADB omis par paramètre'}
    if not probe_adb:
        probes.append(adb)
    states = parse_adb(adb['stdout']) if adb['returncode'] == 0 else []
    mtp = Diagnostics(runner=adapter).mtp(usb)
    mtp_probe = probes[-1]
    mtp['session_query_success'] = mtp_probe['returncode'] == 0 and not mtp_probe.get('stderr')
    metadata = []
    for mount in mtp['mounts']:
        if len(mount['samsung_ports']) == 1 and probe_mtp:
            result = command('mtp_info', ['gio', 'info', '-a', MTP_ATTRIBUTES, mount['uri']])
            attributes = mtp_attributes(result['stdout'])
            metadata.append({'attributes': attributes, 'port': mount['samsung_ports'][0], 'uri': mount['uri'],
                             'returncode': result['returncode'],
                             'root_metadata_accessible': result['returncode'] == 0 and bool(attributes) and not result.get('stderr')})
    devices = []
    for device in usb['devices']:
        matches = [d for d in states if (device.get('serial') and d['serial'] == device['serial'])
                   or (d.get('usb') and d['usb'] == device['port'])]
        device_states = [d['state'] for d in matches]
        devices.append({'port': device['port'], 'adb_states': device_states,
                        'mtp_interface_announced': any(i['role'] == 'PTP/MTP candidat' for i in device['interfaces']),
                        'adb_interface_announced': any(i['role'] == 'ADB annoncé' for i in device['interfaces']),
                        'recovery_transport_observed': any(s in ('sideload', 'recovery') for s in device_states),
                        'recovery_scope': 'sideload/recovery est un transport limité ; aucun accès shell ou fichier essayé',
                        'mtp_mount_announced': any(device['port'] in m['samsung_ports'] for m in mtp['mounts']),
                        'mtp_root_metadata_accessible': any(m['port'] == device['port'] and m['root_metadata_accessible'] for m in metadata)})
    return {'usb': usb, 'probes': probes, 'adb_devices': states, 'mtp': mtp,
            'mtp_metadata': metadata, 'devices': devices,
            'unassociated_adb_count': sum(not any((u.get('serial') and d['serial'] == u['serial']) or
                                                (d.get('usb') and d['usb'] == u['port'])
                                                for u in usb['devices']) for d in states),
            'model': {'expected': 'SM-G990W2', 'observed_exact': None,
                      'status': 'modèle attendu déclaré ; identité exacte non certifiée par descripteur générique'}}


def history(root):
    guide = google.prepare(root)
    records = guide['evidence'].copy()
    for path in sorted((root / 'rapports/v19').glob('dossier-*/rapport.json')):
        record = {'path': str(path.relative_to(root)), 'sha256': digest(path)}
        try:
            r = json.loads(path.read_text(encoding='utf-8'))
            c = r.get('confirmation', {})
            record['analysis'] = {'version': r.get('version'), 'created_at': r.get('created_at'),
                                  'google_screen_confirmed_by_user': c.get('confirmed_by_user') is True
                                  and c.get('screen_text') == 'Vérifier votre compte Google',
                                  'observation_time': c.get('observation_time'),
                                  'limits': 'Observation déclarée ; aucun compte, secret ou drapeau système lu'}
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            record['analysis_error'] = type(exc).__name__
        records.append(record)
    return guide, records


def capabilities(live):
    probes = live['probes']
    adb = next(p for p in probes if p['id'] == 'adb')
    return {
        'usb': 'Samsung détecté dans sysfs' if live['usb']['devices'] else
               'aucun Samsung observé ; absence ou visibilité à vérifier',
        'usb_lib': {k: next(p for p in probes if p['id'] == 'usb').get(k) for k in ('status', 'returncode')},
        'adb': 'non sondé' if adb['status'] == 'skipped' else 'serveur/transport indisponible : voir erreur' if adb['returncode'] != 0 else
               'liste vide' if not live['adb_devices'] else 'états observés ; association Samsung détaillée par port',
        'mtp': 'métadonnées de racine accessibles' if any(m['root_metadata_accessible'] for m in live['mtp_metadata']) else
               'montage annoncé, accès aux métadonnées non établi' if any(d['mtp_mount_announced'] for d in live['devices']) else
               'aucun montage Samsung annoncé par cette session' if live['mtp']['session_query_success'] else
               'vue de session incomplète ou indisponible',
        'recovery': 'transport Recovery/sideload associé à Samsung observé' if any(d['recovery_transport_observed'] for d in live['devices']) else
                    'non établi par un transport ADB associé ; aucun changement de mode tenté',
        'frp': 'écran Google confirmé par déclaration V19 ; drapeau actuel non mesuré',
        'restauration': 'documentation officielle et démarches disponibles ; aucune restauration exécutée',
    }


def prepare(root=ROOT, *, diagnostic=False, label='local', timeout=15,
            probe_adb=True, probe_mtp=True, sysfs=Path('/sys/bus/usb/devices'), runner=run_command):
    root = Path(root)
    before = inventory(root)
    start = utc()
    live = collect(sysfs, runner, timeout, probe_adb, probe_mtp)
    guide, records = history(root)
    operational = capabilities(live)
    if guide['confirmation'].get('confirmed_by_user') is not True:
        operational['frp'] = 'confirmation utilisateur absente ; état FRP non établi'
    return {'version': 20, 'started_at': start, 'finished_at': utc(), 'label': label,
            'label_is_user_declared': True, 'script_sha256': digest(Path(__file__)),
            'parameters': {'diagnostic_only': diagnostic, 'timeout_seconds': timeout,
                           'probe_adb': probe_adb, 'probe_mtp_metadata': probe_mtp},
            'live': live, 'confirmation': guide['confirmation'], 'historical_evidence': records,
            'capabilities': operational, 'limits': LIMITS,
            'official_options': {'checked_on': google.SOURCE_DATE, 'sources': google.SOURCES,
                                 'summary': google.SECTIONS['android'],
                                 'verification_method': 'pages officielles consultées via outil web le 2026-11-09 ; aucun contrôle HTTP effectué par ce lancement'},
            'assistant': {} if diagnostic else guide['sections'],
            'property_drafts': {} if diagnostic else guide['drafts'],
            'preservation': verify_inventory(root, before)}


def text_report(report):
    sections = ['PRÉVOST V20 — RÉCUPÉRATION SAMSUNG',
                'Date UTC : ' + report['started_at'], 'Environnement déclaré : ' + report['label'],
                '\nFONCTIONS ET ACCÈS OBSERVÉS', json.dumps(report['capabilities'], ensure_ascii=False, indent=2),
                '\nLIMITES', '\n'.join('- ' + s for s in report['limits']),
                '\nCONFIRMATION UTILISATEUR', json.dumps(report['confirmation'], ensure_ascii=False, indent=2)]
    for title, body in report['assistant'].items():
        sections.extend(['\nASSISTANT ' + title.upper(), body])
    sections.extend(['\nRESTAURATION OFFICIELLE', report['official_options']['summary'],
                     '\nDONNÉES TECHNIQUES ET HISTORIQUES', json.dumps({k: report[k] for k in
                     ('live', 'historical_evidence', 'preservation')}, ensure_ascii=False, indent=2)])
    return '\n'.join(sections) + '\n'


def save(report, root=ROOT):
    base = Path(root) / 'rapports/v20'
    base.mkdir(parents=True, exist_ok=True)
    stamp = report['started_at'].replace(':', '').replace('.', '')
    out = Path(tempfile.mkdtemp(prefix='recuperation-' + stamp + '-', dir=base))
    files = {'rapport.json': json.dumps(report, ensure_ascii=False, indent=2) + '\n',
             'rapport.txt': text_report(report)}
    files.update({'demande-' + name + '.txt': body for name, body in report['property_drafts'].items()})
    for name, value in files.items():
        with (out / name).open('x', encoding='utf-8') as stream:
            stream.write(value)
    with (out / 'SHA256SUMS').open('x', encoding='utf-8') as stream:
        stream.write(''.join(digest(out / name) + '  ' + name + '\n' for name in files))
    return out


def latest(root=ROOT):
    paths = list((Path(root) / 'rapports/v20').glob('recuperation-*/rapport.json'))
    return max(paths, key=lambda p: p.stat().st_mtime_ns) if paths else None


def run(root=ROOT, *, diagnostic=False, report_only=False, label='local', timeout=15,
        probe_adb=True, probe_mtp=True, section='tout'):
    from prevost_v16.__main__ import show
    show('PRÉVOST V20 — RÉCUPÉRATION SAMSUNG', 'red')
    if report_only:
        path = latest(root)
        if path is None:
            show('Aucun rapport V20. Lancez prevost-samsung recuperation --diagnostic.', 'yellow')
            return 1
        # Lecture seulement : pas de sonde, nouveau dossier ou formulaire.
        show(path.with_suffix('.txt').read_text(encoding='utf-8'), 'sky')
        show('Rapport historique : ' + str(path), 'white')
        return 0
    show('Commandes : lsusb ; adb devices -l ; gio mount -li ; gio info (racine MTP associée uniquement)', 'yellow')
    report = prepare(root, diagnostic=diagnostic, label=label, timeout=timeout,
                     probe_adb=probe_adb, probe_mtp=probe_mtp)
    out = save(report, root)
    show(report['capabilities'], 'sky')
    show('\n'.join(report['limits']), 'white')
    if not diagnostic:
        for name, content in report['assistant'].items():
            if section in ('tout', name):
                show('Assistant ' + name, 'yellow')
                show(content, 'sky')
    show('Rapports JSON/TXT et empreintes : ' + str(out), 'white')
    if report['property_drafts']:
        show('Demandes Samsung/Bell préparées dans ce dossier ; aucun envoi.', 'white')
    return 0
