# Quoridor_A26

Projet INF8175 - agent pour le jeu Quoridor.


# V1

## Structure

- `Quoridor/` : code du jeu fourni (non modifié) + `my_player.py`, notre agent.
- Branche `v1/minimax-distance` : minimax de ma partenaire. Ne pas toucher.

Seul `my_player.py` a été modifié.

## Ce que fait mon agent (`Quoridor/my_player.py`)

En gros : un minimax classique, mais avec de l'élagage alpha-bêta, un tri des coups, et un budget de temps calculé à chaque tour.

Pourquoi pas juste un minimax nu comme la version de ma partenaire ? Un minimax sans élagage doit limiter la profondeur (ici 2) sinon ça explose en temps de calcul. Avec l'alpha-bêta on coupe les branches inutiles, donc pour le même temps on regarde beaucoup plus loin dans la partie.

**Heuristique** : `10 * (distance_adversaire - distance_moi) + 1 * (murs_restants_moi - murs_restants_adversaire)`. La distance (plus court chemin BFS, murs compris) donne l'essentiel : qui est le plus proche de gagner. Les murs restants ne servent qu'à départager deux positions à distance égale. Un état gagnant/perdant vaut ±10000.

**Trop de murs possibles** : au début de partie il y a facilement 100+ murs légaux, impossible de tous les explorer à chaque nœud. Je ne garde que les murs qui touchent le plus court chemin d'un des deux joueurs (les seuls qui changent vraiment une distance à court terme). Les déplacements de pion, eux, sont tous gardés. Limite : un mur "piège" préparé à l'avance, hors du chemin actuel, peut m'échapper. Amélioration possible pour la suite.

**Tri des coups** : avant d'explorer les enfants d'un nœud, je les trie du meilleur au pire (évaluation rapide à un demi-coup). Ça aide l'élagage à couper plus de branches.

**Gestion du temps** : `remaining_time` c'est le temps qui reste pour toute la partie, pas pour un coup. Je calcule `budget = remaining_time / (distance_moi + 8)`, plafonné à 8s et je garde toujours 3s de marge de sécurité (dépasser le temps total = défaite direct, sans tolérance). Ensuite j'augmente la profondeur de recherche (1, puis 2, puis 3...) tant qu'il reste du budget, et je garde le résultat de la dernière profondeur complètement finie. Si le budget est trop court pour chercher, je renvoie direct le meilleur coup à un demi-coup (calcul quasi instantané) donc l'agent répond toujours quelque chose de valide.

## Comment j'ai testé

Pas de Python installé nativement dans l'environnement, donc j'ai créé un venv dédié dans `Quoridor/` (`py -m venv .venv_test`), installé `requirements.txt` dedans, puis lancé des parties en local headless avec le script fourni :

```
python main_quoridor.py -r -g -t local my_player.py random_player_quoridor.py
python main_quoridor.py -r -g -t local my_player.py greedy_player_quoridor.py
python main_quoridor.py -r -g -t local greedy_player_quoridor.py my_player.py
```

Testé dans les deux ordres (mon agent en blanc et en noir) pour vérifier que ça ne dépend pas de la couleur/rangée cible. J'ai regardé les logs de seahorse (`time : ...s` avant chaque coup) pour vérifier le temps consommé par coup et l'absence de `SeahorseTimeoutError`. Résultat : victoire à chaque fois contre random et greedy, ~8s par coup, aucun crash ni dépassement de temps. Le venv de test et les fichiers de replay générés ont été supprimés après coup, rien n'est resté dans le repo.



# V2

La V2 reprend le fonctionnement de la V1 et ajoute deux améliorations.

## Extension tactique

Lorsqu’un joueur se trouve à deux déplacements ou moins de sa ligne d’arrivée, l’agent considère la position comme instable et prolonge la recherche d’un niveau.

Cette extension évite d’arrêter la recherche juste avant une menace immédiate ou une victoire. Elle est limitée à un niveau supplémentaire pour contrôler le temps de calcul.

## Stratégie d’ouverture

Pendant ses trois premiers tours, l’agent privilégie un déplacement de pion qui réduit sa distance vers l’arrivée.

L’objectif est de progresser rapidement en début de partie et d’éviter de dépenser immédiatement des murs sur des positions peu importantes. Après ces trois tours, l’agent utilise normalement sa recherche alpha-bêta.

## Comparaison avec la V1
La V2 améliore la V1 principalement sur deux points.

L’extension tactique permet à l’agent de continuer la recherche lorsqu’un joueur est proche de gagner. La V2 risque donc moins d’arrêter son analyse juste avant une menace ou une victoire immédiate.

La stratégie d’ouverture évite de placer des murs trop tôt. En avançant pendant ses trois premiers tours, l’agent progresse vers son objectif avant de commencer sa recherche alpha-bêta normale.

La V2 conserve donc les avantages de la V1, tout en améliorant les décisions prises au début et à la fin de la partie.

# V3

Réécriture complète du moteur de recherche (fichier `my_player.py`, copie dans `my_player_v3.py`).

## Pourquoi

La V2 appelait `generate_possible_stateless_actions()` et `apply_action()` du moteur à chaque nœud. Ces appels font deux BFS par mur candidat et ne peuvent pas être interrompus : la recherche plafonnait à 2-3 coups de profondeur et la gestion du temps était fragile (risque de timeout).

## Ce qui change

- **Représentation interne** : les murs sont des bits d'un entier, les déplacements bloqués se testent par un ET binaire. Les cartes de distance au but sont calculées par BFS depuis la ligne d'arrivée et mises en cache par configuration de murs (les déplacements de pion ne changent pas les murs, donc le cache sert énormément). Les règles internes ont été vérifiées contre le moteur officiel sur ~6600 positions aléatoires (déplacements, sauts, distances, légalité des murs) : aucune différence.
- **Recherche** : negamax alpha-bêta avec PVS, approfondissement itératif, table de transposition, coups killers. ~4000 nœuds/s, soit en général 6 à 15 demi-coups de profondeur selon la position et le temps alloué, au lieu de 2-3.
- **Murs candidats** : on construit le graphe de tous les plus courts chemins de l'adversaire. Un mur n'est gardé que s'il les coupe tous (donc s'il allonge vraiment l'adversaire), ce qui se vérifie sans BFS complet. Les meilleurs sont gardés (10 par nœud, 40 à la racine).
- **Heuristique** : `10 * (dist_adv - dist_moi) + 6 * (murs_moi - murs_adv) + 5` (bonus du joueur qui a le trait). Fin de partie exacte : si un joueur n'a plus de murs, la course est tranchée directement (celui qui a le trait gagne s'il est au moins aussi proche).
- **Anti-attente** : à profondeur fixe, avancer maintenant ou plus tard peut avoir le même score quand l'adversaire a encore des murs, et l'agent tournait en rond. Si le meilleur coup ne fait pas avancer, on vérifie (recherche à fenêtre nulle) si avancer est presque aussi bon, et dans ce cas on avance.
- **Temps** : budget = (temps restant - réserve de 4 %) / (distance + 12), plafonné à 3,5 % du temps total. Les budgets sont décroissants donc on ne peut pas dépasser le crédit. Vérification de l'échéance tous les 32 nœuds, arrêt propre en gardant le meilleur coup de la dernière profondeur. Pas de recherche quand le résultat est déjà joué (victoire immédiate, course gagnée). Si quoi que ce soit échoue, le coup est vérifié avec le moteur officiel et un coup de secours légal est joué.

## Résultats (arène locale, horloges réduites)

| Match | Score V3 |
|---|---|
| V3 vs V2 (90 s, couleurs alternées) | 6 - 0 |
| V3 vs greedy (60 s) | 4 - 0 |
| V3 vs random | 2 - 0 |
| poids murs 6 vs poids murs 3 | 3 - 1 (6 retenu) |

Aucun coup illégal ni dépassement de temps, y compris sur une partie de 274 demi-coups où les deux agents ont fini avec ~4 s.
