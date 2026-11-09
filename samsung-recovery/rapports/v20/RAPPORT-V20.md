# PRÉVOST V20 — outil de récupération Samsung

9 novembre 2026. Cible déclarée : Galaxy S21 FE 5G SM-G990W2.

## Fonctions opérationnelles

Le lanceur Python principal fournit désormais `recuperation`, `recuperation --diagnostic`
et `recuperation --rapport`, ainsi que le choix 11 du menu. Les trois commandes ont été
exécutées réellement et retournent 0 dans ce projet. Le code 0 signifie que la collecte
ou la lecture du rapport est terminée, pas que toutes les sondes ont réussi.

| Fonction | Essai réel dans Codex | Limite |
|---|---|---|
| Détection automatique Samsung | USB 04e8:6860 visible dans sysfs | Modèle exact non certifié par le produit générique |
| Interfaces, pilotes, endpoints | Descripteurs lisibles ; MTP, CDC ACM et constructeur | Aucune interface ADB ff/42/01 annoncée au relevé |
| Accès libusb | lsusb échoue, code 1 | Restriction de l'environnement ; ne prouve pas une panne USB Ubuntu |
| Liste ADB | Échec du listener local, code 1 | Aucun transport téléphone utilisable établi dans Codex |
| Vue MTP | GIO retourne des erreurs de session | Vue incomplète ; aucune racine Samsung interrogeable ici |
| Recovery | Aucun transport ADB associé observé | Mode Recovery/Download actuel non établi |
| Recherche historique | Relevés V17/V18 et rapports V19 analysés avec provenance/SHA256 | Mesures historiques, pas état actuel |
| Assistant Google | Procédure officielle et variantes adresse oubliée/délai disponibles | Aucune connexion au compte ni saisie de secret |
| Dossier de propriété | Demandes Samsung et Bell générées en mode complet | Pièces réelles à présenter personnellement au prestataire |
| Rapport JSON/TXT | Fichiers uniques avec SHA256SUMS | Rapports bruts locaux, non publiés sur GitHub |
| Lecture `--rapport` | Dernier rapport affiché | Aucune nouvelle sonde ni écriture ; code 1 si absent |

Les essais automatisés couvrent aussi les cas de plusieurs téléphones, ADB non associé,
Recovery/sideload limité, MTP accessible/refusé, outils omis, absence de rapport et absence
de confirmation utilisateur. Les accès MTP réussis sont simulés dans les tests ; aucun
accès MTP réussi au téléphone n'est prétendu mesuré depuis Codex.

## Mise en œuvre

La liste de commandes V20 est fermée : lsusb Samsung, `adb devices -l`, liste GIO et
`gio info` avec trois attributs de racine seulement. La racine MTP doit être reliée à
un unique port Samsung par série ou adresse USB. Aucun parcours des fichiers, aucune
commande `mtp-detect` non ciblée, aucun shell, reboot, sideload, flash ou reset.
L'annonce d'une interface, l'existence d'un montage et le succès de sa requête de
métadonnées sont trois informations séparées. Une erreur de session reste visible même
si GIO retourne 0. Les propriétés Android installées ne sont pas inventées.

Le menu affiche fond noir, bandeau rouge, texte blanc, commandes jaunes et résultats
bleu ciel RGB 135/206/235. Aucune couleur ANSI hors terminal ou avec NO_COLOR.
Toutes les fonctions antérieures restent accessibles. Le choix 7 et l'export intègrent V20.
Les options `--label`, `--delai`, `--sans-adb`, `--sans-mtp` et `--section` sont disponibles.

## Situation Google et remise en service

La déclaration V19 de l'utilisateur confirme l'écran « Vérifier votre compte Google ».
V20 la reprend avec sa provenance et sa date ; aucun écran ni drapeau FRP n'est lu
techniquement. Les relevés Ubuntu historiques montrent MTP et une liste ADB vide ;
ils ne fournissent pas d'autorisation pour changer le téléphone.

La [protection Android officielle](https://support.google.com/android/answer/9459346?hl=fr)
exige un compte Google précédemment ajouté et synchronisé lors de la vérification de
propriété. Un nouveau compte ne remplace pas ce compte. Première démarche : récupérer
personnellement ce compte sur un autre appareil via [Google](https://accounts.google.com/signin/recovery),
ou retrouver son adresse via la recherche officielle. Respecter le délai affiché.
Aucun accès aux mots de passe, cookies ou jetons, aucune tentative automatisée.

Si cela échoue, préparer une preuve d'achat liant l'appareil à son acquisition et
faire confirmer les pièces, conditions et frais au [centre agréé Samsung Canada](https://www.samsung.com/ca/support/service-center/).
Si l'achat provient de Bell, demander un duplicata ou une orientation au soutien officiel.
Les modèles de demandes sont inclus, sans données personnelles ni envoi. La vérification
officielle de propriété ne garantit pas un déblocage ou la conservation des données.
Sans ancien compte utilisable ou solution acceptée par le prestataire officiel, la
remise en service reste bloquée ; V20 ne peut pas lever cette protection.

## Restauration Android officielle

Les sources ont été revérifiées via l'outil web le 9 novembre 2026. La [page du SM-G990W2](https://doc.samsungmobile.com/SM-G990W2/023358220727/eng.html)
publie G990W2VLSNIZI2, Android 16, correctif du 5 octobre 2026. Ce n'est pas une mesure
de la version installée ni une validation d'un binaire BMC ou du bootloader.
[Smart Switch Windows/Mac](https://www.samsung.com/ca/apps/smart-switch/) peut proposer
les mises à jour disponibles ; la [récupération d'urgence Samsung](https://update.kies.samsung.com/SmartSwitchPC_recovery_guide/firmware/emergencyrecovery/)
concerne un échec de mise à jour reconnu. Leur disponibilité effective pour cet appareil
reste à confirmer. L'écran Google ne démontre pas une corruption Android ; une
restauration n'est pas une solution démontrée à la vérification du compte.
Aucun téléchargement firmware ni opération sur le téléphone n'a été effectué.

## Validation et conservation

90 tests automatisés réussis, dont 22 tests V20. Les trois commandes demandées ont été
vérifiées réellement ; leurs codes sont conservés dans un relevé local. Les 83 fichiers
de rapports préexistants au début de V20 sont inchangés selon les contrôles SHA256.
Le journal des tests et le contrôle final sont conservés dans `rapports/v20`.
Les dossiers générés JSON/TXT sont locaux et exclus de Git ; les synthèses et sources
peuvent être publiées. Les anciens rapports V17/V18/V19 restent en place.

La livraison locale utilise `mission-prevost-v20`, dérivée de V19 dans
`exports/prevost-v18-source`. La publication GitHub place ce module dans
`samsung-recovery` de `alexmarceauprevost812-source/prevost-ia-`, avec un lien dans le
README racine. Le code existant de PRÉVOST IA est conservé. Son contrôle V19 a donné
89 tests réussis sur 91 ; deux tests CLI sont bloqués par l'historique en lecture seule
dans le sandbox, indépendamment du module Samsung.
