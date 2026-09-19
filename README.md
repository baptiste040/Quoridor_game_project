# Quoridor_A26

Projet INF8175 - agent pour le jeu Quoridor.

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
