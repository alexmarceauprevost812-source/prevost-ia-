"""Secrets fictifs uniquement ; chiffrement et fichiers réellement testés."""
import contextlib
import getpass
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prevost import vault as v

PASSWORD = 'phrase fictive pour les tests seulement'
SECRET = 'COOKIE_FICTIF_AUCUN_COMPTE_REEL'


@unittest.skipUnless(importlib.util.find_spec('cryptography'), 'dépendance coffre optionnelle absente')
class VaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = v.Vault(Path(self.temp.name)/'private')

    def create(self):
        self.vault.create(PASSWORD)

    def test_real_encryption_roundtrip_and_no_cleartext_on_disk(self):
        self.create()
        identifier = self.vault.add(PASSWORD, 'exemple.test', 'session', SECRET)
        data, _, _ = self.vault.load(PASSWORD)
        self.assertEqual(data['cookies'][identifier]['value'], SECRET)
        for path in self.vault.directory.iterdir():
            blob = path.read_bytes()
            for value in (PASSWORD, SECRET, 'exemple.test', 'session'):
                self.assertNotIn(value.encode(), blob)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.vault.directory.stat().st_mode & 0o777, 0o700)
        self.assertNotIn(SECRET, json.dumps(self.vault.metadata(PASSWORD)))

    def test_wrong_password_and_tampering_never_rewrite_vault(self):
        self.create()
        before = self.vault.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'incorrect ou fichier altéré'):
            self.vault.add('autre phrase fictive mais incorrecte', 'exemple.test', 'session', SECRET)
        self.assertEqual(self.vault.path.read_bytes(), before)
        blob = bytearray(before); blob[-1] ^= 1
        self.vault.path.write_bytes(blob)
        with self.assertRaisesRegex(ValueError, 'incorrect ou fichier altéré'):
            self.vault.metadata(PASSWORD)
        self.assertEqual(self.vault.path.read_bytes(), bytes(blob))

    def test_generic_secret_encryption_reveal_and_remove_with_legacy_cookie(self):
        self.create()
        cookie = self.vault.add(PASSWORD, 'exemple.test', 'session', SECRET)
        identifier = self.vault.add_secret(PASSWORD, 'jeton-api', 'Service fictif', 'JETON_FICTIF_123')
        reopened = v.Vault(self.vault.directory)
        self.assertEqual(reopened.reveal(PASSWORD, identifier), 'JETON_FICTIF_123')
        self.assertEqual(reopened.reveal(PASSWORD, cookie), SECRET)
        with self.assertRaises(ValueError): reopened.reveal('incorrect', identifier)
        with self.assertRaises(ValueError): reopened.reveal(PASSWORD, 'absent')
        self.assertNotIn('JETON_FICTIF_123', json.dumps(reopened.metadata(PASSWORD)))
        for path in self.vault.directory.iterdir():
            self.assertNotIn(b'JETON_FICTIF_123', path.read_bytes())
            self.assertNotIn(b'Service fictif', path.read_bytes())
        reopened.remove(PASSWORD, identifier)
        self.assertEqual(len(reopened.metadata(PASSWORD)), 1)

    def test_cli_reveal_requires_terminal_confirmation_and_password(self):
        self.create()
        identifier = self.vault.add(PASSWORD, 'exemple.test', 'session', SECRET)
        args = ['voir', '--state-dir', str(self.vault.directory)]
        with patch('sys.stdout.isatty', return_value=False), patch.object(v, 'hidden') as hidden, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(v.main(args), 1)
        hidden.assert_not_called()
        self.assertNotIn(SECRET, output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as output, patch('sys.stdout.isatty', return_value=True), \
             patch('builtins.input', side_effect=[identifier, 'non']), patch.object(v, 'hidden') as hidden:
            self.assertEqual(v.main(args), 0)
        hidden.assert_not_called()
        self.assertNotIn(SECRET, output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as output, patch('sys.stdout.isatty', return_value=True), \
             patch('builtins.input', side_effect=[identifier, 'oui']), patch.object(v, 'hidden', return_value=PASSWORD):
            self.assertEqual(v.main(args), 0)
        self.assertIn(SECRET, output.getvalue())
        self.assertNotIn(PASSWORD, output.getvalue())

    def test_cli_add_generic_secret_does_not_display_value(self):
        self.create()
        with patch.object(v, 'hidden', side_effect=[PASSWORD, SECRET]), \
             patch('builtins.input', side_effect=['mot-de-passe', 'Compte fictif', 'oui']), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(v.main(['secret', '--state-dir', str(self.vault.directory)]), 0)
        self.assertNotIn(SECRET, output.getvalue())
        self.assertNotIn(PASSWORD, output.getvalue())
        self.assertEqual(self.vault.reveal(PASSWORD, self.vault.metadata(PASSWORD)[0]['id']), SECRET)

    def test_unique_salt_nonce_and_protected_metadata(self):
        self.create()
        first = self.vault.path.read_bytes()
        a = self.vault.add(PASSWORD, 'exemple.test', 'session', SECRET)
        second = self.vault.path.read_bytes()
        b = self.vault.add(PASSWORD, 'exemple.test', 'session', 'autre-valeur-fictive')
        third = self.vault.path.read_bytes()
        offset = len(v.MAGIC)
        self.assertNotEqual(first[offset+16:offset+28], second[offset+16:offset+28])
        self.assertNotEqual(second[offset+16:offset+28], third[offset+16:offset+28])
        other = v.Vault(Path(self.temp.name)/'other'); other.create(PASSWORD)
        self.assertNotEqual(first[offset:offset+16], other.path.read_bytes()[offset:offset+16])
        self.assertNotEqual(a, b)
        rows = self.vault.metadata(PASSWORD)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r['status'] == 'stocke_sans_autorisation_utilisation' for r in rows))
        self.assertTrue(all('value' not in r for r in rows))

    def test_remove_and_persistent_reopen(self):
        self.create()
        identifier = self.vault.add(PASSWORD, 'exemple.test', 'session', SECRET)
        reopened = v.Vault(self.vault.directory)
        self.assertEqual(reopened.metadata(PASSWORD)[0]['id'], identifier)
        reopened.remove(PASSWORD, identifier)
        self.assertEqual(self.vault.metadata(PASSWORD), [])

    def test_create_refuses_overwrite_and_weak_password(self):
        with self.assertRaises(ValueError): self.vault.create('court')
        self.assertFalse(self.vault.path.exists())
        self.create()
        before = self.vault.path.read_bytes()
        with self.assertRaises(ValueError): self.vault.create(PASSWORD)
        self.assertEqual(self.vault.path.read_bytes(), before)

    def test_invalid_cookies_are_not_saved(self):
        self.create()
        for domain, name, value in [('https://exemple.test', 'x', SECRET), ('*.test', 'x', SECRET),
                                    ('.exemple.test', 'x', SECRET), ('exemple.test', 'a=b', SECRET),
                                    ('exemple.test', 'x', 'injection\r\nCookie: autre'),
                                    ('exemple.test', 'x', 'a;b'), ('exemple.test', 'x', 'x'*8193)]:
            with self.subTest(domain=domain, name=name), self.assertRaises(ValueError):
                self.vault.add(PASSWORD, domain, name, value)
        self.assertEqual(self.vault.metadata(PASSWORD), [])

    def test_outside_git_and_no_symlink_or_hardlink(self):
        repo = Path(self.temp.name)/'repo'; (repo/'.git').mkdir(parents=True)
        (repo/'.git/HEAD').write_text('ref: refs/heads/main')
        with self.assertRaises(ValueError): v.Vault(repo/'private')
        alias = Path(self.temp.name)/'alias'; alias.symlink_to(self.vault.directory)
        with self.assertRaises(ValueError): v.Vault(alias)
        self.create()
        linked = Path(self.temp.name)/'linked'; os.link(self.vault.path, linked)
        with self.assertRaises(ValueError): self.vault.metadata(PASSWORD)
        linked.unlink()
        target = Path(self.temp.name)/'target'; self.vault.path.rename(target)
        self.vault.path.symlink_to(target)
        with self.assertRaises(OSError): self.vault.metadata(PASSWORD)

    def test_atomic_failure_keeps_existing_ciphertext(self):
        self.create()
        before = self.vault.path.read_bytes()
        with patch.object(v.os, 'replace', side_effect=OSError('échec simulé')):
            with self.assertRaises(OSError): self.vault.add(PASSWORD, 'exemple.test', 'session', SECRET)
        self.assertEqual(self.vault.path.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.vault.directory.iterdir()), ['cookies.vault', 'vault.lock'])

    def test_bad_format_rejected_before_password_derivation(self):
        self.vault.path.write_bytes(b'pas un coffre')
        with patch.object(v, 'key_from') as derive, self.assertRaises(ValueError):
            self.vault.metadata(PASSWORD)
        derive.assert_not_called()

    def test_cli_owned_cookie_confirmation_and_no_secret_output(self):
        self.create()
        args = ['ajouter', '--state-dir', str(self.vault.directory)]
        with patch.object(v, 'hidden', side_effect=[PASSWORD, SECRET]), \
             patch('builtins.input', side_effect=['exemple.test', 'session', 'oui']), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(v.main(args), 0)
        self.assertNotIn(SECRET, output.getvalue())
        self.assertNotIn(PASSWORD, output.getvalue())
        self.assertEqual(len(self.vault.metadata(PASSWORD)), 1)

    def test_cli_refusal_never_asks_password_or_value(self):
        with patch.object(v, 'hidden') as hidden, patch('builtins.input', side_effect=['exemple.test', 'session', 'non']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(v.main(['ajouter', '--state-dir', str(self.vault.directory)]), 0)
        hidden.assert_not_called()
        self.assertFalse(self.vault.path.exists())

    def test_secret_input_refuses_echo_or_nonterminal(self):
        with patch('sys.stdin.isatty', return_value=False), self.assertRaises(ValueError):
            v.hidden('test')
        with patch('sys.stdin.isatty', return_value=True), \
             patch('getpass.getpass', side_effect=getpass.GetPassWarning('pas de TTY')), self.assertRaises(ValueError):
            v.hidden('test')

    def test_cli_interruption_and_missing_dependency(self):
        with patch.object(v, 'hidden', side_effect=KeyboardInterrupt()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(v.main(['creer', '--state-dir', str(self.vault.directory)]), 130)
        self.assertFalse(self.vault.path.exists())
        with patch.object(v, 'crypto', side_effect=ValueError('dépendance absente')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(v.main(['creer', '--state-dir', str(self.vault.directory)]), 1)


if __name__ == '__main__':
    unittest.main()
