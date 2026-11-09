"""Installer les raccourcis utilisateur rea-prevost, prevost-rea et claude-rea et corriger le bouton REA local."""
import argparse
import datetime
import os
from pathlib import Path
import shutil
import subprocess

OLD = 'button("🟠 PRÉVOST IA", lambda: launch("ollama run prevost:latest"))'
LEGACY = 'button("🟠 REA-PRÉVOST", lambda: launch("rea-prevost"))'
NEW = '''def launch_rea_prevost():
    from pathlib import Path
    import shlex
    project = filedialog.askdirectory(title="Projet à modifier avec PRÉVOST dans Codex")
    if not project:
        return
    terminal = shutil.which("xfce4-terminal")
    ptyxis = shutil.which("ptyxis") if not terminal else None
    fallback = shutil.which("x-terminal-emulator") if not terminal and not ptyxis else None
    if not terminal and not ptyxis and not fallback:
        log("Aucun terminal compatible trouvé.")
        return
    shortcut = Path(__file__).with_name("rea-prevost")
    try:
        command = [str(shortcut), "--project", project]
        if terminal:
            argv = [terminal, "--disable-server", "--working-directory", project, "--command", shlex.join(command)]
        elif ptyxis:
            argv = [ptyxis, "--new-window", "--working-directory", project, "--"] + command
        else:
            argv = [fallback, "-e"] + command
        subprocess.Popen(argv, cwd=project)
    except OSError as exc:
        log("REA-PRÉVOST non lancé : " + str(exc))

button("rea-prevost", launch_rea_prevost)''' 


PYTHON_BLOCK = '''def launch_prevost_rea():
    from pathlib import Path
    import shlex
    project = filedialog.askdirectory(title="Projet à modifier avec PRÉVOST (plans vérifiés, corrections confirmées)")
    if not project:
        return
    terminal = shutil.which("xfce4-terminal")
    ptyxis = shutil.which("ptyxis") if not terminal else None
    fallback = shutil.which("x-terminal-emulator") if not terminal and not ptyxis else None
    if not terminal and not ptyxis and not fallback:
        log("Aucun terminal compatible trouvé.")
        return
    shortcut = Path(__file__).with_name("prevost-rea")
    try:
        command = [str(shortcut), "--project", project]
        if terminal:
            argv = [terminal, "--disable-server", "--working-directory", project, "--command", shlex.join(command)]
        elif ptyxis:
            argv = [ptyxis, "--new-window", "--working-directory", project, "--"] + command
        else:
            argv = [fallback, "-e"] + command
        subprocess.Popen(argv, cwd=project)
    except OSError as exc:
        log("PRÉVOST non lancé : " + str(exc))

button("prevost-rea", launch_prevost_rea)'''
# Bouton Claude Code : même mécanique que prevost-rea, vers le raccourci claude-rea.
CLAUDE_BLOCK = (PYTHON_BLOCK.replace('launch_prevost_rea', 'launch_claude_rea')
                .replace('Projet à modifier avec PRÉVOST (plans vérifiés, corrections confirmées)',
                         'Projet à modifier avec Claude Code (service Anthropic)')
                .replace('"prevost-rea"', '"claude-rea"')
                .replace('PRÉVOST non lancé', 'Claude non lancé'))
# Version publiée brièvement sous le nom prevost-ia : migrée vers prevost-rea.
PYTHON_BLOCK_V1 = PYTHON_BLOCK.replace('launch_prevost_rea', 'launch_prevost_ia').replace('"prevost-rea"', '"prevost-ia"')
DEPOT_LINE = "DEPOT = None  # remplacé par l'installateur"


def python_shortcut_source():
    """Script du bouton prevost-rea, lié au dépôt où se trouve cet installateur."""
    source = Path(__file__).with_name('prevost-rea').read_text(encoding='utf-8')
    if source.count(DEPOT_LINE) != 1:
        raise ValueError('Modèle prevost-rea inattendu ; installation abandonnée.')
    return source.replace(DEPOT_LINE, 'DEPOT = ' + repr(str(Path(__file__).resolve().parents[1])))


WINDOW_TITLE = 'root.title("PRÉVOST — REA")'
HEADER_TEXT = 'header, text="   REA avec PRÉVOST local (prevost-rea)  |  Codex gardé (rea-prevost)"'


def apply_theme(source):
    replacements = {
        'BG = "#050505"': 'BG = "#000000"',
        'PANEL = "#101010"': 'PANEL = "#000000"',
        'ORANGE = "#FF7900"': 'ORANGE = "#E00000"',
        'WHITE = "#F5F5F5"': 'WHITE = "#FFFFFF"',
        'root.title("REA — LEXOS PRO")': WINDOW_TITLE,
        # Titres posés par une version précédente de l’installateur : mis à jour.
        'root.title("PRÉVOST — rea-prevost")': WINDOW_TITLE,
        'header, text="REA"': 'header, text="PRÉVOST"',
        'header, text="   LEXOS PRO  |  AGENT IA LOCAL"': HEADER_TEXT,
        'header, text="   rea-prevost  |  CODEX LOCAL"': HEADER_TEXT,
        'bg=ORANGE, fg="#000000"': 'bg=ORANGE, fg=WHITE',
        'activebackground="#FFAA33"': 'activebackground="#FF3030"',
        'activeforeground="#000000"': 'activeforeground=WHITE',
        'selectbackground="#703800"': 'selectbackground="#4A0000"',
        'text="R E A"': 'text="P R É V O S T"',
        'bg="#090909", fg=GREEN': 'bg=BG, fg=WHITE',
    }
    for old,new in replacements.items():
        source = source.replace(old,new)
    return source


ICON_NAME = 'rea.svg'
LAUNCHER_NAME = 'rea-interface.desktop'   # menu des applications ; nom distinct de tout ancien REA.desktop
DESKTOP_COPY = 'REA.desktop'              # copie sur le bureau


def exec_quote(path):
    """Chemin entre guillemets selon la spécification des fichiers .desktop."""
    escaped = ''.join('\\' + c if c in '"`$\\' else c for c in str(path))
    return '"' + escaped.replace('%', '%%') + '"'


def desktop_entry(gui, icon):
    """Raccourci nommé REA : ouvre l'interface REA (rea-gui), avec l'image REA."""
    return ('[Desktop Entry]\nType=Application\nName=REA\n'
            'Comment=REA avec PRÉVOST local (prevost-rea) ; Codex gardé (rea-prevost)\n'
            f'Exec=python3 {exec_quote(gui)}\nIcon={icon}\nTerminal=false\nCategories=Development;\n')


def trust(path):
    """Autoriser le lancement du raccourci sur le bureau (GNOME) ; sans effet si gio manque."""
    gio = shutil.which('gio')
    if gio:
        try:
            subprocess.run([gio, 'set', str(path), 'metadata::trusted', 'true'], capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass


def user_desktop():
    """Dossier du bureau de l'utilisateur, ou None s'il n'est pas défini."""
    try:
        out = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    path = Path(out) if out else None
    return path if path and path.is_dir() and path != Path.home() else None


def install(bin_dir, apply=False, theme_dir=None, share_dir=None, desktop_dir=None):
    bin_dir = Path(bin_dir)
    theme_dir = Path(theme_dir) if theme_dir is not None else bin_dir/'themes'
    gui, shortcut, python_shortcut = bin_dir/'rea-gui', bin_dir/'rea-prevost', bin_dir/'prevost-rea'
    claude_shortcut = bin_dir/'claude-rea'
    theme = theme_dir/'prevost-noir.tmTheme'
    extras = {}
    if share_dir is not None:
        share_dir = Path(share_dir)
        icon = share_dir/'icons'/ICON_NAME
        launcher = share_dir/'applications'/LAUNCHER_NAME
        extras = {icon:(Path(__file__).with_name(ICON_NAME).read_text(encoding='utf-8'),0o644),
                  launcher:(desktop_entry(gui,icon),0o755)}
        if desktop_dir is not None and Path(desktop_dir).is_dir():
            extras[Path(desktop_dir)/DESKTOP_COPY] = (desktop_entry(gui,icon),0o755)
    targets = (gui,shortcut,python_shortcut,claude_shortcut,theme,*extras)
    if any(p.is_symlink() for p in targets):
        raise ValueError('Un des fichiers est un lien symbolique : installation automatique refusée.')
    original = gui.read_text(encoding='utf-8')
    if original.count(OLD) == 1:
        updated = original.replace(OLD,NEW)
    elif original.count(LEGACY) == 1:
        updated = original.replace(LEGACY,NEW)
    elif original.count(NEW) == 1 and OLD not in original:
        updated = original
    else:
        raise ValueError('Bouton REA attendu absent ou ambigu ; aucune modification effectuée.')
    if PYTHON_BLOCK_V1 in updated:
        updated = updated.replace(PYTHON_BLOCK_V1,PYTHON_BLOCK)
    if PYTHON_BLOCK not in updated:
        if updated.count(NEW) != 1:
            raise ValueError('Bouton REA attendu absent ou ambigu ; aucune modification effectuée.')
        updated = updated.replace(NEW,NEW+'\n\n'+PYTHON_BLOCK)
    if CLAUDE_BLOCK not in updated:
        updated = updated.replace(PYTHON_BLOCK,PYTHON_BLOCK+'\n\n'+CLAUDE_BLOCK)
    python_source = python_shortcut_source()
    updated = apply_theme(updated)
    compile(updated,str(gui),'exec')
    print('rea-prevost → choix du projet → Codex → modèle local prevost:latest')
    print('prevost-rea → choix du projet → PRÉVOST Python (plans vérifiés, corrections confirmées) → modèle au choix')
    print('claude-rea → choix du projet → Claude Code (service Anthropic, compte requis ; commande claude à installer si absente)')
    print('Thème : fond noir, texte blanc, code coloré, accents rouges.')
    print('Fichiers :',gui,shortcut,python_shortcut,claude_shortcut,theme)
    if extras:
        print('Raccourci REA (image REA) :',*extras)
    if not apply:
        print('Aperçu seulement. Ajouter --apply pour installer avec sauvegarde.')
        return None
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = bin_dir/('rea-prevost-sauvegarde-'+stamp)
    backup.mkdir(mode=0o700)
    for path in targets:
        if path.exists():
            shutil.copy2(path,backup/path.name)
    source = Path(__file__).with_name('rea-prevost')
    pending = []
    try:
        theme_dir.mkdir(parents=True,exist_ok=True)
        for extra in extras:
            extra.parent.mkdir(parents=True,exist_ok=True)
        for path,content,mode in ((gui,updated,gui.stat().st_mode & 0o777),
                                 (shortcut,source.read_text(),0o755),
                                 (python_shortcut,python_source,0o755),
                                 (claude_shortcut,Path(__file__).with_name('claude-rea').read_text(),0o755),
                                 (theme,Path(__file__).with_name('prevost-noir.tmTheme').read_text(),0o600),
                                 *((path,content,mode) for path,(content,mode) in extras.items())):
            temp = path.parent/('.'+path.name+'-'+stamp)
            with temp.open('x',encoding='utf-8') as stream:
                stream.write(content)
            temp.chmod(mode)
            pending.append((temp,path))
        for temp,path in pending:
            os.replace(temp,path)
        for path in extras:
            if path.name == DESKTOP_COPY:
                trust(path)
    except OSError:
        for temp,_ in pending:
            if temp.exists(): temp.unlink()
        for path in targets:
            previous = backup/path.name
            if previous.exists(): shutil.copy2(previous,path)
            elif path != gui and path.exists(): path.unlink()
        raise
    print('Installé. Sauvegarde :',backup)
    print('Fermer puis rouvrir REA ; boutons rea-prevost (Codex), prevost-rea (PRÉVOST Python) et claude-rea (Claude Code). Commandes : rea-prevost, prevost-rea, claude-rea')
    if extras:
        print('Icône REA : menu des applications et bureau (clic droit > Autoriser le lancement si elle reste blanche).')
    return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bin-dir',type=Path,default=Path.home()/'.local/bin')
    parser.add_argument('--theme-dir',type=Path,default=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'themes')
    parser.add_argument('--share-dir',type=Path,default=Path.home()/'.local/share')
    parser.add_argument('--desktop-dir',type=Path,default=None)
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args(argv)
    try:
        install(args.bin_dir,args.apply,args.theme_dir,args.share_dir,args.desktop_dir or user_desktop())
        return 0
    except (OSError,ValueError,SyntaxError) as exc:
        print('Installation non terminée :',exc)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
