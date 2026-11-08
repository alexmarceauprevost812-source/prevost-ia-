# Inventaire réseau consenti

Depuis le dépôt, démarrer une veille explicite au premier plan :

```bash
python3 -m prevost.network veille
```

La conversation propose aussi `/veille-reseau`, `/reseaux`, `/arreter-reseau` et `/retirer-reseau IDENTIFIANT`. `/veille-reseau` occupe l’interface jusqu’à Ctrl+C ou à une demande d’arrêt depuis un autre terminal. Aucun service ni lancement automatique à l’ouverture de session n’est installé. Pendant cette veille, les événements `nmcli monitor` déclenchent une vérification des connexions ; un rafraîchissement périodique a aussi lieu toutes les 60 secondes (`--interval`). Une connexion transitoire déjà disparue n’est jamais explorée.

## Connexion et autorisation

PRÉVOST lit les métadonnées locales de NetworkManager et `ip`, sans demander les secrets des profils. Une connexion est liée au profil UUID, à l’interface, au type, aux sous-réseaux IPv4, à la passerelle et à sa MAC lorsqu’elle est connue. Le Wi-Fi inclut le BSSID du point d’accès courant. Une connexion Ethernet sans MAC de passerelle identifiable dans le cache local est indisponible ; aucun trafic n’est envoyé pour deviner son identité avant autorisation. Les VPN et interfaces non Ethernet/Wi-Fi ne sont pas explorés.

Ces métadonnées servent à distinguer les connexions, pas à authentifier cryptographiquement un réseau. Une usurpation de BSSID ou de passerelle reste possible. Un changement de point d’accès, de passerelle ou de sous-réseau donne un nouvel identifiant et nécessite un nouvel accord. Aucune autorisation n’est déduite du seul fait d’être connecté au Wi-Fi.

À la première rencontre en terminal interactif, PRÉVOST affiche l’identité, demande **un CIDR exact**, puis exige le `oui` habituel. Le périmètre doit être inclus dans un sous-réseau directement connecté et contenir au maximum 4096 adresses. Il ne peut pas provenir d’une réponse du modèle. Refus, saisie invalide ou interruption ne relancent pas la question aux connexions suivantes. Sans terminal interactif, la connexion reste en attente sans découverte ; l’approbation manuelle permet de reprendre explicitement une décision en attente, refusée ou retirée :

```bash
python3 -m prevost.network connexions
python3 -m prevost.network approuver --network IDENTIFIANT --scope CIDR_AUTORISE
```

`IDENTIFIANT` est la valeur `id` complète affichée par `connexions` ou `liste`. L’approbation manuelle exige aussi une connexion actuellement identifiable et une confirmation humaine. Elle autorise uniquement l’inventaire décrit ci-dessous. Pour une collecte ponctuelle, utiliser `python3 -m prevost.network une-fois`.

## Découverte et preuves

Sur une connexion approuvée, PRÉVOST appelle réellement le Nmap installé, avec des arguments fixes : `-sn -n -PR --send-eth --privileged -e INTERFACE`, le seul CIDR approuvé, une limite de 32 requêtes par seconde, une retransmission maximale et un délai global de 180 secondes. Il s’agit de découverte ARP locale, sans scan de ports, script NSE, identification de service, détection d’OS ni requête DNS. Voir la [documentation officielle de la découverte Nmap](https://nmap.org/book/man-host-discovery.html).

Les exécutables `nmcli`, `ip` et `nmap` doivent être installés. ARP nécessite des droits de socket brute pour le processus Nmap. `--privileged` indique le mode à Nmap ; il **n’accorde aucun privilège**. PRÉVOST n’utilise pas `sudo`, n’installe rien et ne change aucune permission système. Un outil absent, des droits insuffisants, un XML incomplet ou une connexion non identifiable produisent une indisponibilité explicite et conservent l’inventaire précédent. Aucun passage silencieux à des sondes TCP ou à un périmètre différent.

Les réponses Nmap donnent l’IP et, quand disponible, la MAC. Les entrées du cache local `ip neigh` sont également conservées, en signalant leur incertitude, même si elles sont périmées. Un nom peut venir d’un résultat de découverte ou de `/etc/hosts` local ; aucune résolution DNS supplémentaire n’est déclenchée. Les valeurs absentes restent inconnues. Aucun fichier distant, cookie ou mot de passe n’est recherché ni collecté.

Un candidat est une association **connexion + IP + MAC éventuellement absente**, pas une identité physique prouvée. Un changement de MAC à la même IP, une même MAC sur une autre IP ou une observation sans MAC créent des candidats distincts. PRÉVOST ne fusionne jamais ces candidats automatiquement. Chaque candidat conserve première et dernière observation, noms et sources avec dates et incertitude. Les anciens candidats restent présents dans l’historique ; « non observé » ne veut pas dire « déconnecté ».

Chaque collecte réussie est comparée à la précédente : nouveaux candidats signalés, réapparitions et candidats non observés enregistrés dans `last_comparison`. La première collecte constitue la référence et signale tous ses candidats. Un candidat déjà signalé n’est pas présenté comme nouveau à chaque rafraîchissement.

Tous les nouveaux candidats restent `a_valider`. **Aucun audit actif n’est ajouté ni lancé par cette extension.** L’autorisation d’inventorier un réseau ne constitue pas l’autorisation d’auditer un appareil. Une future utilisation d’un outil d’audit devra identifier la cible, ses opérations autorisées et exiger une confirmation distincte de l’utilisateur. Les commandes manuelles et les outils existants conservent leurs confirmations.

## Arrêt, révocation et état privé

Depuis un autre terminal du même utilisateur :

```bash
python3 -m prevost.network arreter
python3 -m prevost.network liste
python3 -m prevost.network retirer --network IDENTIFIANT
```

Ctrl+C arrête également la veille. La commande `arreter` annule aussi une demande d’autorisation en attente dans un terminal interactif. L’arrêt et la révocation sont vérifiés pendant la découverte ; le groupe de processus est terminé lorsque l’annulation est constatée. Une vérification de l’identité locale a lieu au plus toutes les 0,5 seconde, mais sa durée dépend des commandes système (délais bornés). La révocation ne peut pas rappeler les requêtes déjà émises. L’autorisation est revérifiée avant d’enregistrer les résultats ; une collecte révoquée n’écrase pas l’inventaire.

Le retrait conserve les observations historiques et supprime l’autorisation de découverte. La connexion retirée ne redemande pas automatiquement la permission. Une nouvelle commande explicite `approuver` est nécessaire. Une seule veille par dossier d’état est autorisée ; les modifications concurrentes des décisions et de l’inventaire sont verrouillées.

Stockage par défaut : `~/.local/share/prevost-ia-local/networks/inventory.json`, dossier mode `700`, fichiers mode `600`, écriture atomique. Aucun inventaire réel n’est livré dans Git. `--state-dir DOSSIER_PRIVE` est possible pour tous les modes sauf `connexions` qui ne stocke rien ; les dossiers de dépôt Git et les liens symboliques sont refusés. Utiliser le même dossier d’état pour la veille, l’arrêt et la révocation.

## Vérification

```bash
python3 -B -m unittest discover -s tests -v
```

Les tests réseau utilisent exclusivement des connexions, événements et réponses Nmap **simulés** ; ils ne lancent aucune découverte sur le réseau. La disponibilité réelle de NetworkManager et les résultats d’une découverte effectivement autorisée doivent être validés séparément sur le terminal hôte. Voir [VALIDATION.md](VALIDATION.md).
