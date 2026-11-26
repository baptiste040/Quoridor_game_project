"""
Convertit les parties exportees d'Abyss (fights/<version>/fight_*.json) au
format de generer_parties.py, pour entrainer l'evaluation sur de vraies
parties contre des adversaires varies.

Chaque position est gardee avec le joueur qui a le trait (s) et le vainqueur :
les positions des deux joueurs servent, y compris celles de l'adversaire, ce
qui apporte des styles de jeu absents de nos parties entre nos versions
(barrages construits tot, notamment). Joueur 0 = celui dont le but est la
rangee 0, comme dans generer_parties.py.

    python abyss_vers_jsonl.py ../../fights donnees/abyss.jsonl
"""
import glob
import json
import os
import sys


def convert(path):
    j = json.load(open(path, encoding="utf-8"))
    steps = j["steps"]
    players = steps[0]["players"]
    by_goal = sorted(players, key=lambda p: p["goal_row"])  # but 0 d'abord
    ids = [str(p["id"]) for p in by_goal]
    winners = j.get("final_summary", {}).get("winners_id", [])
    if len(winners) != 1:
        return None
    winner = ids.index(str(winners[0]))
    pos = []
    for s in steps:
        rep = s["rep"]
        pos.append(dict(
            w=[[w["row"], w["col"], 0 if w["orientation"] == "H" else 1] for w in rep["walls"]],
            p=[list(rep["pawn_positions"][i]) for i in ids],
            wl=[rep["remaining_walls"][i] for i in ids],
            s=ids.index(str(s["active_player"]["id"]))))
    return dict(seed=os.path.basename(path), a=by_goal[0]["name"], b=by_goal[1]["name"],
                winner=winner, pos=pos)


if __name__ == "__main__":
    root, out = sys.argv[1], sys.argv[2]
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for path in sorted(glob.glob(os.path.join(root, "*", "fight_*.json"))):
            g = convert(path)
            if g:
                f.write(json.dumps(g, ensure_ascii=False) + "\n")
                n += 1
    print(n, "parties ecrites dans", out)
