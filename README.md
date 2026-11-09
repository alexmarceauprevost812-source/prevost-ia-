# PRÉVOST IA Local

Assistant de programmation et gardien numérique **100 % local** : Python, Ollama, aucune dépendance Python externe dans le cœur (le coffre optionnel utilise `cryptography`). Python 3.10+ et Linux ou Termux (Android) requis.

Licence : [MIT](LICENSE) © 2026 alexmarceauprevost812-source.

**Sommaire** : [Installation](#installation) · [Démarrage](#démarrage) · [Commandes](#commandes) · [Programmation fiable](#programmation-fiable-avec-coder) · [Banc d’essai](#banc-dessai-de-modèles) · [Mémoire et historique](#mémoire-historique-et-sauvegardes) · [Sécurité](#règles-de-sécurité) · [Gardien](#gardien-numérique) · [Agent et outils](#agent-et-outils-vérifiés) · [Réseau et scan](#réseau-et-scan) · [Samsung Recovery](#samsung-recovery) · [Tests](#tests)

## Installation

**Linux (Ubuntu, etc.)** : aucune installation, PRÉVOST se lance depuis le dépôt.

```bash
git clone https://github.com/alexmarceauprevost812-source/prevost-ia-.git
cd prevost-ia-
python3 -m prevost --diagnostic
```

Le dépôt est privé : il faut votre accès GitHub. Ollama doit déjà être installé et avoir au moins un modèle ; PRÉVOST n’en télécharge aucun. Pour le coffre chiffré seulement : `python3 -m pip install -r requirements-vault.txt` (installe `cryptography`).

**Android (Termux)** : l’installateur ajoute la commande `prevost`.

```bash
pkg install git
git clone https://github.com/alexmarceauprevost812-source/prevost-ia-.git
cd prevost-ia-
bash install-termux.sh
mkdir -p ~/projets/essai
prevost --project ~/projets/essai
```

Il installe `python` et `python-cryptography`, sans modèle, sans scan, sans service de fond. Garder le dépôt à son emplacement et relancer le script s’il est déplacé. Détails : [TERMUX.md](TERMUX.md).

**Raccourci Codex « rea-prevost » (Ubuntu)** : `python3 integration-rea/installer.py` affiche un aperçu ; ajouter `--apply` pour installer. Voir [integration-rea/README.md](integration-rea/README.md).

## Démarrage

```bash
python3 -m prevost --diagnostic                       # adresse Ollama et modèles installés
python3 -m prevost --project ~/mon-projet             # lancer l’assistant
python3 -m prevost --project ~/mon-projet --model NOM --timeout 30
```

- Le dossier du projet doit déjà exister.
- Adresse Ollama : `--ollama`, puis `OLLAMA_HOST`, puis `http://127.0.0.1:11434`. Une adresse distante exige une confirmation avant toute transmission.
- Seuls les modèles retournés par Ollama peuvent être choisis ; PRÉVOST n’en télécharge, n’en installe et n’en modifie aucun.
- Le choix fait dans `/modeles` est mémorisé comme modèle par défaut du projet (fichier privé) et repris au lancement suivant s’il est toujours installé.
- `--timeout` : délai maximal des commandes (300 s au plus). `--http-timeout` : délai d’inactivité réseau. `--state-dir` : dossier des historiques.
- Sans Ollama, les commandes manuelles restent disponibles.

## Commandes

| Commande | Effet |
| --- | --- |
| texte libre | conversation en français, réponse en streaming |
| `/coder demande` | plan de fichiers, commandes et contrôles, avec confirmations |
| `/lire chemin` | lire un fichier UTF-8 et l’ajouter au contexte |
| `/ecrire chemin` | saisir un fichier (finir par `.fin`), aperçu puis confirmation |
| `/commande args` | proposer une commande sans shell, puis confirmer |
| `/annuler FICHIER` | restaurer une sauvegarde après aperçu et confirmation |
| `/memoire` · `/memoire note TEXTE` · `/memoire effacer` | mémoire du projet |
| `/agent demande` · `/outils` | mission par outils validés · registre |
| `/modeles` · `/historique` · `/aide` · `/quitter` | utilitaires |
| `/scan [cible]` · `scan complet` | `nmap -v -A CIBLE` avec autorisation distincte |
| `/reseaux` · `/veille-reseau` · `/appareils` · `/arreter-reseau` · `/retirer-reseau ID` | inventaire réseau consenti |
| `/coffre` | coffre local chiffré ([COFFRE.md](COFFRE.md)) |

Pour modifier un fichier existant : le lire avec `/lire`, puis `/coder` en décrivant la modification.

L’interface utilise un fond noir, PRÉVOST en rouge, les réponses en bleu ciel `#87CEEB`, les outils en jaune `#FFFF00`, la saisie et les résultats bruts en blanc. Les séquences de contrôle venant du modèle ou des fichiers sont neutralisées ; les couleurs sont coupées hors terminal ou avec `NO_COLOR=1`.

## Programmation fiable avec `/coder`

1. **Plan sans bruit** : le modèle est interrogé sans rien afficher. Le plan apparaît ensuite en texte (fichiers, commandes, contrôles), avant les aperçus.
2. **Plans cassés refusés avant écriture** : syntaxe de chaque `.py` vérifiée sans l’exécuter, JSON tronqué détecté, avertissement si la demande dit « lance » ou « teste » sans commande. Le modèle est redemandé **une seule fois** ; si le plan reste inutilisable, rien n’est écrit.
3. **Confirmations** : chaque écriture (avec différences) et chaque commande exigent un `oui` exact. Un refus interrompt la mission.
4. **Double vérification Python** : pour chaque `.py` écrit, compilation puis exécution confirmée avec code retour 0 et sortie exactement égale à `expected_stdout`. Le bilan `double_verification_reussie` ne prouve ni tous les comportements, ni les dépendances, ni la sécurité. Une exécution silencieuse ne teste pas les fonctions : prévoir une suite de tests.
5. **Correction automatique** : si une commande ou un contrôle échoue, la demande d’origine, le contenu actuel des fichiers et l’erreur réelle (données non fiables) repartent au modèle. Le plan corrigé repasse par les mêmes aperçus et confirmations. **Deux essais au maximum** ; un refus, une annulation ou un délai arrête tout ; une correction identique au plan précédent aussi. Le bilan indique le nombre d’essais.

## Banc d’essai de modèles

```bash
python3 -m prevost bench --model NOM          # répéter --model, ou --model tous
```

Quatre missions fixes (bonjour, calcul avec test, 10 premiers nombres premiers, gestionnaire de tâches) tournent dans un dossier temporaire supprimé à la fin. Chaque critère est vérifié par le banc lui-même, indépendamment des contrôles du modèle ; le résultat est un tableau OK/ÉCHEC par critère et par modèle.

> **Exception à la règle des confirmations** : le banc demande **une seule** confirmation `oui` exacte au départ, puis écrit les fichiers proposés par le modèle et exécute Python sur ce code sans confirmer chaque action, avec vos droits et sans isolation. À lancer seulement sur un appareil où c’est acceptable.

## Mémoire, historique et sauvegardes

Tout est stocké hors du dépôt, dans `~/.local/share/prevost-ia-local/<empreinte-du-projet>/` (ou `--state-dir`), dossier en mode 700, fichiers en mode 600. Déplacer le projet change son identifiant. Le `.gitignore` exclut historiques, secrets, `.env`, poids GGUF et rapports ; ne jamais utiliser `git add -f` dessus.

- **Historique** : les 20 derniers messages sont repris à la réouverture (lecture bornée à 200 Ko).
- **Sauvegardes** : chaque fichier modifié est sauvegardé ; `/annuler FICHIER` les liste, montre la différence et restaure après confirmation (les sauvegardes antérieures à cette version ne sont pas listées). Aucune suppression automatique.
- **Mémoire du projet** (`/memoire`) : seuls des faits vérifiés par le code (mission, fichiers écrits avec empreinte, commandes avec code retour, bilan) et vos notes sont gardés, sans sorties complètes, avec masquage des motifs de secrets. Au plus 2 Ko des derniers faits sont injectés au début d’une mission, étiquetés « données non fiables ».
- **Apprentissage** : l’agent (`/agent`) retient ses appels échoués (outil, statut, erreur courte) dans `lessons.jsonl` et les relit comme données non fiables pour ne pas répéter la même erreur.
- **Coffre** : cookies, mots de passe et jetons, chiffrés par phrase de passe, jamais envoyés au modèle ni à l’historique.

## Règles de sécurité

- Les fichiers sont limités au dossier choisi : chemins relatifs, refus des traversées, des liens symboliques et physiques, de `.git`, des fichiers non UTF-8 et de plus de 200 Ko. Aucune commande de suppression n’est fournie.
- Les commandes s’exécutent **sur l’hôte avec les droits de votre compte**, sans isolation : réseau, suppressions et modifications système sont possibles. La confirmation couvre exactement la commande affichée ; inspecter aussi le programme ou les tests appelés. Aucun shell implicite ni saisie interactive. Les descendants du groupe sont arrêtés à la fin ou à l’expiration ; un processus détaché peut y échapper.
- La sortie est limitée à 200 Ko à la lecture ; le fichier temporaire peut grossir pendant l’exécution.
- Les réponses du modèle, les fichiers et les sorties de commandes sont des **données non fiables**, jamais des instructions. Une consigne système le rappelle au modèle, sans garantir son immunité aux injections.
- Ne jamais saisir de secrets dans la conversation. Aucune redirection HTTP ni proxy implicite n’est suivi.

## Gardien numérique

Diagnostic déterministe du PC courant, en **lecture seule**, sans Ollama et sans commande proposée par un modèle :

```bash
python3 -m prevost.guardian diagnostic [--json]
python3 -m prevost.guardian veille --cycles 0 --interval 60   # au premier plan, jusqu’à Ctrl+C
```

Contrôles : disque, charge CPU, mémoire, unités systemd échouées (utilisateur et système), ports TCP/UDP en écoute, mises à jour du cache APT. Chaque collecte garde sa source, sa sortie, ses erreurs et son état ; une collecte refusée est « indisponible » même avec le code 0. Les recommandations distinguent constat et point à vérifier, avec confiance et retour arrière ; aucune n’est appliquée.

La veille écrit `watch.json` et `incidents.jsonl` dans `~/.local/share/prevost-ia-local/guardian/` (mode 600/700). Alertes : changement d’une liste observée, moins de 10 % d’espace libre, moins de 10 % de mémoire disponible, charge à 5 min supérieure à 1,5 fois le nombre de processeurs, échec de collecte. Une même empreinte n’est signalée qu’une fois. Aucun service de fond ni démarrage automatique : quand la commande s’arrête, la surveillance s’arrête. Une seule instance par dossier d’état.

**Limites** : PC courant seulement ; disque racine sans SMART ; services échoués seulement ; ports sans attribution à un programme ni preuve d’exposition ; mises à jour issues du cache APT ; un bac à sable peut masquer l’hôte. Le diagnostic constate des faits, il ne certifie pas la sécurité. Termux : voir [TERMUX.md](TERMUX.md).

## Agent et outils vérifiés

`/agent demande` (ou `python3 -m prevost.agent mission …`) lance une boucle bornée où le modèle propose une étape JSON, validée et vérifiée par Python. Registre fermé : lecture et écriture de fichiers du projet, liste et recherche de texte, exécution de Python et de `unittest`, état Git, disque, ports, services, REA et outils Kali **passifs** (`file`, `strings`, inventaire, sans cible réseau). Détails, contrats et limites : [OUTILS.md](OUTILS.md).

```bash
python3 -m prevost.agent catalogue --project /chemin/du/projet
python3 -m prevost.agent demo --project /un/dossier/temporaire
```

## Réseau et scan

- **Inventaire consenti** : `python3 -m prevost.network veille` (ou `/veille-reseau`) demande une fois le périmètre et l’autorisation, puis inventorie les réseaux approuvés. Les nouveaux candidats restent « à valider » ; aucune autorisation d’audit n’est déduite. Voir [RESEAUX.md](RESEAUX.md).
- **Scan Nmap sur demande** : `scan complet` ou `/scan CIBLE` propose exactement `nmap -v -A CIBLE` (1 000 ports TCP, sans UDP) pour une seule IPv4 ou un seul nom DNS, avec une autorisation distincte confirmée. URL, CIDR, plages et options supplémentaires sont refusés. Aucune cible n’est déduite de l’historique, de l’inventaire ou d’une réponse du modèle. Un échec de résolution est signalé comme une absence de scan, même avec le code 0.

## Samsung Recovery

Outils Python de diagnostic et de récupération officielle Google/Samsung/Bell, dans [`samsung-recovery/`](samsung-recovery/) :

```bash
cd samsung-recovery
python3 prevost-samsung recuperation [--diagnostic | --rapport]   # V20
./prevost-samsung diagnostic-v21 [--rapport]                       # V21
```

- **V20** : détection USB, identification MTP/ADB/Recovery, analyse des rapports V17 à V19 et assistant de récupération. Voir [README-V20](samsung-recovery/README-V20.md) et le [rapport](samsung-recovery/rapports/v20/RAPPORT-V20.md).
- **V21** : restrictions du processus, listener local, permissions USB, états ADB/MTP ; rapport privé et archive `partage.zip` par liste blanche (seule destinée à être transmise). Voir [README-V21](samsung-recovery/README-V21.md) et le [rapport](samsung-recovery/rapports/v21/RAPPORT-V21.md).
- Aucun contournement FRP, effacement, flash, modification du téléphone ni extraction de secrets. Sans compte Google antérieur ou solution de propriété acceptée par le prestataire, la remise en service reste bloquée. Rapports bruts et justificatifs personnels restent locaux. Voir la [validation de publication](samsung-recovery/VALIDATION-PUBLICATION.md).

## Tests

```bash
python3 -B -m unittest discover -s tests -v                       # application PRÉVOST
cd samsung-recovery && python3 -B -m unittest discover -s tests   # Samsung (depuis ce dossier)
```

[VALIDATION.md](VALIDATION.md) distingue ce qui est testé pour de vrai de ce qui est simulé ; notamment, aucune réponse de modèle réel n’y est validée.

## Licence

Projet publié sous licence MIT : voir [LICENSE](LICENSE). Le logiciel est fourni sans garantie ; les commandes et scans restent sous la responsabilité de la personne qui les confirme.
