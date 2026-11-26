"""Bilan par version des parties Abyss (fights/<version>/) : victoires, couleur, murs, temps, marges.

    python analyse_abyss.py ../../fights
"""
import json, sys, os, glob, collections, statistics as S
from collections import deque

ME = "Crabe géant des Caraïbes"
N = 9


def blocked(walls):
    """Set of blocked edges ((r,c),(r2,c2)). Wall (row,col,H) blocks between rows row,row+1 for cols col,col+1
    -- convention guessed; checked with sanity on final positions."""
    b = set()
    for w in walls:
        r, c, o = w["row"], w["col"], w["orientation"]
        if o == "H":
            for cc in (c, c + 1):
                b.add(((r - 1, cc), (r, cc))); b.add(((r, cc), (r - 1, cc)))
        else:
            for rr in (r, r + 1):
                b.add(((rr, c - 1), (rr, c))); b.add(((rr, c), (rr, c - 1)))
    return b


def dist(pos, goal, b):
    q = deque([(tuple(pos), 0)]); seen = {tuple(pos)}
    while q:
        (r, c), d = q.popleft()
        if r == goal: return d
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < N and 0 <= nc < N and (nr, nc) not in seen and ((r, c), (nr, nc)) not in b:
                seen.add((nr, nc)); q.append(((nr, nc), d + 1))
    return 99


def game(f):
    j = json.load(open(f, encoding="utf-8"))
    st = j["steps"]; fs = j.get("final_summary", {})
    pl = st[0]["players"]
    me = [p for p in pl if p["name"].startswith(ME)][0]
    op = [p for p in pl if p["id"] != me["id"]][0]
    mid, oid = str(me["id"]), str(op["id"])
    first = st[0]["active_player"]["id"] == me["id"]
    win = me["id"] in fs.get("winners_id", [])
    traj = []
    for s in st:
        rep = s["rep"]; b = blocked(rep["walls"])
        dm = dist(rep["pawn_positions"][mid], me["goal_row"], b)
        do = dist(rep["pawn_positions"][oid], op["goal_row"], b)
        traj.append(dict(dm=dm, do=do, wm=rep["remaining_walls"][mid], wo=rep["remaining_walls"][oid],
                         tm=s["remaining_time"][mid], to=s["remaining_time"][oid],
                         act=s["active_player"]["id"] == me["id"]))
    last = traj[-1]
    # first wall step by each
    fwm = next((i for i, t in enumerate(traj) if t["wm"] < 10), None)
    fwo = next((i for i, t in enumerate(traj) if t["wo"] < 10), None)
    # step when opponent ran out of walls / we ran out
    zo = next((i for i, t in enumerate(traj) if t["wo"] == 0), None)
    zm = next((i for i, t in enumerate(traj) if t["wm"] == 0), None)
    # race margin when opp hit 0 walls: (do - dm) adjusted for turn
    def margin(t):
        return t["do"] - t["dm"] + (1 if t["act"] else 0)
    m_at_zo = margin(traj[zo]) if zo is not None else None
    m_at_zm = margin(traj[zm]) if zm is not None else None
    # max advantage / min
    margins = [margin(t) for t in traj]
    # loss reason
    reason = "goal"
    if not win and last["dm"] > 0 and last["do"] > 0: reason = "other(timeout/err?)"
    if win and last["dm"] > 0: reason = "opp_fail"
    # repeated positions (cycles) for us
    return dict(f=os.path.basename(f), win=win, first=first, opp=op["name"], steps=len(st) - 1,
                wm_end=last["wm"], wo_end=last["wo"], tm_used=900 - last["tm"], to_used=900 - last["to"],
                fwm=fwm, fwo=fwo, zo=zo, zm=zm, m_zo=m_at_zo, m_zm=m_at_zm,
                maxm=max(margins), minm=min(margins), m_end=margins[-1], reason=reason,
                d0=traj[0]["dm"], dm_max=max(t["dm"] for t in traj), do_max=max(t["do"] for t in traj),
                traj=traj)


def summary(tag, games):
    W = [g for g in games if g["win"]]; L = [g for g in games if not g["win"]]
    def m(xs):
        xs = [x for x in xs if x is not None]
        return "%.1f" % S.mean(xs) if xs else "-"
    print(f"\n===== {tag}: {len(W)}W {len(L)}L  ({100*len(W)/max(1,len(games)):.0f}%)")
    fW = sum(g["win"] for g in games if g["first"]); fN = sum(1 for g in games if g["first"])
    sW = sum(g["win"] for g in games if not g["first"]); sN = len(games) - fN
    print(f"  as first (W, row8->0?): {fW}/{fN}   as second: {sW}/{sN}")
    for name, sub in (("wins", W), ("losses", L)):
        print(f"  [{name}] steps {m([g['steps'] for g in sub])} | our walls left {m([g['wm_end'] for g in sub])}"
              f" opp walls left {m([g['wo_end'] for g in sub])} | time used us {m([g['tm_used'] for g in sub])}s"
              f" opp {m([g['to_used'] for g in sub])}s | first wall us@{m([g['fwm'] for g in sub])}"
              f" opp@{m([g['fwo'] for g in sub])} | maxDist us {m([g['dm_max'] for g in sub])} opp {m([g['do_max'] for g in sub])}"
              f" | best margin {m([g['maxm'] for g in sub])} worst {m([g['minm'] for g in sub])}")
    reasons = collections.Counter(g["reason"] for g in games)
    print("  end reasons:", dict(reasons))
    # losses where we had a positive margin at some point (threw away)
    thrown = [g for g in L if g["maxm"] >= 3]
    print(f"  losses after being >=3 ahead: {len(thrown)}/{len(L)}")
    unused = [g for g in L if g["wm_end"] >= 3]
    print(f"  losses with >=3 walls unused: {len(unused)}/{len(L)}")
    timeouts = [g for g in games if g["tm_used"] > 880]
    print(f"  games where we used >880s: {len(timeouts)}")


def opponents(tag, games):
    c = collections.defaultdict(lambda: [0, 0])
    for g in games:
        c[g["opp"]][0 if g["win"] else 1] += 1
    return c


if __name__ == "__main__":
    root = sys.argv[1]
    allg = {}
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d)
        if not os.path.isdir(p): continue
        allg[d] = [game(f) for f in sorted(glob.glob(os.path.join(p, "*.json")))]
        summary(d, allg[d])
    json.dump({k: [{kk: vv for kk, vv in g.items() if kk != "traj"} for g in v] for k, v in allg.items()},
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultats", "abyss_parties.json"), "w", encoding="utf-8"), ensure_ascii=False)
    # opponent overlap V5 vs v4.1
    if "V5" in allg and "v4.1" in allg:
        o5 = opponents("V5", allg["V5"]); o4 = opponents("v4.1", allg["v4.1"])
        print("\n===== V5 opponents (V5 W-L | v4.1 W-L vs same opponent)")
        for k, v in sorted(o5.items(), key=lambda x: -sum(x[1])):
            print(f"  {k:60s} V5 {v[0]}-{v[1]} | v4.1 {o4[k][0] if k in o4 else '-'}-{o4[k][1] if k in o4 else '-'}")
