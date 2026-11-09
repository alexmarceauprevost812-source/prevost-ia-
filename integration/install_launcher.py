"""Installe un lanceur lié au dépôt, sans modifier le dossier de travail choisi."""
import argparse
from pathlib import Path
import sys

MARKER = '# Lanceur PRÉVOST v2 géré par install_launcher.py'


def install(bin_dir):
    source = Path(__file__).resolve().parents[1]
    directory = Path(bin_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory/'prevost'
    content = (f'#!{sys.executable}\n{MARKER}\n'
               'import runpy, sys\n'
               f'sys.path.insert(0, {str(source)!r})\n'
               "modules = {'coffre': 'prevost.vault', 'reseau': 'prevost.network', "
               "'gardien': 'prevost.guardian'}\n"
               "module = modules.get(sys.argv[1]) if len(sys.argv) > 1 else None\n"
               'if module:\n    del sys.argv[1]\n'
               "runpy.run_module(module or 'prevost', run_name='__main__')\n")
    # Ne remplace jamais un lien ni une commande préexistante étrangère.
    if target.is_symlink():
        raise ValueError('Le lanceur existant est un lien ; installation abandonnée.')
    if target.exists():
        if MARKER not in target.read_text(encoding='utf-8').splitlines()[:2]:
            raise ValueError('Une autre commande prevost existe ; elle est conservée.')
        target.write_text(content, encoding='utf-8')
    else:
        with target.open('x', encoding='utf-8') as stream:
            stream.write(content)
    target.chmod(0o700)
    return target


def main():
    parser = argparse.ArgumentParser(description='Installer le lanceur PRÉVOST v2')
    parser.add_argument('--bin-dir', required=True)
    args = parser.parse_args()
    try:
        print('Lanceur installé :', install(args.bin_dir))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
