# MISSION PRÉVOST V18 — 9 novembre 2026

## Conclusions

Samsung USB **04e8:6860**, produit `SAMSUNG_Android`, actuellement visible dans sysfs.
**Android probable**, sur la base de l'interface MTP. Le mode exact reste indéterminé
sans lecture de l'écran : aucun changement de mode n'a été effectué. Ni Recovery ni
Download ne sont confirmés. Le modèle SM-G990W2 est la cible déclarée du projet ;
le descripteur générique actuel ne suffit pas à confirmer ce modèle précis.

## Analyse V17

Les deux relevés `rapports/v17/environnement-{codex,ubuntu}-*.json` ont été lus.
Leur contenu et empreinte sont référencés dans les nouveaux rapports JSON V18.
La synthèse V17 précédait le relevé Ubuntu : sa mention « Ubuntu pas encore disponible »
est dépassée par la mesure Ubuntu du 9 novembre à 06:26 UTC, sans modification de l'ancien texte.

Ubuntu : lsusb réussit et annonce MTP ; ADB retourne 0 mais **aucun appareil**.
DNS fonctionnel ; documentation Samsung HTTP 200 ; catalogue BMC HTTP **403 mesuré**.
Le code curl 0 exprime ici le succès de la requête HTTP, pas un accès au catalogue.
Codex : échecs libusb, sockets ADB et DNS. Ces restrictions d'environnement ne
prouvent pas une panne du téléphone ni du réseau Ubuntu.

## Interfaces actuellement observées

Port sysfs `3-8`, bus 003, appareil 026, quatre interfaces :

| Interface | Classe / sous-classe / protocole | Libellé | Pilote observé |
|---|---|---|---|
| 00 | 06 / 01 / 01 | MTP | usbfs |
| 01 | 02 / 02 / 01 | CDC Abstract Control Model | cdc_acm |
| 02 | 0a / 00 / 00 | CDC ACM Data | cdc_acm |
| 03 | ff / 40 / 02 | constructeur, usage non établi | aucun |

Aucune interface `ff/42/01` (ADB habituel) n'est annoncée dans cette configuration.
Les interfaces CDC ne sont pas une autorisation ADB ; aucun port série n'a été ouvert.
Les descripteurs sont lisibles, mais le nœud `/dev/bus/usb/003/026` n'est pas visible
dans Codex. La possibilité d'ouvrir réellement une interface n'y est donc pas établie.

`lsusb` : code 1, « unable to initialize libusb: -99 ».
ADB : code 1, impossibilité d'installer le listener local, « Operation not permitted ».
`gio mount -li` : code 0 mais erreurs de connexion aux proxies de session ; aucun
montage MTP observé dans cette vue partielle. Cela ne prouve pas l'absence de montage Ubuntu.
`mtp-detect` est installé (libmtp 1.1.23) mais retourne 1 : « Libusb1 init failed ».
Les capacités MTP, stockage, version logicielle et modèle via MTP ne sont pas lisibles
ici. Aucun fichier utilisateur n'a été listé ou transféré.

## USB, ADB et FRP : trois sujets distincts

- USB : énumération Samsung confirmée ; accès libusb bloqué dans Codex.
- ADB : serveur bloqué dans Codex ; sous Ubuntu V17, liste vide, sans état
  `unauthorized`. L'absence d'interface ADB est cohérente avec cette liste vide,
  sans établir pourquoi le téléphone ne la propose pas.
- FRP : état actuel **indéterminé**. Aucun des constats USB, ADB ou HTTP ne lit
  ce mécanisme. La mention historique de sideload ne décrit pas l'état présent.

## Possibilités officielles SM-G990W2

La [documentation Samsung du modèle](https://doc.samsungmobile.com/SM-G990W2/023358220727/eng.html)
a été vérifiée via l'outil web : G990W2VLSNIZI2, Android 16, publication 2026-10-23,
correctif 2026-10-05. Cela décrit une mise à jour publiée, pas la version installée,
ni un paquet BMC téléchargeable ou compatible avec le bootloader actuel.

[Samsung Canada Smart Switch](https://www.samsung.com/ca/apps/smart-switch/) propose
un logiciel PC Windows/Mac et des mises à jour lorsqu'elles sont disponibles.
Aucun client Linux officiel de restauration n'est établi par cette page.
Le [guide Samsung de récupération d'urgence](https://update.kies.samsung.com/SmartSwitchPC_recovery_guide/firmware/emergencyrecovery/)
concerne un échec de mise à jour reconnu par Smart Switch ; la disponibilité effective
pour cet appareil et ce firmware reste à vérifier auprès de Samsung. Ce n'est pas
une garantie de restauration universelle ni de conservation des données. Aucune
récupération, initialisation ou mise à jour n'est lancée dans cette mission.

Le [centre agréé Samsung Canada](https://www.samsung.com/ca/support/service-center/)
est la voie officielle pour faire confirmer la prise en charge du SM-G990W2 et
les possibilités de réparation avec conservation des données. En cas de problème
de propriété/compte, [Samsung recommande la récupération du compte ou une preuve d'achat au centre agréé](https://www.samsung.com/us/support/answer/ANS10003349/).
Aucun déverrouillage n'est garanti ; une restauration logicielle n'établit pas que
la vérification Google disparaîtra. Aucun paquet firmware n'a été téléchargé.

## Prochaines étapes sans changement de configuration

1. Observer l'écran actuel : écran Android/verrouillage/configuration, menu « Android
   Recovery », ou écran « Downloading ». Noter seulement son libellé, sans sélectionner
   d'action ni communiquer d'identifiants. Cela départagera les modes sans redémarrer.
2. Dans le terminal Ubuntu normal, lancer depuis le projet :
   `./prevost-samsung recovery-v18 --label ubuntu --delai 15`.
   Comparer descripteurs, accès au nœud USB, stderr, états ADB et métadonnées libmtp.
   Si une session MTP est occupée, conserver l'erreur ; aucun démontage automatique.
3. Si aucun accès MTP ne peut être établi, conserver les erreurs exactes et distinguer
   permissions, occupation et écran verrouillé. Ne pas activer le débogage, changer
   le mode USB ou installer de règle udev dans le cadre de cette mission.
4. Faire confirmer à Samsung les options applicables au modèle, en précisant
   l'exigence de conservation des données. Toute opération d'initialisation ou de
   récupération modifiant le téléphone est hors du présent périmètre.
5. Si l'écran demande le compte Google précédemment associé, effectuer personnellement
   la récupération officielle du compte, ou présenter la preuve d'achat au centre.
   Le refus HTTP BMC ne doit pas orienter cette démarche.

## Livraison et validation

Lanceur principal V18 : choix 9, commande `recovery-v18`, options d'environnement,
omission ADB/MTP et délai ; choix 7 avec rapports V18 ; export complet V16/V17/V18.
Les 58 tests automatisés passent (V16, V17 et 9 tests V18). Les cas de téléphone sont
simulés ; les sondes réelles limitées par Codex sont consignées séparément.
Journaux de tests et rapports bruts JSON/TXT/SHA256 dans ce dossier. Les contrôles
intégrés de conservation n'ont trouvé aucun ancien rapport modifié ou manquant.

Le `.git` original est vide/non exploitable et reste intact. À la demande de créer
une branche de remplacement, une livraison source autonome est préparée dans
`exports/prevost-v18-source`, sur `mission-prevost-v18`. Ce n'est pas une branche
d'un historique Git original accessible. Aucun push ni publication.
