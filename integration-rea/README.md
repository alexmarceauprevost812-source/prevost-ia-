# rea-prevost — PRÉVOST dans Codex, depuis REA

Le raccourci et le bouton s'appellent **rea-prevost**. Le bouton demande quel projet
modifier, puis ouvre **Codex** avec le modèle local **prevost:latest**. Codex fournit
la lecture de fichiers, les modifications et les commandes de tests ; les outils MCP
REA déjà configurés restent disponibles selon la configuration et les capacités du modèle.
La configuration utilisateur actuelle déclare REA ; aucun MCP n'est ajouté ou remplacé.

Le lancement fournit des consignes de travail : examiner le projet et ses AGENTS.md,
planifier les changements complexes, modifier de façon ciblée, exécuter les tests adaptés
et distinguer les résultats réels des suppositions. Ce raccordement n'entraîne pas les
poids du modèle et ne garantit pas un niveau de performance « professionnel ».

## Deuxième bouton : prevost-rea (PRÉVOST Python)

Avec les modèles locaux essayés, Codex n'a pas fait le travail : `prevost:latest` écrit un faux appel
d'outil en texte et `qwen3:8b` répond sans créer de fichier. Le bouton **prevost-rea** lance donc
PRÉVOST Python (`python3 -m prevost`) sur le projet choisi : plans vérifiés avant écriture,
corrections après un échec, mémoire du projet, chaque écriture et chaque commande confirmées par
un « oui » exact. Sans `--model`, PRÉVOST liste les modèles installés et demande lequel utiliser ;
`PREVOST_MODEL=qwen3:8b` en fixe un par défaut. Si le démarrage échoue, le terminal reste ouvert
pour lire l'erreur.

L'installateur ajoute ce bouton **à côté** du bouton rea-prevost (Codex), sans le retirer, et met à
niveau un `rea-gui` déjà installé. Il écrit `~/.local/bin/prevost-rea`, lié au dossier de ce dépôt :
si le dépôt est déplacé ou si une autre branche est activée, relancer `installer.py --apply`.
Commande : `prevost-rea --project /chemin/du/projet`.
Le titre de la fenêtre REA devient « PRÉVOST — REA » et l'en-tête indique « REA avec PRÉVOST local (prevost-rea)  |  Codex gardé (rea-prevost) » ; les boutons CODEX et rea-prevost (Codex) restent en place, aucun bouton n'est renommé. Un `rea-gui` déjà installé reçoit ce nouveau titre au prochain `installer.py --apply`.
**Icône REA.** `installer.py --apply` crée aussi un raccourci nommé **REA** qui ouvre l'interface REA (`rea-gui`) avec l'image `integration-rea/rea.svg` (fond noir, REA en rouge, « PRÉVOST local » en bleu ciel néon) : `~/.local/share/icons/rea.svg`, `~/.local/share/applications/rea-interface.desktop` et, si le dossier du bureau est défini (`xdg-user-dir DESKTOP`), une copie `REA.desktop` sur le bureau, marquée « autorisée » avec `gio`. Les fichiers remplacés sont sauvegardés comme les autres ; un lien symbolique est refusé. `--share-dir` et `--desktop-dir` changent les dossiers. Un ancien `REA.desktop` du menu des applications n'est pas touché : il peut rester à côté du nouveau. L'affichage de l'image sur un vrai bureau Ubuntu n'a pas été vu ici : les tests vérifient les fichiers écrits, pas le rendu.
Un `rea-gui` qui avait reçu le bouton sous son ancien nom `prevost-ia` est migré ; un ancien fichier `~/.local/bin/prevost-ia` éventuel n'est pas supprimé et peut être effacé à la main.

## Thème demandé

- Fond noir `#000000`, texte principal blanc `#FFFFFF`.
- Bandeau PRÉVOST et boutons rouges.
- Code coloré : mots-clés rouges, chaînes vertes, nombres jaunes, fonctions bleu ciel,
  types mauves, commentaires gris.

L'installateur prépare le thème de l'interface REA et le fichier Codex
`prevost-noir.tmTheme`. Le raccourci sélectionne ce thème de coloration lorsqu'il est
installé et envoie les couleurs de session blanc/noir aux terminaux compatibles OSC 10/11.
Il ne change ni le thème système ni la configuration permanente de Codex.

## Installation sur Ubuntu

Depuis la racine du dépôt, dans un terminal Ubuntu normal :

```bash
python3 integration-rea/installer.py --apply
```

Sans `--apply`, seul l'aperçu est affiché. L'installateur sauvegarde les fichiers existants
avant remplacement et restaure ces fichiers si l'écriture échoue. Il refuse un bouton
inconnu ou des fichiers ciblés qui sont des liens symboliques. Il ne touche pas aux autres
lanceurs ou au contenu de config.toml.

Fichiers ciblés : `~/.local/bin/rea-gui`, `~/.local/bin/rea-prevost` et
`$CODEX_HOME/themes/prevost-noir.tmTheme` (par défaut `~/.codex/themes`).
`--bin-dir` et `--theme-dir` permettent de préparer une installation dans d'autres dossiers.
Fermer puis rouvrir REA ; cliquer **rea-prevost** et choisir le dossier du projet.
XFCE Terminal est utilisé s'il est disponible ; Ptyxis puis x-terminal-emulator servent
également de lanceurs pris en charge. Aucun terminal n'est installé automatiquement.

```bash
rea-prevost --project /chemin/du/projet --diagnostic
rea-prevost --project /chemin/du/projet
rea-prevost --project /chemin/du/projet 'Corrige les tests en échec et vérifie les changements'
rea-prevost --project /chemin/du/projet --host http://127.0.0.1:11435
```

`--apercu` affiche la commande sans joindre Ollama ou lancer Codex. `--diagnostic` vérifie
les prérequis et les capacités annoncées, sans génération de code. Un modèle absent,
un serveur inaccessible ou des appels d'outils non annoncés interrompent le lancement ;
aucun modèle n'est téléchargé, créé ou substitué. Le modèle demandé peut être indiqué
par `--model`, sans changement du modèle par défaut. Les URL distantes ou avec identifiants
sont refusées ; l'endpoint Ollama choisi correspond à celui du fournisseur Codex local.

## Codex et vérification

Le fournisseur `rea_prevost` est défini pour ce lancement uniquement, avec l'endpoint
local `/v1` et le protocole Responses. La documentation officielle explique les
[fournisseurs locaux et personnalisés](https://learn.chatgpt.com/docs/config-file/config-advanced)
et les [options de Codex](https://learn.chatgpt.com/docs/cli/reference).
Le [thème de coloration Codex](https://learn.chatgpt.com/docs/config-file/config-sample)
est un fichier tmTheme utilisateur, sélectionné par un override de ce lancement.
Le sandbox `workspace-write` et les validations `on-request` restent actifs.
Aucun contournement de validation, lecture de mot de passe, cookie ou jeton n'est ajouté.

L'API Responses doit être compatible avec le serveur et le modèle. L'annonce `tools`
est un préalable, pas une preuve de fonctionnement agentique complet. La définition
PRÉVOST trouvée localement est basée sur qwen2.5-coder:7b avec un contexte de 4096 ;
cela ne prouve pas la configuration du modèle effectivement servi. La qualité réelle,
l'usage des outils et le budget de contexte restent à évaluer dans une session réelle.

```bash
python3 -m unittest discover -s integration-rea -p 'test_*.py' -v
```

**32 tests réussis** (16 pour le bouton prevost-rea, le titre de la fenêtre et l'icône REA : installation unique et idempotente, mise à niveau d'un `rea-gui` déjà modifié pour Codex, migration de l'ancien nom `prevost-ia`, refus d'un fichier inconnu ou d'un lien symbolique, projet avec espaces, annulation, modèle par défaut, exécution réelle depuis un autre dossier, terminal gardé ouvert en cas d'erreur) : installation/sauvegarde/idempotence, migration du précédent
raccourci de conversation, choix du projet avec espaces, terminal de repli, thème noir/blanc
et code coloré, paramètres Codex, refus de serveurs distants, outils non annoncés,
diagnostic sans exécution et séquences couleur.
Codex CLI 0.167.0 et ses options ont été inspectés localement. L'aperçu de l'installation
réelle est valide ; le code GUI préparé compile. Le test graphique sous Xvfb n'a pas pu
joindre son affichage dans le sandbox. Le diagnostic réel Ollama échoue sur une socket
interdite : aucune session de programmation avec le modèle n'est prétendue validée.

Cette session ne peut pas écrire dans les dossiers d'installation ni joindre Ollama.
Les fichiers sont prêts, testés et publiés sur `feature/rea-prevost-shortcut` ;
l'activation sur le bureau reste à faire avec la commande d'installation ci-dessus.
La branche Samsung V21 et sa pull request restent séparées ; aucun changement de main.
