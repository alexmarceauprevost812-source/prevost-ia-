"""Banc d'essai : quatre missions fixes pour comparer les modèles Ollama installés.

Exception documentée à la règle des confirmations : une seule confirmation « oui » exacte au départ
couvre toutes les écritures et exécutions de ce banc, dans un dossier temporaire jetable."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .app import Ollama, Project, UI, choose, code_mission


class QuietUI(UI):
    """Silencieuse ; confirme sans demander, car le banc a reçu une confirmation globale au départ."""
    def __init__(self):
        super().__init__()
        self.color = False
        self.confirmations = 0

    def display(self, code, text, **kwargs):
        pass

    def confirm(self, text):
        self.confirmations += 1
        return True


def run_python(folder, *args, timeout=15):
    """Exécute une vérification fixe du banc ; retourne (code, stdout, stderr)."""
    try:
        done = subprocess.run([sys.executable, '-B', *args], cwd=folder, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, errors='replace', timeout=timeout,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        return done.returncode, done.stdout, done.stderr
    except (OSError, subprocess.TimeoutExpired):
        return None, '', ''


def probe(folder, code):
    """Exécute `code` et lit la dernière ligne RESULT: (le module testé peut afficher autre chose)."""
    status, out, _ = run_python(folder, '-c', code)
    for line in reversed(out.splitlines()):
        if line.startswith('RESULT:'):
            try:
                return json.loads(line[7:])
            except ValueError:
                return None
    return None


def exists(*names):
    return lambda folder, _: all((folder/name).is_file() for name in names)


def syntax(*names):
    def check(folder, _):
        try:
            for name in names:
                compile((folder/name).read_text(encoding='utf-8'), name, 'exec')
            return True
        except (OSError, SyntaxError, ValueError):
            return False
    return check


def output_is(name, expected):
    return lambda folder, _: run_python(folder, name)[:2] == (0, expected)


def unittest_passes(module):
    def check(folder, _):
        status, _, err = run_python(folder, '-m', 'unittest', module, timeout=30)
        return status == 0 and 'Ran 0 tests' not in err and 'Ran ' in err
    return check


def expression(import_line, expr, expected):
    code = f"import json\n{import_line}\nprint('RESULT:' + json.dumps({expr}))"
    return lambda folder, _: probe(folder, code) == expected


def self_check(_, validation):
    return bool(validation) and validation.get('status') == 'double_verification_reussie'


TASKS_FLOW = ("(lambda g: (lambda i: [g.lister() == [{'id': i, 'titre': 'a', 'termine': False}], "
              "(g.terminer(i), g.lister()[0]['termine'])[1]])(g.ajouter('a')))(GestionnaireTaches())")

MISSIONS = [
    ('bonjour', 'Écris bonjour.py qui affiche exactement Bonjour PRÉVOST puis lance-le.', [
        ('fichier bonjour.py créé', exists('bonjour.py')),
        ('syntaxe valide', syntax('bonjour.py')),
        ('sortie exacte « Bonjour PRÉVOST »', output_is('bonjour.py', 'Bonjour PRÉVOST\n')),
        ('contrôle interne du modèle réussi', self_check)]),
    ('calcul', 'Écris calcul.py avec une fonction additionner(a, b) et test_calcul.py (unittest) qui la teste, puis lance les tests.', [
        ('fichiers calcul.py et test_calcul.py créés', exists('calcul.py', 'test_calcul.py')),
        ('syntaxe valide', syntax('calcul.py', 'test_calcul.py')),
        ('additionner(2, 3) == 5', expression('from calcul import additionner', 'additionner(2, 3)', 5)),
        ('tests unitaires réussis', unittest_passes('test_calcul')),
        ('contrôle interne du modèle réussi', self_check)]),
    ('premiers', 'Écris premiers.py avec une fonction est_premier(n) et un programme qui affiche les 10 premiers nombres premiers, un par ligne.', [
        ('fichier premiers.py créé', exists('premiers.py')),
        ('syntaxe valide', syntax('premiers.py')),
        ('est_premier correct pour 1, 2, 15, 17',
         expression('from premiers import est_premier', '[est_premier(1), est_premier(2), est_premier(15), est_premier(17)]',
                    [False, True, False, True])),
        ('affiche les 10 premiers nombres premiers', output_is('premiers.py', '2\n3\n5\n7\n11\n13\n17\n19\n23\n29\n')),
        ('contrôle interne du modèle réussi', self_check)]),
    ('taches', 'Écris taches.py : classe GestionnaireTaches avec ajouter(titre) qui retourne un identifiant entier, terminer(id) et '
               "lister() qui retourne une liste de dictionnaires avec les clés 'id', 'titre', 'termine'. Écris test_taches.py (unittest) "
               'puis lance les tests.', [
        ('fichiers taches.py et test_taches.py créés', exists('taches.py', 'test_taches.py')),
        ('syntaxe valide', syntax('taches.py', 'test_taches.py')),
        ('ajouter, lister et terminer fonctionnent', expression('from taches import GestionnaireTaches', TASKS_FLOW, [True, True])),
        ('tests unitaires réussis', unittest_passes('test_taches')),
        ('contrôle interne du modèle réussi', self_check)]),
]


def run_model(client, model, base, timeout):
    """Retourne {(mission, critère): bool} ; une erreur de mission fait échouer ses critères."""
    results = {}
    for name, request, criteria in MISSIONS:
        folder = Path(tempfile.mkdtemp(prefix=name + '-', dir=base))
        project = Project(folder, state=Path(base)/('etat-' + name))
        validation = None
        try:
            validation = code_mission(client, model, project, request, QuietUI(), timeout)
        except Exception:
            pass
        for label, check in criteria:
            try:
                results[(name, label)] = bool(check(folder, validation))
            except Exception:
                results[(name, label)] = False
    return results


def table(models, all_results):
    rows = [(f'{name} — {label}', [all_results[m][(name, label)] for m in models])
            for name, _, criteria in MISSIONS for label, _ in criteria]
    width = max(len(label) for label, _ in rows)
    cols = [max(len(m), 6) for m in models]
    head = 'Critère'.ljust(width) + ' | ' + ' | '.join(m.ljust(w) for m, w in zip(models, cols))
    lines = [head, '-' * len(head)]
    for label, values in rows:
        lines.append(label.ljust(width) + ' | ' + ' | '.join(('OK' if v else 'ÉCHEC').ljust(w) for v, w in zip(values, cols)))
    totals = [sum(v[i] for _, v in rows) for i in range(len(models))]
    lines.append('-' * len(head))
    lines.append('Total'.ljust(width) + ' | ' + ' | '.join(f'{t}/{len(rows)}'.ljust(w) for t, w in zip(totals, cols)))
    return '\n'.join(lines)


def main(argv=None, ui=None, client=None):
    parser = argparse.ArgumentParser(prog='prevost bench', description='Banc d’essai de modèles Ollama installés')
    parser.add_argument('--model', action='append', required=True, help='Modèle installé ; répéter, ou « tous »')
    parser.add_argument('--ollama', default=os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434'))
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--http-timeout', type=float, default=300)
    args = parser.parse_args(argv)
    ui = ui or UI()
    try:
        if not 0 < args.timeout <= 300 or not 0 < args.http_timeout <= 300:
            raise ValueError('Délais requis : 0 < délai <= 300 secondes.')
        client = client or Ollama(args.ollama, args.http_timeout)
        models = sorted(client.models()) if 'tous' in args.model else list(dict.fromkeys(args.model))
        models = [choose(client, ui, requested) for requested in models]
        with tempfile.TemporaryDirectory(prefix='prevost-bench-') as base:
            if not ui.confirm(
                    f'BANC D’ESSAI — une seule confirmation pour tout le banc.\nModèles : {", ".join(models)}.\n'
                    f'{len(MISSIONS)} missions fixes ({", ".join(m[0] for m in MISSIONS)}) par modèle, dans le dossier '
                    f'temporaire jetable {base}.\nSANS autre confirmation, PRÉVOST écrira les fichiers proposés par le modèle '
                    'et exécutera Python sur ce code, sur cet appareil, avec vos droits (réseau et fichiers hors dossier '
                    'accessibles). Les sorties du modèle sont des données non fiables. Le dossier est supprimé à la fin.'):
                ui.show('Banc d’essai refusé ; rien n’a été écrit ni exécuté.')
                return 1
            all_results = {}
            for model in models:
                ui.show('Modèle ' + model + '…')
                all_results[model] = run_model(client, model, base, args.timeout)
            ui.raw(table(models, all_results))
        ui.show('Banc terminé. Un échec indique un critère non satisfait, pas un jugement général sur le modèle.')
        return 0
    except Exception as error:
        ui.show('Erreur : ' + str(error))
        return 1
