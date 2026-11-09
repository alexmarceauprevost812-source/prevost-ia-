# PRÉVOST SAMSUNG RECOVERY V16

Python 3.9+ sous Linux, bibliothèque standard uniquement. Aucune installation ni sudo requis.

```bash
cd /home/ti-lex/Samsung-Android16
./prevost-samsung                 # menu TUI LexOS
./prevost-samsung diagnostic
./prevost-samsung detect
./prevost-samsung usb --watch 3   # actualisation après chaque sonde + 3 secondes
./prevost-samsung adb --serial NUMERO
./prevost-samsung mtp
./prevost-samsung recovery
./prevost-samsung informations
./prevost-samsung historique
./prevost-samsung rapport
./prevost-samsung export
python3 -m unittest discover -s tests -v
```

Le menu ne se rafraîchit pas en arrière-plan : chaque choix déclenche une mesure actuelle.
`--watch` répète les mesures et enregistre chacune ; Ctrl+C arrête la surveillance.
Chaque commande de sonde réalise le diagnostic complet afin de corréler les transports,
puis affiche la section demandée. Les sondes externes ont un délai maximal de 12 secondes chacune.
Le programme ne modifie ni mode USB, ni état de débogage, ni paramètres Android.
ADB peut démarrer son serveur sur l'ordinateur et utiliser les clés ADB locales habituelles.
Aucune autorisation ADB ne peut être forcée. Les refus sont enregistrés.

## Sources et confiance

USB : lecture de `/sys/bus/usb/devices`, VID Samsung 04e8, PID, numéro de série,
produit, interfaces et port physique. Ces descripteurs ne suffisent pas à prouver SM-G990W2.
MTP : montages existants exposés par `gio mount -li`, association par série USB lorsqu'elle
est possible. Aucune activation de montage et aucune lecture de fichiers du téléphone.
Une interface image USB seule constitue un indice PTP/MTP.
ADB : `adb devices -l`, puis cible explicite `adb -s SERIAL shell` ; seuls `getprop CLE`
et `settings get ESPACE CLE` pour une liste fermée sont exécutés.
La collecte automatique exige un transport corrélé à un périphérique Samsung USB ou
une annonce SM_G990W2. Si plusieurs candidats existent, utiliser `--serial`.
Le fabricant Samsung doit être confirmé avant de poursuivre la collecte.
Les propriétés fabricant/modèle donnent une confiance élevée dans l'identification déclarée
par Android, pas une preuve cryptographique du matériel. Un firmware peut falsifier ses propriétés.
Recovery : état ADB `recovery`, état `sideload` distinct et propriété `ro.bootmode` si lisible.
L'absence de transport ADB ne permet pas d'exclure Recovery.

Configuration : valeurs actuelles `device_provisioned` et `user_setup_complete` ; elles ne
retracent pas la première activation. Aucun historique navigateur, compte, mot de passe,
cookie ou jeton n'est recherché. FRP : drapeau `secure_frp_mode` dans Global (Android récent) et Secure (compatibilité), et présence de `ro.frp.pst`
sans ouvrir la partition annoncée. La présence d'un support FRP ne prouve pas son activation ;
la valeur 0 ou une propriété inaccessible ne prouve pas son absence. Aucun contournement.

## Rapports, conservation et exports

`rapports/v16/` : un JSON et un TXT par diagnostic, historique JSONL automatique,
`erreurs.jsonl` pour outils absents, refus, délais et erreurs locales.
Les fichiers TXT présentent le diagnostic structuré complet avec sources et limites.
Les numéros de série sont conservés pour corréler les connexions : les rapports sont personnels.
Un outil absent, un téléphone débranché ou une information inaccessible restent des résultats
explicites et ne sont jamais remplacés par des valeurs inventées.
Les anciens rapports et archives restent en place. La sauvegarde complète préalable est dans
`sauvegardes/prevost-avant-v16-*.tar.gz`, avec SHA256 et inventaire ; elle contient aussi les
anciens fichiers sensibles et ne doit pas être diffusée.
L'export `exports/prevost-samsung-v16-*.zip` inclut code, documentation, tests et rapports V16,
un manifeste SHA256 interne vérifié et une empreinte externe `.zip.sha256`.
Les anciens rapports sont préservés sur disque et dans la sauvegarde complète ; ils ne sont
pas ajoutés à l'export technique V16, pour éviter de redistribuer les données de navigateur V13.

```bash
cd exports
sha256sum -c prevost-samsung-v16-*.zip.sha256
```

Références : code source Android Settings pour les indicateurs, et documentation ADB :
https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/provider/Settings.java
https://developer.android.com/tools/adb
