# PRÉVOST Samsung V21 — résultats et limites

Date : 9 novembre 2026. Branche de travail : `feature/samsung-recovery-v21`.

## Résultat

Menu 12 « DIAGNOSTIC SAMSUNG V21 » et commandes :

```bash
./prevost-samsung diagnostic-v21
./prevost-samsung diagnostic-v21 --rapport
```

Les deux commandes ont été exécutées dans le projet local. La première crée un dossier
privé et une archive masquée ; la seconde consulte le dernier rapport sans sonde ni écriture.
Le succès de la collecte ne signifie pas que chaque accès matériel est disponible.
Les fonctions V16 à V20, le thème terminal et l'assistant Google sont conservés.

## Mesures réelles dans cette session

| Point | Observation | Portée |
|---|---|---|
| USB Samsung | Un appareil Samsung énuméré dans sysfs, avec quatre interfaces | Détection uniquement, aucun accès aux données démontré |
| Descripteurs | Interface MTP, deux CDC ACM et une constructeur | Aucune interface ADB ff/42/01 annoncée au relevé |
| Contexte processus | NoNewPrivs=1, Seccomp=2, un filtre | Le filtre présent ne permet pas d'identifier sa règle exacte |
| Socket locale | Création AF_INET refusée, errno EPERM | Refus local avant tout accès au téléphone ; cohérent avec une restriction d'environnement |
| Nœud USB | Absent de cette vue | Namespace/devfs restreint possible ; ne prouve pas un câble débranché |
| ADB | Serveur local incapable d'installer son listener | Aucun état ADB téléphone exploitable dans Codex |
| MTP/GIO | Vue de session incomplète, erreurs de permissions | Ne démontre pas l'absence de montage dans Ubuntu normal |
| Recovery | Aucun transport associé établi | Aucun changement de mode effectué |

Les relevés Ubuntu antérieurs montrent une autre visibilité USB/MTP et une liste ADB
vide. Ils ne sont pas de nouvelles mesures V21 sous Ubuntu normal. Une étiquette
`--label ubuntu` ne suffit jamais à certifier l'environnement ni à attribuer un échec
aux permissions Ubuntu. L'attribution précise du filtre ou d'une politique de l'hôte
reste inconnue. Aucune règle udev, ACL, permission, session ou configuration modifiée.

## Fiabilité du diagnostic

V21 distingue le refus du listener local, les permissions apparentes du nœud USB,
l'état `no permissions`, `unauthorized`, `offline`, la liste ADB vide, les outils non
lancés, les délais dépassés et les erreurs de session GIO. Un nœud visible avec des
accès insuffisants appelle un contrôle des droits/ACL dans Ubuntu normal ; V21 ne
présume pas que le pilote ou une règle udev en est la cause.

Les associations ADB utilisent le port USB explicite lorsqu'il est annoncé ; sinon,
une série doit désigner un seul Samsung. Des séries dupliquées ou un port discordant
ne deviennent pas une preuve de Recovery. Le succès d'une lecture d'attributs MTP
reste limité à ces attributs de racine. Aucun fichier utilisateur lu ou listé.

## Partage et dossier de propriété

Les rapports privés JSON/TXT contiennent les preuves locales et restent dans un dossier
0700, avec fichiers 0600. Les versions partageables sont générées par liste blanche :
alias Samsung-1/2, VID/PID, classes, états, codes et constats utiles ; aucune série,
URI MTP, adresse de bus/port, chemin personnel, UID/GID, sortie brute ou empreinte du
rapport privé. Le contrôle de l'archive réelle n'y retrouve aucune série du relevé privé.

`partage.zip` contient seulement les rapports masqués, les deux modèles de demandes
Samsung/Bell sans données personnelles et leur SHA256SUMS. L'export local complet du
menu 8 contient toujours les historiques privés et ne doit pas être confondu avec cette
archive. Les fichiers générés ne sont pas ajoutés à GitHub.

L'assistant Google V20 et les modèles Samsung/Bell restent disponibles. La confirmation
de l'écran Google vient de la déclaration utilisateur V19, pas d'une lecture technique
actuelle. La récupération officielle nécessite le compte antérieurement synchronisé ou
une solution acceptée par le prestataire de vérification de propriété ; aucun déblocage
garanti. Les sources officielles sont datées dans le guide ; V21 ne prétend pas les
revalider en ligne. Aucun contournement FRP, secret collecté, formulaire envoyé,
modification du téléphone, reset, flash, reboot ou paquet sideload.

## Validation avant fusion

- Suite Samsung V16–V21 : **114 tests réussis**, également dans la copie de livraison.
- **24 nouveaux tests V21** : distinctions environnement/permissions/RSA, listener et
  fermeture, nœud absent, association ambiguë, suppression des identifiants, modes de
  lecture, archive et SHA256, conservation, CLI/menu et export.
- Application PRÉVOST IA existante : **89 tests réussis sur 91**. Deux tests CLI
  (`test_cli_manual_mission_real`, `test_cli_typo_fake_nmap_real_subprocess`) échouent
  en tentant d'écrire l'historique dans un emplacement en lecture seule du sandbox.
  Le code de cette application n'a pas été changé ; cette limite était déjà observée avant V21.
- Les scénarios d'accès MTP réussi et de Recovery sont simulés. Les sondes réelles
  restreintes sont consignées séparément ; aucun déblocage réel n'est prétendu validé.
- **117 fichiers de rapports préexistants inchangés**, vérifiés par SHA256.

Pour compléter la vérification matérielle, exécuter depuis le terminal Ubuntu normal
`./prevost-samsung diagnostic-v21 --label ubuntu`, puis transmettre uniquement son
`partage.zip`. Ne pas déduire une autorisation de modifier le téléphone de cette collecte.

La branche GitHub V21 dérive de main ; la pull request est préparée en brouillon avec
ces résultats et limites. Aucun push direct sur main, aucune fusion automatique.
Le raccourci REA `rea-prevost` est livré séparément sur `feature/rea-prevost-shortcut`
pour ne pas mélanger son installation utilisateur avec le diagnostic Samsung.
