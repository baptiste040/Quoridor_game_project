"""
Matchs entre deux agents sans passer par le serveur seahorse.

Chaque coup est joue sur une copie de l'etat reconstruite depuis le JSON (comme
le fait seahorse), le temps est decompte comme sur Abyss et un coup illegal,
une exception ou un depassement donnent la partie a l'adversaire. Les couleurs
alternent et chaque paire de parties part de la meme ouverture aleatoire.

    python arene.py ../Quoridor/my_player_v5.py ../Quoridor/my_player_v3.py -n 24 -c 60
"""
import argparse
import importlib.util
import json
import os
import random
import sys
import time
import traceback
from multiprocessing import Pool

ENGINE = os.environ.get("QENGINE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Quoridor"))
RAND_PLIES = int(os.environ.get("QRAND", "4"))
sys.path.insert(0, ENGINE)


def load(path, tag):
    spec = importlib.util.spec_from_file_location(tag, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def legal(state, action):
    from actions_quoridor import Orientation, Wall
    d = action.data
    if d["type"] == "move":
        return any(a.data["destination"] == tuple(d["destination"]) for a in state._legal_moves())
    r, c = d["destination"]
    o = Orientation.HORIZONTAL if d["type"] == "horizontal" else Orientation.VERTICAL
    return state._is_wall_legal(Wall(r, c, o))


def snapshot(state):
    from game_state_quoridor import GameStateQuoridor
    raw = json.dumps(state.to_json(), default=lambda o: o.to_json() if hasattr(o, "to_json") else str(o))
    return GameStateQuoridor.from_json(raw)


def random_opening(state, rng, plies):
    for _ in range(plies):
        acts = list(state._legal_moves())
        if rng.random() < 0.3 and state.rep.remaining_walls[state.active_player.get_id()] > 8:
            acts = list(state._legal_walls())
        nxt = state.apply_action(rng.choice(acts))
        if nxt.is_done():
            break
        state = nxt
    return state


def play(args):
    pa, pb, clock, seed, max_plies = args
    sys.path.insert(0, ENGINE)
    from board_quoridor import BoardQuoridor
    from game_state_quoridor import GameStateQuoridor
    from seahorse.game.stateless_action import StatelessAction

    swap = seed % 2 == 1
    ma, mb = load(pa, "A%d" % seed), load(pb, "B%d" % seed)
    first, second = (mb, ma) if swap else (ma, mb)
    p1 = first.MyPlayer("W", goal_row=0, name="p1")
    p2 = second.MyPlayer("B", goal_row=8, name="p2")
    ids = [p1.get_id(), p2.get_id()]
    rep = BoardQuoridor({ids[0]: (8, 4), ids[1]: (0, 4)}, frozenset(), {ids[0]: 10, ids[1]: 10})
    state = GameStateQuoridor({ids[0]: 0, ids[1]: 0}, p1, players=[p1, p2], rep=rep, step=0)
    if seed // 2:
        state = random_opening(state, random.Random(seed // 2), RAND_PLIES)

    agents = {ids[0]: p1, ids[1]: p2}
    remaining = {ids[0]: clock, ids[1]: clock}
    longest = {ids[0]: 0.0, ids[1]: 0.0}
    winner, reason = None, ""
    for _ in range(max_plies):
        pid = state.active_player.get_id()
        other = ids[1] if pid == ids[0] else ids[0]
        snap = snapshot(state)
        t0 = time.perf_counter()
        try:
            action = agents[pid].compute_action(snap, remaining_time=remaining[pid])
        except Exception:
            winner, reason = other, "crash " + traceback.format_exc()[-300:]
            break
        dt = time.perf_counter() - t0
        remaining[pid] -= dt
        longest[pid] = max(longest[pid], dt)
        if remaining[pid] < 0:
            winner, reason = other, "timeout"
            break
        if not isinstance(action, StatelessAction):
            action = StatelessAction(action.data)
        if not legal(state, action):
            winner, reason = other, "illegal %s" % action.data
            break
        state = state.apply_action(action)
        if state.is_done():
            winner = pid
            break

    a_id, b_id = (ids[1], ids[0]) if swap else (ids[0], ids[1])
    res = 0.5 if winner is None else (1.0 if winner == a_id else 0.0)
    return dict(seed=seed, a_white=not swap, res=res, plies=state.step, reason=reason,
                a_left=round(remaining[a_id], 1), b_left=round(remaining[b_id], 1),
                a_max=round(longest[a_id], 2), b_max=round(longest[b_id], 2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("-n", type=int, default=8, help="nombre de parties")
    ap.add_argument("-c", "--clock", type=float, default=60, help="credit de temps par joueur (s)")
    ap.add_argument("-j", type=int, default=6, help="parties en parallele")
    ap.add_argument("-s", type=int, default=0, help="graine de depart")
    ap.add_argument("--plies", type=int, default=400, help="au-dela : partie nulle")
    a = ap.parse_args()
    jobs = [(os.path.abspath(a.a), os.path.abspath(a.b), a.clock, a.s + i, a.plies) for i in range(a.n)]
    score = 0
    with Pool(a.j) as pool:
        for r in pool.imap_unordered(play, jobs):
            score += r["res"]
            print(r, flush=True)
    print("A score: %.1f / %d" % (score, a.n))
