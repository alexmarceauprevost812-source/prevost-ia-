# Raccourci rea-prevost pour REA LexOS

Ce paquet corrige le bouton local qui cherchait le nom de programme complet
`ollama run prevost:latest`. Le bouton devient **REA-PRÉVOST** et lance le nouveau
raccourci `rea-prevost`, lequel ouvre le modèle Ollama `prevost:latest`.
Il n'enregistre pas un nouveau fournisseur de décompilation dans le serveur MCP REA.

Depuis le terminal Ubuntu normal :

```bash
python3 /home/ti-lex/Samsung-Android16/integration-rea/installer.py --apply
```

Sur une copie GitHub, exécuter `python3 integration-rea/installer.py --apply`.
Sans `--apply`, seul l'aperçu est affiché. L'installation sauvegarde les lanceurs
existants dans `~/.local/bin/rea-prevost-sauvegarde-DATE` avant de les remplacer.
Fermer puis rouvrir REA pour voir le bouton. La commande `rea-prevost` fonctionne
également depuis le terminal si `~/.local/bin` est dans le PATH.

Aucun modèle téléchargé ou créé. Le modèle doit déjà être présent sur le serveur
Ollama courant ; `OLLAMA_HOST` est conservé. La définition existante de l'utilisateur
emploie qwen2.5-coder:7b ; sa présence sur le serveur n'a pas pu être vérifiée dans le
sandbox, dont les sockets locales sont interdites. Le serveur n'est pas modifié.
Le dossier `~/.local/bin` n'est pas accessible en écriture depuis cette session :
l'installateur est préparé et testé, mais l'installation sur le bureau reste à exécuter.

```bash
python3 -m unittest discover -s integration-rea -p 'test_*.py' -v
```
