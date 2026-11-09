# PRÉVOST V19 — récupération officielle Samsung / Google

Le programme principal `./prevost-samsung` conserve ses neuf premiers choix et ajoute
**10. Récupération Google FRP**. Cette section prépare les démarches ; elle ne communique
avec aucun téléphone, compte, navigateur ou service réseau et ne demande aucun secret.

```bash
./prevost-samsung
./prevost-samsung google-frp
./prevost-samsung google-frp --section google
./prevost-samsung google-frp --section samsung
./prevost-samsung google-frp --section bell
./prevost-samsung google-frp --section android
python3 -m unittest discover -s tests -v
```

`--section tout` est la valeur par défaut. Une sélection limite seulement l'affichage :
le dossier complet reste enregistré. Le paramètre fonctionne également au lancement du
menu. Les options V18 et les commandes V16/V17 restent disponibles ; `--watch` est refusé
pour le guide de récupération afin de ne pas répéter automatiquement les dossiers.

La confirmation visuelle déclarée par l'utilisateur est enregistrée dans
`outils/v19/confirmation_utilisateur.json` : écran « Vérifier votre compte Google »,
modèle déclaré SM-G990W2, provenance utilisateur, date d'enregistrement et limites.
Aucun indicateur système FRP n'est prétendu mesuré ; aucune heure d'observation inventée.
Une copie sans ce fichier ne déclare pas la confirmation acquise.

Chaque consultation crée un nouveau dossier `rapports/v19/dossier-*` contenant :

- `rapport.md` et `rapport.json` : confirmation, analyse limitée des relevés V17/V18,
  références avec empreintes, démarches officielles et sources vérifiées le 9 novembre 2026 ;
- `brouillon-samsung.txt` et `brouillon-bell.txt` : demandes prêtes à relire, sans envoi ;
- `SHA256SUMS` : empreintes des quatre fichiers.

Le choix 7 affiche le dernier rapport V19 s'il existe, ainsi que les derniers rapports V18/V16 disponibles.
Les anciens fichiers restent disponibles sur disque et dans l'export. Le choix 8 produit
une archive V19 avec les sources, tests et rapports V16 à V19, vérifiée par SHA256.
V19 lit uniquement les relevés connus V17/V18 ; ses synthèses ne recopient pas les
numéros de série ni les sorties personnelles brutes. L'intégrité des rapports antérieurs
est contrôlée. Les rapports bruts historiques peuvent toujours contenir des identifiants USB.

Aucun mot de passe, cookie, jeton, formulaire, session Google/MonBell ni document personnel
n'est collecté. Les justificatifs se présentent personnellement au prestataire officiel.
Aucun effacement, flash, contournement FRP, changement téléphone ou configuration système.
Les démarches à effectuer sur le téléphone après récupération restent hors de cette mission.

Voir `rapports/v19/RAPPORT-V19.md` pour les conclusions. La livraison Git autonome
`exports/prevost-v18-source` reçoit la branche `mission-prevost-v19`, dérivée de V18 ;
le `.git` original reste intact. Aucun push.
