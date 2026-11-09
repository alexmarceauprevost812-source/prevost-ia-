import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import installer


class ShortcutTests(unittest.TestCase):
    def test_preview_and_backup(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            root = Path(d)
            gui = root/'rea-gui'
            gui.write_text(installer.OLD+'\n')
            gui.chmod(0o755)
            installer.install(root)
            self.assertEqual(gui.read_text(),installer.OLD+'\n')
            self.assertFalse((root/'rea-prevost').exists())
            backup = installer.install(root,True)
            self.assertEqual((backup/'rea-gui').read_text(),installer.OLD+'\n')
            self.assertIn(installer.NEW,gui.read_text())
            self.assertTrue((root/'rea-prevost').stat().st_mode & 0o111)
            installer.install(root,True)
            self.assertEqual(gui.read_text().count(installer.NEW),1)

    def test_unknown_gui_stays_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            gui=Path(d)/'rea-gui'; gui.write_text('autre version')
            with self.assertRaises(ValueError): installer.install(Path(d),True)
            self.assertEqual(gui.read_text(),'autre version')

    def test_shortcut_has_no_shell_syntax_error(self):
        r=subprocess.run(['bash','-n',str(Path(installer.__file__).with_name('rea-prevost'))],capture_output=True)
        self.assertEqual(r.returncode,0)

    def test_shortcut_uses_model_and_preserves_literal_arguments(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); log=root/'calls.txt'; fake=root/'ollama'
            fake.write_text('#!/bin/sh\nif [ "$1" = show ]; then exit 0; fi\nprintf "%s\\n" "$@" > "$REA_PREVOST_TEST_LOG"\n')
            fake.chmod(0o755)
            env={**os.environ,'PATH':str(root)+os.pathsep+os.environ.get('PATH',''),'REA_PREVOST_TEST_LOG':str(log)}
            marker='$(do-not-execute)'
            r=subprocess.run([str(Path(installer.__file__).with_name('rea-prevost')),marker],env=env,capture_output=True)
            self.assertEqual(r.returncode,0)
            self.assertEqual(log.read_text().splitlines(),['run','prevost:latest',marker])

    def test_missing_model_does_not_run_or_pull(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); log=root/'calls.txt'; fake=root/'ollama'
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$REA_PREVOST_TEST_LOG"\nexit 1\n')
            fake.chmod(0o755)
            env={**os.environ,'PATH':str(root)+os.pathsep+os.environ.get('PATH',''),'REA_PREVOST_TEST_LOG':str(log)}
            r=subprocess.run([str(Path(installer.__file__).with_name('rea-prevost'))],env=env,capture_output=True)
            self.assertNotEqual(r.returncode,0)
            self.assertEqual(log.read_text().splitlines(),['show','prevost:latest'])
