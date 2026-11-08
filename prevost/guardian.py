"""Diagnostic et veille du PC courant ; aucune découverte réseau ni correction."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

from .app import UI

CHECKS = {
    'services': ['systemctl', '--user', '--failed', '--no-legend', '--plain', '--no-pager'],
    'services_systeme': ['systemctl', '--system', '--failed', '--no-legend', '--plain', '--no-pager'],
    'ports': ['ss', '-H', '-lntu'],
    'mises_a_jour': ['apt', 'list', '--upgradable'],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def probe(argv, timeout=8):
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, errors='replace', timeout=timeout,
            env={**os.environ, 'LC_ALL': 'C', 'SYSTEMD_COLORS': '0', 'SYSTEMD_PAGER': 'cat'})
        blocked = any(term in result.stderr.lower() for term in (
            'operation not permitted', 'permission denied', 'cannot open', 'failed to connect'))
        return {'status': 'observe' if result.returncode == 0 and not blocked else 'indisponible',
                'commande': argv, 'code': result.returncode,
                'sortie': result.stdout[:100000], 'erreur': result.stderr[:10000]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'status': 'indisponible', 'commande': argv, 'erreur': str(error), 'sortie': ''}


def collect(run=probe, disk=shutil.disk_usage):
    checks = {}
    try:
        usage = disk('/')
        checks['disque'] = {'status': 'observe', 'source': 'statvfs via shutil.disk_usage(/)',
            'total': usage.total, 'libre': usage.free,
            'pourcentage_libre': round(usage.free / usage.total * 100, 1)}
    except OSError as error:
        checks['disque'] = {'status': 'indisponible', 'erreur': str(error)}
    for name, argv in CHECKS.items():
        checks[name] = run(argv)
    return {'date': now(), 'appareil': {'id': 'pc-local', 'nom': platform.node(),
        'systeme': platform.system(), 'perimetre': 'PC courant seulement',
        'autorise': ['diagnostic local en lecture seule', 'veille locale explicite'],
        'reseaux_voisins': 'non autorisés, non explorés'}, 'controles': checks,
        'limites': ['Vue du processus courant : un bac à sable peut masquer les informations de l’hôte.',
            'Ports TCP/UDP en écoute dans cet espace réseau ; aucun scan ni preuve d’exposition Internet.',
            'Services : unités échouées seulement, pas de vérification de tous les services attendus.',
            'Mises à jour : métadonnées APT existantes, sans rafraîchissement ni installation.',
            'Disque : partition racine seulement ; aucun diagnostic SMART.',
            'Aucune mesure de protection ni surveillance hors des exécutions explicites.']}


def canonical(name, check):
    if check['status'] != 'observe':
        return {'status': 'indisponible', 'erreur': check.get('erreur', '')}
    if name == 'disque':
        return {'status': 'observe', 'espace_faible': check['pourcentage_libre'] < 10}
    lines = check.get('sortie', '').splitlines()
    if name == 'mises_a_jour':
        lines = [line for line in lines if '/' in line and not line.startswith('Listing')]
    return {'status': 'observe', 'lignes': sorted(line.strip() for line in lines if line.strip())}


def recommendations(report):
    result = []
    for name, check in report['controles'].items():
        item = {'controle': name, 'preuve': check, 'confiance': 'élevée sur le résultat de collecte, limitée sur l’état réel du PC',
                'retour_arriere': 'Aucun changement système effectué ; aucune restauration nécessaire.'}
        if check['status'] != 'observe':
            item.update(nature='observe', constat='Collecte indisponible ; santé inconnue.',
                recommandation='Relancer ce diagnostic depuis le terminal LexOS ; examiner l’erreur sans modifier les permissions automatiquement.')
        elif name == 'disque' and check['pourcentage_libre'] < 10:
            item.update(nature='observe', constat='Moins de 10 % d’espace libre sur /.',
                recommandation='Examiner les fichiers volumineux et préparer une sauvegarde avant toute suppression confirmée.')
        elif name.startswith('services') and check['sortie'].strip():
            item.update(nature='a_verifier', constat='Des unités sont signalées en échec par systemd.',
                recommandation='Lire les journaux des unités concernées ; ne pas redémarrer sans diagnostic et confirmation.')
        elif name == 'mises_a_jour' and canonical(name, check)['lignes']:
            item.update(nature='observe', constat='Des mises à jour figurent dans le cache APT local.',
                recommandation='Vérifier la fraîcheur du cache et préparer sauvegarde ou instantané avant toute mise à jour confirmée.')
        elif name == 'ports':
            item.update(nature='observe', constat='Inventaire local des ports collecté ; leur légitimité reste à vérifier.',
                recommandation='Comparer les adresses et ports avec les services attendus. Aucun port n’est déclaré vulnérable sur cette seule preuve.')
        else:
            continue
        result.append(item)
    return result


class Watch:
    def __init__(self, directory):
        self.directory = Path(directory).expanduser()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.state = self.directory/'watch.json'
        self.journal = self.directory/'incidents.jsonl'

    def event(self, entry):
        with self.journal.open('a', encoding='utf-8') as stream:
            os.chmod(self.journal, 0o600)
            stream.write(json.dumps({'date': now(), **entry}, ensure_ascii=False) + '\n')

    def update(self, report):
        old = json.loads(self.state.read_text()) if self.state.exists() else {'checks': {}, 'seen': []}
        current = {name: canonical(name, check) for name, check in report['controles'].items()}
        seen = set(old['seen'])
        alerts = []
        for name, value in current.items():
            changed = name in old['checks'] and old['checks'][name] != value
            initial_problem = not old['checks'] and (value['status'] == 'indisponible' or
                value.get('espace_faible') or (name.startswith('services') and value.get('lignes')))
            if changed or initial_problem:
                fingerprint = hashlib.sha256(json.dumps([name, value], sort_keys=True).encode()).hexdigest()
                if fingerprint not in seen:
                    alert = {'type': 'alerte', 'controle': name, 'id': fingerprint,
                        'constat': 'Changement observé' if changed else 'Collecte indisponible ou anomalie initiale',
                        'preuve': report['controles'][name], 'confiance': 'élevée sur la différence collectée ; cause non vérifiée',
                        'action': 'Aucune correction exécutée', 'retour_arriere': 'Sans objet : collecte en lecture seule.'}
                    alerts.append(alert)
                    self.event(alert)
                    seen.add(fingerprint)
        self.event({'type': 'collecte', 'action': 'diagnostic en lecture seule', 'date_collecte': report['date'],
                    'etats': {name: item['status'] for name, item in current.items()}})
        temporary = self.directory/'watch.tmp'
        temporary.write_text(json.dumps({'checks': current, 'seen': sorted(seen), 'dernier_rapport': report}, ensure_ascii=False), encoding='utf-8')
        os.chmod(temporary, 0o600)
        temporary.replace(self.state)
        return alerts


def main(argv=None):
    parser = argparse.ArgumentParser(description='Gardien PRÉVOST : PC local, lecture seule')
    parser.add_argument('mode', choices=['diagnostic', 'veille'])
    parser.add_argument('--json', action='store_true', help='Diagnostic structuré')
    parser.add_argument('--interval', type=float, default=60)
    parser.add_argument('--cycles', type=int, default=1, help='Nombre de collectes ; 0 pour continuer jusqu’à Ctrl+C')
    parser.add_argument('--state-dir', default=str(Path.home()/'.local/share/prevost-ia-local/guardian'))
    args = parser.parse_args(argv)
    if args.interval < 1 or args.cycles < 0:
        parser.error('Intervalle >= 1 seconde et cycles >= 0 requis.')
    ui = UI()
    watch = Watch(args.state_dir) if args.mode == 'veille' else None
    cycle = 0
    try:
        while True:
            report = collect()
            report['recommandations'] = recommendations(report)
            if watch:
                report['alertes'] = watch.update(report)
                report['veille'] = 'Collecte ponctuelle terminée ; prochaine collecte seulement si le processus reste actif.'
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(ui.paint('41;97', ' PRÉVOST — SANTÉ DU PC LOCAL '))
                ui.show(f"Collecte : {report['date']} — {report['appareil']['nom']}")
                for name, check in report['controles'].items():
                    ui.show(f"\n{name} : {check['status']}")
                    if 'commande' in check:
                        ui.show('Preuve : ' + ' '.join(check['commande']))
                        lines = check.get('sortie', '').splitlines()
                        ui.show('\n'.join(lines[:12]))
                        if len(lines) > 12:
                            ui.show(f'{len(lines)} lignes collectées ; utiliser --json pour la preuve complète.')
                        if check.get('erreur'):
                            ui.show(check['erreur'])
                    else:
                        ui.show(json.dumps(check, ensure_ascii=False))
                for item in report['recommandations']:
                    ui.show(f"\n{item['nature']} — {item['constat']}\n{item['recommandation']}\nConfiance : {item['confiance']}\nRetour arrière : {item['retour_arriere']}")
                if watch:
                    ui.show(f"Alertes nouvelles : {len(report['alertes'])} — journal : {watch.journal}")
                    for alert in report['alertes']:
                        ui.show(f"ALERTE {alert['controle']} : {alert['constat']}")
                ui.show('\nLimites :\n' + '\n'.join(report['limites']))
            cycle += 1
            if not watch or (args.cycles and cycle >= args.cycles):
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        ui.show('Veille arrêtée. PRÉVOST ne surveille plus ce PC.')
    except (OSError, ValueError, KeyError) as error:
        ui.show('Diagnostic ou veille interrompu : ' + str(error))
        return 1
    finally:
        if ui.color:
            print('\033[0m', end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
