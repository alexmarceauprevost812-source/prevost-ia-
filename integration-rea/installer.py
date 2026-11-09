"""Installer le raccourci utilisateur rea-prevost et corriger le bouton REA local."""
import argparse
import datetime
import os
from pathlib import Path
import shutil

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


def apply_theme(source):
    replacements = {
        'BG = "#050505"': 'BG = "#000000"',
        'PANEL = "#101010"': 'PANEL = "#000000"',
        'ORANGE = "#FF7900"': 'ORANGE = "#E00000"',
        'WHITE = "#F5F5F5"': 'WHITE = "#FFFFFF"',
        'root.title("REA — LEXOS PRO")': 'root.title("PRÉVOST — rea-prevost")',
        'header, text="REA"': 'header, text="PRÉVOST"',
        'header, text="   LEXOS PRO  |  AGENT IA LOCAL"': 'header, text="   rea-prevost  |  CODEX LOCAL"',
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


def install(bin_dir, apply=False, theme_dir=None):
    bin_dir = Path(bin_dir)
    theme_dir = Path(theme_dir) if theme_dir is not None else bin_dir/'themes'
    gui, shortcut = bin_dir/'rea-gui', bin_dir/'rea-prevost'
    theme = theme_dir/'prevost-noir.tmTheme'
    targets = (gui,shortcut,theme)
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
    updated = apply_theme(updated)
    compile(updated,str(gui),'exec')
    print('rea-prevost → choix du projet → Codex → modèle local prevost:latest')
    print('Thème : fond noir, texte blanc, code coloré, accents rouges.')
    print('Fichiers :',gui,shortcut,theme)
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
        for path,content,mode in ((gui,updated,gui.stat().st_mode & 0o777),
                                 (shortcut,source.read_text(),0o755),
                                 (theme,Path(__file__).with_name('prevost-noir.tmTheme').read_text(),0o600)):
            temp = path.parent/('.'+path.name+'-'+stamp)
            with temp.open('x',encoding='utf-8') as stream:
                stream.write(content)
            temp.chmod(mode)
            pending.append((temp,path))
        for temp,path in pending:
            os.replace(temp,path)
    except OSError:
        for temp,_ in pending:
            if temp.exists(): temp.unlink()
        for path in targets:
            previous = backup/path.name
            if previous.exists(): shutil.copy2(previous,path)
            elif path != gui and path.exists(): path.unlink()
        raise
    print('Installé. Sauvegarde :',backup)
    print('Fermer puis rouvrir REA ; bouton rea-prevost. Commande : rea-prevost')
    return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bin-dir',type=Path,default=Path.home()/'.local/bin')
    parser.add_argument('--theme-dir',type=Path,default=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'themes')
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args(argv)
    try:
        install(args.bin_dir,args.apply,args.theme_dir)
        return 0
    except (OSError,ValueError,SyntaxError) as exc:
        print('Installation non terminée :',exc)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
