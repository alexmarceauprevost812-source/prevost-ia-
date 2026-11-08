# PRÉVOST — boucle d’outils locale

Cette extension conserve l’agent de programmation et le diagnostic/veille existants. Elle ajoute un registre fermé et une boucle vérifiée, sans installation ni modification des lanceurs.

## Lancement

Depuis ce dépôt :

```bash
# Sondes réelles en lecture seule : disponibilité et contrats complets en JSON
python3 -m prevost.agent catalogue --project /chemin/du/projet

# Démo sans modèle : création, relecture, exécution, comparaison exacte et rapport
python3 -m prevost.agent demo --project /un/dossier/temporaire --report reports/demo.md

# Mission de diagnostic locale prédéfinie, sans modèle
python3 -m prevost.agent diagnostic --project /chemin/du/projet

# Planification par un modèle Ollama réellement installé
python3 -m prevost.agent mission "Crée un programme Python de salutation et vérifie sa sortie" \
  --project /chemin/du/projet --ollama http://127.0.0.1:11435 --model NOM_INSTALLE

# Un outil précis avec validation des paramètres
python3 -m prevost.agent outil local.disk --project /chemin/du/projet --params '{}'
```

Dans l’interface `python3 -m prevost`, `/outils` affiche le même registre et `/agent demande` lance la boucle avec le modèle sélectionné. Les anciennes commandes `/coder` et `/commande` sont conservées ; elles ne passent pas par ce nouveau registre et gardent les limites documentées dans le README.

## Boucle

1. Demande et périmètre explicites : PC courant et dossier choisi.
2. Plan court ; choix d’un seul outil inscrit au registre.
3. Validation Python des paramètres exacts, types, tailles, extensions et chemins.
4. Vérification de disponibilité ; confirmation humaine pour écriture ou exécution de code.
5. Exécution réelle avec collecte de la sortie et des erreurs.
6. Vérification déterministe du résultat suivant le contrat de l’outil.
7. Lecture du résultat pour choisir la prochaine étape, ou rapport final fondé sur les preuves.

Le modèle propose seulement `{plan, tool, parameters}` en JSON. Il ne peut pas ajouter un outil, une option shell, une cible ni une autorisation. Les résultats lui sont transmis comme données non fiables. Les contrats et résultats sont revérifiés par le code, et le rapport ne reprend pas comme faits les affirmations du modèle.

Une erreur peut être examinée à l’étape suivante ; un appel identique est refusé pendant la même mission. Un refus humain ou une annulation arrête la mission. Limites par défaut : huit étapes, 120 secondes ; plafonds configurables de vingt étapes et 600 secondes. Les confirmations peuvent être interrompues avec Ctrl+C ; le budget est revérifié avant l’exécution après une attente prolongée.

## Registre initial

Tous les paramètres sont obligatoires et tout paramètre supplémentaire est refusé. Aucun outil n’a de paramètre de cible réseau.

| Outil | Paramètres | Effets | Délai déclaré | Vérification |
| --- | --- | --- | --- | --- |
| `project.read` | `path` relatif | Lecture du projet | 3 s, coopératif | Lecture UTF-8 bornée, SHA-256 |
| `project.write` | `path`, `content` | Écriture confirmée, sauvegarde | 5 s, coopératif | Relecture exactement identique |
| `python.run` | `path` en `.py`, `expected_stdout` | Exécution sensible sur l’hôte, effets possibles sur fichiers/système/réseau | 15 s | Code 0 et stdout exactement attendu |
| `local.disk` | Aucun | Lecture statvfs de `/` | 3 s, coopératif | Cohérence des valeurs de capacité |
| `local.ports` | Aucun | Lecture `ss -H -lntu` | 8 s | Retour 0, sortie complète, aucun refus d’accès |
| `local.services` | Aucun | Lecture des unités systemd utilisateur échouées | 8 s | Retour 0, sortie complète, aucun refus d’accès |
| `rea.doctor` | Aucun | Diagnostic CLI REA/Codex, sans réparation | 15 s | JSON valide, champ `healthy` booléen, code 0 ou 1 |
| `rea.inspect_pyc` | `path` en `.pyc` | Inspection statique REA sans exécution cible | 20 s | Retour 0 et Evidence JSON REA identifiable |
| `kali.inventory` | Aucun | Lecture des chemins d’exécutables dans le conteneur déjà actif | 10 s | Inventaire JSON réel des cinq noms attendus |

La disponibilité est sondée lors de la création du registre. Les outils locaux natifs Python déclarent leur implémentation ; leur résultat est vérifié à chaque appel. Un exécutable trouvé, un moteur REA configuré et une analyse réussie sont des faits distincts. Le contrat JSON indique l’environnement, les effets, les sondes, les délais, la méthode de vérification et la politique de délai.

Les sondes Kali vérifient d’abord Podman et la présence de `kali-lexos` parmi les conteneurs actifs. Elles ne démarrent aucun conteneur. L’inventaire recherche `python3`, `nmap`, `tshark`, `file` et `strings` : un chemin observé signifie présence seulement. Ces exécutables ne deviennent pas automatiquement des outils exécutables du registre. Dans cette session, Podman est bloqué ; aucune présence Kali n’a donc été affirmée.

## Vérification et preuves

Chaque résultat comporte un identifiant, une date, le périmètre, les paramètres, les effets, la sortie réelle, les erreurs, la durée, le critère de vérification, un booléen `verified`, le niveau de confiance et une empreinte de la preuve. Les statuts distinguent réussite, vérification échouée, erreur, indisponibilité, refus, annulation, délai et sortie trop volumineuse.

`rea.doctor` peut être vérifié tout en indiquant `healthy=false` : cela confirme le diagnostic, pas la santé de REA. Une comparaison de stdout confirme seulement cette sortie, pas l’absence de tout autre effet du programme. Une sortie de diagnostic ne suffit pas à attribuer un incident ou à affirmer une vulnérabilité.

Les sous-processus, y compris le planificateur Ollama, sont arrêtés à leur délai ou sur annulation ; leur groupe de processus est nettoyé. Les sorties sont plafonnées à 200 Ko pendant la collecte, sans fichier temporaire de sortie pouvant grossir indéfiniment. La réponse de planification est limitée à 15 000 caractères. Les messages envoyés au planificateur sont limités à 120 Ko ; un contexte trop gros provoque un arrêt explicite.

Les opérations de fichiers et statvfs ont un budget **coopératif** : Python ne peut pas interrompre de façon fiable un appel système bloqué sur un stockage défaillant. Le registre annonce cette différence ; leur délai n’est pas une isolation matérielle. Un descendant se détachant du groupe peut aussi échapper à l’arrêt. Le mode de programmation conserve l’exécution sur l’hôte avec les droits du compte, sans bac à sable ; le code complet est présenté avant confirmation et une modification du fichier pendant la confirmation annule l’exécution. Les dépendances importées et les changements concurrents après ce contrôle ne sont pas isolés.

## Journal et rapport d’enquête

L’état privé par projet conserve `tools.jsonl` (mode 600), les plans, paramètres, résultats et fins de mission. Un rapport Markdown privé est sauvegardé même si l’export est refusé ou si la mission est annulée. Une exportation vers `reports/mission-IDENTIFIANT.md` est proposée avec aperçu et confirmation. En cas d’export impossible ou de rapport de plus de 200 Ko, le rapport privé complet reste disponible.

Le rapport contient demande, périmètre, preuves par appel, résultats vérifiés ou non, inconnues, recommandations et retour arrière. Les effets du code exécuté ne sont jamais annoncés comme annulés automatiquement. Les rapports sont des données sensibles et ne sont pas ajoutés au dépôt ; le `.gitignore` exclut `reports/` et les journaux. Aucune transmission automatique à GitHub ou ailleurs.

Les empreintes servent à repérer une modification accidentelle de la preuve ; ce n’est pas une chaîne de garde infalsifiable ni une expertise judiciaire. Les journaux n’ont pas de rotation ni de verrou entre processus : une seule instance par dossier d’état est recommandée.

## Audits et actions offensives

Le périmètre du registre est `pc-local`, le dossier du projet et le diagnostic du conteneur local existant. La liste de cibles réseau est vide. Aucun outil de scan réseau, d’exploitation, de force brute, de persistance ou d’attaque automatique n’est fourni dans cette étape.

Un futur audit d’appareil devra enregistrer la cible exacte, la preuve d’autorisation déclarée, les opérations permises, leur durée et leurs limites hors du modèle. Toute cible découverte devra être validée séparément avant une analyse active. Un scan, même complet, n’autorise pas une attaque. Les validations offensives devront être ajoutées comme outils spécifiques, testées dans un laboratoire autorisé, et les actions sensibles confirmées séparément.

Cette politique n’est pas un filtre réseau de l’hôte : un programme Python exécuté avec vos droits peut dépasser le périmètre logique. Ne confirmer aucun code d’audit actif tant que ses cibles et actions ne sont pas autorisées et revues. Les résultats d’outils ne peuvent jamais tenir lieu d’autorisation.

## Inventaire réseau séparé

La commande `python3 -m prevost.network veille` et `/veille-reseau` utilisent maintenant le Nmap installé pour la seule découverte ARP de CIDR explicitement approuvés. Ce module est séparé du registre et du planificateur : le modèle ne peut pas créer d’autorisation ni démarrer un audit à partir d’une découverte. Les appareils restent `a_valider`. Voir [RESEAUX.md](RESEAUX.md) pour les autorisations, les commandes d’arrêt et de révocation et le stockage privé. Les contrats et confirmations des outils existants ne changent pas.
