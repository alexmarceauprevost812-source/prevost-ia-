"""Bilan déterministe des deux contrôles de code, lié aux sources présentes."""
import hashlib
from pathlib import Path


def assess_code(project, paths, results):
    files = []
    normalized = sorted({str(Path(path)) for path in paths})
    for path in normalized:
        row = {'path': path, 'verified': False, 'reason': 'Deux contrôles manquants.'}
        if not path.endswith('.py'):
            row['reason'] = 'Double vérification automatique disponible pour Python seulement.'
            files.append(row)
            continue
        candidates = [result for result in results if result.get('tool') == 'python.run'
                      and str(Path(result['parameters']['path'])) == path]
        if candidates:
            result = candidates[-1]
            row['evidence_id'] = result['id']
            try:
                current = hashlib.sha256(project.read(path).encode()).hexdigest()
                checks = result.get('code_checks', {})
                row['verified'] = (result['verified'] and result['status'] == 'ok'
                                   and checks.get('syntax') == 'passed'
                                   and checks.get('execution') == 'passed'
                                   and result.get('source_sha256') == current)
                row['reason'] = ('Syntaxe et exécution avec sortie attendue vérifiées sur la source actuelle.'
                                 if row['verified'] else 'Contrôle échoué ou source modifiée depuis la vérification.')
            except (OSError, ValueError):
                row['reason'] = 'Source actuelle inaccessible ; validation impossible.'
        files.append(row)
    return {'status': ('sans_modification' if not files else
                       'double_verification_reussie' if all(row['verified'] for row in files)
                       else 'verification_incomplete'), 'files': files,
            'limit': 'Deux contrôles réussis ne prouvent pas tous les cas fonctionnels ni la sécurité du code.'}
