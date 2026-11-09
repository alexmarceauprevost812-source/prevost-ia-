"""Préparation locale de la récupération officielle ; aucune communication téléphone ou compte."""
import json
from pathlib import Path
import re
import tempfile
from outils.v17.diagnostic_environnement import digest, inventory, utc, verify_inventory
from prevost_v16.core import parse_adb

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DATE = '2026-11-09'
SOURCES = {
    'google_recovery': 'https://support.google.com/accounts/answer/7682439?hl=fr',
    'google_tips': 'https://support.google.com/accounts/answer/7299973?hl=fr',
    'google_delay': 'https://support.google.com/accounts/answer/9412469?hl=fr',
    'google_protection': 'https://support.google.com/android/answer/9459346?hl=fr',
    'samsung_frp': 'https://www.samsung.com/ca/support/mobile-devices/perform-a-factory-reset-on-samsung-galaxy-device/',
    'samsung_ownership': 'https://www.samsung.com/us/support/answer/ANS10003349/',
    'samsung_centres': 'https://www.samsung.com/ca/support/service-center/',
    'bell_repairs': 'https://support.bell.ca/mobility/Using_my_device/Repairs',
    'bell_bills': 'https://support.bell.ca/billing-and-accounts/billing/how_to_download_or_print_my_bill',
    'bell_contact': 'https://support.bell.ca/Contact-Us',
    'smart_switch': 'https://www.samsung.com/ca/apps/smart-switch/',
    'emergency': 'https://update.kies.samsung.com/SmartSwitchPC_recovery_guide/firmware/emergencyrecovery/',
    'model_updates': 'https://doc.samsungmobile.com/SM-G990W2/023358220727/eng.html',
}

SECTIONS = {
    'google': '''1. Sur un autre appareil, ouvrir personnellement https://accounts.google.com/signin/recovery
   pour récupérer le compte déjà ajouté et synchronisé sur ce téléphone avant sa réinitialisation.
   Si l’adresse est oubliée : https://accounts.google.com/signin/usernamerecovery ; Google
   demande un moyen de récupération et le nom du compte. Ne rien saisir dans PRÉVOST.
2. Utiliser si possible l’appareil, le navigateur et le lieu habituels. Répondre aux questions
   directement sur accounts.google.com ; choisir une autre méthode si Google la propose.
3. Respecter les délais réellement affichés. Un délai de récupération peut durer des heures
   ou des jours ; une modification des informations de récupération peut prendre jusqu’à
   sept jours. Aucun délai universel de déblocage du téléphone n’est garanti ici.
4. Retrouver l’accès au compte sur l’autre appareil est la première étape. Une future validation
   sur le téléphone sera effectuée personnellement par le propriétaire, hors de cette mission
   sans changement téléphone. Un nouveau compte Google ne remplace pas un compte antérieurement
   synchronisé exigé par la protection. Un compte Samsung ne remplace pas ce compte Google.
5. Si un tiers est titulaire du compte antérieur, lui demander de suivre lui-même la démarche
   officielle ou de contacter Samsung ; ne pas demander son mot de passe. Aucun essai automatisé.

Sources :
''' + '\n'.join(SOURCES[k] for k in ('google_recovery', 'google_tips', 'google_delay', 'google_protection')),
    'samsung': '''Préparer un dossier à remettre soi-même au centre agréé : preuve d’achat d’origine ou
   duplicata/contrat, modèle SM-G990W2, IMEI ou série provenant de la boîte ou des documents,
   et pièce d’identité si le centre la demande. La liste exacte des pièces et leur acceptation
   doivent être confirmées par le centre ; une boîte seule n’est pas une preuve suffisante garantie.
Ne pas déposer ces pièces ni ces identifiants dans PRÉVOST. Faire vérifier la correspondance
   appareil/document uniquement au prestataire officiel.
Demander au centre canadien : prise en charge de ce modèle et de la vérification Google,
   justificatifs acceptés, éventuels frais et possibilités de conservation des données.
   La recommandation Samsung de présenter une preuve d’achat ne garantit pas un déverrouillage.
Préciser : diagnostic et vérification de propriété uniquement à ce stade ; aucun effacement,
   flash, remplacement ou modification du téléphone autorisé par cette mission.

Sources :
''' + '\n'.join(SOURCES[k] for k in ('samsung_frp', 'samsung_ownership', 'samsung_centres')),
    'bell': '''Si l’appareil a été acheté chez Bell, consulter personnellement MonBell pour les factures
   disponibles et demander une preuve d’achat de l’appareil ou un duplicata de contrat si nécessaire.
   Une facture de service mobile seule ne prouve pas nécessairement l’achat de cet appareil.
Le guide Bell permet de télécharger/imprimer les factures et décrit un historique de 18 mois.
   Pour un achat plus ancien ou un compte fermé, demander au soutien la disponibilité d’archives,
   les conditions, frais éventuels et vérifications d’identité : aucun duplicata n’est garanti.
Le service de réparation Bell indique un compte actif et un titulaire/utilisateur autorisé.
   Si ces conditions ne sont pas remplies, demander les possibilités de preuve d’achat et
   d’orientation vers Samsung ; ne pas présumer l’admissibilité à une réparation Bell.
Demander une référence de dossier et une orientation officielle. Bell ne récupère pas le mot
   de passe Google. Garder tout secret pour la saisie personnelle dans le service officiel.

Sources :
''' + '\n'.join(SOURCES[k] for k in ('bell_bills', 'bell_repairs', 'bell_contact')),
    'android': '''La documentation Samsung SM-G990W2 consultée publie G990W2VLSNIZI2, Android 16,
   le 23 octobre 2026, correctif du 5 octobre 2026. Elle ne prouve ni la version installée,
   ni la disponibilité d’un paquet BMC, ni la compatibilité du bootloader de cet appareil.
Smart Switch Windows/Mac propose les mises à jour disponibles pour les appareils compatibles.
   La récupération d’urgence officielle concerne notamment un échec de mise à jour reconnu ;
   sa disponibilité pour ce téléphone reste à confirmer auprès de Samsung.
L’écran Google signalé n’établit pas une corruption d’Android. La restauration logicielle
   n’est pas une solution démontrée à la vérification du compte. Aucun outil de restauration
   n’est lancé ; aucune garantie de conservation des données n’est établie pour une intervention.
   L’effacement et le flash restent exclus. Aucun paquet firmware téléchargé.

Sources :
''' + '\n'.join(SOURCES[k] for k in ('model_updates', 'smart_switch', 'emergency', 'samsung_frp')),
}

DRAFTS = {
    'samsung': '''Objet : SM-G990W2 — vérification Google et preuve de propriété

Bonjour,
Mon Samsung Galaxy S21 FE 5G (SM-G990W2) affiche « Vérifier votre compte Google ».
Je souhaite préparer sa remise en service par les voies officielles.
Quels justificatifs de propriété acceptez-vous et pouvez-vous examiner ce modèle au Canada ?
Je peux présenter personnellement les documents disponibles via votre canal officiel.
Merci de préciser les frais éventuels, les possibilités de conservation des données et les limites
   de votre intervention. Ma demande actuelle porte sur le diagnostic et la vérification de propriété ;
   aucun effacement, flash ou changement sur le téléphone n’est autorisé à ce stade.
Merci de me donner une référence de dossier et les prochaines démarches.
''',
    'bell': '''Objet : SM-G990W2 — demande de preuve d’achat et orientation Samsung

Bonjour,
Mon Samsung Galaxy S21 FE 5G (SM-G990W2) affiche « Vérifier votre compte Google ».
Si votre dossier confirme un achat chez Bell, pouvez-vous indiquer comment obtenir un duplicata
   de preuve d’achat ou de contrat permettant de rattacher l’appareil à son achat ?
Merci de préciser les justificatifs, conditions d’accès aux archives, frais éventuels et modalités
   si le compte est fermé. Si une prise en charge Bell n’est pas possible, pouvez-vous m’orienter
   vers un centre Samsung agréé ? Je ne demande pas de récupération de mot de passe Google.
Aucun effacement, flash ou changement sur le téléphone n’est autorisé à ce stade.
Merci de me donner une référence de dossier. Je fournirai les informations personnelles nécessaires
   directement dans votre canal officiel, sans passer par l’outil PRÉVOST.
''',
}


def confirmation(root):
    path = root / 'outils/v19/confirmation_utilisateur.json'
    if not path.is_file():
        return {'confirmed_by_user': False, 'source': 'confirmation utilisateur absente de cette copie'}
    return json.loads(path.read_text(encoding='utf-8'))


def analyze(path, version):
    """Restituer seulement les faits utiles, sans série USB ni sorties personnelles brutes."""
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Rapport JSON non structuré en objet')
    probes = {p['id']: p for p in data.get('tests' if version == 17 else 'probes', [])}
    adb = probes.get('adb_devices' if version == 17 else 'adb', {})
    states = [d['state'] for d in parse_adb(adb.get('stdout', ''))] if adb.get('returncode') == 0 else []
    result = {'version': version, 'label': data.get('label'), 'observed_at': data.get('started_at'),
              'adb_returncode': adb.get('returncode'), 'adb_states': states,
              'adb_list_empty': adb.get('returncode') == 0 and not states}
    if version == 17:
        result.update(usb_returncode=probes.get('usb_samsung', {}).get('returncode'),
                      bmc_http_statuses=re.findall(r'HTTP/\S+\s+(\d{3})', probes.get('http_metadata_3', {}).get('stdout', '')),
                      dns_returncodes={k: v.get('returncode') for k, v in probes.items() if k.startswith('dns_')})
    else:
        result.update(usb_ids=[d.get('vendor_id', '') + ':' + d.get('product_id', '')
                               for d in data.get('usb', {}).get('devices', [])],
                      mtp_mount_announced='mtp://' in probes.get('mtp_mounts', {}).get('stdout', ''),
                      mtp_metadata_status=probes.get('mtp_metadata', {}).get('status'),
                      historical_mode=data.get('findings', {}).get('mode'))
    return result


def prepare(root=ROOT):
    root = Path(root)
    before = inventory(root)
    evidence = []
    for version, pattern in ((17, 'environnement-*.json'), (18, 'recovery-*.json')):
        for path in sorted((root / f'rapports/v{version}').glob(pattern)):
            item = {'path': str(path.relative_to(root)), 'sha256': digest(path)}
            try:
                item['analysis'] = analyze(path, version)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                item['analysis_error'] = type(exc).__name__
            evidence.append(item)
    case = confirmation(root)
    return {'version': 19, 'created_at': utc(), 'confirmation': case,
            'conclusion': 'Écran de vérification Google confirmé visuellement par l’utilisateur ; '
                          'situation compatible avec la protection FRP pendant la configuration Android. '
                          'Aucun drapeau système FRP mesuré.' if case.get('confirmed_by_user') is True else
                          'Confirmation utilisateur non enregistrée ; ne pas présumer un état FRP.',
            'limits': 'Observation utilisateur distincte des sondes USB/ADB. Aucun mode Recovery ou Download '
                      'actuel démontré. Les mesures V17/V18 sont historiques. Aucun nouveau diagnostic téléphone.',
            'evidence': evidence, 'source_checked_on': SOURCE_DATE, 'sources': SOURCES,
            'sections': SECTIONS, 'drafts': DRAFTS,
            'preservation': verify_inventory(root, before)}


def render(report, section='tout'):
    case = report['confirmation']
    text = '# PRÉVOST V19 — Récupération Google FRP\n\n'
    text += report['conclusion'] + '\n\n' + report['limits'] + '\n\n'
    text += 'Confirmation : ' + json.dumps(case, ensure_ascii=False, indent=2) + '\n\n'
    for key, content in report['sections'].items():
        if section in ('tout', key):
            text += '## ' + key.capitalize() + '\n\n' + content + '\n\n'
    if section == 'tout':
        text += '## Analyse des rapports antérieurs\n\n'
        text += json.dumps(report['evidence'], ensure_ascii=False, indent=2) + '\n\n'
        text += '## Conservation\n\n' + json.dumps(report['preservation'], ensure_ascii=False, indent=2) + '\n'
    text += '\nSources vérifiées le ' + report['source_checked_on'] + ' via outil web indépendant. '
    text += 'Ce menu reste hors ligne et ne revalide pas ces pages à chaque lancement.\n'
    return text


def save(report, root=ROOT):
    directory = Path(root) / 'rapports/v19'
    directory.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='dossier-', dir=directory))
    files = {'rapport.json': json.dumps(report, ensure_ascii=False, indent=2) + '\n',
             'rapport.md': render(report)}
    files.update({'brouillon-' + key + '.txt': value for key, value in report['drafts'].items()})
    for name, value in files.items():
        with (out / name).open('x', encoding='utf-8') as stream:
            stream.write(value)
    with (out / 'SHA256SUMS').open('x', encoding='utf-8') as stream:
        stream.write(''.join(digest(out / name) + '  ' + name + '\n' for name in files))
    return out


def run(root=ROOT, section='tout'):
    report = prepare(root)
    out = save(report, root)
    print(render(report, section))
    print('Dossier local (rapport complet et brouillons non envoyés) : ' + str(out))
    return out
