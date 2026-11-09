"""Banc d'essai : quatre missions fixes pour comparer les modèles Ollama installés.

Exception documentée à la règle des confirmations : une seule confirmation « oui » exacte au départ
couvre toutes les écritures et exécutions de ce banc, dans un dossier temporaire jetable.

Chaque critère est vérifié par le banc lui-même et renvoie '' s'il est satisfait, sinon la raison de l'échec.
Avec --essais N, chaque mission est rejouée N fois, chacune dans un dossier neuf, pour obtenir un taux de réussite."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from .app import Ollama, Project, UI, choose, code_mission

MAX_TRIALS = 10


def short(text, limit=240):
    """Texte sur une seule ligne, tronqué : une raison d'échec doit tenir dans le rapport."""
    text = ' '.join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


def error_line(text):
    """Ligne la plus parlante d'un message d'erreur : la dernière qui mentionne Error ou Exception, sinon la dernière."""
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    for line in reversed(lines):
        if 'Error' in line or 'Exception' in line:
            return short(line)
    return short(lines[-1]) if lines else 'aucun message d’erreur'


def describe_problem(text):
    """Résume un résultat d'exécution ou de contrôle raté affiché par `code_mission` ; '' si rien d'anormal."""
    try:
        data = json.loads(text)
    except ValueError:
        return ''
    if not isinstance(data, dict):
        return ''
    if data.get('tool') == 'python.run' and data.get('verified') is False:
        parameters = data.get('parameters') or {}
        evidence = data.get('evidence') or {}
        text = f"contrôle de {parameters.get('path', '?')} raté ({data.get('status')})"
        if evidence:
            text += (f" : sortie obtenue {short(repr(evidence.get('stdout', '')), 100)}, "
                     f"attendue {short(repr(parameters.get('expected_stdout', '')), 100)}")
            if evidence.get('stderr'):
                text += ' ; erreur : ' + error_line(evidence['stderr'])
        elif data.get('error'):
            text += ' : ' + short(data['error'])
        return text
    if 'returncode' in data and 'output' in data:
        if data.get('timeout'):
            return 'commande interrompue : délai dépassé'
        if data.get('returncode') not in (0, None):
            return f"commande : code retour {data['returncode']} — {error_line(data['output'])}"
    return ''


class QuietUI(UI):
    """Silencieuse ; confirme sans demander, car le banc a reçu une confirmation globale au départ.

    Elle ne montre rien mais retient de quoi expliquer un échec : le dernier constat de la tentative en cours
    (`problem`) et la dernière conclusion de la mission (`conclusion`)."""
    def __init__(self):
        super().__init__()
        self.color = False
        self.confirmations = 0
        self.problem = ''
        self.conclusion = ''

    def display(self, code, text, **kwargs):
        text = str(text)
        if code == self.SKY:
            if text.startswith('Plan proposé'):
                self.problem = ''
            elif text.startswith(('Mission interrompue', 'Plan refusé')):
                self.conclusion = text
        elif code == self.WHITE:
            self.problem = describe_problem(text) or self.problem

    def progress(self, chunks, label):
        return ''.join(chunks)

    def answer(self, chunks):
        return ''.join(chunks)

    def confirm(self, text):
        self.confirmations += 1
        return True


class Attempt:
    """Ce qu'une mission a produit : le bilan de `code_mission`, l'éventuelle exception et ce que l'interface a retenu."""
    def __init__(self):
        self.ui = QuietUI()
        self.validation = None
        self.error = ''


def run_python(folder, *args, timeout=15):
    """Exécute une vérification fixe du banc ; retourne (code, stdout, stderr)."""
    try:
        done = subprocess.run([sys.executable, '-B', *args], cwd=folder, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, errors='replace', timeout=timeout,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        return done.returncode, done.stdout, done.stderr
    except (OSError, subprocess.TimeoutExpired):
        return None, '', ''


NO_RESULT = object()


def probe(folder, code):
    """Exécute `code` et lit la dernière ligne RESULT: (le module testé peut afficher autre chose).

    Retourne (valeur, code de retour, stderr) ; valeur vaut NO_RESULT si aucune ligne RESULT: n'est lisible."""
    status, out, err = run_python(folder, '-c', code)
    for line in reversed(out.splitlines()):
        if line.startswith('RESULT:'):
            try:
                return json.loads(line[7:]), status, err
            except ValueError:
                break
    return NO_RESULT, status, err


def exists(*names):
    def check(folder, _):
        missing = [name for name in names if not (folder/name).is_file()]
        return 'fichier absent : ' + ', '.join(missing) if missing else ''
    return check


def syntax(*names):
    def check(folder, _):
        for name in names:
            try:
                compile((folder/name).read_text(encoding='utf-8'), name, 'exec')
            except OSError:
                return f'{name} absent ou illisible'
            except SyntaxError as error:
                return f'{name} ligne {error.lineno} : {error.msg}'
            except ValueError as error:
                return f'{name} : {short(error)}'
        return ''
    return check


def output_is(name, expected):
    def check(folder, _):
        if not (folder/name).is_file():
            return f'{name} absent'
        status, out, err = run_python(folder, name)
        if status is None:
            return f'{name} : exécution impossible ou délai dépassé'
        if status != 0:
            return f'{name} : code retour {status} — {error_line(err)}'
        if out != expected:
            return f'sortie obtenue {short(repr(out), 100)}, attendue {short(repr(expected), 100)}'
        return ''
    return check


def unittest_passes(module):
    def check(folder, _):
        if not (folder/(module + '.py')).is_file():
            return f'{module}.py absent'
        status, _, err = run_python(folder, '-m', 'unittest', module, timeout=30)
        if status is None:
            return f'tests de {module} : exécution impossible ou délai dépassé'
        if 'Ran ' not in err:
            return f'tests de {module} non lancés — {error_line(err)}'
        if 'Ran 0 tests' in err:
            return f'aucun test trouvé dans {module}'
        if status != 0:
            return f'tests de {module} en échec — {error_line(err)}'
        return ''
    return check


def expression(import_line, expr, expected):
    code = f"import json\n{import_line}\nprint('RESULT:' + json.dumps({expr}))"

    def check(folder, _):
        value, status, err = probe(folder, code)
        if value is NO_RESULT:
            if status is None:
                return 'exécution impossible ou délai dépassé'
            return 'aucun résultat — ' + error_line(err)
        if value != expected:
            return (f'obtenu {short(json.dumps(value, ensure_ascii=False), 100)}, '
                    f'attendu {short(json.dumps(expected, ensure_ascii=False), 100)}')
        return ''
    return check


def self_check(_, attempt):
    """Contrôle interne de PRÉVOST : la double vérification (syntaxe + exécution avec sortie annoncée) a réussi."""
    validation = attempt.validation
    if validation and validation.get('status') == 'double_verification_reussie':
        return ''
    if attempt.error:
        return 'mission en erreur : ' + short(attempt.error)
    if validation:
        unverified = [f"{row['path']} : {row['reason']}" for row in validation.get('files', []) if not row.get('verified')]
        why = f"bilan « {validation.get('status')} » après {validation.get('attempts', 1)} tentative(s)"
        if unverified:
            why += ' — ' + ' ; '.join(unverified)
    else:
        why = 'pas de bilan : ' + (attempt.ui.conclusion or 'la mission n’a pas atteint les contrôles')
    if attempt.ui.problem:
        why += ' ; dernier constat : ' + attempt.ui.problem
    return short(why, 400)


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


def duration(seconds):
    seconds = round(seconds)
    return f'{seconds} s' if seconds < 60 else f'{seconds // 60} min {seconds % 60:02d} s'


def run_mission(client, model, base, timeout, mission, trial=1):
    """Joue une mission dans un dossier neuf ; retourne {critère: raison} (raison '' = critère satisfait).

    Une erreur de mission fait échouer ses critères ; chaque essai a son dossier et son état propres."""
    name, request, criteria = mission
    folder = Path(tempfile.mkdtemp(prefix=f'{name}-{trial}-', dir=base))
    project = Project(folder, state=Path(base)/f'etat-{name}-{trial}')
    attempt = Attempt()
    try:
        attempt.validation = code_mission(client, model, project, request, attempt.ui, timeout)
    except Exception as error:
        attempt.error = f'{type(error).__name__} : {error}'
    outcomes = {}
    for label, check in criteria:
        try:
            outcomes[label] = check(folder, attempt)
        except Exception as error:
            outcomes[label] = 'vérification impossible : ' + short(f'{type(error).__name__} : {error}')
    return outcomes


def run_model(client, model, base, timeout, trials=1, progress=None):
    """Retourne {(mission, critère): [raison, …]} avec une raison par essai ('' = critère satisfait).

    `progress`, s'il est donné, reçoit une ligne de texte au début et à la fin de chaque essai."""
    results = {}
    for mission in MISSIONS:
        name = mission[0]
        for trial in range(1, trials + 1):
            label = name if trials == 1 else f'{name} (essai {trial}/{trials})'
            if progress:
                progress(f'  {label}…')
            started = time.monotonic()
            outcomes = run_mission(client, model, base, timeout, mission, trial)
            for criterion, reason in outcomes.items():
                results.setdefault((name, criterion), []).append(reason)
            if progress:
                passed = sum(reason == '' for reason in outcomes.values())
                progress(f'  {label} : {passed}/{len(outcomes)} critères en {duration(time.monotonic() - started)}')
    return results


def percent(part, whole):
    return round(100 * part / whole)


def table(models, all_results, trials=1):
    """Tableau critère × modèle : OK/ÉCHEC pour un essai, sinon le nombre d'essais réussis."""
    def passes(model, key):
        return sum(reason == '' for reason in all_results[model][key])

    keys = [(name, label) for name, _, criteria in MISSIONS for label, _ in criteria]
    rows = [(f'{name} — {label}', [passes(m, (name, label)) for m in models]) for name, label in keys]
    width = max(len(label) for label, _ in rows)
    cols = [max(len(m), 6 if trials == 1 else 13) for m in models]
    head = 'Critère'.ljust(width) + ' | ' + ' | '.join(m.ljust(w) for m, w in zip(models, cols))
    lines = [head, '-' * len(head)]
    for label, values in rows:
        cells = [('OK' if v else 'ÉCHEC') if trials == 1 else f'{v}/{trials}' for v in values]
        lines.append(label.ljust(width) + ' | ' + ' | '.join(c.ljust(w) for c, w in zip(cells, cols)))
    totals = [sum(v[i] for _, v in rows) for i in range(len(models))]
    possible = len(rows) * trials
    lines.append('-' * len(head))
    cells = [f'{t}/{possible}' if trials == 1 else f'{t}/{possible} ({percent(t, possible)} %)' for t in totals]
    lines.append('Total'.ljust(width) + ' | ' + ' | '.join(c.ljust(w) for c, w in zip(cells, cols)))
    if trials > 1:
        lines.append('')
        lines.append('Missions réussies de bout en bout (tous les critères satisfaits dans le même essai) :')
        for model in models:
            parts = []
            for name, _, criteria in MISSIONS:
                perfect = sum(all(all_results[model][(name, label)][i] == '' for label, _ in criteria) for i in range(trials))
                parts.append(f'{name} {perfect}/{trials}')
            lines.append(f'  {model} — ' + ', '.join(parts))
    return '\n'.join(lines)


def failures(models, all_results, trials=1):
    """Raisons des échecs, regroupées quand elles se répètent d'un essai à l'autre ; '' s'il n'y en a aucune."""
    lines = []
    for model in models:
        found = []
        for name, _, criteria in MISSIONS:
            for label, _ in criteria:
                reasons = all_results[model][(name, label)]
                grouped = {}
                for trial, reason in enumerate(reasons, 1):
                    if reason:
                        grouped.setdefault(reason, []).append(trial)
                if grouped:
                    found.append(f'  {name} — {label}')
                    for reason, numbers in grouped.items():
                        where = '' if trials == 1 else ('essai ' if len(numbers) == 1 else 'essais ') + ', '.join(map(str, numbers)) + ' : '
                        found.append(f'      {where}{reason}')
        if found:
            lines.append(f'Raisons des échecs — {model}')
            lines.extend(found)
    return '\n'.join(lines)


def main(argv=None, ui=None, client=None):
    parser = argparse.ArgumentParser(prog='prevost bench', description='Banc d’essai de modèles Ollama installés')
    parser.add_argument('--model', action='append', required=True, help='Modèle installé ; répéter, ou « tous »')
    parser.add_argument('--essais', type=int, default=1,
                        help=f'Essais par mission (1 à {MAX_TRIALS}) ; plusieurs essais donnent un taux de réussite (défaut : 1)')
    parser.add_argument('--ollama', default=os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434'))
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--http-timeout', type=float, default=300)
    args = parser.parse_args(argv)
    ui = ui or UI()
    try:
        if not 0 < args.timeout <= 300 or not 0 < args.http_timeout <= 300:
            raise ValueError('Délais requis : 0 < délai <= 300 secondes.')
        if not 1 <= args.essais <= MAX_TRIALS:
            raise ValueError(f'Nombre d’essais requis : de 1 à {MAX_TRIALS}.')
        client = client or Ollama(args.ollama, args.http_timeout)
        models = sorted(client.models()) if 'tous' in args.model else list(dict.fromkeys(args.model))
        models = [choose(client, ui, requested) for requested in models]
        with tempfile.TemporaryDirectory(prefix='prevost-bench-') as base:
            if not ui.confirm(
                    f'BANC D’ESSAI — une seule confirmation pour tout le banc.\nModèles : {", ".join(models)}.\n'
                    f'{len(MISSIONS)} missions fixes ({", ".join(m[0] for m in MISSIONS)}) par modèle, '
                    f'{args.essais} essai(s) par mission, dans le dossier temporaire jetable {base}.\n'
                    'SANS autre confirmation, PRÉVOST écrira les fichiers proposés par le modèle '
                    'et exécutera Python sur ce code, sur cet appareil, avec vos droits (réseau et fichiers hors dossier '
                    'accessibles). Les sorties du modèle sont des données non fiables. Le dossier est supprimé à la fin.'):
                ui.show('Banc d’essai refusé ; rien n’a été écrit ni exécuté.')
                return 1
            def say(text):
                ui.show(text)
                sys.stdout.flush()  # sans cela, une sortie redirigée n'afficherait rien avant la fin du banc

            all_results = {}
            for model in models:
                say(f'Modèle {model} : {len(MISSIONS)} missions × {args.essais} essai(s)…')
                all_results[model] = run_model(client, model, base, args.timeout, args.essais, progress=say)
            ui.raw(table(models, all_results, args.essais))
            reasons = failures(models, all_results, args.essais)
            if reasons:
                ui.raw('\n' + reasons)
        ui.show('Banc terminé. Un échec indique un critère non satisfait, pas un jugement général sur le modèle.'
                + (' Un seul essai par mission : à confirmer avec --essais 3.' if args.essais == 1 else ''))
        return 0
    except Exception as error:
        ui.show('Erreur : ' + str(error))
        return 1
