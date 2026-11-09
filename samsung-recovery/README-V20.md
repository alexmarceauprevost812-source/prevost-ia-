# PRÉVOST V20 — outil Python de récupération Samsung

Python 3.9+, Linux ; bibliothèque standard uniquement. Le lanceur principal conserve
les commandes V16/V18/V19 et ajoute le choix **11. Assistant récupération Samsung V20**.
Le menu utilise un fond noir, un bandeau rouge, du texte blanc, des commandes jaunes
et des résultats bleu ciel RGB 135/206/235. Hors terminal ou avec `NO_COLOR`, pas d'ANSI.

Depuis le dossier du projet (ou `samsung-recovery` sur GitHub) :

```bash
./prevost-samsung recuperation
./prevost-samsung recuperation --diagnostic
./prevost-samsung recuperation --rapport
```

`prevost-samsung recuperation` fonctionne aussi si ce dossier est déjà dans votre PATH.
Aucune installation globale ou modification du PATH n'est réalisée par la mission.

- `recuperation` : sondes actuelles, recherche dans les anciens rapports, guide Google,
  démarches officielles Android et création des demandes Samsung/Bell non envoyées.
- `--diagnostic` : mêmes sondes et rapport, sans générer les demandes de propriété.
- `--rapport` : lire le dernier rapport V20 local, sans sondes, réseau ni écriture.
  Retour 1 s'il n'existe pas ; aucun diagnostic lancé automatiquement.

Autres paramètres :

```bash
./prevost-samsung recuperation --label ubuntu --delai 15
./prevost-samsung recuperation --sans-adb --sans-mtp --section bell
```

`--label` est déclaratif (`local`, `ubuntu`, `codex`). `--delai` borne chaque commande
entre 1 et 60 secondes. `--sans-adb` évite tout appel ADB ; `--sans-mtp` évite la lecture
des métadonnées de racine mais conserve la liste des montages. `--section` choisit la
partie affichée du guide ; le dossier complet reste conservé. Ces paramètres peuvent
aussi être fournis au lancement du menu. Les modes diagnostic/rapport sont exclusifs.
V20 refuse `--watch` et `--serial` ; il énumère les Samsung et ne sélectionne aucun shell.

## Mesures et limites

V20 lit le fabricant/produit USB, les interfaces, les pilotes, les endpoints et les
permissions apparentes du nœud. Il utilise exclusivement :

- `lsusb -d 04e8:` ;
- `adb devices -l` (peut démarrer le serveur local et utiliser ses clés habituelles) ;
- `gio mount -li` ;
- `gio info -a standard::type,filesystem::type,filesystem::readonly URI_MTP` uniquement
  pour une racine MTP associée à un unique port Samsung par série ou adresse USB.

Aucun parcours de fichiers MTP ni `mtp-detect` non ciblé. Une erreur GIO/libusb/ADB est
conservée avec son code et sa sortie ; elle n'est pas interprétée comme une preuve FRP.
Un retour GIO 0 avec des erreurs de session reste une vue incomplète. Les transports
ADB non associés sont séparés des Samsung ; `sideload` confirme un transport limité,
pas un shell ou une autorisation de flash. Plusieurs Samsung restent distincts par port.

Le modèle SM-G990W2 est déclaré par l'utilisateur. Un descripteur `SAMSUNG_Android`
ne certifie pas le modèle exact ; Android installé, bootloader et drapeau FRP ne sont
pas lus. La confirmation utilisateur V19 de l'écran Google est reprise comme historique.
Le compte Google antérieurement synchronisé ou une démarche officielle de propriété
reste nécessaire pour la remise en service ; aucun résultat de déblocage n'est garanti.

Les sources Samsung/Google ont été consultées le 9 novembre 2026 via l'outil web.
Le lancement de l'outil ne vérifie pas ces pages en ligne : le rapport donne la date et
les liens. Smart Switch/récupération d'urgence ne sont pas exécutés et ne constituent
pas une solution démontrée à la vérification Google.

## Dossier et validation

Chaque collecte crée `rapports/v20/recuperation-DATE-ALEA/` : `rapport.json`,
`rapport.txt`, `SHA256SUMS` et, en mode complet, `demande-samsung.txt` et
`demande-bell.txt`. Les anciens rapports ne sont jamais réécrits. Leur conservation
est contrôlée par empreintes pendant la collecte. Les analyses historiques ciblent
uniquement les relevés V17/V18 et rapports V19 connus, avec provenance et SHA256.
Le choix 7 affiche aussi le dernier rapport V20 ; l'export inclut maintenant V16 à V20.

```bash
python3 -m unittest discover -s tests -v
```

Aucun effacement, flash, réinitialisation, changement téléphone, extraction de secrets,
lecture de navigateur ou automatisation de formulaire. Les justificatifs et identifiants
restent à présenter personnellement au service officiel. Les rapports techniques locaux
peuvent contenir une série USB ; les dossiers générés sont exclus de la livraison GitHub.
Voir `rapports/v20/RAPPORT-V20.md` pour les mesures réelles et fonctions opérationnelles.
