"""
Genere les parties d'entrainement de l'evaluation de la V5.

Chaque partie oppose deux agents tires au hasard dans la liste, avec 0 a 8
coups aleatoires au depart et une horloge courte. Toutes les positions sont
enregistrees avec le vainqueur. Les parties sans vainqueur sont ignorees.

    python generer_parties.py 0 500 donnees/parties.jsonl ../Quoridor/my_player_v3.py ../Quoridor/my_player_v5.py
"""
import json
import os
import random
import sys
import time
from multiprocessing import Pool

from arene import ENGINE, legal, load, snapshot


def game(args):
    seed, agents = args
    sys.path.insert(0, ENGINE)
    from board_quoridor import BoardQuoridor
    from game_state_quoridor import GameStateQuoridor
    from seahorse.game.stateless_action import StatelessAction

    rng = random.Random(seed)
    pa, pb = rng.choice(agents), rng.choice(agents)
    p1 = load(pa, "ga%d" % seed).MyPlayer("W", goal_row=0, name="p1")
    p2 = load(pb, "gb%d" % seed).MyPlayer("B", goal_row=8, name="p2")
    ids = [p1.get_id(), p2.get_id()]
    rep = BoardQuoridor({ids[0]: (8, 4), ids[1]: (0, 4)}, frozenset(), {ids[0]: 10, ids[1]: 10})
    state = GameStateQuoridor({ids[0]: 0, ids[1]: 0}, p1, players=[p1, p2], rep=rep, step=0)
    for _ in range(rng.randint(0, 8)):
        acts = list(state._legal_moves())
        if rng.random() < 0.35 and state.rep.remaining_walls[state.active_player.get_id()] > 7:
            acts = list(state._legal_walls())
        nxt = state.apply_action(rng.choice(acts))
        if nxt.is_done():
            break
        state = nxt

    agents_by_id = {ids[0]: p1, ids[1]: p2}
    clock = rng.choice([10.0, 15.0, 25.0])
    remaining = {ids[0]: clock, ids[1]: clock}
    positions, winner = [], None
    for _ in range(300):
        r = state.rep
        side = ids.index(state.active_player.get_id())
        positions.append(dict(
            w=[[x.row, x.col, 0 if x.orientation.name == "HORIZONTAL" else 1] for x in r.walls],
            p=[list(r.pawn_positions[i]) for i in ids],
            wl=[r.remaining_walls[i] for i in ids],
            s=side))
        pid = ids[side]
        t0 = time.perf_counter()
        a = agents_by_id[pid].compute_action(snapshot(state), remaining_time=remaining[pid])
        remaining[pid] -= time.perf_counter() - t0
        if not isinstance(a, StatelessAction):
            a = StatelessAction(a.data)
        if remaining[pid] < 0 or not legal(state, a):
            winner = 1 - side
            break
        state = state.apply_action(a)
        if state.is_done():
            winner = side
            break
    return dict(seed=seed, a=os.path.basename(pa), b=os.path.basename(pb), winner=winner, pos=positions)


if __name__ == "__main__":
    start, n, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    agents = [os.path.abspath(p) for p in sys.argv[4:]]
    with Pool(10) as pool, open(out, "a") as f:
        for g in pool.imap_unordered(game, [(s, agents) for s in range(start, start + n)]):
            if g["winner"] is not None:
                f.write(json.dumps(g) + "\n")
                f.flush()
            print(g["seed"], g["a"], g["b"], g["winner"], len(g["pos"]), flush=True)
