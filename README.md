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

# V5

Même moteur de recherche que la V3 et la V4.2 (fichier `my_player.py`, copie dans `my_player_v5.py`). Ce qui change : la fonction d'évaluation, apprise au lieu d'être réglée à la main. La détection des cycles A-B-A de la V4.2 est conservée.

## Pourquoi

En arène, la V3 avec deux fois plus de temps ne bat pas la V3 (5,5 / 12). Chercher plus profond ne sert donc presque à rien : la limite vient de l'heuristique `10 * Δdistance + 6 * Δmurs + 5`, dont les poids avaient été choisis à la main.

## Évaluation apprise (régression logistique)

Même idée que Logistello (Buro, 2002) : on garde l'alpha-bêta et on apprend l'évaluation à partir de parties.

- **Données** : 455 parties (29 000 positions) jouées entre nos versions (V3, variantes de la V5) avec des horloges courtes et 0 à 8 coups aléatoires au départ pour varier les positions. Chaque position est étiquetée par le résultat final pour le joueur qui a le trait. Les positions dont la course est déjà tranchée (un joueur sans murs) sont exclues, l'agent les calcule exactement.
- **Caractéristiques** (vues par le joueur actif) : écart de distance, écart de murs, écart de distance × murs encore en jeu, `murs / (distance adverse + 1)` pour chaque joueur, longueur totale de la course.
- **Apprentissage** : descente de gradient sur la log-vraisemblance avec une petite régularisation L2, 1 partie sur 5 gardée pour le test. Les poids sont ensuite mis à l'échelle pour qu'un pas de distance vaille 10, comme avant.

| Évaluation | log-loss (test) | précision (test) |
|---|---|---|
| V3 (poids à la main) | 0,674 | 55,6 % |
| V5 (poids appris) | 0,540 | 69,0 % |

Ce que disent les poids : un mur en main vaut environ 2 pas (la V3 l'estimait à 0,6, elle posait donc ses murs trop vite) et il vaut moins quand l'adversaire est déjà proche du but. Les poids ont peu bougé entre 230 et 455 parties. Un second tour avec 345 parties où l'agent appris joue aussi n'a presque rien changé aux poids ni aux résultats (10,5 / 24 contre la version retenue), on a donc gardé ceux du premier tour.

Une piste testée puis abandonnée : compter les murs qui allongeraient seuls le chemin d'un joueur (fragilité du chemin). Elle ne prédisait presque rien une fois les autres termes présents et divisait la vitesse de recherche par 3.

## Autres changements

- **Murs candidats par comptage de chemins** : pour chaque arête du graphe des plus courts chemins, on compte le nombre de plus courts chemins qui l'empruntent (passe avant puis passe arrière par niveaux de distance). Un mur ne peut couper tous les chemins que si le nombre de chemins qu'il bloque atteint le total. Ça remplace une recherche par mur candidat. Même ensemble de murs que la V3 sur 1800 positions testées.
- **Deux versions du moteur** : le moteur du sujet compte le bord du plateau comme un mur pour les sauts (saut en diagonale quand l'adversaire est collé au bord), celui du dépôt non. L'agent interroge le moteur reçu et applique la bonne règle. Vérifié sur ~7500 positions avec chacun des deux moteurs : aucune différence.
- **Ouverture** : tant qu'aucun mur n'est posé, l'agent avance sans chercher (comme la V2).
- **Cycles** : repris de la V4.2. Si notre pion revient sur la case d'il y a deux coups, les déplacements vers les cases récentes sont retirés à la racine. Sans ça, 5 parties sur 16 entre la V5 et la V4.2 finissaient en boucle.
- **Réductions** : à partir de la profondeur 3, les murs mal classés sont d'abord cherchés avec deux niveaux en moins et une fenêtre nulle, puis refaits normalement seulement s'ils dépassent alpha.
- **Temps** : budget multiplié par 0,5 en ouverture, 1,4 en milieu de partie (les deux joueurs ont des murs et un pion est à 5 cases ou moins du but) et 0,7 quand un joueur n'a plus de murs. Un coup ne prend jamais plus de 14 % du temps restant hors réserve ni plus de 2 % du crédit (18 s sur 15 min). Arrêt anticipé quand le même coup ressort trois itérations de suite.

## Résultats (arène locale)

| Match | Score V5 |
|---|---|
| V5 vs V4.2 (60 s puis 240 s, couleurs alternées) | 27,5 / 48 |
| V5 vs V3 (60 s, couleurs alternées) | 34,5 / 48 |
| V5 vs V2 (60 s) | 7 / 8 |
| V5 vs greedy (60 s) | 4 / 4 |
| V5 vs V3 (900 s, conditions réelles) | 2 / 2 |

Avec une horloge courte (60 s, ~1 s par coup) la V5 et la V4.2 sont proches (18 / 32). Avec 240 s la V5 prend l'avantage (9,5 / 16) : l'évaluation apprise profite davantage de la profondeur.

Aucun coup illégal ni dépassement de temps. Sur 15 min, la V5 a utilisé entre 130 et 190 s par partie (18 s au plus pour un coup), la V3 jusqu'à 490 s.

# V5.1

Correctif de la V5 après une défaite sur Abyss (fichier `my_player.py`, copie dans `my_player_v5_1.py`, la V5 soumise reste dans `my_player_v5.py`).

## La partie perdue

L'adversaire a construit un barrage dès le début : notre distance au but est passée de 7 à 19 en huit coups, la sienne est restée à 8. L'évaluation apprise de la V5 trouvait pourtant la position de plus en plus favorable (+30 avec 11 pas de retard, +85 au moment où il n'avait plus de murs et nous encore 8). Un mur en main valant environ deux pas pour le modèle, chaque mur adverse dépensé nous semblait une bonne nouvelle et nous ne posions un mur que s'il rapportait plus de deux pas d'un coup. On a perdu avec 4 murs jamais posés.

Nos parties d'entraînement ne contenaient pas ce type de barrage : le modèle extrapole mal hors de ce qu'il a vu.

## Correctif

Quand l'adversaire n'a plus de murs, la partie devient une course où nos murs ne servent que s'ils sont posés avant son arrivée. Dans ce cas l'évaluation n'utilise plus les poids appris :

`score = 10,33 * (dist_adv - dist_moi) + 5 * min(murs_moi, dist_adv)`

Un mur en main vaut alors moins qu'un pas : tout mur qui allonge l'adversaire est préférable à le garder, et un mur gardé ne vaut plus rien quand l'adversaire est sur le point d'arriver.

Variantes écartées : appliquer la même règle quand c'est nous qui n'avons plus de murs (discontinuité au dernier mur, l'agent vidait son stock trop tôt : 11,5 / 32 contre la V4.2), une valeur de 12 par mur (encore supérieure à un pas, sans effet), des murs défensifs à la racine qui rendent illégales les menaces adverses (aucun gain mesuré).

## Résultats

Positions de la partie perdue rejouées avec notre agent à notre place (adversaire : V5, 4 essais par position) :

| Position de départ | V5 | V5.1 |
|---|---|---|
| après le demi-coup 31 (adversaire : 1 mur, nous : 9) | 1 / 4 | 4 / 4 |
| après le demi-coup 37 (adversaire : 0 mur, 10 pas de retard) | 0 / 4 | 0 / 4 |

| Match (arène locale) | Score |
|---|---|
| V5.1 vs V5 (60 s) | 16 / 32 |
| V5.1 vs V4.2 (90 s, 24 ouvertures) | 11 / 24, la V5 fait 11 / 24 sur les mêmes |

Le correctif règle le cas de la partie perdue sans rien changer au reste du jeu. Aucun coup illégal ni dépassement de temps.

# V5.2

Fichier `my_player_v5_2.py` (copie soumise dans `V5_2_abyss/my_player.py`). La V5 et la V5.1 restent dans `my_player_v5.py` et `my_player_v5_1.py`. Le moteur de recherche est celui de la V5 ; ce qui change vient de l'analyse des 1 358 parties exportées d'Abyss (rangées par version dans `fights/`).

## Ce que disent les parties d'Abyss

Scripts : `outils/analyse_abyss.py`, `outils/analyse_abyss_murs.py`, `outils/analyse_abyss_eval_v5.py`.

- Sur la même période, la V5 (33 V / 29 D, 53 %) et la v4.1 (33 / 61, 54 %) gagnent autant. Elles perdent de façons opposées.
- **La V5 garde ses murs et se laisse enfermer.** Au demi-coup 30, il lui en reste 6,5 contre 3,0 à l'adversaire (v4.1 : 2,5 contre 5,3). Dans ses défaites, quand l'adversaire n'a plus de murs, elle en a encore 6,5 avec 11,8 pas de retard ; 12 défaites sur 29 se terminent avec au moins 3 murs jamais posés. Le scénario type : barrage adverse entre les demi-coups 12 et 35, notre distance passe de 5 à plus de 20.
- **L'évaluation de la V5 se trompe sur ces positions.** Sur les 283 positions de ses défaites avec au moins 6 pas de retard (murs des deux côtés), elle en juge 111 (39 %) nulles ou favorables, par exemple +31 avec 18 pas contre 4. Le modèle n'a été entraîné que sur nos parties, où personne ne construit de barrage.
- **La V5 n'utilise pas son temps** : environ 4 s par coup, 140 s sur 900. Les adversaires en utilisent 500 à 700, la v4.1 jouait environ 12 s par coup.
- **La v4.1 a le défaut inverse** : premier mur vers le demi-coup 6, stock vidé tôt ; 118 de ses 137 défaites arrivent après avoir mené d'au moins 3 pas.
- Les agents étant déterministes, une même défaite se répète à l'identique contre un même adversaire (`141030` = `141692`, `142759` = `144165`, `144992` = `146074`).

## Ce qui change

- **Évaluation réapprise sur Abyss** (`outils/abyss_vers_jsonl.py`, `outils/entrainer_v52.py`). La régression logistique de la V5 est refaite sur 102 410 positions : 1 358 parties d'Abyss, prises du point de vue des deux joueurs (donc aussi des styles qu'on ne joue pas), plus les 455 parties locales du premier tour. Les murs y sont à rendements décroissants : `u = m / (1 + 0,1 m)` avec `m = min(murs, distance adverse)`. Un mur ne sert à rien au-delà de la distance qui reste à l'adversaire, et le cinquième vaut moins que le premier. La règle de la V5.1 (adversaire sans murs) est conservée.

| Évaluation (test, 1 partie sur 5) | log-loss | précision |
|---|---|---|
| V5 | 0,619 | 64,3 % |
| V5.2 | 0,601 | 64,2 % |

  Un mur en main vaut maintenant 1 à 1,9 pas pour les premiers et 0,1 à 0,8 pas au-delà du quatrième (la V5 : environ 2 pas pour chacun). Sur les positions nettement perdues (au moins 6 pas de retard, murs des deux côtés, 11 254 positions, gagnées en réalité dans 32 % des cas), la V5.2 en juge 25 % favorables, contre 40 % pour la V5. Les poids sont presque les mêmes en n'utilisant que les parties d'Abyss.

- **Murs défensifs à la racine.** On repère les menaces : les murs que l'adversaire pourrait poser et qui nous allongeraient d'au moins 2 pas (6 au plus). Les murs qui les rendent illégales (chevauchement ou croisement) sans nous allonger sont ajoutés aux coups candidats (8 au plus), et la recherche décide. La V5.1 avait essayé sans gain, mais seulement contre nos versions, qui ne font pas de barrages.
- **Temps** : plafond par coup remonté de 2 % à 3,5 % du crédit (31,5 s, comme la V4.2). Facteurs de phase : 0,7 en ouverture, 1,8 en milieu de partie ou quand l'adversaire nous a mis au moins 3 pas de retard, 0,8 quand un joueur n'a plus de murs, 1,2 sinon. L'arrêt sur coup stable n'intervient plus avant la profondeur 8.

## Résultats (arène locale, couleurs alternées)

| Match | Score V5.2 |
|---|---|
| V5.2 vs V5 (120 s) | 20 / 32 |
| V5.2 vs V5 (300 s) | 7 / 12 |
| V5.2 vs V4.2 (120 s) | 20,5 / 32 |
| V5.2 vs V4.2 (300 s) | 8 / 12 |

Au total, 27 / 44 contre la V5 (61 %) et 28,5 / 44 contre la V4.2 (65 %). Pour comparer : la V5 faisait 18 / 32 contre la V4.2 à 60 s et 11 / 24 à 90 s.

**Positions tirées des défaites sur Abyss** (`outils/positions_abyss.py`, 108 positions prises quelques demi-coups avant la bascule). Notre agent reprend notre place, contre la V4.2, avec 60 s :

| Agent à notre place | Défaites V5 (29) | Défaites v4.1 (79) | Total |
|---|---|---|---|
| V5.2 | 13 | 22,5 | **35,5 / 108** |
| V5 | 14 | 12 | 26 / 108 |
| V4.2 | 12 | 15 | 27 / 108 |

Les positions tirées des défaites de la V5 sont sans doute déjà trop compromises à ce stade, quel que soit l'agent.

**Apport de chaque changement** (contre la V5, 120 s, 24 parties) :

| Variante | Score |
|---|---|
| évaluation seule (temps V5, sans murs défensifs) | 12 / 24 |
| évaluation + temps (sans murs défensifs) | 14 / 24 |
| évaluation + murs défensifs (temps V5) | 15 / 24 |
| V5.2 complète | 20 / 32 |

Entre nos propres versions, l'évaluation seule ne change rien, ce qui était attendu : aucune ne construit de barrage. Les gains viennent de la combinaison avec les murs défensifs et le temps. Les échantillons restent petits (±9 points environ sur 24 parties) : c'est Abyss qui tranchera.

Temps utilisé : 64 s sur 120 et 123 s sur 300 (la V5 : 26 et 48 s). En conditions réelles (900 s, 2 parties contre la V4.2, 1 / 2), la V5.2 a utilisé 341 et 471 s, coup le plus long 31,5 s (plafond). Aucun coup illégal ni dépassement de temps sur l'ensemble des parties.
