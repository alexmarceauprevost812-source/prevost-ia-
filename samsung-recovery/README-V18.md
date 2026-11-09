# PRÉVOST V18 — Samsung Recovery

Le lanceur principal `./prevost-samsung` intègre V18 (choix 9). Les fonctions V16 et
l'analyse V17 restent disponibles. Le choix 7 affiche aussi le dernier relevé V18 ;
l'export ZIP inclut maintenant les sources, tests et rapports V16 à V18.

```bash
./prevost-samsung
./prevost-samsung recovery-v18 --label ubuntu --delai 15
./prevost-samsung recovery-v18 --sans-adb --sans-mtp
python3 -m unittest discover -s tests -v
```

Les paramètres V18 fonctionnent aussi au lancement du menu :

- `--label local|ubuntu|codex` : environnement déclaré, pas une attestation.
- `--sans-adb` : aucun appel ADB, ni tentative de démarrage de son serveur.
- `--sans-mtp` : omettre `mtp-detect`, conserver sysfs et la liste des montages.
- `--delai 1..60` : secondes maximales par commande (15 par défaut).

Ils ne modifient que le diagnostic V18. `--serial` concerne les sondes V16 ; V18
énumère les appareils et ne lance pas de shell. La répétition `--watch` reste
réservée aux diagnostics V16 afin d'éviter des sessions libmtp répétées.

V18 lit les descripteurs et pilotes USB, les permissions apparentes du nœud,
`lsusb`, `adb devices -l`, `gio mount -li` (liste uniquement). Il tente `mtp-detect`
si un seul Samsung est visible et aucun montage MTP annoncé. Cette commande ouvre
une session de métadonnées MTP ; elle ne parcourt ni ne copie les fichiers. Un
montage existant évite cette session concurrente. Fermer manuellement un logiciel
MTP peut être utile pour un futur relevé Ubuntu ; le diagnostic ne le ferme pas.
Les commandes ont un délai, et leurs codes, sorties et erreurs sont conservés.
ADB peut tenter de démarrer son serveur local et utiliser ses clés habituelles.

Aucune installation, sudo, règle udev, configuration USB/Android, commande de
redémarrage, flash, effacement ou contournement FRP. Rapports locaux à noms uniques
et empreintes SHA256 ; intégrité des anciens rapports vérifiée pendant la collecte.
Les rapports bruts peuvent contenir un numéro de série USB : vérifier avant partage.
Un succès du collecteur indique que le rapport a été écrit, pas que les sondes ont réussi.

Voir `rapports/v18/RAPPORT-V18.md` pour les conclusions et sources officielles.
La livraison Git autonome se trouve dans `exports/prevost-v18-source`, branche
`mission-prevost-v18`. Le dossier `.git` original est vide et n'a pas été modifié.
