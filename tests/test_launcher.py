"""Lanceur réel dans des dossiers temporaires ; aucune installation de paquet."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prevost_launcher', SOURCE/'integration/install_launcher.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_launcher_subcommands_from_another_directory(self):
        with tempfile.TemporaryDirectory(prefix='prevost espace ') as directory:
            target = launcher.install(Path(directory)/'bin')
            self.assertEqual(launcher.install(target.parent), target)
            for command in ([], ['coffre'], ['reseau'], ['gardien']):
                with self.subTest(command=command):
                    result = subprocess.run([str(target), *command, '--help'], cwd=directory,
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('usage:', result.stdout)

    def test_preserves_foreign_command_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'prevost'
            target.write_text('commande existante')
            with self.assertRaises(ValueError): launcher.install(directory)
            self.assertEqual(target.read_text(), 'commande existante')
            link_dir = Path(directory)/'links'
            link_dir.mkdir()
            (link_dir/'prevost').symlink_to(target)
            with self.assertRaises(ValueError): launcher.install(link_dir)
            self.assertEqual(target.read_text(), 'commande existante')
