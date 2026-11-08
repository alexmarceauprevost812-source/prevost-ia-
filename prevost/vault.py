"""Coffre local de cookies fournis explicitement ; aucune extraction ni transmission."""
import argparse
from contextlib import contextmanager
import fcntl
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import tempfile
import warnings

from .app import UI
from .guardian import now

DEFAULT_STATE = Path.home()/'.local/share/prevost-ia-local/vault'
MAGIC = b'PREVOST-VAULT-1\x00'
MAX_BYTES = 1_000_000
TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]{1,256}$")


def crypto():
    try:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    except ImportError:
        raise ValueError('Le coffre exige la dépendance optionnelle cryptography ; voir COFFRE.md.') from None
    return AESGCM, Scrypt, InvalidTag


def key_from(password, salt):
    if not isinstance(password, str) or not password or len(password.encode()) > 4096:
        raise ValueError('Phrase de passe requise, maximum 4096 octets.')
    _, Scrypt, _ = crypto()
    return Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(password.encode('utf-8'))


def validate_cookie(domain, name, value):
    try:
        domain = domain.lower().encode('idna').decode('ascii')
    except UnicodeError:
        raise ValueError('Domaine invalide.') from None
    if len(domain) > 253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                               for label in domain.split('.')):
        raise ValueError('Nom d’hôte exact requis, sans URL, point initial ni joker.')
    if not TOKEN.fullmatch(name):
        raise ValueError('Nom de cookie invalide.')
    if not isinstance(value, str) or len(value.encode()) > 8192 or any(
            ord(c) < 33 or ord(c) > 126 or c in ';,' for c in value):
        raise ValueError('Valeur de cookie invalide (8192 octets maximum, sans contrôle ni séparateur).')
    return {'domain': domain, 'name': name, 'value': value,
            'allowed_origin': 'https://' + domain, 'status': 'stocke_sans_autorisation_utilisation'}


class Vault:
    def __init__(self, directory=DEFAULT_STATE):
        self.directory = Path(directory).expanduser().absolute()
        for parent in (self.directory, *self.directory.parents):
            if (parent.is_symlink() or (parent/'.git').is_file()
                    or (parent/'.git/HEAD').exists() or parent.name == '.git'):
                raise ValueError('Coffre requis hors Git, sans lien symbolique.')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.path = self.directory/'cookies.vault'

    def private_open(self, name, flags):
        fd = os.open(self.directory/name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
            os.close(fd)
            raise ValueError('Fichier privé ordinaire appartenant à cet utilisateur requis.')
        os.fchmod(fd, 0o600)
        return fd

    @contextmanager
    def lock(self):
        fd = self.private_open('vault.lock', os.O_RDWR | os.O_CREAT)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def load(self, password):
        fd = self.private_open(self.path.name, os.O_RDONLY)
        with os.fdopen(fd, 'rb') as stream:
            blob = stream.read(MAX_BYTES + 1)
        if len(blob) > MAX_BYTES or not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 16 + 12 + 16:
            raise ValueError('Format de coffre invalide.')
        offset = len(MAGIC)
        salt, nonce = blob[offset:offset+16], blob[offset+16:offset+28]
        AESGCM, _, InvalidTag = crypto()
        key = key_from(password, salt)
        try:
            clear = AESGCM(key).decrypt(nonce, blob[offset+28:], MAGIC + salt)
            data = json.loads(clear)
        except (InvalidTag, ValueError, UnicodeError):
            raise ValueError('Coffre verrouillé : mot de passe incorrect ou fichier altéré.') from None
        if not isinstance(data, dict) or set(data) != {'cookies'} or not isinstance(data['cookies'], dict):
            raise ValueError('Contenu de coffre invalide.')
        return data, key, salt

    def save(self, data, key, salt):
        AESGCM, _, _ = crypto()
        nonce = secrets.token_bytes(12)
        clear = json.dumps(data, ensure_ascii=False).encode('utf-8')
        if len(clear) + len(MAGIC) + 44 > MAX_BYTES:
            raise ValueError('Coffre limité à 1 Mo.')
        blob = MAGIC + salt + nonce + AESGCM(key).encrypt(nonce, clear, MAGIC + salt)
        fd, name = tempfile.mkstemp(dir=self.directory, prefix='encrypted-')
        try:
            # Seules des données déjà chiffrées atteignent le disque temporaire.
            with os.fdopen(fd, 'wb') as stream:
                stream.write(blob)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def create(self, password):
        if len(password) < 16:
            raise ValueError('Choisir une phrase de passe d’au moins 16 caractères.')
        with self.lock():
            if self.path.exists() or self.path.is_symlink():
                raise ValueError('Un coffre existe déjà ; il ne sera pas remplacé.')
            salt = secrets.token_bytes(16)
            self.save({'cookies': {}}, key_from(password, salt), salt)

    def add(self, password, domain, name, value):
        cookie = validate_cookie(domain, name, value)
        with self.lock():
            data, key, salt = self.load(password)
            identifier = secrets.token_hex(12)
            data['cookies'][identifier] = {**cookie, 'created_at': now()}
            self.save(data, key, salt)
        return identifier

    def metadata(self, password):
        with self.lock():
            data, _, _ = self.load(password)
            # La valeur ne sort pas du coffre et n’est pas rendue à l’interface.
            return [{'id': identifier, **{k: item[k] for k in
                    ('domain', 'name', 'allowed_origin', 'status', 'created_at')}}
                    for identifier, item in data['cookies'].items()]

    def remove(self, password, identifier):
        with self.lock():
            data, key, salt = self.load(password)
            if identifier not in data['cookies']:
                raise ValueError('Identifiant absent du coffre.')
            del data['cookies'][identifier]
            self.save(data, key, salt)


def hidden(prompt):
    if not sys.stdin.isatty():
        raise ValueError('Terminal interactif requis pour une saisie secrète sans écho.')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            return getpass.getpass(prompt)
        except getpass.GetPassWarning:
            raise ValueError('Saisie masquée indisponible ; opération abandonnée.') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description='PRÉVOST — coffre local chiffré de vos propres cookies')
    parser.add_argument('mode', nargs='?', choices=['creer', 'ajouter', 'liste', 'retirer'])
    parser.add_argument('--state-dir', default=str(DEFAULT_STATE))
    args = parser.parse_args(argv)
    ui = UI()
    try:
        crypto()  # Pas de coffre créé si la dépendance est absente.
        mode = args.mode or ui.read('Coffre local : creer / ajouter / liste / retirer > ').strip()
        if mode not in ('creer', 'ajouter', 'liste', 'retirer'):
            raise ValueError('Commande de coffre inconnue.')
        vault = Vault(args.state_dir)
        if mode == 'creer':
            password = hidden('Nouvelle phrase de passe (16 caractères minimum) > ')
            confirmation = hidden('Répéter la phrase de passe > ')
            if not secrets.compare_digest(password.encode(), confirmation.encode()):
                raise ValueError('Les phrases de passe ne correspondent pas.')
            vault.create(password)
            ui.show('Coffre chiffré créé localement. Conserver votre phrase de passe : aucune récupération possible.')
        elif mode == 'ajouter':
            domain = ui.read('Domaine exact de votre compte (exemple : exemple.com) > ').strip()
            name = ui.read('Nom du cookie > ').strip()
            validate_cookie(domain, name, '')
            if not ui.confirm(f'Confirmez que ce cookie appartient à votre compte sur {domain} et que vous autorisez son stockage local chiffré. Cela n’autorise aucune utilisation par un outil.'):
                return 0
            password = hidden('Phrase de passe du coffre > ')
            # Vérifier le déverrouillage avant de demander le secret à enregistrer.
            vault.metadata(password)
            value = hidden('Valeur du cookie (masquée ; ne pas la coller dans le chat) > ')
            identifier = vault.add(password, domain, name, value)
            ui.show('Cookie enregistré localement, sans autorisation d’utilisation. Identifiant : ' + identifier)
        elif mode == 'liste':
            ui.raw(json.dumps(vault.metadata(hidden('Phrase de passe du coffre > ')), ensure_ascii=False, indent=2))
        else:
            identifier = ui.read('Identifiant du cookie à retirer > ').strip()
            if ui.confirm('Retirer du coffre le cookie ' + identifier + ' ?'):
                vault.remove(hidden('Phrase de passe du coffre > '), identifier)
                ui.show('Cookie retiré du coffre. Pour invalider la session, utiliser les paramètres du compte concerné.')
        return 0
    except (EOFError, KeyboardInterrupt):
        ui.show('Coffre refermé ; opération interrompue.')
        return 130
    except (OSError, ValueError) as error:
        # Ne jamais afficher le chemin d’entrée, le contenu brut ou les exceptions crypto.
        if isinstance(error, OSError):
            ui.show('Accès au coffre indisponible ; vérifier son existence et ses permissions.')
        else:
            ui.show(str(error))
        return 1
    finally:
        ui.reset()


if __name__ == '__main__':
    raise SystemExit(main())
