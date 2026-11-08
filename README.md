# PRÉVOST IA Local — v1

Assistant Python de programmation locale avec Ollama, sans dépendance Python externe. Python 3.10+ et Linux sont requis pour l’arrêt des groupes de processus.

## Lancement

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
- `/historique` : afficher les derniers échanges ; `/aide` et `/quitter`.

Pour modifier un fichier avec Ollama, le lire d’abord avec `/lire`, puis utiliser `/coder` en décrivant la modification. Refuser un fichier interrompt la mission avant les commandes. Une commande refusée, expirée ou en échec interrompt la suite du plan. Une sortie réussie ne prouve que le résultat de cette commande ; le modèle ne vérifie pas automatiquement la conformité à la demande.

Sans Ollama, les commandes manuelles restent disponibles. L’interface emploie un fond noir, un bandeau rouge, PRÉVOST jaune et une invite bleu ciel dans un terminal compatible ANSI. Les séquences de contrôle provenant du modèle et des fichiers sont neutralisées. Les couleurs sont désactivées hors terminal ou avec `NO_COLOR=1`.

## Historique et sauvegardes

Les échanges, résultats de commandes et sauvegardes des fichiers modifiés restent dans `~/.local/share/prevost-ia-local/<empreinte-du-chemin-du-projet>/`, hors du dépôt. À la réouverture du même dossier, les vingt derniers messages sont repris, avec une lecture bornée à 200 Ko d’historique. Le fichier de journal est privé (mode 600), son dossier en mode 700. Les sauvegardes permettent une restauration manuelle ; aucune suppression automatique n’est effectuée. Déplacer le projet change son identifiant de mémoire.

Le `.gitignore` exclut aussi les historiques, mémoires locales, secrets, `.env`, poids GGUF et rapports d’audit éventuellement créés dans le dépôt. Ne pas utiliser `git add -f` pour ces données.

## Contrôle et limites

Les outils de fichiers sont limités au dossier choisi : chemins relatifs, refus des traversées, liens symboliques et physiques, métadonnées `.git`, fichiers non UTF-8 et contenus de plus de 200 Ko. Chaque écriture affiche les différences et exige une confirmation. L’application ne fournit aucune commande de suppression.

Les commandes sont exécutées **sur l’hôte avec les droits de votre compte**, après présentation du dossier, des arguments et du délai. Elles ne sont pas isolées : elles peuvent accéder au réseau, supprimer des données, transmettre des fichiers et modifier le système. La confirmation couvre exactement la commande affichée ; inspecter aussi le programme ou les tests appelés, surtout s’ils ont été générés. Aucun shell implicite, aucune saisie interactive transmise au sous-processus. Un shell peut néanmoins être lancé explicitement si vous le confirmez. Les descendants du même groupe sont arrêtés après la commande ou à l’expiration ; un processus qui se détache peut échapper à cet arrêt.

La sortie est collectée dans un fichier temporaire et affichée à la fin, limitée à 200 Ko à la lecture. Le fichier temporaire peut grossir pendant l’exécution : éviter les commandes produisant une sortie illimitée. Le délai réseau est un délai d’inactivité, pas une durée totale de génération. Le journal local peut grossir au fil des missions.

Les données de fichiers et résultats ne sont jamais exécutés comme instructions par l’application. Une consigne système demande aussi au modèle de les traiter comme données ; cela ne garantit pas l’immunité du modèle aux injections. Chaque action proposée reste soumise à votre confirmation. Ne pas lire de secrets dans une conversation. Une adresse Ollama distante exige une confirmation de transmission avant utilisation ; aucune redirection HTTP ni proxy implicite n’est suivi.

Cette version reste centrée sur la programmation : pas d’intégration Kali, REA, audit réseau, téléchargement de modèles ou modification des lanceurs installés. Les composants PRÉVOST existants restent séparés et inchangés. REA et audits de cibles explicitement autorisées restent des objectifs ultérieurs.

## Vérification

```bash
python3 -B -m unittest discover -s tests -v
```

Voir [VALIDATION.md](VALIDATION.md) pour distinguer les essais locaux réels, les simulations et les blocages Ollama.
