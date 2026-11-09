# Validation locale — 8 novembre 2026

## Résultats obtenus

Douze tests `unittest` réussis avec Python local :

- Mission complète avec réponse de modèle **simulée**, création réelle d’un programme Python, exécution réelle en sous-processus et vérification exacte de `Bonjour PRÉVOST\n`, code retour 0 ; reprise réelle de l’historique.
- Mission complète via l’interface en mode sans Ollama : saisie d’un fichier dans un dossier temporaire, confirmation, exécution réelle de Python et sortie `MISSION_OK` vérifiée.
- Refus de commande sans exécution, arrêt réel au délai maximal et conservation d’un code retour non nul avec sa sortie.
- Lecture/écriture réelles, refus d’écriture, sauvegarde avant modification, détection de modification concurrente, rejet des chemins hors projet et liens symboliques.
- Historiques distincts par projet et journal de mode 600.
- Décodage des fragments NDJSON et détection de flux incomplet : **transport simulé en mémoire**, sans serveur Ollama.
- Choix parmi modèles retournés et refus d’un modèle absent : **liste simulée**.
- Refus d’un plan invalide avant toute création de fichier : **modèle simulé**.

Les fichiers de ces missions sont temporaires et ne sont pas livrés dans le dépôt.

## Essai réel Ollama bloqué

Commande réellement exécutée :

```bash
python3 -B -m prevost --diagnostic --http-timeout 3
```

Adresse effective issue de `OLLAMA_HOST` : `http://127.0.0.1:11435`.
Résultat : `urlopen error [Errno 1] Operation not permitted`, code retour 1.
Cette session interdit les sockets locales. Cela ne démontre ni que le service est arrêté ni qu’il fonctionne. Aucun modèle installé n’a pu être confirmé. Aucune conversation, génération de code ou sélection de modèle réelle avec Ollama n’est déclarée validée.

Sur le terminal LexOS disposant de l’accès réseau local : lancer le diagnostic, sélectionner un modèle retourné, créer un dossier temporaire avec `mktemp -d`, puis lancer `python3 -m prevost --project CE_DOSSIER --ollama http://127.0.0.1:11435`. Demander avec `/coder` un programme affichant `Bonjour PRÉVOST`, examiner et confirmer les différences puis la commande. Vérifier la sortie et rouvrir le même dossier pour contrôler la reprise.

## Non vérifié

Couleurs visuelles dans un terminal graphique, génération réelle Ollama, serveur distant, processus se détachant du groupe et résistance à un acteur modifiant simultanément l’arborescence pendant une écriture. Les vérifications de chemin et de contenu réduisent les erreurs courantes mais ne constituent pas une isolation de sécurité face à cet acteur.

Aucun lanceur installé n’a été modifié. Aucune publication GitHub n’est revendiquée.

## Extension gardien local

18 tests réussis au total après ajout du diagnostic et de la veille. Les six nouveaux tests couvrent : refus netlink malgré un code retour 0, outil absent, commandes de collecte fixes et locales, seuil disque, changement simulé de port, déduplication, reprise et journal privé. Les changements de ports et seuils de disque sont **simulés**, sans modifier le système pour les provoquer.

Essai réel de `python3 -B -m prevost.guardian diagnostic` :

- Disque racine lisible : environ 47,1 % d’espace libre au moment de l’essai.
- Cache APT lisible ; mises à jour listées, sans rafraîchissement ni installation.
- systemd utilisateur et système : bus refusé (`Operation not permitted`).
- Ports : sockets netlink refusées. `ss` retourne néanmoins 0 ; le diagnostic classe bien cette collecte comme indisponible.

Essai réel de veille dans un dossier temporaire : deux collectes à une seconde d’intervalle, trois alertes initiales correspondant aux collectes refusées, aucun doublon. Relance réelle d’une troisième collecte avec le même dossier : journal conservé, aucune alerte répétée. Assertions Python vérifiées sur les enregistrements du journal. Aucun port, service, paquet ni réglage système n’a été modifié. Les données de test temporaires n’ont pas été ajoutées au dépôt.

La boucle infinie, les notifications graphiques, la collecte systemd/netlink hors de cette session restreinte et la surveillance durable en production ne sont pas déclarées validées. La veille s’exécute uniquement quand sa commande est active.

## Registre et boucle d’outils — essais du 8 novembre 2026

35 tests automatisés réussis : les 18 précédents sont conservés et 17 tests supplémentaires couvrent la mission complète, les paramètres et outils refusés, la sortie attendue incorrecte, les confirmations refusées, le changement du code pendant la confirmation, l’indisponibilité, les limites d’étapes, l’appel identique, le plan invalide, les sorties traitées comme données, le délai réel, la sortie excessive, l’entrée standard réelle, l’annulation réelle, l’outil manquant et les rapports d’échec.

Le protocole du planificateur est testé avec une **réponse de transport simulée**. Le décodage du flux Ollama reste aussi couvert par les simulations précédentes ; aucune simulation n’est présentée comme un appel réel à un modèle.

Essais réels supplémentaires :

- Mission par registre : création d’un programme dans un dossier temporaire, relecture, exécution de Python, comparaison exacte de `PRÉVOST : mission locale vérifiée\n`, journal et rapport Markdown présents. Aucun modèle requis pour cette mission prédéfinie.
- Même mission via la CLI `prevost.agent demo`, avec trois confirmations explicites fournies par le pilote d’essai : trois résultats vérifiés, code retour 0, rapport relu et vérifié.
- CLI `prevost.agent diagnostic` : rapport produit, disque et diagnostic REA vérifiés, systemd et ports indisponibles ; code retour 1 pour diagnostic partiel, sans prétendre que le PC est sain.
- `rea.doctor` via le registre : JSON vérifié, `healthy=false` ; aucune réparation appliquée.
- Compilation locale d’un `.pyc` temporaire puis inspection statique réelle par REA : Evidence JSON identifiée, retour 0, bytecode cible non exécuté par REA.
- Registre réel : outils de fichiers/Python/disque et CLI REA disponibles ; ports, systemd utilisateur et conteneur Kali indisponibles dans cette session restreinte. Aucun outil Kali prétendu présent.
- CLI `prevost.agent mission` vers l’adresse réelle `http://127.0.0.1:11435` : refus de socket `Operation not permitted`, code retour 1. La boucle pilotée par un vrai modèle Ollama reste donc **non validée** ici.

Aucune cible réseau scannée ou attaquée. Aucun rapport ni journal d’essai ajouté à Git. Aucune modification des lanceurs installés. Les garanties et limites des délais, confirmations, périmètres et preuves figurent dans OUTILS.md.

## Inventaire réseau consenti — 8 novembre 2026

**70 tests automatisés réussis** avec `python3 -B -m unittest discover -s tests -v` : les 41 tests précédents, 28 tests réseau et un test de routage des commandes de conversation.

### Validation simulée réussie

Toutes les données réseau de ces tests sont fabriquées : profils NetworkManager Ethernet/Wi-Fi, BSSID, passerelle, CIDR, réponses XML Nmap, cache des voisins et noms locaux. Aucun paquet de découverte n’est émis par la suite de tests réseau. Le test d’événements lance un processus Python qui produit un message simulé à la place de NetworkManager ; il vérifie réellement le nettoyage du sous-processus. Un autre test utilise un processus Python inoffensif en attente pour vérifier que la révocation persistée termine réellement le processus en cours, sans accès réseau.

Les assertions couvrent : demande unique et décision persistante après relance, refus et interruption sans découverte, connexion sans terminal en attente, Wi-Fi non approuvé implicitement, liaison de l’identité au BSSID et à la passerelle, refus d’une identité Ethernet insuffisante, périmètres invalides/hors connexion/trop vastes/IPv6/options, exécution automatique uniquement après approbation, arguments ARP fixes sans audit, XML incomplet et hors périmètre, noms et sources avec incertitude, premières/dernières observations, nouveaux candidats et réapparitions, conservation des absents, absence de fusion par IP ou MAC seule, interruption et révocation pendant la collecte, refus de réenregistrer un résultat révoqué, commande d’arrêt, interruption d’un prompt en attente, rejet d’une deuxième veille, arrêt ou échec du moniteur, permissions privées, refus des dépôts Git et des liens symboliques, transaction invalide sans écriture partielle, codes de retour pour collecte ponctuelle réussie ou indisponible et routage des quatre commandes de conversation.

### Validation réelle non effectuée sur le réseau utilisateur

Essai réel, sans découverte d’hôtes :

```bash
python3 -B -m prevost.network connexions
```

Retour 1 : `Cannot open netlink socket: Operation not permitted`. La lecture directe de `nmcli ... connection show --active` est aussi refusée : `Could not connect: Operation not permitted`. Les exécutables locaux `nmcli`, `ip` et `nmap` sont présents ; `nmap --help` indique la version 7.95. Leur présence n’est pas une validation de leurs droits d’accès réseau.

Le périmètre CIDR et l’identité du réseau à autoriser ont été demandés à l’utilisateur mais n’ont pas encore été fournis. Aucun réseau n’est donc déclaré approuvé et aucun Nmap de découverte n’a été lancé sur le réseau utilisateur. Cette session ne permet pas de valider la surveillance des connexions de l’hôte ni les droits ARP de Nmap. Les tests simulés ne remplacent pas cette validation.

Pour compléter depuis un terminal hôte ayant accès au réseau, dans le dépôt :

1. Exécuter `python3 -m prevost.network connexions` et contrôler l’identité affichée.
2. Exécuter `python3 -m prevost.network veille`, saisir le CIDR dont on autorise l’inventaire, examiner l’interface et confirmer avec `oui`.
3. Examiner `python3 -m prevost.network liste` depuis un second terminal : sources, premières/dernières dates, candidats `a_valider`, modes 700/600 dans le dossier privé.
4. Reconnecter le même réseau : vérifier qu’il n’y a pas de nouvelle demande et qu’une collecte est effectuée ; un BSSID ou une passerelle différents nécessitent un nouvel accord.
5. Si un appareil de test autorisé peut être connecté, observer son signalement puis vérifier l’absence de doublon au rafraîchissement. Une non-détection ARP ne prouve pas l’absence d’appareil.
6. Exécuter `python3 -m prevost.network retirer --network IDENTIFIANT` ; vérifier que la découverte cesse sur ce réseau et que l’historique est conservé. Terminer avec `python3 -m prevost.network arreter`.

Aucun test réel n’est annoncé réussi avant observation de ces résultats. Aucun audit actif, fichier distant, cookie ou mot de passe n’est collecté par ce module. Aucun service, lanceur ou privilège système n’est modifié.

## Coffre privé local — 8 novembre 2026

**84 tests réussis**, dont 13 tests spécifiques au coffre et un test supplémentaire de séparation entre le coffre, le modèle et l’historique. La dépendance `cryptography` 43.0.0 était déjà présente dans l’environnement ; aucune installation n’a été effectuée.

Les tests du coffre exécutent réellement AES-GCM, Scrypt et les opérations de fichiers avec des **cookies et phrases de passe fictifs** dans des dossiers temporaires. Ils vérifient : déchiffrement correct, absence des secrets et métadonnées en clair sur disque, mauvais mot de passe, altération du fichier, sels/nonces distincts, liste sans valeur, état sans autorisation d’utilisation, suppression et réouverture, refus d’écrasement, validation des entrées, liens symboliques et physiques refusés, dossiers hors Git, permissions 700/600, conservation du fichier après échec d’écriture atomique, format invalide rejeté avant dérivation, confirmation du propriétaire, refus sans demande du secret, interdiction du repli vers une saisie avec écho, interruption et dépendance absente.

Le test de conversation vérifie que `/coffre` appelle directement l’interface locale, sans appel au modèle ni création d’historique ; des secrets fictifs passés à tort après la commande ne sont pas reproduits dans les messages d’erreur.

Aucun cookie réel, profil de navigateur ou compte connecté n’est lu. Les saisies CLI sont **simulées**, distinctes du chiffrement et du stockage réellement testés. Aucun coffre personnel n’est initialisé et aucune phrase de passe n’est demandée dans la conversation. Aucun test de connexion ni branchement à Themus n’est effectué : son lien/dossier et la provenance des cookies restent à préciser. La fonction permet seulement le stockage local explicite, sans usage automatique ni transmission d’un cookie à un outil.

## Reconnaissance de « scan complet » — 8 novembre 2026

**91 tests réussis** : sept tests supplémentaires vérifient la reconnaissance exacte de `scan complet` et de la faute `scam complet`, le routage vers le profil fixe `nmap -v -A`, la demande de cible, la confirmation distincte, le fonctionnement sans Ollama, le rejet des plages/options/URL, le refus et l’annulation sans sous-processus, les couleurs, le signalement d’un échec DNS malgré un code retour 0 et l’absence de déclenchement depuis une réponse du modèle.

Un test lance réellement la CLI PRÉVOST et son sous-processus, en remplaçant Nmap par un **exécutable factice** dans un dossier temporaire. Celui-ci affiche ses arguments et n’effectue aucun accès réseau. Les autres résultats Nmap sont simulés. Aucun scan réel supplémentaire n’a été lancé pendant ces tests.

L’essai réel précédent de la commande exacte `nmap -v -A scanme.nmap.org` a produit `Failed to resolve "scanme.nmap.org"` et `0 IP addresses`, malgré un code retour 0. Il n’a donc analysé aucun hôte. Les résultats d’un audit réel, les droits de détection du système et les scripts sur le serveur de démonstration restent non validés dans cet environnement.

## V2 — Termux, coffre étendu et double vérification

**110 tests réussis** sous Linux avec `python3 -B -m unittest discover -s tests -q`.
Les lanceurs sont installés et exécutés réellement dans des dossiers temporaires,
y compris depuis un autre répertoire. Les tests du coffre utilisent uniquement des
secrets fictifs ; le chiffrement et le déverrouillage sont réels, les saisies sont simulées.
La détection Termux et les informations disque Android sont simulées. Le diagnostic
JSON a aussi été lancé réellement sous Linux ; aucun essai sur téléphone ni installation
de paquet Android n’est présenté comme validé.

Les contrôles de syntaxe et les exécutions Python sont réels dans les tests : bonne
sortie, mauvaise sortie, erreur de syntaxe sans exécution, fichier se modifiant lui-même,
modification après les contrôles, contrôles manquants, nouvelle dépendance et seconde
validation, fichier non Python et protection du code contre son remplacement par le
rapport. Les tests `/coder` utilisent une génération de plan simulée, puis des écritures
et exécutions réelles. Aucun nouveau résultat Ollama réel n’est revendiqué. Ces essais
vérifient le mécanisme de validation, pas la qualité générale des programmes d’un modèle.

## Plans refusés avant écriture, boucle de correction et mémoire — 9 novembre 2026

Branche `totalité` (fusion de `main`, v2, Samsung V16–V21 et rea-prevost) : **142 tests** pour PRÉVOST (dont 32 nouveaux), **114** pour `samsung-recovery` et **16** pour `integration-rea`, tous réussis sous Linux avec `python3 -B -m unittest discover -s tests` (et `python3 -B -m unittest test_installer` dans `integration-rea`).

Les nouveaux tests couvrent : JSON tronqué (une reprise, puis arrêt sans écriture), fichier Python qui ne compile pas, JSON invalide, demande « lance/teste » sans commande ni contrôle, contrôle ou commande visant un fichier inconnu, chemin dangereux non retenté ; correction après contrôle ou commande en échec avec preuve transmise, plafond de corrections (0, 1, 2), arrêt sur fichier refusé, commande ou contrôle non confirmé, délai dépassé ; mémoire (étiquette « non fiable », plafond de 2 Ko, enregistrement de toutes les issues, aucun code, sortie ni secret conservé, fichier privé en mode 600 hors du projet, fichier corrompu, `/memoire` et `--corrections` en ligne de commande).

Limite : la génération du modèle est **simulée** dans ces tests ; les écritures, compilations, sous-processus et contrôles sont réels. Aucun essai Ollama réel de la boucle de correction n’est revendiqué : il reste à mesurer avec `prevost-codex:v4`, `qwen2.5-coder:7b` et `qwen3:8b` sur des missions réelles.

## Essais réels sur Ubuntu (Ollama local) — 9 novembre 2026

Essais faits par l'utilisateur, sortie collée dans la conversation. Résultats **réels mais en très petit nombre** :

- `qwen3:8b` via `/coder` : `bonjour.py` écrit, lancé et vérifié (le premier contrôle a expiré parce que le temps de confirmation humaine comptait dans le délai : bogue corrigé, test de régression ajouté).
- `qwen3:8b` via `/coder`, mission `taches.py` : premier plan avec deux contrôles contradictoires sur le même fichier (refusé désormais avant écriture) ; second essai : le contrôle a échoué parce que la sortie attendue par le modèle (« Erreur: Tâche vide. ») différait de la sortie réelle (« Erreur: Tâche vide ») ; **une correction** (un point ajouté au message d'erreur) a donné `double_verification_reussie` en 2 essais, chaque étape confirmée.
- Limite : ce bilan prouve que le programme produit la sortie que le modèle avait annoncée, pas que le programme fait ce que l'utilisateur voulait. Ici, `terminer` supprime la tâche au lieu de la marquer terminée, et la correction a modifié le code pour coller à l'attente du modèle plutôt que l'inverse.
- Codex via `rea-prevost` : `prevost:latest` écrit un faux appel d'outil en texte ; `qwen3:8b` répond avec du code sans créer ni lancer de fichier. Le raccordement démarre mais n'est pas validé pour programmer avec ces modèles ; cause non établie. D'où le bouton `prevost-rea`.

## Code coloré dans l'interface — 9 novembre 2026

12 tests ajoutés (`tests/test_highlight.py`) : couleurs de chaque rôle, texte préservé caractère pour caractère, code cassé ou tronqué sans erreur, séquences de contrôle hostiles neutralisées, différences de fichiers `.py`, code à examiner avant un contrôle (y compris un code qui contient lui-même « Projet : »), confirmations inchangées hors terminal, terminal restauré en cas d'interruption. Les séquences ANSI sont vérifiées par les tests ; **l'aspect réel dans ton terminal n'a pas été vu** et reste à confirmer. Le thème de Codex (`prevost-noir.tmTheme`, bouton `rea-prevost`) est un autre mécanisme, non vérifié ici faute de Codex dans cet environnement.

## Plan lisible et /annuler — 9 novembre 2026

**172 tests** pour PRÉVOST (16 ajoutés dans `tests/test_plan_and_undo.py`), 114 pour `samsung-recovery`, 26 pour `integration-rea`, tous réussis sous Linux. Les tests couvrent : résumé du plan (nouveau/modifié, commandes avec arguments, aperçu tronqué des sorties attendues, avertissement sans contrôle, caractères de contrôle), progression sans JSON brut et option `--plan-brut`, un plan par correction, sauvegardes attribuées à leur fichier, restauration avec différence et confirmation, restauration annulable, refus sans changement, index falsifié (chemins hors du dossier, entrées invalides) ignoré, sauvegardes anciennes comptées mais non listées, commandes `/annuler` de bout en bout. La génération du modèle est simulée ; écritures et restaurations sont réelles. Rien de cela n'a encore été essayé par l'utilisateur sur son Ubuntu.

## Essais réels du 9 novembre 2026 et corrections

**181 tests** pour PRÉVOST, 114 pour `samsung-recovery`, 32 pour `integration-rea`, tous réussis sous Linux.

Essayé par l'utilisateur sur son Ubuntu avec `qwen3:8b` : plan lisible avec diff en couleurs, mission de modification de `taches.py` avec `double_verification_reussie`, boucle de correction, `/annuler` (liste, restauration, aller-retour sans perte), `/memoire`, lanceur `prevost-rea` en terminal, boutons `rea-prevost` et `prevost-rea` dans REA, titre et icône REA, icône REA sur le bureau (ce dernier point rapporté par l'utilisateur, non vu par moi).

Défauts relevés pendant ces essais, puis corrigés avec des tests (6 des 7 nouveaux tests échouent sans les corrections) :
- le modèle annonçait une sortie sans le `\n` final : un seul `\n` final manquant dans l'annonce est maintenant toléré ; tout autre écart reste une erreur (deux sauts de ligne réels, saut annoncé mais absent, texte différent) ;
- le message « Rien n'a été écrit » était faux quand des tentatives précédentes avaient déjà écrit des fichiers : il nomme maintenant ces fichiers et rappelle `/annuler` ;
- réécrire un fichier identique demandait un « oui » et créait une sauvegarde inutile : plus de confirmation ni de sauvegarde, le plan affiche « inchangé », et restaurer une sauvegarde identique au fichier actuel ne fait rien ;
- `/coder` sans demande envoyait une mission vide au modèle : il est refusé tout de suite avec un message d'usage.

Limites confirmées : un contrôle réussi prouve seulement que la sortie correspond à l'annonce du modèle ; `qwen3:8b` peut écrire du code valable seulement en Python 3.12+ (guillemets doubles dans un f-string) sans que PRÉVOST le détecte ; ses explications en conversation peuvent contenir des détails faux (un exemple relevé sur `memory.py`).

## Fiabilité de `/coder`, mémoire et banc d’essai — 9 novembre 2026

> **Section venue de `main` avant la fusion.** Elle décrit la version de `main` de la boucle de correction, de la mémoire et de `/annuler`, **remplacée dans `totalité` par la version décrite plus haut** (la mémoire de `totalité` refuse les secrets au lieu de les masquer, et `/annuler` y liste des sauvegardes par fichier). Les résultats concernant le banc d’essai (`prevost/bench.py`) restent valables.


Commandes lancées : `python3 -B -m unittest discover -s tests` (127 tests réussis) et, dans `samsung-recovery`, `python3 -B -m unittest discover -s tests` (114 tests réussis).

### Testé pour de vrai

- Exécution réelle de Python et de sous-processus dans des dossiers temporaires : échec d’un contrôle puis correction, échec d’une commande (code retour 3), expiration d’un délai, refus d’une confirmation, limite de deux essais, absence de progrès.
- Compilation réelle (sans exécution) des `.py` proposés ; aucun fichier cassé n’est écrit.
- Écritures réelles, sauvegardes en mode 600, restauration par `/annuler` après différence et confirmation, refus sans effet.
- Mémoire : fichier réel en mode 600 dans un dossier 700, masquage de secrets, limite de 2 Ko, effacement avec confirmation exacte.
- Banc d’essai : vérifications indépendantes exécutées réellement sur les fichiers produits ; confirmation unique et refus sans effet.

### Simulé

- **Toutes les réponses du modèle** (plans JSON, plans tronqués, corrections) viennent de faux clients en mémoire. Aucun essai avec un vrai Ollama : le comportement réel des modèles installés, leur taux de réussite et la qualité de leurs corrections ne sont pas validés.
- Le tableau du banc a été produit uniquement avec un « bon » et un « mauvais » faux modèle ; il ne dit rien des modèles réels.
- Linux seulement a été exécuté ; Termux n’a pas été relancé dans cette session.

### Non fait

- Outil web en lecture seule et description d’image (mission 7, prévue plus tard).

## Fusion de `main` dans `totalité` — 9 novembre 2026

**Gardé de `totalité`** (déjà éprouvé en vrai avec Ollama) : boucle de correction `--corrections`, mémoire `ProjectMemory` (refuse les secrets), `/annuler FICHIER`, plan lisible, tolérance d’un seul `\n` final dans la sortie annoncée, fichier identique = ni confirmation ni sauvegarde.

**Repris de `main`** : banc d’essai `prevost bench` (`prevost/bench.py`), outils du registre `project.list`, `project.search`, `python.tests`, modèle par défaut mémorisé (`/modeles` le change), changements du Gardien, `premiers.py`.

**Abandonné de `main`** (même fonction, deux versions : celle de `totalité` reste) : sa classe `Memory` (masquage au lieu de refus), son `undo`, sa boucle de reprise. Douze de ses tests, qui visaient ces fonctions, ont été retirés de `tests/test_app.py` ; les mêmes comportements sont couverts par `tests/test_coder_loop.py`, `tests/test_memory.py` et `tests/test_plan_and_undo.py`. **Un comportement de `main` n’est pas repris** : arrêt anticipé quand le modèle repropose exactement le même plan (« absence de progrès ») ; `totalité` utilise alors ses deux corrections.

**Ajusté pour que les deux se marient** : le banc d’essai tourne maintenant en silence (aucun point de progression affiché) et un test le vérifie.

Commandes lancées après la fusion, Python 3.13 sous Linux : `python3 -B -m unittest discover -s tests` (196 tests réussis), `python3 -B -m unittest test_premiers` (4), dans `samsung-recovery` (114) et dans `integration-rea` (32).

**Non vérifié** : le banc d’essai n’a jamais tourné avec un vrai modèle Ollama (seulement un « bon » et un « mauvais » faux modèle) ; l’interface complète fusionnée n’a pas été relancée à la main sur le PC d’Alex.

## Bouton Claude dans REA — 9 novembre 2026

Ajout du raccourci `claude-rea` et d'un troisième bouton dans l'interface REA (Claude Code sur le projet choisi). Tests de `integration-rea` : 45 réussis (13 nouveaux : bouton ajouté une fois et après les deux autres, `rea-gui` déjà installé avec deux boutons, sauvegarde et refus des liens, dossier avec espaces et annulation, recherche de `claude`, commande officielle affichée si absent, terminal gardé ouvert en cas d'échec, aucune option de contournement des autorisations).

**Essayé pour de vrai** : l'installateur sur un faux `rea-gui` dans un dossier temporaire (le fichier compile, trois boutons) ; `claude-rea` lancé avec un faux `claude` dans le PATH (bon dossier de travail, options transmises, code 0) et sans aucun `claude` (message d'installation, code 127).

**Non vérifié** : le vrai Claude Code (jamais lancé par ces tests), le clic sur le vrai bouton REA et l'ouverture du terminal sur Ubuntu, la longueur du bandeau (inchangé). Le `rea-gui` réel d'Alex n'a pas été lu depuis cette session.

## Banc d’essai amélioré — 9 novembre 2026

Premier passage réel du banc, lancé par Alex avec `qwen3:8b` et un seul essai : **15 critères sur 19**. `bonjour` et `premiers` réussis ; `calcul` 4/5 (le code et ses tests passent, seul le contrôle interne échoue) ; `taches` 2/5 (fonctionnement et tests unitaires en échec, même avec deux corrections). Le banc n’affichait alors ni la raison des échecs ni aucune progression, et un essai unique ne permet pas de conclure.

**Changements** (`prevost/bench.py`) : chaque critère renvoie la raison de son échec (fichier absent, ligne de la faute de syntaxe, sortie obtenue et attendue, dernière ligne d’erreur des tests, bilan de PRÉVOST et dernier constat) ; `--essais N` (1 à 10) rejoue chaque mission dans un dossier et un état neufs et affiche un taux de réussite, avec les raisons identiques regroupées d’un essai à l’autre ; une ligne au début et à la fin de chaque mission, vidée aussitôt (une sortie redirigée n’attend plus la fin du banc) ; la confirmation unique annonce le nombre d’essais. `--model tous` existait déjà.

Tests : `tests/test_bench.py` passe de 6 à 19 tests (raisons d’échec réelles avec un faux modèle qui se trompe de trois façons, fichiers absents signalés comme absents, exception d’une mission, essais multiples, modèle capricieux à 50 %, regroupement des raisons, dossier et état distincts par essai, validation de `--essais`, vidage de la sortie). Vérifié en cassant volontairement le code : raison supprimée, vidage retiré, état partagé entre essais et regroupement faussé sont tous détectés. Python 3.13 sous Linux : `python3 -B -m unittest discover -s tests` (209 tests réussis), `samsung-recovery` (114), `integration-rea` (45).

**Essayé pour de vrai** : la commande `python3 -m prevost bench --model … --essais 2` contre un faux serveur Ollama local, sortie redirigée vers un fichier : les lignes de progression apparaissent pendant l’exécution (10 lignes après 5 s, 18 après 10 s), puis le tableau, le taux (28/38) et les raisons des échecs.

**Non vérifié** : la nouvelle version n’a pas encore tourné avec un vrai modèle Ollama ; la durée d’un banc à plusieurs essais n’est pas mesurée (elle se multiplie par le nombre d’essais).
