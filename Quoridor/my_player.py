# Auteurs : Baptiste ALLAIN 
# INF8175 - Projet Quoridor - V1

from __future__ import annotations

import time
from collections import deque

from actions_quoridor import Orientation, Wall
from game_state_quoridor import GameStateQuoridor
from player_quoridor import PlayerQuoridor
from seahorse.game.action import Action
from seahorse.game.stateless_action import StatelessAction


class _SearchTimeUp(Exception):
    """Raised internally to unwind the search once the time budget is spent."""


class MyPlayer(PlayerQuoridor):
    """
    Agent Quoridor base sur un minimax avec elagage alpha-beta, approfondissement
    iteratif et gestion explicite du temps de jeu.

    Idee generale : a chaque tour, on cherche le plus loin possible dans l'arbre
    de jeu tant que le budget de temps alloue au coup n'est pas ecoule, en gardant
    toujours en memoire la meilleure action trouvee a la derniere profondeur
    completement explore. Un coup de secours, tres rapide a calculer, garantit
    qu'une action valide est toujours retournee meme si le temps restant est
    presque nul.
    """

    # Valeur attribuee a un etat gagnant / perdant (bien plus grande que tout
    # score heuristique atteignable, pour qu'une victoire prime toujours).
    WIN_VALUE = 10_000.0

    # Poids de l'heuristique : H(s) = PATH_WEIGHT * (dist_adv - dist_moi)
    #                                + WALL_WEIGHT * (murs_moi - murs_adv)
    PATH_WEIGHT = 10.0
    WALL_WEIGHT = 1.0

    # Gestion du temps (en secondes). Le budget total pour toute la partie est
    # transmis via `remaining_time` a chaque appel de compute_action.
    SAFETY_RESERVE = 3.0     # temps jamais utilise, garde en reserve
    HARD_CAP_PER_MOVE = 8.0  # temps maximal alloue a un seul coup
    MIN_BUDGET = 0.05        # sous ce seuil, on ne lance pas de recherche
    WALL_TIME_BUFFER = 8     # coups de murs supplementaires estimes restants
    MAX_DEPTH = 20           # garde-fou, jamais vraiment atteint en pratique

    def __init__(self, piece_type: str, goal_row: int = 0, name: str = "bob", *args, **kwargs) -> None:
        super().__init__(piece_type, goal_row, name)

    # ------------------------------------------------------------------
    # Point d'entree
    # ------------------------------------------------------------------

    def compute_action(self, current_state: GameStateQuoridor, remaining_time: float = 15 * 60, **kwargs) -> Action:
        """
        Choisit une action a jouer pour l'etat courant.

        Args:
            current_state (GameStateQuoridor): Etat courant du jeu.
            remaining_time (float): Temps total restant pour l'ensemble de la
                partie (et non pour ce seul coup).

        Returns:
            Action: L'action choisie.
        """
        start = time.perf_counter()

        legal_actions = list(current_state.generate_possible_stateless_actions())
        if not legal_actions:
            raise RuntimeError("No legal action available.")

        # Coup de secours : le meilleur coup a un demi-coup de profondeur,
        # calcule sur l'ensemble des actions legales (comme l'agent greedy).
        # Toujours disponible, quasi instantane, sert de filet de securite.
        fallback_ranking = self._rank_actions(current_state, legal_actions)
        best_action = fallback_ranking[0][1]

        time_budget = self._compute_time_budget(current_state, remaining_time)
        if time_budget <= self.MIN_BUDGET:
            return best_action

        deadline = start + time_budget

        depth = 1
        try:
            while depth <= self.MAX_DEPTH:
                action = self._search_root(current_state, depth, deadline)
                best_action = action
                if time.perf_counter() >= deadline:
                    break
                depth += 1
        except _SearchTimeUp:
            # La derniere profondeur n'a pas termine : on garde le resultat
            # de la profondeur precedente (deja stocke dans best_action).
            pass

        return best_action

    # ------------------------------------------------------------------
    # Gestion du temps
    # ------------------------------------------------------------------

    def _compute_time_budget(self, state: GameStateQuoridor, remaining_time: float) -> float:
        """
        Determine combien de temps consacrer au coup courant.

        On estime grossierement le nombre de coups qu'il nous reste a jouer
        (notre distance actuelle jusqu'au but, plus une marge pour les murs)
        et on repartit le temps restant sur ces coups. Le budget est ensuite
        borne pour ne jamais risquer un depassement du temps total alloue.
        """
        if remaining_time <= self.SAFETY_RESERVE:
            return 0.0

        agent = self._get_player(state, self.get_id())
        own_distance = state._shortest_path(agent) or 1

        estimated_moves_left = max(own_distance + self.WALL_TIME_BUFFER, 1)
        budget = remaining_time / estimated_moves_left

        budget = min(budget, remaining_time - self.SAFETY_RESERVE)
        budget = min(budget, self.HARD_CAP_PER_MOVE)
        budget = max(budget, 0.0)

        return budget

    def _check_time(self, deadline: float) -> None:
        if time.perf_counter() >= deadline:
            raise _SearchTimeUp()

    # ------------------------------------------------------------------
    # Recherche minimax avec elagage alpha-beta
    # ------------------------------------------------------------------

    def _search_root(self, state: GameStateQuoridor, depth: int, deadline: float) -> StatelessAction:
        """
        Lance une recherche alpha-beta complete a la profondeur donnee et
        retourne la meilleure action trouvee a la racine.
        """
        actions = self._candidate_actions(state)
        ranked = self._rank_actions(state, actions)

        alpha, beta = -float("inf"), float("inf")
        best_value = -float("inf")
        best_action = ranked[0][1]

        for value, action, child in ranked:
            self._check_time(deadline)
            value = self._alphabeta(child, depth - 1, alpha, beta, deadline)
            if value > best_value:
                best_value = value
                best_action = action
            alpha = max(alpha, best_value)

        return best_action

    def _alphabeta(self, state: GameStateQuoridor, depth: int, alpha: float, beta: float, deadline: float) -> float:
        self._check_time(deadline)

        if state.is_done() or depth == 0:
            return self._evaluate(state)

        actions = self._candidate_actions(state)
        ranked = self._rank_actions(state, actions)
        if not ranked:
            return self._evaluate(state)

        maximizing = state.active_player.get_id() == self.get_id()

        if maximizing:
            value = -float("inf")
            for _, _, child in ranked:
                value = max(value, self._alphabeta(child, depth - 1, alpha, beta, deadline))
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value
        else:
            value = float("inf")
            for _, _, child in ranked:
                value = min(value, self._alphabeta(child, depth - 1, alpha, beta, deadline))
                beta = min(beta, value)
                if alpha >= beta:
                    break
            return value

    # ------------------------------------------------------------------
    # Generation et tri des coups
    # ------------------------------------------------------------------

    def _candidate_actions(self, state: GameStateQuoridor) -> list[StatelessAction]:
        """
        Restreint les actions considerees par la recherche pour limiter le
        facteur de branchement (le nombre de murs legaux peut depasser la
        centaine). Tous les deplacements de pion sont conserves. Seuls les
        murs qui touchent le plus court chemin d'un des deux joueurs sont
        conserves, car ce sont les seuls murs susceptibles de vraiment
        changer la distance de l'un des joueurs a court terme.
        """
        actions = list(state.generate_possible_stateless_actions())

        move_actions = [a for a in actions if a.data["type"] == "move"]
        wall_actions = [a for a in actions if a.data["type"] != "move"]

        if not wall_actions:
            return move_actions

        relevant_walls = self._relevant_walls(state)
        pruned_walls = [a for a in wall_actions if self._to_wall(a) in relevant_walls]

        return move_actions + pruned_walls

    def _relevant_walls(self, state: GameStateQuoridor) -> set[Wall]:
        """
        Calcule l'ensemble des murs pouvant bloquer une case du plus court
        chemin (ignorant les pions) de l'un ou l'autre des deux joueurs.
        """
        relevant = set()
        for player in state.players:
            path = self._shortest_path_cells(state, player)
            for a, b in zip(path, path[1:]):
                relevant.update(state._candidate_blocking_walls(a, b))
        return relevant

    def _shortest_path_cells(self, state: GameStateQuoridor, player) -> list[tuple[int, int]]:
        """
        Reconstruit un plus court chemin (liste de cases) entre le pion du
        joueur et sa rangee cible, en ignorant l'autre pion (memes regles que
        GameStateQuoridor._shortest_path, mais avec reconstruction du chemin).
        """
        start = state.rep.pawn_positions[player.id]
        if start[0] == player.get_goal_row():
            return [start]

        previous = {start: None}
        queue = deque([start])

        while queue:
            position = queue.popleft()
            if position[0] == player.get_goal_row():
                path = []
                current = position
                while current is not None:
                    path.append(current)
                    current = previous[current]
                path.reverse()
                return path

            for neighbour in state._reachable_neighbours(position):
                if neighbour not in previous:
                    previous[neighbour] = position
                    queue.append(neighbour)

        # Ne devrait pas arriver : la legalite des murs garantit un chemin.
        return [start]

    def _to_wall(self, action: StatelessAction) -> Wall:
        row, col = action.data["destination"]
        orientation = Orientation.VERTICAL if action.data["type"] == "vertical" else Orientation.HORIZONTAL
        return Wall(row=row, col=col, orientation=orientation)

    def _rank_actions(self, state: GameStateQuoridor, actions: list[StatelessAction]):
        """
        Applique chaque action, evalue l'etat resultant et trie les actions
        du meilleur au pire coup pour le joueur actif de `state`.

        Sert a la fois de tri pour ameliorer l'elagage alpha-beta (jouer
        d'abord les coups prometteurs coupe davantage de branches) et de
        base pour le coup de secours retourne quand le temps manque.

        Returns:
            list[tuple[float, StatelessAction, GameStateQuoridor]]: triplets
            (valeur, action, etat resultant) tries du meilleur au pire coup.
        """
        maximizing = state.active_player.get_id() == self.get_id()

        scored = []
        for action in actions:
            child = state.apply_action(action)
            value = self._evaluate(child)
            scored.append((value, action, child))

        scored.sort(key=lambda triplet: triplet[0], reverse=maximizing)
        return scored

    # ------------------------------------------------------------------
    # Heuristique
    # ------------------------------------------------------------------

    def _evaluate(self, state: GameStateQuoridor) -> float:
        """
        Evalue un etat du point de vue de l'agent (valeurs positives = bon
        pour l'agent). Combine deux criteres :
            - l'avance en distance (plus courts chemins) sur l'adversaire,
            - le nombre de murs qu'il nous reste par rapport a l'adversaire.
        """
        agent = self._get_player(state, self.get_id())
        opponent = self._get_player(state, self._opponent_id(state))

        if state.is_done():
            return self.WIN_VALUE if state.scores.get(agent.get_id(), 0.0) == 1.0 else -self.WIN_VALUE

        agent_distance = state._shortest_path(agent)
        opponent_distance = state._shortest_path(opponent)

        path_term = (opponent_distance - agent_distance) * self.PATH_WEIGHT
        wall_term = (state.rep.remaining_walls[agent.get_id()] - state.rep.remaining_walls[opponent.get_id()]) * self.WALL_WEIGHT

        return path_term + wall_term

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def _get_player(self, state: GameStateQuoridor, player_id: int):
        return next(p for p in state.players if p.get_id() == player_id)

    def _opponent_id(self, state: GameStateQuoridor) -> int:
        return next(p.get_id() for p in state.players if p.get_id() != self.get_id())
