"""
Apprend les poids de l'evaluation de la V5 par regression logistique.

Chaque position enregistree devient un exemple : les caracteristiques de
MyPlayer._features vues par le joueur qui a le trait, et l'etiquette 1 s'il a
gagne la partie. Les positions dont la course est deja tranchee (un joueur
sans murs) sont exclues, l'agent les calcule exactement. Une partie sur cinq
sert de test, jamais d'entrainement.

    python entrainer.py donnees/parties_tour1.jsonl ../Quoridor/my_player_v5.py
"""
import importlib.util
import json
import sys

import numpy as np

from arene import ENGINE

sys.path.insert(0, ENGINE)
spec = importlib.util.spec_from_file_location("agent", sys.argv[2])
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)

player = agent.MyPlayer("W")
player._geo = agent._Geometry(9)
player._goals = (0, 8)
geo = player._geo


def situation(rec):
    walls = 0
    for r, c, o in rec["w"]:
        walls |= 1 << (geo.hbit(r, c) if o == 0 else geo.vbit(r, c))
    pos = tuple(r * 9 + c for r, c in rec["p"])
    s = rec["s"]
    ds = player._dist(walls, s)[pos[s]]
    do = player._dist(walls, 1 - s)[pos[1 - s]]
    return ds, do, rec["wl"][s], rec["wl"][1 - s]


def load_dataset(path):
    rows, labels, games, v3 = [], [], [], []
    for k, line in enumerate(open(path)):
        game = json.loads(line)
        for rec in game["pos"]:
            ds, do, ws, wo = situation(rec)
            if ds == 0 or do == 0:
                continue
            if (wo == 0 and ds <= do) or (ws == 0 and do < ds):
                continue
            rows.append((1.0,) + agent.MyPlayer._features(ds, do, ws, wo))
            labels.append(1.0 if game["winner"] == rec["s"] else 0.0)
            games.append(k)
            v3.append((1.0, 10 * (do - ds) + 6 * (ws - wo) + 5))
    return np.array(rows), np.array(labels), np.array(games), np.array(v3, dtype=float)


def fit(X, y, l2=1e-3, lr=0.5, epochs=4000):
    """Descente de gradient sur la log-vraisemblance, colonnes centrees reduites."""
    mu, sd = X[:, 1:].mean(0), X[:, 1:].std(0) + 1e-9
    Z = np.hstack([X[:, :1], (X[:, 1:] - mu) / sd])
    w = np.zeros(Z.shape[1])
    for _ in range(epochs):
        p = 1 / (1 + np.exp(-Z @ w))
        w -= lr * (Z.T @ (p - y) / len(y) + l2 * np.r_[0, w[1:]])
    return np.r_[w[0] - (w[1:] * mu / sd).sum(), w[1:] / sd]


def report(name, X, y, w, mask):
    for part, m in (("entrainement", ~mask), ("test", mask)):
        p = np.clip(1 / (1 + np.exp(-X[m] @ w)), 1e-6, 1 - 1e-6)
        loss = -np.mean(y[m] * np.log(p) + (1 - y[m]) * np.log(1 - p))
        acc = np.mean((p > 0.5) == (y[m] > 0.5))
        print("%-6s %-12s log-loss %.4f  precision %.3f" % (name, part, loss, acc))


if __name__ == "__main__":
    X, y, games, v3 = load_dataset(sys.argv[1])
    test = games % 5 == 0
    print("positions", len(y), "parties", games.max() + 1)
    w_v3 = fit(v3[~test], y[~test])
    report("V3", v3, y, w_v3, test)
    w = fit(X[~test], y[~test])
    report("appris", X, y, w, test)
    # Facteur 30 : un pas de distance vaut alors environ 10, comme dans la V3
    scaled = w * 30
    print("poids bruts :", np.round(w, 4).tolist())
    print("WEIGHTS =", tuple(round(float(x), 2) for x in scaled))
