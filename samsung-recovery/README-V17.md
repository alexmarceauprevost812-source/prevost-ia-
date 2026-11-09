# PRÉVOST V17 — étude des blocages et comparaison d’environnements

Complément de diagnostic à V16, sans remplacement de l’application existante.
Python 3.9+ ; outils déjà présents utilisés sans installation, sudo ou modification DNS.

Depuis le terminal Ubuntu normal :

```bash
cd /home/ti-lex/Samsung-Android16
python3 outils/v17/diagnostic_environnement.py --label ubuntu
```

Depuis l’environnement Codex, le même script est lancé avec `--label codex`.
Les étiquettes indiquent le lieu déclaré de lancement ; ce ne sont pas des attestations.

Le script exécute 20 tests : versions Python/ADB, résolution locale et publique,
état du résolveur, accès USB, `adb devices -l`, permissions de sockets locales et
requêtes HEAD vers trois URL de métadonnées Samsung. Aucune image firmware n’est
chargée, aucun formulaire soumis, aucune session navigateur inspectée.
ADB peut lancer son serveur sur le PC et utiliser ses clés locales habituelles.
Aucune commande `adb shell`, reboot, reset, flash, pull, push ou sideload n’est exécutée.

Les sorties exactes stdout/stderr, argv, codes de retour, durées et horodatages sont dans
`rapports/v17/environnement-LABEL-*.json` et `.txt`. Une empreinte du JSON est ajoutée.
Un outil absent a un code `null`, car aucun processus n’a démarré. Un processus tué sur
délai a son code réel (généralement -9 sous Linux). Le code 0 du script signifie que la
collecte est terminée ; les tests individuels peuvent échouer.

Les requêtes curl ignorent ~/.curlrc et les proxys hérités : ce sont des tests directs
sans cookies ni identifiants. Sur un réseau qui exige un proxy, leur échec ne démontre
pas que le navigateur normal échoue. HEAD ne valide pas une image firmware.
Les rapports système peuvent contenir des adresses réseau, noms d’interfaces et séries
USB : conserver ces fichiers localement et vérifier leur contenu avant diffusion.

Chaque lancement vérifie les empreintes des rapports déjà présents et crée de nouveaux
fichiers. S’il trouve un relevé de l’autre environnement, il ajoute une comparaison des
codes. Il faut aussi comparer stdout/stderr : ADB code 0 peut avoir une liste vide ou un
appareil non autorisé. Des relevés faits à des moments différents ont cette limite.
Le contenu des anciens historiques de navigateur n’est jamais interprété.

Tests :

```bash
python3 -m unittest discover -s tests -v
```

Solutions envisagées : exécuter les sondes matérielles depuis Ubuntu normal ; garder
Codex pour l’analyse locale ; vérifier la connectivité hôte seulement si elle échoue
également hors Codex ; employer les pages officielles Samsung pour le firmware et les
canaux Google/Samsung/Bell pour la propriété et le compte. Aucune désactivation du
sandbox, règle de sécurité ou protection du téléphone n’est effectuée par cet outil.
