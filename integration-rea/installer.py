"""Installer le raccourci utilisateur rea-prevost et corriger le bouton REA local."""
import argparse
import datetime
import os
from pathlib import Path
import shutil

OLD = 'button("🟠 PRÉVOST IA", lambda: launch("ollama run prevost:latest"))'
NEW = 'button("🟠 REA-PRÉVOST", lambda: launch("rea-prevost"))'


def install(bin_dir, apply=False):
    bin_dir = Path(bin_dir)
    gui, shortcut = bin_dir / 'rea-gui', bin_dir / 'rea-prevost'
    if gui.is_symlink() or shortcut.is_symlink():
        raise ValueError('Un des lanceurs est un lien symbolique : installation automatique refusée.')
    original = gui.read_text(encoding='utf-8')
    if original.count(OLD) == 1:
        updated = original.replace(OLD, NEW)
    elif original.count(NEW) == 1 and OLD not in original:
        updated = original
    else:
        raise ValueError('Bouton REA attendu absent ou ambigu ; aucune modification effectuée.')
    print('Bouton : REA-PRÉVOST → rea-prevost → ollama run prevost:latest')
    print('Fichiers :', gui, shortcut)
    if not apply:
        print('Aperçu seulement. Ajouter --apply pour installer avec sauvegarde.')
        return None
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = bin_dir / ('rea-prevost-sauvegarde-' + stamp)
    backup.mkdir(mode=0o700)
    for path in (gui, shortcut):
        if path.exists():
            shutil.copy2(path, backup / path.name)
    source = Path(__file__).with_name('rea-prevost')
    pending = []
    try:
        for path, content, mode in ((gui, updated, gui.stat().st_mode & 0o777),
                                    (shortcut, source.read_text(), 0o755)):
            temp = bin_dir / ('.' + path.name + '-' + stamp)
            with temp.open('x', encoding='utf-8') as stream:
                stream.write(content)
            temp.chmod(mode)
            pending.append((temp, path))
        for temp, path in pending:
            os.replace(temp, path)
    except OSError:
        for temp, _ in pending:
            if temp.exists():
                temp.unlink()
        for path in (gui, shortcut):
            previous = backup / path.name
            if previous.exists():
                shutil.copy2(previous, path)
            elif path == shortcut and path.exists():
                path.unlink()
        raise
    print('Installé. Sauvegarde :', backup)
    print('Fermer puis rouvrir REA ; bouton REA-PRÉVOST. Commande : rea-prevost')
    return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bin-dir', type=Path, default=Path.home() / '.local/bin')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        install(args.bin_dir, args.apply)
        return 0
    except (OSError, ValueError) as exc:
        print('Installation non terminée :', exc)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
