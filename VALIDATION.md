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
