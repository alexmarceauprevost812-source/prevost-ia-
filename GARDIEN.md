# Gardien numérique — diagnostic du PC LexOS

Dans Termux, le gardien identifie son environnement Android, mesure le stockage du dossier personnel et indique les contrôles systemd comme indisponibles sans les exécuter. Les autres collectes restent soumises aux permissions Android ; voir [TERMUX.md](TERMUX.md).

L’agent de programmation est conservé. Un module distinct fournit un diagnostic déterministe, sans Ollama et sans commandes proposées par un modèle :

```bash
python3 -m prevost.guardian diagnostic
python3 -m prevost.guardian diagnostic --json
```

Il présente l’inventaire explicite du seul appareil courant (`pc-local`), le périmètre autorisé, l’espace disque de `/`, les unités systemd échouées (utilisateur et système), les ports TCP/UDP en écoute et les mises à jour signalées dans le cache APT. Aucun scan, aucune requête aux appareils voisins, aucun rafraîchissement APT, aucun changement système. Le diagnostic seul ne crée aucun journal. L’identité `pc-local` désigne l’environnement où la commande tourne, pas une preuve que l’ensemble du PC est visible depuis un bac à sable.

Chaque collecte conserve sa source, sa sortie, ses erreurs et son état. Une collecte refusée est indisponible, même quand le programme termine avec le code 0. Les recommandations distinguent constat et point à vérifier, précisent la confiance et le retour arrière. Aucune recommandation n’est appliquée. Puisqu’il n’y a aucun changement système, le retour arrière consiste actuellement à ne rien restaurer ; toute future correction devra définir son propre plan de restauration avant confirmation.

## Veille explicite

```bash
# Une collecte avec journal et référence pour la prochaine fois
python3 -m prevost.guardian veille

# Trois collectes à une minute d’intervalle
python3 -m prevost.guardian veille --cycles 3 --interval 60

# Boucle au premier plan, jusqu’à Ctrl+C
python3 -m prevost.guardian veille --cycles 0 --interval 60
```

Seule la veille écrit ses propres données locales : `~/.local/share/prevost-ia-local/guardian/watch.json` contient le dernier diagnostic et la référence ; `incidents.jsonl` contient les alertes et le journal des collectes. Les fichiers sont de mode 600, le dossier de mode 700. `--state-dir DOSSIER` choisit un autre emplacement. Garder ces données privées et hors Git. Aucun service de fond ni démarrage automatique n’est installé. Quand la commande s’arrête, la surveillance s’arrête ; PRÉVOST ne prétend pas protéger les périodes non observées.

Les alertes sont affichées dans le terminal et inscrites au journal, sans notification externe. Elles signalent les changements des listes observées, le passage sous 10 % d’espace libre et les échecs de collecte. Le premier relevé sert de référence ; les échecs et anomalies de disque/services présents dès ce relevé sont signalés immédiatement. L’espace disque ne déclenche pas une alerte à chaque octet : seul le seuil est comparé.

La déduplication persiste entre lancements : une même empreinte « contrôle + état observé » est signalée une seule fois dans ce journal, même si elle réapparaît après une résolution. Cela réduit les répétitions, mais ne compte pas les récidives. Les variations entre deux collectes peuvent être manquées. Le journal et la liste d’empreintes ne sont pas purgés automatiquement. Lancer une seule instance de veille par dossier d’état ; aucune coordination entre instances concurrentes n’est implémentée.

## Limites actuelles

- Inventaire limité au PC courant ; aucun ajout ou suivi d’autre appareil dans cette version.
- Disque racine seulement, sans SMART ni surveillance de contenu des fichiers.
- Services échoués seulement, sans liste personnalisée des services attendus.
- Ports de l’espace réseau visible seulement ; aucune attribution à un programme ni preuve d’exposition externe.
- Mises à jour issues du cache APT : fraîcheur et pertinence non garanties, aucune évaluation automatique des vulnérabilités.
- Le diagnostic constate des faits de collecte, pas une certification de sécurité. Les collectes indisponibles restent inconnues.
- Aucun pare-feu, redémarrage, installation, suppression ou autre mesure de protection sensible n’est exécuté par ce module.
