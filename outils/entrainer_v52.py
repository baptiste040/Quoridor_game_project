"""
Apprend l'evaluation de la V5.2 (regression logistique, comme la V5) sur un
ou plusieurs fichiers de parties, dont les parties exportees d'Abyss.

Differences avec entrainer.py :
- plusieurs fichiers en entree (Abyss + parties locales) ;
- caracteristiques de la V5.2 (FEATURES ci-dessous, recopiees dans l'agent) ;
- diagnostics de coherence : valeur d'un mur en pas selon la situation, et
  part des positions nettement perdues (6 pas de retard ou plus, murs des deux
  cotes) que l'evaluation juge pourtant favorables.

    python entrainer_v52.py donnees/abyss.jsonl [donnees/parties_tour1.jsonl ...]
"""
import importlib.util
import json
import os
import sys

import numpy as np

from arene import ENGINE

sys.path.insert(0, ENGINE)
spec = importlib.util.spec_from_file_location("agent", os.path.join(ENGINE, "my_player_v5_1.py"))
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)

player = agent.MyPlayer("W")
player._geo = agent._Geometry(9)
player._goals = (0, 8)
geo = player._geo


def features(ds, do, ws, wo):
    """
    Vues par le joueur actif.
    - do - ds : ecart de distance
    - u(ws) - u(wo) : murs "utiles", u(w, d) = min(w, d) / (1 + 0.1 * min(w, d)), un
      mur sert moins quand on en a deja beaucoup et ne sert a rien au-dela de la
      distance qui reste a l'adversaire (rendements decroissants)
    - (do - ds) * (ws + wo) / 10 : un ecart de distance compte moins tant qu'il reste des murs
    - ws / (do + 1) - wo / (ds + 1) : un mur sert moins contre un pion presque arrive
    - (ds + do) / 10 : longueur de la course
    """
    us = min(ws, do) / (1 + 0.1 * min(ws, do))
    uo = min(wo, ds) / (1 + 0.1 * min(wo, ds))
    return (do - ds, us - uo, (do - ds) * (ws + wo) / 10, ws / (do + 1) - wo / (ds + 1), (ds + do) / 10)


def situation(rec):
    walls = 0
    for r, c, o in rec["w"]:
        walls |= 1 << (geo.hbit(r, c) if o == 0 else geo.vbit(r, c))
    pos = tuple(r * 9 + c for r, c in rec["p"])
    s = rec["s"]
    ds = player._dist(walls, s)[pos[s]]
    do = player._dist(walls, 1 - s)[pos[1 - s]]
    return ds, do, rec["wl"][s], rec["wl"][1 - s]


def load(paths):
    rows, labels, games, raw = [], [], [], []
    k = 0
    for path in paths:
        for line in open(path, encoding="utf-8"):
            game = json.loads(line)
            for rec in game["pos"]:
                ds, do, ws, wo = situation(rec)
                if ds == 0 or do == 0 or ds >= 900 or do >= 900:
                    continue
                if (wo == 0 and ds <= do) or (ws == 0 and do < ds):
                    continue
                rows.append((1.0,) + features(ds, do, ws, wo))
                labels.append(1.0 if game["winner"] == rec["s"] else 0.0)
                games.append(k)
                raw.append((ds, do, ws, wo))
            k += 1
    return np.array(rows), np.array(labels), np.array(games), np.array(raw)


def fit(X, y, l2=1e-3, lr=0.5, epochs=5000):
    mu, sd = X[:, 1:].mean(0), X[:, 1:].std(0) + 1e-9
    Z = np.hstack([X[:, :1], (X[:, 1:] - mu) / sd])
    w = np.zeros(Z.shape[1])
    for _ in range(epochs):
        p = 1 / (1 + np.exp(-Z @ w))
        w -= lr * (Z.T @ (p - y) / len(y) + l2 * np.r_[0, w[1:]])
    return np.r_[w[0] - (w[1:] * mu / sd).sum(), w[1:] / sd]


def logloss(X, y, w, m):
    p = np.clip(1 / (1 + np.exp(-X[m] @ w)), 1e-6, 1 - 1e-6)
    return -np.mean(y[m] * np.log(p) + (1 - y[m]) * np.log(1 - p)), np.mean((p > 0.5) == (y[m] > 0.5))


def v5_score(ds, do, ws, wo):
    w = (-0.22, 10.33, 22.52, -0.4, -35.6, 39.14, 0.08)
    if wo == 0:
        return w[1] * (do - ds) + 5 * min(ws, do)
    return w[0] + w[1] * (do - ds) + w[2] * (ws - wo) + w[3] * ((do - ds) * (ws + wo)) \
        + w[4] * (ws / (do + 1)) + w[5] * (wo / (ds + 1)) + w[6] * (ds + do)


if __name__ == "__main__":
    X, y, games, raw = load(sys.argv[1:])
    test = games % 5 == 0
    print("positions", len(y), "parties", games.max() + 1)
    w = fit(X[~test], y[~test])
    for part, m in (("entrainement", ~test), ("test", test)):
        print("V5.2 %-12s log-loss %.4f  precision %.3f" % ((part,) + logloss(X, y, w, m)))
    # Evaluation V5 sur les memes positions de test, ramenee en logit par une regression a 1 variable
    s5 = np.array([v5_score(*r) for r in raw])
    X5 = np.c_[np.ones(len(s5)), s5]
    w5 = fit(X5[~test], y[~test])
    print("V5   %-12s log-loss %.4f  precision %.3f" % (("test",) + logloss(X5, y, w5, test)))

    scale = 10 / w[1]  # un pas de distance vaut 10
    W = tuple(round(float(x * scale), 2) for x in w)
    print("WEIGHTS =", W)

    def score(ds, do, ws, wo):
        return float(np.dot(W, (1.0,) + features(ds, do, ws, wo)))

    print("Valeur d'un mur en main (en pas) :")
    for d in (2, 4, 8, 12):
        vals = [(score(8, d, k, 5) - score(8, d, k - 1, 5)) / 10 for k in (2, 5, 9)]
        print("   adversaire a %2d pas : 2e mur %.2f  5e mur %.2f  9e mur %.2f" % ((d,) + tuple(vals)))
    lost = [(r, lab) for r, lab in zip(raw, y) if r[0] - r[1] >= 6 and r[2] > 0 and r[3] > 0]
    bad52 = sum(score(*r) >= 0 for r, _ in lost)
    bad5 = sum(v5_score(*r) >= 0 for r, _ in lost)
    wr = np.mean([lab for _, lab in lost])
    print("positions avec >=6 pas de retard (murs des deux cotes) : %d, gagnees en realite %.1f %%" % (len(lost), 100 * wr))
    print("   jugees >= 0 : V5 %.1f %%   V5.2 %.1f %%" % (100 * bad5 / len(lost), 100 * bad52 / len(lost)))
