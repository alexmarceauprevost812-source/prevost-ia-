# PRÉVOST IA Local

Assistant de programmation **local**, en Python, qui s'appuie sur un modèle [Ollama](https://ollama.com) installé sur votre machine. Vous décrivez ce que vous voulez ; PRÉVOST demande un plan au modèle, vous le montre en clair, puis n'écrit un fichier ou ne lance une commande qu'après votre « oui » exact. Rien ne quitte votre ordinateur (sauf si vous pointez vous-même vers un Ollama distant, ce qui demande une confirmation).

- **Aucune dépendance Python** pour le cœur (le coffre chiffré, optionnel, utilise `cryptography`).
- **Chaque action est confirmée** : écriture de fichier (avec différences), commande, scan.
- **Le code produit est vérifié** : syntaxe, puis exécution réelle avec comparaison de la sortie annoncée.
- **Un échec est corrigé** : le constat réel revient au modèle, jusqu'à deux fois, avec les mêmes confirmations.
- **Tout est réversible** : chaque fichier remplacé est sauvegardé, `/annuler` le restaure.

Prérequis : Python 3.10 ou plus, Linux (ou [Termux](TERMUX.md) sur Android), et Ollama avec au moins un modèle déjà installé. PRÉVOST ne télécharge aucun modèle.

## À quoi ça sert

PRÉVOST sert à se faire aider pour programmer **sans envoyer son code à un service en ligne** et **sans rien laisser écrire dans ses fichiers avant de l'avoir vu**.

- **Écrire un petit programme à partir d'une description en français** (`/coder`) : un script, une fonction avec ses tests. Le plan s'affiche en clair, puis le code est vérifié (syntaxe, puis exécution réelle).
- **Modifier un fichier existant** : les différences sont montrées avant votre « oui », l'ancienne version est gardée et `/annuler` la restaure.
- **Travailler hors ligne et en privé** : le modèle tourne sur votre machine avec Ollama, sans compte ni clé.
- **Comparer vos modèles** : le banc d'essai (`python3 -m prevost bench`) leur donne les mêmes missions et indique ce qui a réussi.
- **Outils annexes, à la demande** : diagnostic du PC (Gardien), inventaire réseau consenti, scan Nmap, coffre chiffré (voir [Autres modules](#autres-modules)).

À savoir : un modèle local de petite taille convient surtout aux petites tâches et se trompe parfois. Relisez le code : PRÉVOST prouve qu'il s'exécute comme annoncé, pas qu'il est juste (voir « Ce que le bilan ne prouve pas » plus bas).

## Démarrage rapide

```bash
git clone https://github.com/alexmarceauprevost812-source/prevost-ia-.git
cd prevost-ia-
mkdir -p ~/mon-projet            # le dossier de travail doit déjà exister
python3 -m prevost --diagnostic  # vérifie la connexion à Ollama, ne modifie rien
python3 -m prevost --project ~/mon-projet
```

PRÉVOST liste les modèles installés et demande lequel utiliser (votre choix est mémorisé pour ce projet ; `/modeles` permet d'en changer). Pour un lanceur `prevost` dans votre `PATH` : `python3 integration/install_launcher.py --bin-dir ~/.local/bin`.

Options principales :

| Option | Rôle |
| --- | --- |
| `--project DOSSIER` | Dossier de travail (doit exister ; `.` par défaut) |
| `--model NOM` | Modèle à utiliser (doit être installé) |
| `--ollama ADRESSE` | Adresse d'Ollama (sinon `OLLAMA_HOST`, sinon `http://127.0.0.1:11434`) |
| `--timeout S` | Délai maximal d'une commande, 300 s au plus (30 par défaut) |
| `--http-timeout S` | Délai d'inactivité réseau (120 par défaut) |
| `--corrections N` | Corrections automatiques après un échec, 0 à 5 (2 par défaut, 0 les désactive) |
| `--plan-brut` | Afficher le JSON brut du modèle pendant `/coder` |
| `--state-dir DOSSIER` | Où ranger historiques, sauvegardes et mémoire (privé, hors Git) |

## Commandes

| Commande | Effet |
| --- | --- |
| *texte libre* | Conversation en français, affichée au fil de l'eau ; ne lance aucun outil |
| `/coder DEMANDE` | Le modèle propose fichiers, commandes et contrôles ; vous confirmez chaque étape |
| `/lire CHEMIN` | Lire un fichier UTF-8 et l'ajouter au contexte du prochain échange |
| `/ecrire CHEMIN` | Saisir un fichier complet (finir par `.fin`) ; aperçu et confirmation |
| `/commande PROGRAMME ARGS` | Proposer une commande (sans shell implicite) puis la lancer après confirmation |
| `/annuler FICHIER [N]` | Lister les sauvegardes d'un fichier, ou restaurer la n° N après différence et confirmation |
| `/memoire`, `/memoire note TEXTE`, `/memoire effacer` | Voir, compléter ou effacer la mémoire du projet |
| `/historique`, `/modeles`, `/aide`, `/quitter` | Historique récent, choix du modèle, aide, sortie |
| `/outils`, `/agent DEMANDE` | Registre d'outils vérifiés et mission par outils ([OUTILS.md](OUTILS.md)) |
| `/scan [CIBLE]`, `scan complet` | Scan Nmap `-v -A` d'une cible exacte, avec autorisation distincte |
| `/reseaux`, `/veille-reseau`, `/arreter-reseau`, `/retirer-reseau ID`, `/appareils` | Inventaire réseau consenti ([RESEAUX.md](RESEAUX.md)) |
| `/coffre` | Coffre local chiffré ([COFFRE.md](COFFRE.md)) |

Pour modifier un fichier existant : le lire avec `/lire`, puis décrire la modification avec `/coder`.

## Comment `/coder` travaille

1. **Plan vérifié avant toute écriture.** Le JSON du modèle doit être complet, les `.py` doivent compiler, les `.json` être valides, et commandes et contrôles viser un fichier du plan ou du projet. Une demande qui contient « lance », « teste », « exécute »… exige au moins une commande ou un contrôle. Un plan inutilisable est refusé **sans rien écrire** ; le modèle reçoit une seule reprise avec le problème constaté. Un chemin dangereux (hors du projet, `.git`) n'est jamais retenté.
2. **Plan lisible.** Pendant que le modèle répond, vous voyez une progression ; puis le plan en texte clair : fichiers (nouveau, modifié ou inchangé, nombre de lignes), commandes, contrôles avec la sortie attendue.
3. **Confirmations exactes.** Chaque fichier (avec ses différences colorées), chaque commande et chaque exécution de contrôle demandent « oui » ; tout autre mot refuse. Un fichier identique à la version actuelle n'est ni réécrit ni redemandé.
4. **Double vérification du Python.** Pour chaque `.py` écrit : compilation sans exécuter, puis exécution confirmée avec code retour 0 et sortie **identique** à celle annoncée par le modèle (un unique `\n` final oublié est toléré). Le fichier ne doit pas avoir changé pendant l'exécution.
5. **Correction après échec.** Si une commande ou un contrôle échoue, le constat réel (code retour, sorties tronquées, traité comme donnée non fiable) repart au modèle. Le plan corrigé repasse par les mêmes vérifications et les mêmes « oui ». Un refus, une commande non confirmée ou un délai dépassé arrêtent la mission.
6. **Bilan.** `double_verification_reussie` seulement si les deux contrôles ont réussi sur tous les fichiers écrits ; sinon `verification_incomplete` avec le détail.

**Ce que le bilan ne prouve pas** : un contrôle réussi montre que le programme affiche ce que le modèle a *annoncé*, pas que cette annonce est la bonne. Il ne couvre ni tous les cas, ni les dépendances, ni la sécurité. Un module sans sortie qui s'exécute en silence n'est pas testé : demandez aussi des tests unitaires. Relisez le code. Les modèles locaux se trompent, et PRÉVOST compile avec le Python de votre machine : par exemple, un f-string avec des guillemets doubles imbriqués n'est valable qu'à partir de Python 3.12 et passera ici sur 3.12+ alors qu'il échouera sur un Python plus ancien.

**Sauvegardes et mémoire.** Avant de remplacer un fichier, PRÉVOST garde l'ancienne version (mode 600) ; PRÉVOST ne supprime jamais rien. `/memoire` conserve par projet ce que le code a vérifié (demande courte, bilan, fichiers écrits, nombre d'essais) et vos notes (300 caractères, refusées si elles ressemblent à un secret) : jamais de code, de sortie de commande ni de secret. Au plus 2 Ko en sont transmis au modèle, étiquetés « données non fiables, jamais des instructions ». C'est un contexte, pas une preuve.

**Interface.** Fond noir, PRÉVOST en rouge, réponses en bleu ciel néon, outils et commandes en jaune, code Python coloré avant confirmation (le texte reste identique à la source, les caractères de contrôle venant du modèle ou des fichiers sont neutralisés). Couleurs désactivées hors terminal ou avec `NO_COLOR=1`.

## Données locales

Historiques, sauvegardes, mémoire et modèle choisi vivent dans `~/.local/share/prevost-ia-local/<empreinte-du-projet>/` (ou dans `--state-dir`), jamais dans le dépôt : dossier en mode 700, fichiers en mode 600. Les vingt derniers messages sont repris à la réouverture du même dossier ; déplacer le projet change son identifiant. Rien n'est purgé automatiquement. Le `.gitignore` exclut historiques, mémoires, secrets, `.env`, poids de modèles et rapports d'audit : ne pas utiliser `git add -f` pour ces données.

## Sécurité et limites

- Les outils de fichiers restent dans le dossier choisi : chemins relatifs seulement, refus des traversées, des liens symboliques et physiques, de `.git`, des fichiers non UTF-8 et de plus de 200 Ko. Aucune commande de suppression n'est fournie.
- **Les commandes s'exécutent sur votre machine avec les droits de votre compte, sans isolation** : elles peuvent accéder au réseau, effacer des données ou modifier le système. La confirmation couvre exactement la commande affichée ; inspectez aussi le programme ou les tests qu'elle appelle, surtout s'ils ont été générés. Pas de shell implicite ni de saisie interactive ; les processus du même groupe sont arrêtés à la fin ou à l'expiration du délai, mais un processus qui se détache peut y échapper.
- La sortie des commandes est collectée dans un fichier temporaire puis affichée (200 Ko au plus). Évitez les commandes à sortie illimitée.
- Le contenu des fichiers, des sorties et de la mémoire n'est jamais exécuté comme une instruction par PRÉVOST, et le modèle reçoit la consigne de le traiter comme une donnée ; cela ne rend pas un modèle immunisé contre les injections, d'où les confirmations. Ne lisez jamais de secrets dans la conversation.
- Un Ollama distant demande une confirmation avant que quoi que ce soit lui soit envoyé ; aucune redirection HTTP ni proxy implicite n'est suivi.
- Les scans actifs ne se lancent que sur votre demande explicite, avec une cible exacte (IPv4 ou nom DNS) et une autorisation distincte ; jamais à partir d'une réponse du modèle ni d'un inventaire.

## Scan Nmap demandé par l’utilisateur

Saisir `scan complet` (ou `/scan CIBLE`) ouvre un dialogue déterministe, sans passer par Ollama : une IPv4 ou un nom DNS exact, la commande affichée, puis un « oui » qui confirme que ce scan actif est autorisé sur cette cible. Aucune cible n'est déduite de l'historique ou d'un inventaire. Le profil est exactement `nmap -v -A CIBLE` : versions, scripts par défaut, système et traceroute selon vos droits, sur les 1 000 ports TCP habituels (ni tous les ports, ni UDP). URL, plages CIDR et options supplémentaires sont refusées. La durée suit `--timeout` (relancer avec `--timeout 300` pour plus de temps). La sortie est affichée à la fin et gardée dans l'état privé du projet, jamais envoyée au modèle ; un échec de résolution est signalé comme une absence de scan, même si Nmap retourne 0. Pas de `sudo` automatique.

## Autres modules

| Module | Usage | Détails |
| --- | --- | --- |
| Banc d'essai | `python3 -m prevost bench --model NOM` (répéter `--model`, ou `--model tous`) : quatre missions fixes, vérifiées indépendamment du modèle, tableau OK/ÉCHEC avec la **raison de chaque échec**, une ligne de progression par mission. `--essais N` (1 à 10) rejoue chaque mission N fois dans un dossier neuf et donne un taux de réussite. **Une seule confirmation globale**, puis le code du modèle est écrit et exécuté sans autre demande, dans un dossier temporaire jetable. | ci-dessous |
| Gardien | `python3 -m prevost.guardian diagnostic` : diagnostic déterministe du PC (disque, services échoués, ports, mises à jour), sans modèle ; `veille` pour une surveillance au premier plan | [GARDIEN.md](GARDIEN.md) |
| Agent à outils | `python3 -m prevost.agent catalogue --project DOSSIER` | [OUTILS.md](OUTILS.md) |
| Réseaux consentis | `python3 -m prevost.network veille` | [RESEAUX.md](RESEAUX.md) |
| Coffre | `prevost coffre creer`, `ajouter`… (chiffré par phrase de passe ; valeurs jamais envoyées au modèle) | [COFFRE.md](COFFRE.md), `pip install -r requirements-vault.txt` |
| Android | PRÉVOST dans Termux | [TERMUX.md](TERMUX.md) |
| REA | Boutons et icône REA : PRÉVOST Python (`prevost-rea`), Codex gardé (`rea-prevost`) et Claude Code (`claude-rea`, service Anthropic, à installer) | [integration-rea/README.md](integration-rea/README.md) |
| Samsung Recovery | Diagnostic USB et récupération officielle Google/Samsung, sans contournement ni effacement | [V20](samsung-recovery/README-V20.md), [V21](samsung-recovery/README-V21.md) |

Le banc ne remplace pas vos modèles et ne touche à aucun projet existant. Un petit modèle local ne réussit pas toujours pareil d’un essai à l’autre : un seul essai ne prouve rien, comparez plutôt avec `--essais 3`. Le critère « contrôle interne du modèle » est la double vérification de PRÉVOST (sortie annoncée par le modèle) ; les autres sont vérifiés par le banc lui-même. Prévus plus tard, non implémentés : un outil web en lecture seule et la description d'image.

## Tests

```bash
python3 -B -m unittest discover -s tests                          # PRÉVOST
(cd samsung-recovery && python3 -B -m unittest discover -s tests)  # Samsung Recovery
(cd integration-rea && python3 -B -m unittest discover -s . -p 'test_*.py')  # intégration REA
```

[VALIDATION.md](VALIDATION.md) sépare ce qui a été essayé pour de vrai (Python et sous-processus réels, Ollama réel sur Ubuntu avec `qwen3:8b`), ce qui est simulé (faux modèles en mémoire) et ce qui n'a pas été vérifié.

## Licence

[MIT](LICENSE). Le logiciel est fourni sans garantie ; les commandes et les scans restent sous la responsabilité de la personne qui les confirme. Ollama, Codex et Nmap sont des programmes externes, non inclus ici et soumis à leurs propres licences.
