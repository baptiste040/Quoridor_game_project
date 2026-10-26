# Auteurs : Baptiste ALLAIN (matricule) - <nom partenaire> (matricule)
# INF8175 - Projet Quoridor - V3

from __future__ import annotations

import time

from actions_quoridor import Orientation, Wall
from game_state_quoridor import GameStateQuoridor
from player_quoridor import PlayerQuoridor
from seahorse.game.action import Action
from seahorse.game.stateless_action import StatelessAction

FAR = 999
WIN = 100_000
RACE = 50_000
EXACT, LOWER, UPPER = 0, 1, 2


class _TimeUp(Exception):
    pass


class _Geometry:
    """
    Tables precalculees pour un plateau n x n.

    Cases numerotees r * n + c. Un mur est un bit d'un entier :
    horizontal (r, c) -> r * n + c, vertical (r, c) -> n * n + r * n + c.
    Tester si un deplacement est bloque revient donc a un simple ET binaire.
    """

    DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))
    PERP = ((2, 3), (2, 3), (0, 1), (0, 1))

    def __init__(self, n: int) -> None:
        self.n = n
        self.nn = n * n
        self.step = []
        self.edge_bits = []
        for cell in range(self.nn):
            r, c = divmod(cell, n)
            steps, bits_list = [], []
            for dr, dc in self.DIRS:
                bits = self._blocking(r, c, dr, dc)
                mask = 0
                for b in bits:
                    mask |= 1 << b
                nr, nc = r + dr, c + dc
                target = nr * n + nc if 0 <= nr < n and 0 <= nc < n else -1
                steps.append((target, mask))
                bits_list.append(bits)
            self.step.append(steps)
            self.edge_bits.append(bits_list)
        self.adj = [[(v, m) for v, m in s if v >= 0] for s in self.step]

        self.conflict = {}
        for r in range(n):
            for c in range(n - 1):
                b = self.hbit(r, c)
                m = 1 << b
                if c > 0:
                    m |= 1 << self.hbit(r, c - 1)
                if c < n - 2:
                    m |= 1 << self.hbit(r, c + 1)
                if r > 0:
                    m |= 1 << self.vbit(r - 1, c + 1)
                self.conflict[b] = m
        for r in range(n - 1):
            for c in range(n):
                b = self.vbit(r, c)
                m = 1 << b
                if r > 0:
                    m |= 1 << self.vbit(r - 1, c)
                if r < n - 2:
                    m |= 1 << self.vbit(r + 1, c)
                if c > 0:
                    m |= 1 << self.hbit(r + 1, c - 1)
                self.conflict[b] = m

    def hbit(self, r: int, c: int) -> int:
        return r * self.n + c

    def vbit(self, r: int, c: int) -> int:
        return self.nn + r * self.n + c

    def _blocking(self, r: int, c: int, dr: int, dc: int) -> list[int]:
        # Memes murs que GameStateQuoridor._candidate_blocking_walls
        n = self.n
        bits = []
        if dr == 1 and r + 1 < n:
            if c > 0:
                bits.append(self.hbit(r + 1, c - 1))
            if c < n - 1:
                bits.append(self.hbit(r + 1, c))
        elif dr == -1:
            if c > 0:
                bits.append(self.hbit(r, c - 1))
            if c < n - 1:
                bits.append(self.hbit(r, c))
        elif dc == 1 and c + 1 < n:
            if r > 0:
                bits.append(self.vbit(r - 1, c + 1))
            if r < n - 1:
                bits.append(self.vbit(r, c + 1))
        elif dc == -1:
            if r > 0:
                bits.append(self.vbit(r - 1, c))
            if r < n - 1:
                bits.append(self.vbit(r, c))
        return bits

    def wall_of(self, bit: int) -> tuple[str, tuple[int, int]]:
        if bit < self.nn:
            return "horizontal", divmod(bit, self.n)
        return "vertical", divmod(bit - self.nn, self.n)


class MyPlayer(PlayerQuoridor):
    """
    V3 : negamax alpha-beta (PVS) avec approfondissement iteratif, table de
    transposition et coups killers, sur une representation interne du plateau
    beaucoup plus rapide que celle du moteur (murs en bits, distances en cache).
    """

    STEP_W = 10
    WALL_W = 6
    TEMPO = 5
    PROGRESS_MARGIN = 10
    ROOT_WALLS = 40
    NODE_WALLS = 10
    MAX_DEPTH = 40

    def __init__(self, piece_type: str, goal_row: int = 0, name: str = "bob", *args, **kwargs) -> None:
        super().__init__(piece_type, goal_row, name, *args, **kwargs)
        self._geo = None
        self._goals = (0, 0)
        self._dcache = {}
        self._tt = {}
        self._killers = []
        self._total = None
        self._deadline = 0.0
        self._nodes = 0
        self._root_best = None
        self._fallbacks = 0
        self._last_depth = 0

    def compute_action(self, current_state: GameStateQuoridor, remaining_time: float = 15 * 60, **kwargs) -> Action:
        start = time.perf_counter()
        if self._total is None:
            self._total = max(remaining_time, 1.0)

        try:
            walls, pos, wl, side = self._load(current_state)
            move = self._choose(walls, pos, wl, side, start, remaining_time)
            action = self._to_action(move)
            if self._is_legal(current_state, action):
                return action
        except Exception:
            pass
        self._fallbacks += 1
        return self._fallback(current_state)

    # ------------------------------------------------------------------
    # Conversion etat moteur <-> representation interne
    # ------------------------------------------------------------------

    def _load(self, state: GameStateQuoridor):
        rep = state.rep
        n = rep.dimension
        if self._geo is None or self._geo.n != n:
            self._geo = _Geometry(n)
            self._dcache.clear()
            self._tt.clear()
        g = self._geo
        players = state.players
        ids = [p.get_id() for p in players]
        self._goals = (players[0].get_goal_row(), players[1].get_goal_row())

        pos = tuple(rep.pawn_positions[i][0] * n + rep.pawn_positions[i][1] for i in ids)
        wl = tuple(rep.remaining_walls[i] for i in ids)
        walls = 0
        for w in rep.walls:
            if w.orientation == Orientation.HORIZONTAL:
                walls |= 1 << g.hbit(w.row, w.col)
            else:
                walls |= 1 << g.vbit(w.row, w.col)
        side = ids.index(state.active_player.get_id())
        return walls, pos, wl, side

    def _to_action(self, move: int) -> StatelessAction:
        g = self._geo
        if move >= 0:
            return StatelessAction({"type": "move", "destination": divmod(move, g.n)})
        kind, dest = g.wall_of(-1 - move)
        return StatelessAction({"type": kind, "destination": dest})

    def _is_legal(self, state: GameStateQuoridor, action: StatelessAction) -> bool:
        data = action.data
        if data["type"] == "move":
            return any(a.data["destination"] == data["destination"] for a in state._legal_moves())
        r, c = data["destination"]
        orientation = Orientation.HORIZONTAL if data["type"] == "horizontal" else Orientation.VERTICAL
        return state._is_wall_legal(Wall(r, c, orientation))

    def _fallback(self, state: GameStateQuoridor) -> StatelessAction:
        # Filet de securite : deplacement qui rapproche le plus du but (moteur officiel).
        moves = state._legal_moves()
        if not moves:
            return next(iter(state.generate_possible_stateless_actions()))
        me = next(p for p in state.players if p.get_id() == self.get_id())

        def dist(a):
            d = state.apply_action(a)._shortest_path(me)
            return FAR if d is None else d

        return min(moves, key=dist)

    # ------------------------------------------------------------------
    # Choix du coup et gestion du temps
    # ------------------------------------------------------------------

    def _choose(self, walls, pos, wl, side, start, remaining_time) -> int:
        g = self._geo
        s, o = side, 1 - side
        dm_s = self._dist(walls, s)
        ds, do = dm_s[pos[s]], self._dist(walls, o)[pos[o]]
        moves = self._pawn_moves(walls, pos[s], pos[o])
        best = min(moves, key=lambda m: dm_s[m])

        if dm_s[best] == 0:
            return best
        # Course gagnee d'avance : l'adversaire n'a plus de murs et on arrive avant lui
        if wl[o] == 0 and ds <= do:
            return best

        budget = self._budget(remaining_time, ds)
        self._deadline = start + budget
        soft = start + 0.45 * budget

        if len(self._tt) > 1_000_000:
            self._tt.clear()
        if len(self._dcache) > 250_000:
            self._dcache.clear()

        children = self._children(walls, pos, wl, s, self.ROOT_WALLS)
        children.sort(key=lambda t: t[0], reverse=True)
        best = children[0][1]
        self._killers = [[None, None] for _ in range(self.MAX_DEPTH + 2)]
        self._nodes = 0

        value, done = None, 0
        for depth in range(1, self.MAX_DEPTH + 1):
            self._root_best = None
            try:
                value, move = self._root_search(children, s, depth)
            except _TimeUp:
                if self._root_best is not None:
                    best = self._root_best
                break
            best, done = move, depth
            self._last_depth = depth
            children.sort(key=lambda t: t[1] != move)
            if abs(value) >= WIN - 1000 or time.perf_counter() > soft:
                break

        if done >= 2 and (best < 0 or dm_s[best] >= ds):
            best = self._prefer_progress(children, s, done, value, best, dm_s, ds)
        return best

    def _prefer_progress(self, children, side, depth, value, best, dm_s, ds):
        """
        Effet d'horizon : quand l'adversaire a encore des murs, avancer maintenant
        ou plus tard donne souvent le meme score a profondeur fixe, et l'agent
        peut tourner en rond. Si le meilleur deplacement vers le but est presque
        aussi bon que le coup trouve, on le prefere.
        """
        if value is None or abs(value) >= RACE:
            return best
        forward = [t for t in children if t[1] >= 0 and t[2] is not None and dm_s[t[1]] < ds]
        if not forward:
            return best
        _, move, (w2, p2, wl2) = forward[0]
        target = value - self.PROGRESS_MARGIN
        if best < 0:
            target = value - self.PROGRESS_MARGIN // 2
        try:
            val = -self._negamax(w2, p2, wl2, 1 - side, depth - 1, -target, -target + 1, 1)
        except _TimeUp:
            return best
        return move if val >= target else best

    def _budget(self, remaining: float, own_distance: int) -> float:
        """
        Temps alloue au coup. Le credit est global (15 min pour la partie, sans
        tolerance), donc on repartit le temps restant hors reserve sur une
        estimation des coups restants. La suite des budgets est decroissante,
        ce qui garantit qu'on ne depasse jamais le credit total.
        """
        total = self._total
        reserve = max(2.0, 0.04 * total)
        if remaining <= reserve:
            return max(0.01, remaining / 60)
        moves_left = max(10, own_distance + 12)
        return min((remaining - reserve) / moves_left, 0.035 * total)

    # ------------------------------------------------------------------
    # Recherche
    # ------------------------------------------------------------------

    def _root_search(self, children, side, depth):
        alpha, beta = -WIN - 1, WIN + 1
        best_val, best_move = -WIN - 1, children[0][1]
        for i, (_, move, child) in enumerate(children):
            if child is None:
                val = WIN
            else:
                w2, p2, wl2 = child
                if i == 0:
                    val = -self._negamax(w2, p2, wl2, 1 - side, depth - 1, -beta, -alpha, 1)
                else:
                    val = -self._negamax(w2, p2, wl2, 1 - side, depth - 1, -alpha - 1, -alpha, 1)
                    if alpha < val < beta:
                        val = -self._negamax(w2, p2, wl2, 1 - side, depth - 1, -beta, -alpha, 1)
            if val > best_val:
                best_val, best_move = val, move
            alpha = max(alpha, val)
            self._root_best = best_move
        return best_val, best_move

    def _negamax(self, walls, pos, wl, side, depth, alpha, beta, ply) -> int:
        self._nodes += 1
        if not self._nodes & 31 and time.perf_counter() > self._deadline:
            raise _TimeUp()

        if depth <= 0:
            return self._evaluate(walls, pos, wl, side)

        if wl[0] == 0 or wl[1] == 0:
            static = self._evaluate(walls, pos, wl, side)
            if abs(static) >= RACE:
                return static

        key = (walls, pos, wl, side)
        entry = self._tt.get(key)
        tt_move = None
        if entry is not None:
            e_depth, flag, val, tt_move = entry
            if e_depth >= depth:
                if flag == EXACT:
                    return val
                if flag == LOWER and val >= beta:
                    return val
                if flag == UPPER and val <= alpha:
                    return val

        children = self._children(walls, pos, wl, side, self.NODE_WALLS)

        # Profondeur 1 : la valeur de chaque enfant est deja son score statique
        if depth == 1:
            best = max(t[0] for t in children)
            return WIN - ply if best >= WIN else best

        killers = self._killers[ply]
        children.sort(key=lambda t: (t[1] == tt_move, t[1] in killers, t[0]), reverse=True)

        alpha0 = alpha
        best, best_move = -WIN - 1, None
        for score, move, child in children:
            if child is None:
                val = WIN - ply
            else:
                w2, p2, wl2 = child
                val = -self._negamax(w2, p2, wl2, 1 - side, depth - 1, -beta, -alpha, ply + 1)
            if val > best:
                best, best_move = val, move
                if val > alpha:
                    alpha = val
                    if alpha >= beta:
                        if move != killers[0]:
                            killers[1] = killers[0]
                            killers[0] = move
                        break

        if best <= alpha0:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        else:
            flag = EXACT
        self._tt[key] = (depth, flag, best, best_move)
        return best

    def _children(self, walls, pos, wl, side, wall_limit):
        """
        Coups candidats avec leur score statique (point de vue du joueur actif).
        Tous les deplacements sont gardes. Pour les murs, seuls ceux qui coupent
        tous les plus courts chemins adverses (donc qui l'allongent vraiment) sont
        consideres, puis on garde les wall_limit meilleurs.
        """
        g = self._geo
        o = 1 - side
        goal = self._goals[side]
        dm_s = self._dist(walls, side)
        dm_o = self._dist(walls, o)
        ds, do = dm_s[pos[side]], dm_o[pos[o]]
        out = []

        for cell in self._pawn_moves(walls, pos[side], pos[o]):
            if cell // g.n == goal:
                out.append((WIN, cell, None))
                continue
            np = (cell, pos[1]) if side == 0 else (pos[0], cell)
            out.append((-self._score(do, dm_s[cell], wl[o], wl[side]), cell, (walls, np, wl)))

        if wl[side] > 0:
            nwl = (wl[0] - 1, wl[1]) if side == 0 else (wl[0], wl[1] - 1)
            own_edges, own_bits = self._dag(walls, pos[side], dm_s)
            opp_edges, opp_bits = self._dag(walls, pos[o], dm_o)
            cand = []
            for bit in opp_bits:
                if walls & g.conflict[bit]:
                    continue
                mask = 1 << bit
                if self._still_short(opp_edges, pos[o], mask):
                    continue
                nw = walls | mask
                d_o2 = self._dist(nw, o)[pos[o]]
                if d_o2 >= FAR:
                    continue
                if bit in own_bits and not self._still_short(own_edges, pos[side], mask):
                    d_s2 = self._dist(nw, side)[pos[side]]
                else:
                    d_s2 = ds
                if d_s2 >= FAR:
                    continue
                cand.append((-self._score(d_o2, d_s2, wl[o], nwl[side]), -1 - bit, (nw, pos, nwl)))
            if len(cand) > wall_limit:
                cand.sort(key=lambda t: t[0], reverse=True)
                cand = cand[:wall_limit]
            out.extend(cand)

        return out

    def _evaluate(self, walls, pos, wl, side) -> int:
        """
        Score du point de vue du joueur qui doit jouer.

        Si un des deux joueurs n'a plus de murs, la course peut etre tranchee
        exactement : celui qui joue gagne s'il est au moins aussi proche.
        Sinon : ecart de distance, murs restants et un bonus de trait.
        """
        o = 1 - side
        ds = self._dist(walls, side)[pos[side]]
        do = self._dist(walls, o)[pos[o]]
        return self._score(ds, do, wl[side], wl[o])

    def _score(self, ds, do, ws, wo) -> int:
        if wo == 0 and ds <= do:
            return RACE + do - ds
        if ws == 0 and do < ds:
            return -RACE - ds + do
        return self.STEP_W * (do - ds) + self.WALL_W * (ws - wo) + self.TEMPO

    # ------------------------------------------------------------------
    # Regles et plus courts chemins sur la representation interne
    # ------------------------------------------------------------------

    def _pawn_moves(self, walls, me, opp) -> list[int]:
        # Reprend exactement GameStateQuoridor._try_direction (sauts et diagonales)
        step = self._geo.step
        res = []
        for d in range(4):
            v, m = step[me][d]
            if v < 0 or walls & m:
                continue
            if v != opp:
                res.append(v)
                continue
            w, m2 = step[opp][d]
            if m2 and walls & m2:
                for pd in _Geometry.PERP[d]:
                    x, m3 = step[opp][pd]
                    if x >= 0 and not walls & m3:
                        res.append(x)
            elif w >= 0:
                res.append(w)
        return res

    def _dag(self, walls, start, dm):
        """
        Graphe de tous les plus courts chemins depuis start (aretes ou la
        distance au but baisse de 1) et ensemble des murs qui touchent une arete.
        """
        g = self._geo
        edges, bits = {}, set()
        stack = [start]
        while stack:
            u = stack.pop()
            if u in edges:
                continue
            out = []
            du = dm[u]
            if du:
                for d in range(4):
                    v, m = g.step[u][d]
                    if v >= 0 and not walls & m and dm[v] == du - 1:
                        out.append((v, m))
                        bits.update(g.edge_bits[u][d])
                        stack.append(v)
            edges[u] = out
        return edges, bits

    @staticmethod
    def _still_short(edges, start, wall_mask) -> bool:
        # Vrai si un plus court chemin survit au nouveau mur (distance inchangee)
        stack, seen = [start], {start}
        while stack:
            out = edges[stack.pop()]
            if not out:
                return True
            for v, m in out:
                if not m & wall_mask and v not in seen:
                    seen.add(v)
                    stack.append(v)
        return False

    def _dist(self, walls, who) -> list[int]:
        goal = self._goals[who]
        key = (walls, goal)
        dm = self._dcache.get(key)
        if dm is None:
            if len(self._dcache) > 400_000:
                self._dcache.clear()
            dm = self._bfs(walls, goal)
            self._dcache[key] = dm
        return dm

    def _bfs(self, walls, goal_row) -> list[int]:
        g = self._geo
        adj = g.adj
        dist = [FAR] * g.nn
        frontier = list(range(goal_row * g.n, goal_row * g.n + g.n))
        for cell in frontier:
            dist[cell] = 0
        k = 0
        while frontier:
            k += 1
            nxt = []
            for u in frontier:
                for v, m in adj[u]:
                    if dist[v] == FAR and not walls & m:
                        dist[v] = k
                        nxt.append(v)
            frontier = nxt
        return dist
