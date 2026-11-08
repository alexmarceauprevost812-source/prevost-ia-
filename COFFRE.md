# Coffre local privé

Le coffre reste sur votre appareil. Il ne fait aucun appel réseau, synchronisation, téléchargement ou envoi au modèle. Le mot de passe n’est jamais écrit sur disque. Les valeurs de cookies ne sont jamais affichées ni ajoutées aux historiques de conversation ou d’outils. Les métadonnées (domaine, nom, date) sont aussi chiffrées au repos ; leur consultation nécessite le mot de passe.

Cette première version accepte une saisie explicite de cookies appartenant à vos propres comptes. Elle ne recherche ni n’extrait les bases de cookies d’un navigateur et n’intercepte aucune session. Le branchement à Themus ou à un outil de connexion reste à définir avec le lien/dossier de l’application et le compte concerné. Aucun cookie n’est fourni à un outil par cette version. Chaque enregistrement porte le statut `stocke_sans_autorisation_utilisation` ; consentir au stockage n’autorise pas son utilisation future.

## Utilisation

Dans le dépôt :

```bash
python3 -m prevost.vault creer
python3 -m prevost.vault ajouter
python3 -m prevost.vault liste
python3 -m prevost.vault retirer
```

La commande `/coffre` dans PRÉVOST ouvre le même menu, sans passer par Ollama. Ne placer ni cookie ni mot de passe après `/coffre` ou dans une demande au modèle. Le domaine et le nom se saisissent normalement ; les valeurs de cookie et phrases de passe se saisissent uniquement dans les invites masquées. Il n’existe aucun argument de ligne de commande pour transmettre un secret. Une saisie sans terminal ou un échec de masquage est refusé.

`creer` demande une phrase de passe d’au moins 16 caractères, puis sa répétition. Une phrase longue et unique est préférable. Aucun mécanisme de récupération n’existe : conserver cette phrase de passe dans un endroit sûr.

`ajouter` exige le domaine exact (sans URL ni joker), le nom du cookie, la confirmation qu’il appartient à votre compte et l’autorisation de stockage local, puis le mot de passe et la valeur masquée. Les valeurs sont limitées à 8192 octets et les contrôles/séparateurs sont refusés. Les doublons sont conservés séparément. La suppression demande une confirmation et le mot de passe. Supprimer un cookie du coffre ne révoque pas la session sur le site : cette révocation se fait dans les paramètres du compte.

Le coffre est optionnel : si nécessaire, installer sa dépendance dans votre environnement Python avec `python3 -m pip install -r requirements-vault.txt`. PRÉVOST n’installe rien automatiquement. L’installation de dépendances peut accéder à un dépôt de paquets ; l’utilisation du coffre elle-même n’effectue aucune connexion.

## Stockage et chiffrement

Chemin par défaut : `~/.local/share/prevost-ia-local/vault/cookies.vault`. Le dossier est de mode `700` et les fichiers de mode `600`. Le coffre refuse les chemins dans un dépôt Git, les liens symboliques et les fichiers à liens physiques multiples. `.gitignore` exclut aussi les fichiers `*.vault`. L’option `--state-dir DOSSIER_PRIVE` permet de choisir un autre dossier local hors Git ; ne pas choisir un dossier synchronisé dans un nuage.

Le chiffrement est AES-256-GCM avec un nonce aléatoire de 12 octets renouvelé à chaque écriture. Scrypt dérive une clé de 32 octets depuis la phrase de passe et un sel aléatoire de 16 octets (`N=131072`, `r=8`, `p=1`). L’en-tête et le sel sont authentifiés. Le format impose ces paramètres ; un fichier modifié ne peut pas imposer un coût de dérivation arbitraire. Un mauvais mot de passe ou une modification des données chiffrées ferme le coffre avec une erreur générique. Les primitives sont celles de [cryptography : AES-GCM](https://cryptography.io/en/stable/hazmat/primitives/aead/) et [Scrypt](https://cryptography.io/en/stable/hazmat/primitives/key-derivation-functions/#scrypt).

Les écritures sont verrouillées entre processus et remplacent atomiquement le fichier. Les fichiers temporaires contiennent uniquement du contenu déjà chiffré, jamais de copie en clair. Taille maximale : 1 Mo. Aucun coffre réel n’est créé par l’installation ou les tests ; l’utilisateur le crée lui-même dans son terminal.

Les données déchiffrées existent temporairement dans la mémoire du processus pendant une opération ; Python ne garantit pas leur effacement physique immédiat ni l’absence de copie dans l’espace d’échange. Le chiffrement au repos ne protège pas d’un appareil déjà compromis ou d’un utilisateur administrateur pouvant observer la saisie. Utiliser aussi le verrouillage et le chiffrement du disque de l’appareil. Cette fonction n’est pas une expertise de sécurité indépendante.

## Validation

Les tests utilisent exclusivement des phrases de passe et cookies fictifs dans des dossiers temporaires. Le chiffrement AES-GCM, Scrypt, les écritures et les modes des fichiers sont réellement exécutés. Aucun profil navigateur ni compte réel n’est lu. Les tests de saisie sont simulés ; l’apparence dans le terminal utilisateur et l’intégration Themus restent à valider séparément.
