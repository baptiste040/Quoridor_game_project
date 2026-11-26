"""Efficacite des murs et rythme de pose par version, detail des defaites de la V5.

    python analyse_abyss_murs.py ../../fights
"""
import sys, os, glob, statistics as S
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyse_abyss import game

root = sys.argv[1]


def wall_eff(t):
    """Gain per wall: for each wall placed by X, increase of the other's distance at that step."""
    me_gain, op_gain = [], []
    for a, b in zip(t, t[1:]):
        if b["wm"] < a["wm"]:
            me_gain.append(b["do"] - a["do"])
        if b["wo"] < a["wo"]:
            op_gain.append(b["dm"] - a["dm"])
    return me_gain, op_gain


def mean(x):
    x = [v for v in x if v is not None]
    return S.mean(x) if x else float("nan")


for tag in ("v3", "V3_majuscule", "v4.1", "V5"):
    gs = [game(f) for f in sorted(glob.glob(os.path.join(root, tag, "*.json")))]
    print(f"\n######## {tag} ({len(gs)} parties, ids {gs[0]['f']}..{gs[-1]['f']})")
    for lab, sub in (("W", [g for g in gs if g["win"]]), ("L", [g for g in gs if not g["win"]])):
        mg, og, mt, ot = [], [], [], []
        walls_when_opp_zero, margin_opp_zero = [], []
        steps_per_move = []
        for g in sub:
            a, b = wall_eff(g["traj"])
            mg += a; og += b
            if g["zo"] is not None:
                walls_when_opp_zero.append(g["traj"][g["zo"]]["wm"]); margin_opp_zero.append(g["m_zo"])
            # time per own move
            own = [x for x in g["traj"] if x["act"]]
            if len(own) > 1:
                steps_per_move.append((own[0]["tm"] - own[-1]["tm"]) / (len(own) - 1))
            # how many walls we placed while opp still had walls vs after
        print(f"  [{lab}] n={len(sub)} gain/mur nous {mean(mg):.2f} (n={len(mg)}) | gain/mur adv {mean(og):.2f} (n={len(og)})"
              f" | murs nous quand adv=0: {mean(walls_when_opp_zero):.1f} marge {mean(margin_opp_zero):.1f}"
              f" | s/coup {mean(steps_per_move):.1f}")
    # wall timing: average remaining walls at given game step
    for k in (10, 20, 30, 40):
        wm = [g["traj"][k]["wm"] for g in gs if len(g["traj"]) > k]
        wo = [g["traj"][k]["wo"] for g in gs if len(g["traj"]) > k]
        print(f"   step {k}: murs restants nous {mean(wm):.1f} adv {mean(wo):.1f}")

    if tag == "V5":
        print("\n  --- détail des défaites V5 ---")
        for g in [g for g in gs if not g["win"]]:
            t = g["traj"]
            # find step where margin turned decisively negative and remained
            line = []
            for i in range(0, len(t), 6):
                x = t[i]
                line.append(f"{x['dm']}/{x['do']}w{x['wm']}-{x['wo']}")
            print(f"  {g['f']} first={g['first']} opp={g['opp'][:40]!s:40s} steps={g['steps']} "
                  f"murs fin {g['wm_end']}-{g['wo_end']} t={g['tm_used']:.0f}s/{g['to_used']:.0f}s")
            print("      ", " ".join(line))
