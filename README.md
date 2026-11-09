# PRÉVOST IA Local — v2

La branche `v2` réunit les historiques de `main` et `feature/prevost-local-v1`, dont les fichiers étaient identiques au moment de la réunion. La branche `supabase` est déjà incluse dans `main` ; elle ne contient aucune intégration Supabase supplémentaire. Cette base v2 conserve les fonctions existantes et ajoute le choix du dossier d’historique avec `--state-dir`.

Assistant Python de programmation locale avec Ollama. Le cœur fonctionne sans dépendance Python externe ; le coffre optionnel utilise `cryptography`. Python 3.10+ et Linux sont requis pour l’arrêt des groupes de processus.

## Lancement

Pour Android, voir la [version Termux](TERMUX.md) : installateur, lanceur `prevost`, coffre et limites réseau.

Depuis ce dépôt :

```bash
python3 -m prevost --diagnostic
python3 -m prevost --project ~/mon-projet --ollama http://127.0.0.1:11435
```

Le dossier du projet doit déjà exister. L’adresse vient de `--ollama`, puis de `OLLAMA_HOST`, puis de `http://127.0.0.1:11434`. Le diagnostic affiche l’adresse effective et interroge `/api/tags`. Il n’installe et ne télécharge aucun modèle. La sélection proposée correspond uniquement aux modèles retournés par ce service ; `--model NOM` doit aussi correspondre à cette liste.

```bash
python3 -m prevost --project /tmp/mon-projet --model NOM_INSTALLE --timeout 30
```

`--timeout` fixe le délai maximal des commandes (300 secondes au maximum). `--http-timeout` fixe le délai d’inactivité réseau. `/modeles` permet de réessayer la connexion ou de changer de modèle.

## Utilisation

- Texte libre : conversation en français, réponse affichée au fil des fragments Ollama.
- `/lire chemin` : lire un fichier UTF-8 et l’ajouter au contexte de conversation.
- `/ecrire chemin` : saisir un fichier complet ; terminer par `.fin` sur sa propre ligne.
- `/coder demande` : demander à Ollama un plan de fichiers et de commandes. Le plan apparaît progressivement ; les différences de chaque fichier et chaque commande nécessitent ensuite un `oui` explicite.
- `/commande python3 programme.py` : proposer puis exécuter une commande après confirmation.
- `/scan [cible]`, `scan complet` ou `scam complet` : demander une cible précise et proposer `nmap -v -A CIBLE` avec une autorisation distincte, même sans modèle disponible.
- `/historique` : afficher les derniers échanges ; `/aide` et `/quitter`.

Pour modifier un fichier avec Ollama, le lire d’abord avec `/lire`, puis utiliser `/coder` en décrivant la modification. Refuser un fichier interrompt la mission avant les commandes. Une commande refusée, expirée ou en échec interrompt la suite du plan. Une sortie réussie ne prouve que le résultat de cette commande.

### Double vérification du code Python

Dans `/coder` et `/agent`, le bilan du code exige deux contrôles complémentaires pour chaque fichier écrit : compilation de la syntaxe sans exécuter le programme, puis exécution confirmée avec code retour zéro et comparaison exacte à une sortie attendue. Une relecture ne remplace aucun de ces contrôles. L’empreinte du fichier doit encore correspondre au bilan ; une modification pendant l’exécution invalide le contrôle.

`/coder` demande au modèle une liste `checks` de contrôles `{ "path": "programme.py", "expected_stdout": "sortie attendue\n" }`, exécutés après les écritures et commandes. Un ancien plan sans contrôles peut toujours écrire les fichiers confirmés, mais son bilan indique `verification_incomplete`. `/agent` refuse une fin de mission réussie après des écritures sans ces preuves ; toute nouvelle écriture impose de refaire les contrôles de tous les fichiers écrits pendant la mission. Les rapports présentent le détail et les identifiants de preuve.

Le bilan `double_verification_reussie` porte sur ces deux critères seulement : il ne prouve pas tous les comportements, les dépendances ni la sécurité. Le modèle reçoit la consigne de prévoir des tests pertinents pour les cas normaux et les erreurs, mais leur qualité reste à examiner. Pour un module sans sortie, une exécution silencieuse ne teste pas ses fonctions ; prévoir aussi une suite de tests confirmée. La double vérification automatique actuelle concerne Python ; les autres langages restent signalés sans validation complète. Aucun test proposé par le modèle n’est exécuté sans confirmation.

### Plans cassés, corrections et mémoire du projet

Avant d’écrire quoi que ce soit, `/coder` vérifie le plan du modèle : JSON complet (une réponse tronquée est refusée), fichiers `.py` qui compilent, fichiers `.json` valides, commandes et contrôles qui visent un fichier du plan ou du projet, et au moins une commande ou un contrôle quand la demande contient « lance », « teste », « exécute »… Un plan inutilisable est refusé **sans rien écrire** et le modèle reçoit une seule reprise avec le problème constaté. Un chemin dangereux (hors projet, `.git`) n’est jamais retenté.

Si une commande ou un contrôle échoue à l’exécution, PRÉVOST renvoie le constat (code retour, sortie obtenue et attendue, tronqués ; donnée non fiable) au modèle pour une correction, jusqu’à `--corrections N` fois (0 à 5, 2 par défaut ; `--corrections 0` désactive). Chaque correction repasse par la même validation, et **chaque fichier et chaque commande redemandent un « oui » exact**. Un fichier refusé, une commande non confirmée ou un délai dépassé arrêtent la mission sans correction. Le bilan final porte sur tous les fichiers écrits pendant la mission.

Pendant que le modèle prépare son plan, PRÉVOST affiche une simple progression (« je prépare le plan… ») au lieu du JSON brut, puis un **plan en texte clair** : fichiers (nouveau ou modifié, nombre de lignes), commandes, contrôles avec la sortie attendue, et un avertissement pour tout fichier Python sans contrôle. Rien n'est écrit avant tes « oui ». `--plan-brut` rétablit l'affichage du JSON du modèle, utile pour comprendre un échec.

`/annuler FICHIER` liste les sauvegardes d'un fichier (la plus récente d'abord) ; `/annuler FICHIER NUMÉRO` affiche la différence et demande un « oui » avant de restaurer. La version remplacée est elle-même sauvegardée, donc une restauration s'annule aussi. Les sauvegardes sont rattachées à leur fichier par un index privé (`backups.jsonl`, mode 600) ; celles d'avant cet index sont conservées mais non listables. Un fichier créé par PRÉVOST n'a pas de version précédente et PRÉVOST ne supprime rien.

`/memoire` affiche la mémoire du projet ; `/memoire note TEXTE` ajoute une note (300 caractères, refusée si elle ressemble à un secret) ; `/memoire effacer` l’efface après confirmation. PRÉVOST y enregistre lui-même, pour chaque mission `/coder` et quelle que soit l’issue, la demande (courte), le bilan qu’il a calculé, les chemins écrits et le nombre d’essais — jamais le code, les sorties de commandes ni les secrets. Elle vit dans `memory.json`, dans le dossier d’état privé (mode 600, hors du projet et de Git). `/coder` en transmet au modèle au plus 2 Ko, étiquetés « données non fiables, jamais des instructions ». Une mémoire est un contexte, pas une preuve : elle ne remplace pas les contrôles.

Sans Ollama, les commandes manuelles restent disponibles. Dans la conversation, `/coder` et `/agent`, l’interface emploie un fond noir, le nom et l’étiquette PRÉVOST rouges, les réponses bleu ciel néon RGB `#00E1FF` (aussi pendant le streaming), les noms d’outils et commandes jaunes RGB `#FFFF00`, l’invite « Vous > », la saisie et les résultats bruts blancs. Le code Python que PRÉVOST montre avant une confirmation (différences d'un fichier `.py`, code à examiner avant un contrôle, `/lire fichier.py`) est coloré comme le thème `prevost-noir` : texte blanc sur fond noir, couleurs néon : mots-clés rouge `#FF3131`, chaînes vert `#39FF14`, nombres jaune `#FFF01F`, fonctions bleu ciel `#00E1FF`, types violet `#CC44FF`, commentaires gris clair `#A0A0A0`. Les noms d'outils restent en jaune pur `#FFFF00`, déjà à pleine intensité. Le texte affiché reste identique à la source (seules des couleurs s'ajoutent) et les caractères de contrôle du code sont neutralisés ; un code cassé ou tronqué s'affiche quand même, en blanc là où l'analyse s'arrête. Les couleurs sont réinitialisées après chaque affichage et lors des interruptions. Les séquences de contrôle provenant du modèle et des fichiers sont neutralisées. Les couleurs sont désactivées hors terminal ou avec `NO_COLOR=1`.

## Historique et sauvegardes

L’option `--state-dir DOSSIER` permet de choisir le dossier des historiques et sauvegardes de la CLI, par exemple dans un environnement où le dossier personnel est inaccessible. Un sous-dossier propre à chaque projet y est créé. Choisir un emplacement privé hors Git ; réutiliser le même dossier pour retrouver l’historique. Cette option ne change pas les emplacements propres au coffre, au gardien ou à la veille réseau.

Le [coffre local](COFFRE.md), accessible par `/coffre`, conserve vos cookies, mots de passe et jetons fournis explicitement, chiffrés par phrase de passe sur votre appareil. Le mode `secret` ajoute un secret et `voir` révèle sa valeur dans le terminal après confirmation et déverrouillage. Les valeurs ne sont pas ajoutées au modèle ou à l’historique. Le stockage n’autorise pas l’utilisation par un outil ; aucun branchement à `mon-secret-cookie` n’est encore effectué.

Les échanges, résultats de commandes et sauvegardes des fichiers modifiés restent dans `~/.local/share/prevost-ia-local/<empreinte-du-chemin-du-projet>/`, hors du dépôt. À la réouverture du même dossier, les vingt derniers messages sont repris, avec une lecture bornée à 200 Ko d’historique. Le fichier de journal est privé (mode 600), son dossier en mode 700. Les sauvegardes permettent une restauration manuelle ; aucune suppression automatique n’est effectuée. Déplacer le projet change son identifiant de mémoire.

Le `.gitignore` exclut aussi les historiques, mémoires locales, secrets, `.env`, poids GGUF et rapports d’audit éventuellement créés dans le dépôt. Ne pas utiliser `git add -f` pour ces données.

## Contrôle et limites

Les outils de fichiers sont limités au dossier choisi : chemins relatifs, refus des traversées, liens symboliques et physiques, métadonnées `.git`, fichiers non UTF-8 et contenus de plus de 200 Ko. Chaque écriture affiche les différences et exige une confirmation. L’application ne fournit aucune commande de suppression.

Les commandes sont exécutées **sur l’hôte avec les droits de votre compte**, après présentation du dossier, des arguments et du délai. Elles ne sont pas isolées : elles peuvent accéder au réseau, supprimer des données, transmettre des fichiers et modifier le système. La confirmation couvre exactement la commande affichée ; inspecter aussi le programme ou les tests appelés, surtout s’ils ont été générés. Aucun shell implicite, aucune saisie interactive transmise au sous-processus. Un shell peut néanmoins être lancé explicitement si vous le confirmez. Les descendants du même groupe sont arrêtés après la commande ou à l’expiration ; un processus qui se détache peut échapper à cet arrêt.

La sortie est collectée dans un fichier temporaire et affichée à la fin, limitée à 200 Ko à la lecture. Le fichier temporaire peut grossir pendant l’exécution : éviter les commandes produisant une sortie illimitée. Le délai réseau est un délai d’inactivité, pas une durée totale de génération. Le journal local peut grossir au fil des missions.

Les données de fichiers et résultats ne sont jamais exécutés comme instructions par l’application. Une consigne système demande aussi au modèle de les traiter comme données ; cela ne garantit pas l’immunité du modèle aux injections. Chaque action proposée reste soumise à votre confirmation. Ne pas lire de secrets dans une conversation. Une adresse Ollama distante exige une confirmation de transmission avant utilisation ; aucune redirection HTTP ni proxy implicite n’est suivi.

Les outils Kali/REA du registre sont décrits dans [OUTILS.md](OUTILS.md). L’inventaire réseau consenti est décrit dans [RESEAUX.md](RESEAUX.md). Le scan actif Nmap est proposé uniquement sur demande explicite de l’utilisateur, avec cible exacte et confirmation distincte. Aucun audit n’est déclenché par l’inventaire ou une réponse du modèle. Aucun téléchargement de modèles ou changement des lanceurs installés n’est ajouté.

## Vérification

```bash
python3 -B -m unittest discover -s tests -v
```

Voir [VALIDATION.md](VALIDATION.md) pour distinguer les essais locaux réels, les simulations et les blocages Ollama.

## Gardien numérique — diagnostic du PC LexOS

Dans Termux, le gardien identifie son environnement Android, mesure le stockage du dossier personnel et indique les contrôles systemd comme indisponibles sans les exécuter. Les autres collectes restent soumises aux permissions Android ; voir [TERMUX.md](TERMUX.md).

L’agent de programmation est conservé. Un module distinct fournit un diagnostic déterministe, sans Ollama et sans commandes proposées par un modèle :

```bash
python3 -m prevost.guardian diagnostic
python3 -m prevost.guardian diagnostic --json
```

Il présente l’inventaire explicite du seul appareil courant (`pc-local`), le périmètre autorisé, l’espace disque de `/`, les unités systemd échouées (utilisateur et système), les ports TCP/UDP en écoute et les mises à jour signalées dans le cache APT. Aucun scan, aucune requête aux appareils voisins, aucun rafraîchissement APT, aucun changement système. Le diagnostic seul ne crée aucun journal. L’identité `pc-local` désigne l’environnement où la commande tourne, pas une preuve que l’ensemble du PC est visible depuis un bac à sable.

Chaque collecte conserve sa source, sa sortie, ses erreurs et son état. Une collecte refusée est indisponible, même quand le programme termine avec le code 0. Les recommandations distinguent constat et point à vérifier, précisent la confiance et le retour arrière. Aucune recommandation n’est appliquée. Puisqu’il n’y a aucun changement système, le retour arrière consiste actuellement à ne rien restaurer ; toute future correction devra définir son propre plan de restauration avant confirmation.

### Veille explicite

```bash
# Une collecte avec journal et référence pour la prochaine fois
python3 -m prevost.guardian veille

# Trois collectes à une minute d’intervalle
python3 -m prevost.guardian veille --cycles 3 --interval 60

# Boucle au premier plan, jusqu’à Ctrl+C
python3 -m prevost.guardian veille --cycles 0 --interval 60
```

Seule la veille écrit ses propres données locales : `~/.local/share/prevost-ia-local/guardian/watch.json` contient le dernier diagnostic et la référence ; `incidents.jsonl` contient les alertes et le journal des collectes. Les fichiers sont de mode 600, le dossier de mode 700. `--state-dir DOSSIER` choisit un autre emplacement. Garder ces données privées et hors Git. Aucun service de fond ni démarrage automatique n’est installé. Quand la commande s’arrête, la surveillance s’arrête ; PRÉVOST ne prétend pas protéger les périodes non observées.

Les alertes sont affichées dans le terminal et inscrites au journal, sans notification externe. Elles signalent les changements des listes observées, le passage sous 10 % d’espace libre et les échecs de collecte. Le premier relevé sert de référence ; les échecs et anomalies de disque/services présents dès ce relevé sont signalés immédiatement. L’espace disque ne déclenche pas une alerte à chaque octet : seul le seuil est comparé.

La déduplication persiste entre lancements : une même empreinte « contrôle + état observé » est signalée une seule fois dans ce journal, même si elle réapparaît après une résolution. Cela réduit les répétitions, mais ne compte pas les récidives. Les variations entre deux collectes peuvent être manquées. Le journal et la liste d’empreintes ne sont pas purgés automatiquement. Lancer une seule instance de veille par dossier d’état ; aucune coordination entre instances concurrentes n’est implémentée.

### Limites actuelles

- Inventaire limité au PC courant ; aucun ajout ou suivi d’autre appareil dans cette version.
- Disque racine seulement, sans SMART ni surveillance de contenu des fichiers.
- Services échoués seulement, sans liste personnalisée des services attendus.
- Ports de l’espace réseau visible seulement ; aucune attribution à un programme ni preuve d’exposition externe.
- Mises à jour issues du cache APT : fraîcheur et pertinence non garanties, aucune évaluation automatique des vulnérabilités.
- Le diagnostic constate des faits de collecte, pas une certification de sécurité. Les collectes indisponibles restent inconnues.
- Aucun pare-feu, redémarrage, installation, suppression ou autre mesure de protection sensible n’est exécuté par ce module.

## Agent utilisant des outils

Le registre et la nouvelle boucle de mission sont documentés dans [OUTILS.md](OUTILS.md). Exemple :

```bash
python3 -m prevost.agent catalogue --project /chemin/du/projet
python3 -m prevost.agent demo --project /un/dossier/temporaire
```

Dans la conversation : `/outils` et `/agent demande`. Les rapports restent locaux et exclus de Git.

## Inventaire des réseaux approuvés

`python3 -m prevost.network veille` (ou `/veille-reseau` dans la conversation) identifie les connexions, demande une seule fois leur périmètre et l’autorisation explicite, puis inventorie automatiquement les réseaux approuvés. Les nouveaux candidats restent « à valider » ; aucune autorisation d’audit n’est déduite de la découverte.

`python3 -m prevost.network arreter` arrête la veille ; `python3 -m prevost.network retirer --network IDENTIFIANT` retire une autorisation. `/reseaux`, `/arreter-reseau` et `/retirer-reseau IDENTIFIANT` sont aussi disponibles. L’état reste privé hors Git. Voir [RESEAUX.md](RESEAUX.md) pour les commandes d’approbation, les prérequis et les limites.

## Scan Nmap demandé par l’utilisateur

Saisir `scan complet` ou même `scam complet` ouvre un dialogue déterministe, sans transmettre cette demande à Ollama : choisir une IPv4 ou un nom DNS exact, vérifier la commande et confirmer avec `oui` que ce scan actif est autorisé sur cette cible. `/scan scanme.nmap.org` ouvre directement la même proposition. Aucune cible n’est déduite de l’historique ou de l’inventaire. Une réponse du modèle contenant ces mots ne déclenche rien.

Le profil demandé est exactement `nmap -v -A CIBLE`. `-A` active versions, scripts par défaut, détection du système et traceroute selon les droits disponibles ; ce profil conserve la sélection habituelle de 1 000 ports TCP, sans couvrir tous les ports ni UDP. Voir les documentations officielles des [options Nmap](https://nmap.org/book/man-briefoptions.html) et de la [sélection des ports](https://nmap.org/book/man-port-specification.html). Seule une cible est acceptée ; URL, CIDR, plage et options supplémentaires sont refusés par `/scan`. Les commandes manuelles `/commande` conservent leur fonctionnement et leur confirmation habituels.

Le délai est celui de `--timeout` (30 secondes par défaut, maximum 300) ; pour laisser davantage de temps, relancer PRÉVOST avec `python3 -m prevost --project . --timeout 300`. Les sorties sont affichées à la fin et conservées localement dans l’état privé du projet, jamais envoyées automatiquement au modèle. Un échec de résolution est signalé comme une absence de scan même si Nmap retourne 0. Aucun recours automatique à `sudo` et aucun changement de cible si la commande échoue.



## Samsung Recovery — PRÉVOST V20

L’[outil Python Samsung Recovery](samsung-recovery/README-V20.md) fournit une détection
USB automatique, l’identification des transports MTP/ADB/Recovery, l’analyse des rapports
V17/V18/V19 et un assistant de récupération officielle Google/Samsung/Bell. Les fonctions
de PRÉVOST IA ci-dessus sont conservées.

```bash
cd samsung-recovery
python3 prevost-samsung recuperation
python3 prevost-samsung recuperation --diagnostic
python3 prevost-samsung recuperation --rapport
python3 -m unittest discover -s tests -v
```

Le menu terminal propose V20 au choix 11. Chaque collecte crée un rapport JSON/TXT et,
en mode complet, des demandes Samsung/Bell non envoyées. Le mode `--rapport` consulte
seulement le dernier relevé local. Les anciennes commandes V16/V18/V19 restent disponibles.
Aucun contournement FRP, effacement, flash, changement du téléphone ni extraction de secrets.
Sans compte Google antérieurement synchronisé ou solution de propriété acceptée par le
prestataire officiel, la remise en service reste bloquée ; aucun déblocage garanti.

Les [conclusions V20](samsung-recovery/rapports/v20/RAPPORT-V20.md), les sources et 90 tests
Samsung sont inclus. Les rapports bruts du téléphone et les justificatifs personnels restent
locaux. Voir la [validation de publication](samsung-recovery/VALIDATION-PUBLICATION.md).


## Samsung V21 — diagnostic USB et rapports masqués

Le [diagnostic V21](samsung-recovery/README-V21.md) complète V20 avec des mesures de
restrictions du processus, de listener local, de permissions des nœuds USB et des états
ADB/MTP. Il conserve les commandes antérieures et ajoute le choix 12 au menu Samsung.

```bash
cd samsung-recovery
./prevost-samsung diagnostic-v21
./prevost-samsung diagnostic-v21 --rapport
```

Chaque collecte crée un rapport privé et une archive `partage.zip` par liste blanche.
Seule cette archive est destinée à être transmise ; la détection USB ne prouve aucun
accès aux données. Aucun changement téléphone ou contournement FRP.

[Résultats V21 et limites](samsung-recovery/rapports/v21/RAPPORT-V21.md) : 114 tests
Samsung réussis, dont 24 nouveaux. Les 91 tests de l’application IA existante ont aussi
été lancés : 89 réussis, deux lancements CLI bloqués par l’historique en lecture seule
dans le sandbox. Cette version est préparée sur `feature/samsung-recovery-v21`, en
pull request avant fusion. Aucun rapport privé ou justificatif personnel publié.
