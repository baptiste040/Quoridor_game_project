# Résultats V5

Toutes les parties sont jouées avec `arene.py` : couleurs alternées, chaque paire de parties part de la même ouverture aléatoire (4 coups), au-delà de 400 demi-coups la partie est nulle. Dans chaque fichier, `A` est le premier agent nommé, `a_left` / `b_left` le temps restant en fin de partie et `a_max` / `b_max` le coup le plus long.

## Le temps ne suffit pas

| Fichier | Match | Score A |
|---|---|---|
| `v3_temps_x2_vs_v3.txt` | V3 avec 240 s contre V3 avec 120 s | 5,5 / 12 |

Doubler le temps ne rend pas la V3 plus forte : la limite vient de l'évaluation.

## Évaluation apprise

| Données | Évaluation | log-loss (test) | précision (test) |
|---|---|---|---|
| 455 parties, 29 452 positions | V3 `10Δd + 6Δm + 5` | 0,674 | 55,6 % |
| | V5 apprise | 0,540 | 69,0 % |

Poids bruts (logits) : biais -0,0074 ; Δdistance 0,3443 ; Δmurs 0,7507 ; Δdistance × murs en jeu -0,0132 ; murs / (distance adverse + 1) -1,1867 ; murs adverses / (distance + 1) 1,3047 ; somme des distances 0,0026.

Un mur en main vaut 0,75 / 0,34 ≈ 2,2 pas (0,6 dans la V3), un peu moins quand l'adversaire est près du but.

Second tour (345 parties de plus avec l'agent appris) : poids presque identiques, `poids_tour2_vs_tour1_60s.txt` = 10,5 / 24, premier tour conservé.

## Matchs

| Fichier | Match | Score V5 |
|---|---|---|
| `v5_vs_v3_60s_poids230.txt` | V5 (poids sur 230 parties) contre V3, 60 s | 12 / 16 |
| `v5_vs_v3_60s.txt` | V5 contre V3, 60 s | 22,5 / 32 |
| `v5_vs_v3_900s.txt` | V5 contre V3, 900 s | 2 / 2 |
| `v5_vs_v2_60s.txt` | V5 contre V2, 60 s | 7 / 8 |
| `v5_vs_greedy_60s.txt` | V5 contre greedy, 60 s | 4 / 4 |
| `v5_vs_v42_60s.txt` | V5 contre V4.2, 60 s | 18 / 32 |
| `v5_vs_v42_240s.txt` | V5 contre V4.2, 240 s | 9,5 / 16 |
| `v42_vs_v3_60s.txt` | V4.2 contre V3, 60 s (score V4.2) | 7,5 / 16 |

Les deux premières lignes font 34,5 / 48 contre la V3 (72 %). Contre la V4.2 : 27,5 / 48 (57 %), l'écart grandit avec le temps de réflexion.

## Pistes abandonnées

| Fichier | Variante | Score |
|---|---|---|
| `v5_main_fragilite_vs_v3_60s.txt` | poids à la main + fragilité des chemins | 14 / 24 (2 nulles) |
| `v5_main_sans_fragilite_vs_v3_60s.txt` | poids à la main sans fragilité | 14 / 24 (8 nulles) |
| `v5_sans_cycles_vs_v42_60s.txt` | V5 sans la détection de cycles de la V4.2 | 16 / 32 |
| `v5_sans_cycles_vs_v42_240s.txt` | idem, 240 s | 6,5 / 8 |

La fragilité (nombre de murs qui allongeraient seuls un chemin) divisait la vitesse par 3 et n'apportait rien une fois l'évaluation apprise (poids ≈ 0 en régression).

## Temps et mémoire

- 900 s : la V5 a utilisé 132 et 188 s, coup le plus long 18,0 s (plafond de 2 %). La V3 jusqu'à 493 s, coups de 31,5 s.
- Aucun coup illégal, aucun dépassement sur l'ensemble des parties.
- Pic mémoire mesuré : 367 Mo sur six recherches de 6 à 10 s (limite 4 Go). Profondeur atteinte : 11 à 13 demi-coups.
- Règles internes comparées au moteur officiel sur ~7 500 positions, avec la version du dépôt et celle du sujet : aucune différence.

## V5.1 : partie perdue sur Abyss

`partie_abyss_perdue_140410.log` : nous sommes `agent_2107` (noirs). Barrage adverse aux demi-coups 5 à 21 (notre distance passe de 7 à 19), évaluation V5 positive pendant tout ce temps (+30 au demi-coup 19, +85 au 37), défaite avec 4 murs jamais posés.

| Fichier | Match | Score |
|---|---|---|
| `v51_vs_v5_60s.txt` | V5.1 contre V5 | 16 / 32 |
| `v51_vs_v42_90s.txt` | V5.1 contre V4.2 | 11 / 24 |
| `v5_vs_v42_90s.txt` | V5 contre V4.2, mêmes ouvertures | 11 / 24 |
| `v51_lw12_vs_v42_90s.txt` | variante valeur 12 par mur | 12 / 24 |
| `v51_symetrique_vs_v42_120s.txt` | variante appliquée aussi quand on n'a plus de murs | 11,5 / 32 |

Fins de partie rejouées depuis la partie perdue (adversaire V5, 120 s, 4 essais) : après le demi-coup 31, V5 1 / 4, V5.1 4 / 4, valeur 12 0 / 4, valeur 0 3 / 4. Après le demi-coup 37 : 0 / 4 pour toutes les versions.

## V5.2

| Fichier | Match | Score A |
|---|---|---|
| `v52_vs_v5_120s.txt` | V5.2 contre V5, 120 s | 20 / 32 |
| `v52_vs_v5_300s.txt` | V5.2 contre V5, 300 s | 7 / 12 |
| `v52_vs_v42_120s.txt` | V5.2 contre V4.2, 120 s | 20,5 / 32 |
| `v52_vs_v42_300s.txt` | V5.2 contre V4.2, 300 s | 8 / 12 |
| `v52_eval_seule_vs_v5_120s.txt` | évaluation V5.2 seule contre V5 | 12 / 24 |
| `v52_sans_def_vs_v5_120s.txt` | V5.2 sans murs défensifs contre V5 | 14 / 24 |
| `v52_temps_v5_vs_v5_120s.txt` | V5.2 avec le temps de la V5 contre V5 | 15 / 24 |
| `positions_abyss_vs_v42_60s.txt` | 108 positions des défaites Abyss, adversaire V4.2 | V5.2 35,5 · V5 26 · V4.2 27 |
| `v52_vs_v42_900s.txt` | V5.2 contre V4.2, 900 s (conditions réelles) | 1 / 2 (341 et 471 s utilisées, coup max 31,5 s) |

Données : `donnees/abyss.jsonl` (1 358 parties Abyss converties), `donnees/positions_abyss.json` (banc de positions).
