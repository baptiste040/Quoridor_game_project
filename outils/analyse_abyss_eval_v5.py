"""Ce que l evaluation apprise de la V5 pensait des positions de ses defaites sur Abyss.

    python analyse_abyss_eval_v5.py ../../fights
"""
import sys, os, glob, statistics as S
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyse_abyss import game

W = (-0.22, 10.33, 22.52, -0.4, -35.6, 39.14, 0.08)
RACE = 50000


def score(ds, do, ws, wo):
    if wo == 0 and ds <= do: return RACE + do - ds
    if ws == 0 and do < ds: return -RACE - ds + do
    w = W
    return w[0] + w[1] * (do - ds) + w[2] * (ws - wo) + w[3] * ((do - ds) * (ws + wo)) \
        + w[4] * (ws / (do + 1)) + w[5] * (wo / (ds + 1)) + w[6] * (ds + do)


root = sys.argv[1]
gs = [game(f) for f in sorted(glob.glob(os.path.join(root, "V5", "*.json")))]
L = [g for g in gs if not g["win"]]
# positions (our turn) where we are >=6 steps behind in race but eval says >= 0
bad, tot = 0, 0
for g in L:
    for t in g["traj"]:
        if not t["act"] or t["wo"] == 0 and t["wm"] == 0: continue
        if t["wo"] == 0 or t["wm"] == 0: continue
        if t["dm"] - t["do"] >= 6:
            tot += 1
            if score(t["dm"], t["do"], t["wm"], t["wo"]) >= 0: bad += 1
print(f"Défaites V5 : positions (notre trait, les 2 ont des murs) avec >=6 pas de retard : {tot}, dont évaluées >=0 par V5 : {bad}")
for name in ("fight_144343.json", "fight_141030.json", "fight_143857.json"):
    g = next(x for x in gs if x["f"] == name)
    print("\n", name, g["opp"])
    for i, t in enumerate(g["traj"]):
        if t["act"] and i % 4 in (0, 1) and i <= 50:
            print(f"   step {i:3d} dist nous {t['dm']:2d} adv {t['do']:2d}  murs nous {t['wm']} adv {t['wo']}  eval V5 = {score(t['dm'], t['do'], t['wm'], t['wo']):+.0f}")
