"""
Banc de test tire des defaites sur Abyss.

1) extraire : pour chaque defaite de notre agent (dossiers fights/V5 et
   fights/v4.1), on garde la position ou c'est a nous de jouer quelques
   demi-coups avant la bascule (premier moment ou nous avons 4 pas de retard
   ou plus alors que les deux joueurs ont encore des murs). Les positions
   identiques (parties rejouees a l'identique) ne sont gardees qu'une fois.

    python positions_abyss.py extraire ../../fights donnees/positions_abyss.json

2) jouer : chaque agent candidat reprend notre place dans chaque position,
   contre un adversaire fixe, avec une horloge donnee. Score = parties gagnees.

    python positions_abyss.py jouer donnees/positions_abyss.json ADVERSAIRE.py -c 90 CANDIDAT1.py CANDIDAT2.py ...
"""
import argparse
import glob
import json
import os
import sys
import time
import traceback
from collections import deque
from multiprocessing import Pool

from arene import ENGINE, legal, load, snapshot

ME = "Crabe géant des Caraïbes"
BACK = 4


def _blocked(walls):
    b = set()
    for r, c, o in walls:
        if o == "H":
            for cc in (c, c + 1):
                b.add(((r - 1, cc), (r, cc))); b.add(((r, cc), (r - 1, cc)))
        else:
            for rr in (r, r + 1):
                b.add(((rr, c - 1), (rr, c))); b.add(((rr, c), (rr, c - 1)))
    return b


def _dist(pos, goal, b):
    q, seen = deque([(tuple(pos), 0)]), {tuple(pos)}
    while q:
        (r, c), d = q.popleft()
        if r == goal:
            return d
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (r + dr, c + dc)
            if 0 <= n[0] < 9 and 0 <= n[1] < 9 and n not in seen and ((r, c), n) not in b:
                seen.add(n); q.append((n, d + 1))
    return 99


def extract(root, out):
    found, seen = [], set()
    for folder in ("V5", "v4.1"):
        for path in sorted(glob.glob(os.path.join(root, folder, "fight_*.json"))):
            j = json.load(open(path, encoding="utf-8"))
            players = j["steps"][0]["players"]
            me = next(p for p in players if p["name"].startswith(ME))
            op = next(p for p in players if p["id"] != me["id"])
            if me["id"] in j["final_summary"].get("winners_id", []):
                continue
            mid, oid = str(me["id"]), str(op["id"])
            steps = j["steps"]
            pivot = None
            for i, s in enumerate(steps):
                rep = s["rep"]
                if not (rep["remaining_walls"][mid] and rep["remaining_walls"][oid]):
                    continue
                w = [(x["row"], x["col"], x["orientation"]) for x in rep["walls"]]
                b = _blocked(w)
                if _dist(rep["pawn_positions"][mid], me["goal_row"], b) - _dist(rep["pawn_positions"][oid], op["goal_row"], b) >= 4:
                    pivot = i
                    break
            if pivot is None:
                continue
            k = max(0, pivot - BACK)
            while k > 0 and steps[k]["active_player"]["id"] != me["id"]:
                k -= 1
            s = steps[k]
            if s["active_player"]["id"] != me["id"]:
                continue
            rep = s["rep"]
            key = json.dumps([rep["walls"], rep["pawn_positions"][mid], rep["pawn_positions"][oid]], sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            found.append(dict(source=folder + "/" + os.path.basename(path), step=k, opp=op["name"],
                              me_goal=me["goal_row"],
                              me_pos=rep["pawn_positions"][mid], op_pos=rep["pawn_positions"][oid],
                              me_walls=rep["remaining_walls"][mid], op_walls=rep["remaining_walls"][oid],
                              walls=[[x["row"], x["col"], x["orientation"]] for x in rep["walls"]]))
    json.dump(found, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(len(found), "positions ->", out)


def play(args):
    cand, opp, pos, clock, max_plies, tag = args
    sys.path.insert(0, ENGINE)
    from actions_quoridor import Orientation, Wall
    from board_quoridor import BoardQuoridor
    from game_state_quoridor import GameStateQuoridor
    from seahorse.game.stateless_action import StatelessAction

    mc, mo = load(cand, "C" + tag), load(opp, "O" + tag)
    # Le joueur blanc (but 0) est toujours players[0], comme sur Abyss
    if pos["me_goal"] == 0:
        p_me = mc.MyPlayer("W", goal_row=0, name="me"); p_op = mo.MyPlayer("B", goal_row=8, name="op")
        order = [p_me, p_op]
    else:
        p_op = mo.MyPlayer("W", goal_row=0, name="op"); p_me = mc.MyPlayer("B", goal_row=8, name="me")
        order = [p_op, p_me]
    me, op = p_me.get_id(), p_op.get_id()
    walls = frozenset(Wall(r, c, Orientation.HORIZONTAL if o == "H" else Orientation.VERTICAL) for r, c, o in pos["walls"])
    rep = BoardQuoridor({me: tuple(pos["me_pos"]), op: tuple(pos["op_pos"])}, walls,
                        {me: pos["me_walls"], op: pos["op_walls"]})
    state = GameStateQuoridor({me: 0, op: 0}, p_me, players=order, rep=rep, step=pos["step"])
    agents = {me: p_me, op: p_op}
    remaining = {me: clock, op: clock}
    winner, reason = None, ""
    for _ in range(max_plies):
        pid = state.active_player.get_id()
        other = op if pid == me else me
        t0 = time.perf_counter()
        try:
            action = agents[pid].compute_action(snapshot(state), remaining_time=remaining[pid])
        except Exception:
            winner, reason = other, "crash " + traceback.format_exc()[-200:]
            break
        remaining[pid] -= time.perf_counter() - t0
        if remaining[pid] < 0:
            winner, reason = other, "timeout"
            break
        if not isinstance(action, StatelessAction):
            action = StatelessAction(action.data)
        if not legal(state, action):
            winner, reason = other, "illegal"
            break
        state = state.apply_action(action)
        if state.is_done():
            winner = pid
            break
    return dict(cand=os.path.basename(cand), source=pos["source"], res=1.0 if winner == me else (0.5 if winner is None else 0.0),
                reason=reason, left=round(remaining[me], 1))


if __name__ == "__main__":
    if sys.argv[1] == "extraire":
        extract(sys.argv[2], sys.argv[3])
        sys.exit()
    ap = argparse.ArgumentParser()
    ap.add_argument("mode")
    ap.add_argument("positions")
    ap.add_argument("adversaire")
    ap.add_argument("candidats", nargs="+")
    ap.add_argument("-c", "--clock", type=float, default=90)
    ap.add_argument("-j", type=int, default=6)
    ap.add_argument("--plies", type=int, default=300)
    a = ap.parse_args()
    positions = json.load(open(a.positions, encoding="utf-8"))
    jobs = [(os.path.abspath(c), os.path.abspath(a.adversaire), p, a.clock, a.plies, "%d_%d" % (i, k))
            for i, c in enumerate(a.candidats) for k, p in enumerate(positions)]
    score = {os.path.basename(c): [0.0, 0] for c in a.candidats}
    by_source = {}
    with Pool(a.j) as pool:
        for r in pool.imap_unordered(play, jobs):
            score[r["cand"]][0] += r["res"]; score[r["cand"]][1] += 1
            by_source.setdefault(r["source"], {})[r["cand"]] = r["res"]
            print(r, flush=True)
    print("adversaire :", os.path.basename(a.adversaire), "horloge", a.clock)
    for c, (s, n) in score.items():
        print("%-25s %.1f / %d" % (c, s, n))
