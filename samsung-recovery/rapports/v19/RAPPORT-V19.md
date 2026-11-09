# MISSION PRÉVOST V19 — récupération officielle du SM-G990W2

Date : 9 novembre 2026. Appareil déclaré : Samsung Galaxy S21 FE 5G, SM-G990W2.

## Résultat et nouvelle preuve

L'utilisateur confirme visuellement l'écran **« Vérifier votre compte Google »**.
Cette observation est enregistrée dans `outils/v19/confirmation_utilisateur.json`,
avec sa provenance et une heure d'observation inconnue. Aucun secret ni capture collecté.

La situation est compatible avec une vérification de propriété FRP pendant la
configuration Android. C'est une confirmation de l'écran par l'utilisateur, pas une
lecture technique du drapeau FRP. L'écran décrit une étape de configuration Android ;
il ne correspond pas au menu Recovery ni à l'écran Download habituels. Ce raisonnement
repose sur la déclaration utilisateur, sans nouvelle interrogation du téléphone.

L'étape prioritaire est de retrouver l'accès au compte Google antérieurement synchronisé
ou de faire examiner les justificatifs par Samsung. La remise en service n'est pas encore
accomplie : elle dépend de la validation Google ou d'une décision du prestataire officiel.

## Analyse V17 et V18

Les deux relevés environnement V17 et les quatre relevés de diagnostic V18 présents ont
été analysés. Les dossiers V19 générés conservent leurs chemins, dates, empreintes SHA256
et une synthèse des éléments utiles, sans recopier les numéros de série.

| Élément | Preuve historique | Conclusion permise |
|---|---|---|
| USB Ubuntu V17/V18 | 04e8:6860, produit Samsung, MTP | Énumération USB fonctionnelle au relevé |
| ADB Ubuntu V17/V18 | Retour 0, liste vide | Aucun transport ADB annoncé ; aucun état unauthorized observé |
| MTP Ubuntu V18 | Montage MTP annoncé par GIO | Montage reconnu ; accès aux fichiers et capacités non vérifiés |
| Métadonnées V18 Ubuntu | mtp-detect omis car montage présent | Aucun échec libmtp Ubuntu à inventer |
| Codex V17/V18 | libusb/sockets/session restreints | Blocages d'environnement distincts du téléphone |
| DNS Ubuntu V17 | Résolutions réussies | Pas de panne DNS Ubuntu démontrée |
| Catalogue BMC V17 Ubuntu | HTTP 403 réel | Accès au catalogue refusé, sans lien démontré avec FRP |
| Écran V19 | Confirmation utilisateur explicite | Vérification Google visible ; nouvelle preuve indépendante |

Le rapport narratif V18 a précédé le relevé Ubuntu V18 supplémentaire. Sa limite
« métadonnées MTP indisponibles ici » concernait Codex ; elle ne doit pas effacer le
montage MTP réellement annoncé sous Ubuntu. Les anciens rapports restent inchangés.
La précédente conclusion « FRP indéterminé par USB/ADB » reste valable pour ces sondes.
La déclaration V19 apporte une information d'écran que ces sondes ne mesuraient pas.

## Démarches Google à effectuer personnellement

1. Depuis un autre appareil, utiliser la [récupération Google officielle](https://accounts.google.com/signin/recovery).
   Si l'adresse est oubliée, passer par la [recherche du nom d'utilisateur](https://accounts.google.com/signin/usernamerecovery).
   Google utilise notamment un moyen de récupération et le nom du compte pour cette recherche.
   Voir la [procédure Google](https://support.google.com/accounts/answer/7682439?hl=fr).
2. Utiliser l'appareil, le navigateur et le lieu habituels. Répondre directement dans
   l'interface Google et utiliser les méthodes proposées. Les identifiants et codes ne
   doivent jamais être saisis dans PRÉVOST. Voir les [conseils Google](https://support.google.com/accounts/answer/7299973?hl=fr).
3. Respecter le délai effectivement indiqué. Une demande peut être différée des heures
   ou des jours ; aucun délai universel de remise en service ne peut être promis.
   Une modification des informations de récupération peut prendre jusqu'à sept jours.
   Voir les [délais de sécurité Google](https://support.google.com/accounts/answer/9412469?hl=fr)
   et la procédure de récupération ci-dessus.
4. Le compte pertinent est un compte Google précédemment ajouté et synchronisé sur cet
   appareil. Créer un autre compte ne satisfait pas cette exigence. La propriété du
   téléphone et celle du compte sont deux vérifications distinctes. Voir la
   [protection Android officielle](https://support.google.com/android/answer/9459346?hl=fr).
5. Une fois l'accès au compte retrouvé, la future validation sur le téléphone sera réalisée
   personnellement par son propriétaire, hors de cette mission qui ne change rien au téléphone.
   Aucun identifiant, code ou compte n'a été testé par l'agent. Si un ancien propriétaire
   est concerné, lui demander de suivre lui-même la voie officielle sans partager ses secrets.

## Dossier Samsung à préparer

Le [support Samsung Canada sur FRP](https://www.samsung.com/ca/support/mobile-devices/perform-a-factory-reset-on-samsung-galaxy-device/)
recommande un centre de service lorsque la vérification Google ne peut pas être achevée.
La [documentation Samsung sur la propriété](https://www.samsung.com/us/support/answer/ANS10003349/)
mentionne l'appareil accompagné d'une preuve d'achat. Cette page américaine ne garantit
pas les modalités canadiennes : les confirmer au [centre agréé canadien](https://www.samsung.com/ca/support/service-center/).

Préparation recommandée, à confirmer avec ce centre :

- Preuve d'achat d'origine, duplicata ou contrat reliant l'achat à l'appareil ; modèle et
  IMEI/série depuis les documents ou la boîte, sans nouvelle manipulation du téléphone.
- Pièce d'identité si le centre la demande ; vérifier personnellement la correspondance
  des documents. Une boîte seule n'est pas une preuve suffisante garantie.
- Demande précise : prise en charge SM-G990W2, vérification de propriété Google,
  pièces acceptées, frais éventuels, préservation des données et référence du dossier.

Les justificatifs restent chez l'utilisateur et ne sont pas collectés par PRÉVOST.
Aucune garantie de déverrouillage ou d'intervention sans perte de données n'est donnée.
Le brouillon Samsung précise qu'aucun effacement, flash ou changement téléphone n'est autorisé.

## Démarches Bell à préparer

Si l'achat a été fait chez Bell, consulter personnellement MonBell pour les factures
accessibles. Le [guide officiel de téléchargement des factures](https://support.bell.ca/billing-and-accounts/billing/how_to_download_or_print_my_bill)
décrit l'impression et le téléchargement, dont un historique de 18 mois. Pour un achat
ancien ou un compte fermé, demander au [soutien Bell](https://support.bell.ca/Contact-Us)
si un duplicata de preuve d'achat ou de contrat est disponible, à quelles conditions et
avec quels frais éventuels. Une facture de service seule peut ne pas identifier l'appareil.

Le [service de réparation Bell](https://support.bell.ca/mobility/Using_my_device/Repairs)
indique notamment un compte actif et un titulaire/utilisateur autorisé. Si ce n'est pas
le cas, demander séparément une recherche documentaire et une orientation vers Samsung,
sans présumer l'admissibilité à la réparation. Bell ne rétablit pas le mot de passe Google.
Le brouillon Bell ne présume ni achat prouvé, ni compte actif ; aucun message n'a été envoyé.

## Restauration Android : possibilités et limites

La [page officielle SM-G990W2](https://doc.samsungmobile.com/SM-G990W2/023358220727/eng.html)
publie G990W2VLSNIZI2, Android 16, le 23 octobre 2026, correctif du 5 octobre 2026.
Cette publication ne mesure pas la version installée et ne valide aucun paquet BMC
ou niveau de bootloader pour cet appareil.

[Smart Switch Samsung Canada](https://www.samsung.com/ca/apps/smart-switch/) propose
les mises à jour disponibles sur Windows/Mac. Le [guide Samsung de récupération d'urgence](https://update.kies.samsung.com/SmartSwitchPC_recovery_guide/firmware/emergencyrecovery/)
vise un échec de mise à jour reconnu ; sa disponibilité effective pour ce téléphone
reste à vérifier auprès de Samsung. L'écran Google ne démontre pas une corruption
Android. Aucune restauration n'est une solution démontrée à l'exigence de compte ;
aucune conservation des données n'est garantie pour une intervention future.
Aucun logiciel de restauration lancé, firmware téléchargé, flash ou effacement réalisé.

## Intégration PRÉVOST et validation

- Menu principal V19 : choix 10 « Récupération Google FRP », commande `google-frp`.
- Paramètre `--section tout|google|samsung|bell|android`, disponible aussi avec le menu.
- Chaque consultation enregistre un dossier unique : rapport Markdown/JSON, deux
  brouillons non envoyés, empreintes SHA256. Le choix 7 affiche le dernier rapport V19.
- Choix 1 à 9 et commandes existantes conservés ; export complet V16 à V19 mis à jour.
- 68 tests réussis, dont 10 tests V19 : provenance, absence de confirmation non inventée,
  séparation HTTP/ADB/MTP, données personnelles non recopiées, absence d'accès externe,
  conservation, empreintes, navigation et export. Ces tests ne valident pas un déblocage réel.

La mission ne lit aucun mot de passe, cookie ou jeton et ne change ni le téléphone ni
la configuration système. Les sources officielles ont été consultées le 9 novembre 2026
via outil web indépendant ; le menu fonctionne ensuite hors ligne.
La conservation de tous les rapports antérieurs est vérifiée par empreintes avant/après.
La branche de livraison `mission-prevost-v19`, dérivée de V18 dans
`exports/prevost-v18-source`, conserve la branche V18. Aucun push ni modification du `.git` original.
