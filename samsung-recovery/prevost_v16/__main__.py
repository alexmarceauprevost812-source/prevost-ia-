"""Interface terminal et commandes directes partageant les mêmes sondes."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from .core import Diagnostics, Store, now

LABELS = ['Diagnostic Samsung', 'Détection USB / MTP', 'Diagnostic ADB',
          'Diagnostic Recovery', 'Vérification des informations accessibles',
          'Historique des connexions', 'Rapports techniques', 'Export ZIP / SHA256',
          'Diagnostic Recovery V18 (USB / MTP / ADB)', 'Récupération Google FRP', 'Assistant récupération Samsung V20', 'DIAGNOSTIC SAMSUNG V21']


def paint(text, color='white'):
    if not sys.stdout.isatty() or os.environ.get('NO_COLOR') is not None:
        return text
    colors = {'red': 31, 'white': 97, 'yellow': 93, 'sky': '38;2;135;206;235'}
    return f'\033[40;{colors[color]}m{text}\033[0m'


def show(obj, color='white'):
    print(paint(json.dumps(obj, ensure_ascii=False, indent=2) if not isinstance(obj, str) else obj, color))


def execute(command, store, serial=None, recovery_options=None, google_section='tout', recuperation_options=None, v21_options=None):
    if command == 'diagnostic-v21':
        from outils.v21.diagnostic import run
        return run(store.root, **(v21_options or {}))
    if command == 'recuperation':
        from outils.v20.recuperation import run
        return run(store.root, section=google_section, **(recuperation_options or {}))
    if command == 'google-frp':
        from outils.v19.recuperation_google import run
        run(store.root, section=google_section)
        return
    if command == 'recovery-v18':
        from outils.v18.diagnostic_recovery import main as recovery_main
        recovery_main(recovery_options or ['--label', 'local'])
        return
    if command == 'historique':
        show(store.history())
    elif command == 'rapport':
        from outils.v21.diagnostic import latest as latest_v21
        v21_report = latest_v21(store.root)
        if v21_report:
            show((v21_report.parent / 'partage/rapport.txt').read_text(encoding='utf-8'), 'sky')
        from outils.v20.recuperation import latest
        v20_report = latest(store.root)
        if v20_report:
            show(v20_report.with_suffix('.txt').read_text(encoding='utf-8'), 'sky')
        v19_reports = sorted((store.root / 'rapports/v19').glob('dossier-*/rapport.md'), key=lambda p: p.stat().st_mtime_ns)
        if v19_reports:
            show(v19_reports[-1].read_text(encoding='utf-8'))
            show('Dossier V19 : ' + str(v19_reports[-1].parent))
        v18_reports = sorted((store.root / 'rapports/v18').glob('recovery-*.txt'), key=lambda p: p.stat().st_mtime_ns)
        if v18_reports:
            show(v18_reports[-1].read_text(encoding='utf-8'))
            show('Dossier V18 : ' + str(store.root / 'rapports/v18'))
        reports = store.reports()
        if reports:
            show(reports[-1].with_suffix('.txt').read_text(encoding='utf-8'))
            show('Rapports JSON :\n' + '\n'.join(map(str, reports)))
        elif not v18_reports and not v19_reports and not v20_report and not v21_report:
            show('Aucun rapport. Exécutez diagnostic ou recovery-v18.')
    elif command == 'export':
        archive, checksum = store.export()
        show(f'Archive vérifiée : {archive}\nSHA256 : {checksum}')
    else:
        report = Diagnostics().run(serial)
        path = store.save(report)
        sections = {'detect': ['usb', 'identification'], 'usb': ['usb'], 'mtp': ['usb', 'mtp'],
                    'adb': ['adb', 'android'], 'recovery': ['recovery'],
                    'informations': ['android', 'frp_setup']}
        keys = sections.get(command)
        show({k: report[k] for k in keys} if keys else report,
             'sky' if command in ('usb', 'mtp', 'detect') else 'white')
        show(f'Rapports TXT / JSON enregistrés : {path}')


def tui(store, serial=None, recovery_options=None, google_section='tout', recuperation_options=None, v21_options=None):
    commands = ['diagnostic', 'mtp', 'adb', 'recovery', 'informations', 'historique', 'rapport', 'export', 'recovery-v18', 'google-frp', 'recuperation', 'diagnostic-v21']
    while True:
        print(paint('\nPRÉVOST SAMSUNG RECOVERY V21 — LexOS', 'red'))
        for number, label in enumerate(LABELS, 1):
            print(paint(f'{number}. ', 'yellow') + paint(label))
        print(paint('0. Quitter', 'yellow'))
        try:
            answer = input('> ').strip()
        except EOFError:
            return
        if answer == '0':
            return
        if answer not in tuple(str(i) for i in range(1, len(commands) + 1)):
            show('Choix invalide.', 'red')
            continue
        try:
            if commands[int(answer) - 1] == 'diagnostic-v21':
                execute('diagnostic-v21', store, v21_options=v21_options)
            elif commands[int(answer) - 1] == 'recuperation':
                execute('recuperation', store, google_section=google_section, recuperation_options=recuperation_options)
            elif commands[int(answer) - 1] == 'google-frp':
                execute('google-frp', store, serial, google_section=google_section)
            elif recovery_options:
                execute(commands[int(answer) - 1], store, serial, recovery_options)
            else:
                execute(commands[int(answer) - 1], store, serial)
        except (OSError, ValueError) as exc:
            log_error(store, exc)
            show('Erreur locale : ' + str(exc), 'red')


def log_error(store, exc):
    try:
        store.directory.mkdir(parents=True, exist_ok=True)
        store.append('erreurs.jsonl', {'time': now(), 'operation': 'application',
                                     'status': type(exc).__name__, 'message': str(exc)})
    except OSError:
        print('Journal inaccessible.', file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description='PRÉVOST V21 — diagnostics Samsung en lecture seule')
    parser.add_argument('command', nargs='?', default='tui', choices=(
        'tui', 'detect', 'diagnostic', 'usb', 'adb', 'mtp', 'recovery', 'informations',
        'historique', 'rapport', 'export', 'recovery-v18', 'google-frp', 'recuperation', 'diagnostic-v21'))
    parser.add_argument('--serial', help='Cible ADB explicite ; obligatoire en cas d’ambiguïté')
    parser.add_argument('--watch', type=float, metavar='SECONDES',
                        help='Répéter un diagnostic en direct jusqu’à Ctrl+C (minimum 2 secondes)')
    parser.add_argument('--label', choices=('local', 'ubuntu', 'codex'), default='local', help='Environnement déclaré V18/V20/V21')
    parser.add_argument('--sans-mtp', action='store_true', help='V18/V20/V21 : omettre la session libmtp ou les métadonnées MTP')
    parser.add_argument('--sans-adb', action='store_true', help='V18/V20/V21 : omettre ADB')
    parser.add_argument('--delai', type=int, choices=range(1, 61), default=15, metavar='1..60', help='V18/V20/V21 : délai maximal par sonde')
    parser.add_argument('--section', choices=('tout', 'google', 'samsung', 'bell', 'android'),
                        default='tout', help='V19/V20 : partie du guide officiel à afficher ; dossier complet conservé')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--diagnostic', action='store_true', help='V20 : diagnostic et rapport, sans générer de demandes de propriété')
    mode.add_argument('--rapport', dest='report_only', action='store_true', help='V20/V21 : lire le dernier rapport sans lancer de sondes')
    privacy = parser.add_mutually_exclusive_group()
    privacy.add_argument('--prive', action='store_true', help='V21 : afficher les détails locaux sensibles')
    privacy.add_argument('--partage', action='store_true', help='V21 : afficher la version masquée (défaut)')
    args = parser.parse_args(argv)
    if args.diagnostic and args.command not in ('tui', 'recuperation'):
        parser.error('--diagnostic est réservé à recuperation ou au menu')
    if args.report_only and args.command not in ('tui', 'recuperation', 'diagnostic-v21'):
        parser.error('--rapport est réservé à recuperation, diagnostic-v21 ou au menu')
    if (args.prive or args.partage) and args.command not in ('tui', 'diagnostic-v21'):
        parser.error('--prive/--partage sont réservés à diagnostic-v21 ou au menu')
    if args.command in ('recuperation', 'diagnostic-v21') and args.serial:
        parser.error('V20 énumère les Samsung sans shell ; --serial reste réservé aux sondes V16')
    recuperation_options = {'diagnostic': args.diagnostic, 'report_only': args.report_only,
                            'label': args.label, 'timeout': args.delai,
                            'probe_adb': not args.sans_adb, 'probe_mtp': not args.sans_mtp}
    v21_options = {'report_only': args.report_only, 'private': args.prive, 'label': args.label,
                   'timeout': args.delai, 'probe_adb': not args.sans_adb, 'probe_mtp': not args.sans_mtp}
    recovery_options = ['--label', args.label, '--delai', str(args.delai)]
    if args.sans_mtp:
        recovery_options.append('--sans-mtp')
    if args.sans_adb:
        recovery_options.append('--sans-adb')
    if args.watch is not None and (not 2 <= args.watch <= 86400 or args.command in
                                  ('tui', 'historique', 'rapport', 'export', 'recovery-v18', 'google-frp', 'recuperation', 'diagnostic-v21')):
        parser.error('--watch exige une commande de diagnostic et un intervalle entre 2 et 86400 secondes')
    store = Store()
    try:
        if args.command == 'tui':
            tui(store, args.serial, recovery_options, args.section, recuperation_options, v21_options)
        else:
            while True:
                if args.command == 'diagnostic-v21':
                    return execute(args.command, store, v21_options=v21_options)
                elif args.command == 'recuperation':
                    return execute(args.command, store, google_section=args.section, recuperation_options=recuperation_options)
                elif args.command == 'google-frp':
                    execute(args.command, store, args.serial, google_section=args.section)
                elif args.command == 'recovery-v18':
                    execute(args.command, store, args.serial, recovery_options)
                else:
                    execute(args.command, store, args.serial)
                if args.watch is None:
                    break
                time.sleep(args.watch)
        return 0
    except KeyboardInterrupt:
        print('\nArrêt demandé.')
        return 130
    except (OSError, ValueError) as exc:
        log_error(store, exc)
        print('Erreur : ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
