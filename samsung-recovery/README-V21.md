# PRÉVOST Samsung V21 — diagnostic USB et environnement

Python 3.9+, Linux, bibliothèque standard. V21 ajoute **12 — DIAGNOSTIC SAMSUNG V21**
au menu principal ; les commandes et assistants V16 à V20 sont conservés.

```bash
./prevost-samsung diagnostic-v21
./prevost-samsung diagnostic-v21 --rapport
./prevost-samsung diagnostic-v21 --label ubuntu --delai 15
./prevost-samsung diagnostic-v21 --rapport --prive
```

Le lancement collecte et enregistre un dossier unique sous `rapports/v21/diagnostic-*`.
`--rapport` lit le dernier relevé V21 sans sonde ni écriture ; code 1 si aucun rapport.
L'affichage est masqué par défaut (`--partage` facultatif). `--prive` affiche les détails
locaux sensibles. Les deux modes sont exclusifs. L'étiquette `local|ubuntu|codex` est
déclarative ; elle n'établit pas à elle seule l'environnement réel ou la cause d'un échec.
`--sans-adb`, `--sans-mtp` et `--delai 1..60` restent disponibles. V21 refuse `--watch`,
`--serial` et le drapeau V20 `--diagnostic` pour éviter des comportements ambigus.

## Ce qui est mesuré

- Samsung visibles dans sysfs : interfaces, pilotes, endpoints et VID/PID. Le produit
  générique ne certifie pas le modèle SM-G990W2 déclaré et ne prouve aucun accès aux données.
- Existence et métadonnées du nœud USB : permissions apparentes, propriétaire/groupe,
  accès avec les identifiants effectifs. Aucun nœud n'est ouvert pour écriture.
- Restrictions de processus : uniquement NoNewPrivs, Seccomp et Seccomp_filters.
- Possibilité de créer puis écouter sur une socket loopback éphémère, fermée immédiatement.
  Aucun trafic externe ni service permanent. Un refus EPERM/EACCES précède l'accès téléphone.
- Sondes V20 conservées : `lsusb -d 04e8:`, `adb devices -l`, `gio mount -li`, et attributs
  de racine GIO uniquement sur un montage lié à un unique port Samsung. Aucun parcours de fichiers.
  ADB peut démarrer son serveur local et employer ses clés habituelles.

Seccomp actif ne prouve pas à lui seul une opération bloquée. Un listener local refusé,
un nœud absent du namespace, des droits de nœud insuffisants, une liste ADB vide, l'état
`unauthorized`, `no permissions` et les erreurs de session GIO ont des constats distincts.
V21 n'attribue pas automatiquement toute erreur à Ubuntu, udev, Codex ou FRP.
Un port USB explicite dans ADB prime ; une série sans port doit correspondre à un seul
Samsung. Une série dupliquée ou un port discordant ne permet pas d'associer Recovery.
Une réponse GIO réussie démontre au plus des métadonnées de racine, pas l'accès aux fichiers.

## Rapports privés et partage

Le dossier de collecte est privé (0700), ses fichiers 0600 :

- `rapport-prive.json` et `rapport-prive.txt` : sorties exactes, interfaces et preuves locales ;
- `partage/rapport.json` et `partage/rapport.txt` : projection par liste blanche ;
- `partage/demande-samsung.txt` et `partage/demande-bell.txt` : modèles génériques non envoyés ;
- `partage/SHA256SUMS`, `partage.zip` et `SHA256SUMS` : vérification des fichiers et archive dédiée.

**Seul `partage.zip` est destiné à être transmis.** Il ne contient ni rapports privés,
ni empreintes de ceux-ci, ni séries, URI MTP, bus/ports, chemins personnels, UID/GID,
sorties brutes ou noms personnalisés d'appareils. Les Samsung y sont nommés Samsung-1,
Samsung-2, etc. VID/PID, classes USB, états et codes utiles au diagnostic restent visibles.
Les rapports historiques restent locaux ; leur synthèse de partage donne des compteurs.

Le choix 8 « Export ZIP » reste un export local complet V16–V21 contenant des données
privées historiques. Cet export n'est pas l'archive de partage. Le choix 7 affiche aussi
la version masquée du dernier V21, tout en conservant l'accès historique aux autres versions.
Les dossiers générés sont ignorés par Git. Aucun rapport privé, justificatif personnel ou
sortie brute n'est publié dans la pull request.

## Démarches et limites

L'assistant Google et les demandes Samsung/Bell de V20 sont conservés dans la commande
`recuperation` et dans les rapports V21. Aucune saisie de mot de passe, cookie ou jeton,
authentification automatisée, vérification de compte ou formulaire envoyé. Les sources
officielles portent leur date de consultation ; V21 ne prétend pas les revalider en ligne.
Sans ancien compte synchronisé ou solution acceptée par le prestataire officiel,
l'outil ne peut pas remettre le téléphone en service. Aucun déblocage garanti.
Aucun changement du téléphone, de mode USB, de règles udev ou de configuration système ;
aucun flash, effacement, reset, redémarrage ou paquet sideload.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

Voir `rapports/v21/RAPPORT-V21.md` pour les essais réels, les simulations et les limites.
La branche GitHub est `feature/samsung-recovery-v21`. La pull request présente les résultats
avant fusion ; aucun changement direct de main et aucune fusion automatique.
