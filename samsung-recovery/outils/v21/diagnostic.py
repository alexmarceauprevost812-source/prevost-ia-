"""Diagnostic V21 en lecture seule, avec rapport privé et partage par liste blanche."""
import errno
import json
import os
from pathlib import Path
import re
import socket
import stat
import tempfile
import zipfile

from outils.v17.diagnostic_environnement import digest, inventory, run_command, utc, verify_inventory
from outils.v19 import recuperation_google as google
from outils.v20 import recuperation as v20

ROOT = Path(__file__).resolve().parents[2]
LABELS = ('local', 'ubuntu', 'codex')
LIMITS = [
    'La détection USB ne prouve aucun accès aux données du téléphone.',
    'Une interface annoncée, un montage MTP et des métadonnées de racine sont trois observations distinctes ; aucun fichier utilisateur lu.',
    'Seccomp actif ne désigne pas à lui seul une opération bloquée ; une étiquette Ubuntu/Codex reste déclarative.',
    'Un refus du nœud USB ne détermine pas à lui seul sa cause : droits, ACL, namespace ou politique de sécurité.',
    'Vérification Google : ancien compte synchronisé ou démarche officielle de propriété ; aucun déblocage garanti.',
    'Aucun shell Android, changement de mode, réinitialisation, flash, sideload ni modification du téléphone.',
]


def socket_check(factory=socket.socket):
    sock = None
    stage = 'creation'
    try:
        sock = factory(socket.AF_INET, socket.SOCK_STREAM)
        stage = 'bind_loopback'
        sock.bind(('127.0.0.1', 0))
        stage = 'listen_loopback'
        sock.listen(1)
        return {'status': 'ok', 'stage': 'termine', 'errno': None,
                'scope': 'listener éphémère loopback seulement, fermé immédiatement ; aucun accès externe'}
    except OSError as exc:
        return {'status': 'refuse' if exc.errno in (errno.EPERM, errno.EACCES) else 'erreur',
                'stage': stage, 'errno': exc.errno, 'error_type': type(exc).__name__}
    finally:
        if sock is not None:
            sock.close()


def environment(status_file=Path('/proc/self/status'), probe=socket_check):
    restrictions = {}
    try:
        for line in Path(status_file).read_text().splitlines():
            key, _, value = line.partition(':')
            if key in ('NoNewPrivs', 'Seccomp', 'Seccomp_filters') and value.strip().isdigit():
                restrictions[key] = int(value)
        status = 'lu'
    except OSError:
        status = 'indisponible'
    return {'process_restrictions': restrictions, 'process_status': status,
            'loopback_listener': probe(), 'dbus_session_address_present': bool(os.environ.get('DBUS_SESSION_BUS_ADDRESS')),
            'runtime_dir_present': bool(os.environ.get('XDG_RUNTIME_DIR'))}


def node_evidence(device):
    path = device.get('node', {}).get('path')
    if not path:
        return {'status': 'adresse_indisponible'}
    node = Path(path)
    try:
        info = node.stat()
        return {'status': 'visible', 'mode': stat.filemode(info.st_mode), 'owner_uid': info.st_uid,
                'group_gid': info.st_gid, 'effective_uid': os.geteuid(),
                'owner_matches': info.st_uid == os.geteuid(),
                'group_matches': info.st_gid in (os.getegid(), *os.getgroups()),
                'read_access': os.access(node, os.R_OK, effective_ids=os.access in os.supports_effective_ids),
                'write_access': os.access(node, os.W_OK, effective_ids=os.access in os.supports_effective_ids)}
    except FileNotFoundError:
        return {'status': 'absent_de_cette_vue', 'scope': 'pas une preuve de débranchement physique'}
    except OSError as exc:
        return {'status': 'lecture_refusee' if exc.errno in (errno.EPERM, errno.EACCES) else 'erreur_stat',
                'errno': exc.errno}


def associate(live):
    """Un port ADB explicite prime ; une série seule doit correspondre à un seul USB."""
    devices = live['usb']['devices']
    result = []
    for entry in live['adb_devices']:
        candidates = [d for d in devices if d['port'] == entry['usb']] if entry.get('usb') else [
            d for d in devices if d.get('serial') and d['serial'] == entry['serial']]
        result.append({'state': entry['state'], 'port': candidates[0]['port'] if len(candidates) == 1 else None,
                       'basis': ('port_usb' if entry.get('usb') else 'serie_unique') if len(candidates) == 1 else 'non_etablie'})
    return result


def findings(live, context, nodes, associations):
    items = []

    def add(code, message, confidence='observe', **evidence):
        items.append({'code': code, 'message': message, 'confidence': confidence, 'evidence': evidence})

    by_id = {p['id']: p for p in live['probes']}
    local_refused = context['loopback_listener'].get('errno') in (errno.EPERM, errno.EACCES)
    if local_refused:
        add('restriction_locale_observee', 'Listener loopback refusé dans cet environnement avant tout accès au téléphone. '
            'Cohérent avec une restriction du sandbox ; la règle exacte et son attribution à Codex restent à confirmer.',
            errno=context['loopback_listener']['errno'])
    elif context['loopback_listener']['status'] == 'ok':
        add('listener_local_possible', 'Création et écoute loopback possibles ; cela ne valide ni ADB ni les permissions USB.')
    if context['process_restrictions'].get('Seccomp', 0):
        add('seccomp_actif', 'Filtrage seccomp actif ; sa présence seule ne prouve pas la cause d’un échec USB/ADB.')
    if not live['usb']['devices']:
        add('samsung_non_observe', 'Aucun Samsung visible dans sysfs ; branchement ou visibilité de l’environnement à vérifier.',
            sysfs_status=live['usb'].get('status'))
    for index, (device, node) in enumerate(zip(live['usb']['devices'], nodes), 1):
        alias = f'Samsung-{index}'
        if node['status'] == 'absent_de_cette_vue':
            add('noeud_usb_non_visible', 'Descripteurs Samsung visibles, mais nœud USB absent de cette vue. '
                'Un namespace/devfs restreint est possible ; ne pas en déduire un câble débranché.',
                confidence='interpretation', device=alias)
        elif node['status'] == 'lecture_refusee' or (node['status'] == 'visible' and not (node['read_access'] and node['write_access'])):
            add('acces_noeud_usb_refuse', 'Accès requis au nœud USB non disponible. Vérifier droits/ACL et politiques depuis Ubuntu normal ; '
                'aucune règle udev ou commande sudo appliquée. La cause ne se déduit pas de l’étiquette d’environnement.', device=alias)
        if not any(i['role'] == 'ADB annoncé' for i in device['interfaces']):
            add('interface_adb_non_annoncee', 'Aucune interface ADB ff/42/01 annoncée sur ce Samsung ; une liste ADB vide reste compatible.',device=alias)
    for probe in live['probes']:
        if probe.get('status') == 'not_started':
            add('outil_non_demarre', 'Sonde non démarrée : outil absent ou lancement refusé ; code processus inconnu.', probe=probe['id'])
        elif probe.get('timed_out'):
            add('sonde_expiree', 'Délai de sonde dépassé ; aucune conclusion positive sur son accès.',probe=probe['id'])
    usb_probe = by_id.get('usb', {})
    if usb_probe.get('returncode') not in (0, None):
        add('usb_libusb_echec', 'Énumération libusb en échec ; le code seul ne désigne pas une règle de permissions Ubuntu.', returncode=usb_probe['returncode'])
    adb = by_id['adb']
    adb_error = adb.get('stderr', '').lower()
    if adb['status'] == 'skipped':
        add('adb_omis', 'Sonde ADB omise par paramètre.')
    elif adb.get('returncode') == 0:
        if not live['adb_devices']:
            add('adb_liste_vide', 'Serveur ADB répond mais aucun transport n’est annoncé ; aucun refus RSA ou FRP n’est démontré.')
        for state in sorted(set(a['state'] for a in associations)):
            add('adb_etat_' + state, {'unauthorized':'Autorisation RSA ADB non accordée ; cela ne mesure pas FRP.',
                'no_permissions':'ADB signale un refus d’accès USB. Vérifier permissions/ACL et restrictions de l’hôte.',
                'offline':'Transport ADB hors ligne ; accès opérationnel non établi.',
                'device':'Transport ADB device annoncé ; aucun shell ou accès utilisateur essayé.',
                'recovery':'Transport Recovery annoncé ; association physique détaillée séparément.',
                'sideload':'Transport sideload limité annoncé ; aucun paquet envoyé.'}.get(state,'État ADB observé.'))
    elif 'smartsocket' in adb_error or 'daemon' in adb_error:
        add('serveur_adb_indisponible', 'Échec du serveur local ADB avant de pouvoir évaluer le téléphone. '
            'Comparer avec Ubuntu normal ; ne pas attribuer cet échec à FRP.', returncode=adb.get('returncode'))
    else:
        add('adb_echec', 'Commande ADB en échec ou indisponible ; aucune liste exploitable.',returncode=adb.get('returncode'))
    if not live['mtp']['session_query_success']:
        add('mtp_vue_incomplete', 'Vue GIO indisponible ou partielle. Aucun montage observé ici ne prouve pas son absence dans la session Ubuntu.')
    if any(m['root_metadata_accessible'] for m in live['mtp_metadata']):
        add('mtp_metadonnees_seulement', 'Attributs de racine MTP obtenus ; aucun accès aux données ou fichiers utilisateur démontré.')
    elif any(d['mtp_mount_announced'] for d in live['devices']):
        add('mtp_metadonnees_non_etablies', 'Montage MTP annoncé mais lecture des attributs de racine non établie ou omise ; aucun démontage automatique.')
    add('donnees_non_testees', 'Aucun fichier utilisateur lu ou listé. USB, ADB et FRP sont des diagnostics distincts.')
    return items


def prepare(root=ROOT, *, label='local', timeout=15, probe_adb=True, probe_mtp=True,
            sysfs=Path('/sys/bus/usb/devices'), runner=run_command, environment_reader=environment):
    root = Path(root)
    before = inventory(root)
    start = utc()
    context = environment_reader()
    live = v20.collect(sysfs, runner, timeout, probe_adb, probe_mtp)
    guide, evidence = v20.history(root)
    # V20 conservé ; V21 ne propage pas ses associations si plusieurs séries sont ambiguës.
    associations = associate(live)
    for device in live['devices']:
        device['adb_states'] = [a['state'] for a in associations if a['port'] == device['port']]
        device['recovery_transport_observed'] = any(s in ('sideload', 'recovery') for s in device['adb_states'])
    live['unassociated_adb_count'] = sum(a['port'] is None for a in associations)
    nodes = [node_evidence(d) for d in live['usb']['devices']]
    return {'version': 21, 'started_at': start, 'finished_at': utc(), 'label': label,
            'label_is_user_declared': True, 'script_sha256': digest(Path(__file__)), 'parameters': {'timeout_seconds': timeout, 'probe_adb': probe_adb, 'probe_mtp': probe_mtp},
            'environment': context, 'live': live, 'node_evidence': nodes, 'adb_associations': associations,
            'findings': findings(live, context, nodes, associations),
            'phone_data_access': 'non_teste', 'confirmation': guide['confirmation'],
            'historical_evidence': evidence, 'official_assistant': guide['sections'],
            'property_drafts': guide['drafts'], 'sources_checked_on': google.SOURCE_DATE,
            'sources': google.SOURCES, 'limits': LIMITS,
            'preservation': verify_inventory(root, before)}


def safe_environment(context):
    loop = context['loopback_listener']
    return {'process_restrictions': {k: v for k, v in context['process_restrictions'].items()
            if k in ('NoNewPrivs', 'Seccomp', 'Seccomp_filters') and type(v) is int},
            'process_status': 'lu' if context['process_status'] == 'lu' else 'indisponible',
            'loopback_listener': {'status': loop['status'] if loop['status'] in ('ok', 'refuse', 'erreur') else 'inconnu',
                                  'stage': loop['stage'] if loop['stage'] in ('creation', 'bind_loopback', 'listen_loopback', 'termine') else 'inconnu',
                                  'errno': loop.get('errno') if type(loop.get('errno')) is int else None},
            'dbus_session_address_present': bool(context['dbus_session_address_present']),
            'runtime_dir_present': bool(context['runtime_dir_present'])}


def share(report):
    """Projection par liste blanche : jamais de nettoyage optimiste des sorties brutes."""
    live = report['live']
    aliases = {d['port']: f'Samsung-{i}' for i, d in enumerate(live['usb']['devices'], 1)}
    devices = []
    for d, summary, node in zip(live['usb']['devices'], live['devices'], report['node_evidence']):
        interfaces = [{k: i.get(k) for k in ('bInterfaceClass', 'bInterfaceSubClass', 'bInterfaceProtocol')}
                      for i in d['interfaces']]
        # Les champs numériques USB sont eux aussi validés, pas copiés arbitrairement.
        for interface in interfaces:
            for k, value in interface.items():
                interface[k] = value if isinstance(value, str) and re.fullmatch('[0-9a-fA-F]{2}', value) else None
        devices.append({'device': aliases[d['port']], 'hardware_identifiers': '[MASQUÉS]',
                        'vendor_id': '04e8', 'product_id': d.get('product_id') if re.fullmatch('[0-9a-fA-F]{4}', d.get('product_id') or '') else None,
                        'interfaces': interfaces, 'usb_node': {k: node.get(k) for k in ('status', 'read_access', 'write_access')},
                        'adb_states': summary['adb_states'],
                        'mtp_interface_announced': summary['mtp_interface_announced'],
                        'mtp_mount_announced': summary['mtp_mount_announced'],
                        'mtp_root_metadata_accessible': summary['mtp_root_metadata_accessible'],
                        'recovery_transport_observed': summary['recovery_transport_observed']})
    counts = {str(v): sum(e.get('analysis', {}).get('version') == v for e in report['historical_evidence']) for v in (17,18,19)}
    return {'version': 21, 'visibility': 'partage', 'redaction': 'liste blanche ; aucun stdout/stderr, URI, série, chemin utilisateur, UID/GID ou empreinte de rapport privé',
            'started_at': report['started_at'], 'finished_at': report['finished_at'],
            'label': report['label'] if report['label'] in LABELS else 'non_precise',
            'label_is_user_declared': True, 'environment': safe_environment(report['environment']),
            'devices': devices, 'adb_unassociated_count': live['unassociated_adb_count'],
            'adb_associations': [{'state': a['state'], 'device': aliases.get(a['port']), 'basis': a['basis']} for a in report['adb_associations']],
            'probes': [{k: p.get(k) for k in ('id', 'status', 'returncode', 'timed_out', 'duration_seconds')} for p in live['probes']],
            'findings': findings(live, report['environment'], report['node_evidence'], report['adb_associations']), 'phone_data_access': 'non_teste',
            'confirmation': {'google_screen_confirmed_by_user': report['confirmation'].get('confirmed_by_user') is True
                             and report['confirmation'].get('screen_text') == 'Vérifier votre compte Google',
                             'source': 'Déclaration utilisateur V19 historique ; aucune nouvelle lecture d’écran'},
            'history': {'report_counts': counts, 'analysis_errors': sum('analysis_error' in e for e in report['historical_evidence'])},
            'preservation': {'files_checked': report['preservation']['files_checked'],
                             'changed_or_missing_count': len(report['preservation']['changed_or_missing'])},
            'official_assistant': google.SECTIONS, 'sources_checked_on': google.SOURCE_DATE,
            'sources': google.SOURCES, 'limits': LIMITS}


def text_report(report):
    lines = ['PRÉVOST SAMSUNG V21 — DIAGNOSTIC', 'Version : ' + report.get('visibility', 'privée locale'),
             'Une détection USB ne prouve aucun accès aux données du téléphone.', '\nCONSTATS']
    lines.extend('- ' + item['message'] for item in report['findings'])
    lines.extend(['\nDÉTAILS VÉRIFIABLES', json.dumps(report, ensure_ascii=False, indent=2)])
    return '\n'.join(lines) + '\n'


def write_private(path, content):
    with path.open('x', encoding='utf-8') as stream:
        path.chmod(0o600)
        stream.write(content)


def save(report, root=ROOT):
    base = Path(root) / 'rapports/v21'
    base.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='diagnostic-', dir=base))
    public = out / 'partage'
    public.mkdir(mode=0o700)
    shared = share(report)
    files = {'rapport-prive.json': json.dumps(report, ensure_ascii=False, indent=2)+'\n',
             'rapport-prive.txt': text_report(report),
             'partage/rapport.json': json.dumps(shared, ensure_ascii=False, indent=2)+'\n',
             'partage/rapport.txt': text_report(shared)}
    files.update({'partage/demande-' + k + '.txt': v for k,v in google.DRAFTS.items()})
    for name, content in files.items():
        write_private(out/name, content)
    public_files = [p for p in sorted(public.iterdir()) if p.is_file()]
    write_private(public/'SHA256SUMS', ''.join(digest(p)+'  '+p.name+'\n' for p in public_files))
    archive = out/'partage.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(public.iterdir()):
            z.write(p,p.name)
    archive.chmod(0o600)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise OSError('Archive partage invalide')
    hashes = [out/name for name in files] + [public/'SHA256SUMS', archive]
    write_private(out/'SHA256SUMS',''.join(digest(p)+'  '+str(p.relative_to(out))+'\n' for p in hashes))
    return out


def latest(root=ROOT):
    paths = list((Path(root)/'rapports/v21').glob('diagnostic-*/rapport-prive.json'))
    return max(paths,key=lambda p:p.stat().st_mtime_ns) if paths else None


def run(root=ROOT, *, report_only=False, private=False, label='local', timeout=15, probe_adb=True, probe_mtp=True):
    from prevost_v16.__main__ import show
    show('PRÉVOST — DIAGNOSTIC SAMSUNG V21','red')
    if report_only:
        path = latest(root)
        if path is None:
            show('Aucun rapport V21. Exécuter ./prevost-samsung diagnostic-v21.','yellow')
            return 1
        selected = path.parent/('rapport-prive.txt' if private else 'partage/rapport.txt')
        show(selected.read_text(encoding='utf-8'),'sky')
        return 0
    show('Sondes en lecture : USB, ADB, GIO ; contexte de permissions et listener loopback temporaire.','yellow')
    report = prepare(root,label=label,timeout=timeout,probe_adb=probe_adb,probe_mtp=probe_mtp)
    out = save(report,root)
    view = report if private else share(report)
    show(text_report(view),'sky')
    show('Dossier local privé : '+str(out),'white')
    show('Seule l’archive partage.zip est destinée au partage ; rapports privés à conserver localement.','yellow')
    return 0
