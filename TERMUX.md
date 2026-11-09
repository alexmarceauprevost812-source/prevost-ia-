# PRÉVOST v2 sur Termux

Installer Termux selon ses [instructions officielles](https://github.com/termux/termux-app#installation).
Garder le dépôt et le coffre dans le stockage privé de Termux, pas dans `/sdcard`.

## Installation

Dans Termux, récupérer le dépôt (s’il est encore privé, il exige votre accès GitHub) :

```bash
pkg install git
cd ~
git clone https://github.com/alexmarceauprevost812-source/prevost-ia-.git
cd prevost-ia-
bash install-termux.sh
mkdir -p ~/projets/essai
prevost --project ~/projets/essai
```

Le script installe `python` et le paquet officiel
[`python-cryptography`](https://github.com/termux/termux-packages/blob/master/packages/python-cryptography/build.sh).
Il ajoute `prevost` dans `$PREFIX/bin`, lié à ce dépôt. Une commande existante étrangère est préservée.
Il ne télécharge aucun modèle, ne lance aucun scan et ne crée aucun coffre personnel.
Réexécuter le script après avoir déplacé le dépôt. Il n’installe pas de service de fond.

## Coffre et programmation

```bash
prevost coffre creer
prevost coffre ajouter
prevost coffre secret
prevost coffre liste
prevost coffre voir
prevost reseau appareils
```

La phrase de passe et les valeurs sont saisies sans écho. Les secrets sont chiffrés
dans `~/.local/share/prevost-ia-local/vault/cookies.vault`. `voir` les affiche après
confirmation et déverrouillage ; ils restent visibles dans le défilement du terminal.
Le coffre n’est pas encore relié à `mon-secret-cookie` et ne collecte rien automatiquement.
Voir [COFFRE.md](COFFRE.md).

Sans Ollama, les outils manuels restent disponibles. Pour un service Ollama que
vous avez déjà configuré, utiliser `--ollama URL` ou `OLLAMA_HOST`. Une adresse
distante demande confirmation avant transmission du contexte. Aucun cookie du
coffre n’est ajouté à ce contexte. L’installation et les performances d’Ollama sur
Android ne sont pas validées par cette adaptation.

## Fonctions disponibles et limites

| Fonction | Dans Termux |
| --- | --- |
| Programmation et commandes confirmées | Python et outils réellement installés, dans les dossiers accessibles à Termux |
| Coffre chiffré | Paquet `python-cryptography` requis, saisie terminal obligatoire |
| Consultation des ID/IP/MAC enregistrés | `prevost reseau appareils`, aucune nouvelle sonde |
| Scan Nmap sur cible explicitement autorisée | `pkg install nmap` en option ; dépend des droits Android et des options du profil |
| Veille réseau automatique | Exige NetworkManager (`nmcli`) et les droits ARP ; indisponible dans une installation Termux standard |
| Diagnostic gardien | `prevost gardien diagnostic` ; stockage du dossier personnel, systemd signalé indisponible sans exécution, ports selon les permissions Android |

Le profil `/scan` reste `nmap -v -A` : son fonctionnement complet n’est pas garanti
sans les privilèges requis. Aucun contournement, passage automatique en root ou
remplacement silencieux du profil n’est ajouté. Les échecs restent signalés.
Les outils Kali, REA et Podman ne sont proposés que s’ils sont réellement présents.
Android peut arrêter le processus : aucune surveillance n’est garantie après cet arrêt.

Le diagnostic reconnaît Android via Python ou l’environnement Termux (`TERMUX_VERSION`
et `PREFIX`). Il mesure le système de fichiers du dossier personnel au lieu de `/`,
qui peut être une partition système distincte. Le rapport précise le chemin mesuré ;
il ne calcule pas l’espace du stockage partagé ni de toutes les partitions Android.
Les mises à jour consultées restent celles du cache APT Termux, pas celles d’Android.

## Validation

```bash
python -B -m unittest discover -s tests -q
```

Le lanceur et ses sous-commandes sont testés sous Linux, avec des dossiers temporaires.
L’installation de paquets et l’exécution sur un téléphone Android réel restent à valider.
