#!/usr/bin/env python3
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw"
PROCESSED = REPO / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

TEMF_PREPARED = PROCESSED / "temf_prepared.npz"
OUTPUT = PROCESSED / "temf_final_graph_prepared.npz"
K = 10
TRAIN_END = 34


def part_number(path: Path) -> int:
    m = re.search(r"part(\d+)", path.name)
    if not m:
        raise ValueError(f"Cannot parse part number: {path}")
    return int(m.group(1))


def choose_one_per_part(pattern: str, expected: range) -> list[Path]:
    candidates = list(RAW.glob(pattern))
    by_part: dict[int, list[Path]] = {}
    for p in candidates:
        by_part.setdefault(part_number(p), []).append(p)
    chosen = []
    for n in expected:
        if n not in by_part:
            raise FileNotFoundError(f"Missing part {n} for {pattern}")
        chosen.append(sorted(by_part[n], key=lambda p: (len(p.name), p.name))[0])
    return chosen


def choose_class_file() -> Path:
    for name in ("wallets_classes.txt", "wallets_classes(2).txt"):
        p = RAW / name
        if p.exists():
            return p
    cands = sorted(RAW.glob("wallets_classes*.txt"))
    if not cands:
        raise FileNotFoundError("No wallets_classes*.txt found in data/raw/")
    return cands[0]


def csr_from_edges(key: np.ndarray, val: np.ndarray, n: int):
    order = np.argsort(key, kind="mergesort")
    key, val = key[order], val[order]
    counts = np.bincount(key, minlength=n)
    ptr = np.empty(n + 1, dtype=np.int64)
    ptr[0] = 0
    np.cumsum(counts, out=ptr[1:])
    return ptr, val


def main():
    if not TEMF_PREPARED.exists():
        raise FileNotFoundError(
            f"{TEMF_PREPARED} not found. Run experiments/01_prepare_temf_data.py first."
        )

    z = np.load(TEMF_PREPARED)
    Xseq = z["Xseq"].astype(np.float32)
    times = z["times"]
    y = z["y"]
    prior = z["prior_count"]
    starts = z["starts"]
    ends = z["ends"]

    feature_parts = choose_one_per_part("wallets_features_part*.txt", range(1, 16))
    edge_parts = choose_one_per_part("AddrAddr_edgelist_part*.txt", range(1, 6))
    class_file = choose_class_file()

    classes = pd.read_csv(class_file)
    classes = classes[classes["class"].isin([1, 2])].copy()
    classes["address"] = classes["address"].astype(str)
    labeled = set(classes["address"])

    with open(feature_parts[0], "r") as f:
        header = f.readline().rstrip("\n").split(",")

    keys = []
    for i, p in enumerate(feature_parts):
        if i == 0:
            d = pd.read_csv(p, usecols=["address", "Time step"])
        else:
            d = pd.read_csv(
                p, names=header, header=None, usecols=["address", "Time step"]
            )
        d["address"] = d["address"].astype(str)
        keys.append(d[d["address"].isin(labeled)])

    obs = pd.concat(keys, ignore_index=True).drop_duplicates()
    obs = (
        obs.groupby(["address", "Time step"], as_index=False, sort=False)
        .size()
        .drop(columns="size")
        .sort_values(["address", "Time step"])
        .reset_index(drop=True)
    )

    if len(obs) != len(times):
        raise ValueError(f"Observation mismatch: {len(obs)} vs {len(times)}")
    if not np.array_equal(obs["Time step"].to_numpy(np.int16), times):
        raise ValueError("Time order does not match temf_prepared.npz")

    wallet_addrs = np.array([obs.address.iloc[s] for s in starts], dtype=object)
    addr_to_wid = {a: i for i, a in enumerate(wallet_addrs)}
    nwallet = len(wallet_addrs)

    row_wid = np.empty(len(times), dtype=np.int32)
    for wid, (s0, e0) in enumerate(zip(starts, ends)):
        row_wid[s0:e0] = wid

    indeg, outdeg, selfloops = Counter(), Counter(), Counter()
    for i, p in enumerate(edge_parts):
        for ch in pd.read_csv(
            p,
            header=0 if i == 0 else None,
            names=None if i == 0 else ["input_address", "output_address"],
            chunksize=300_000,
        ):
            a = ch.iloc[:, 0].astype(str)
            b = ch.iloc[:, 1].astype(str)
            outdeg.update(a)
            indeg.update(b)
            eq = a.eq(b)
            if eq.any():
                selfloops.update(a[eq])

    addr = obs["address"].astype(str).to_numpy()
    gin = np.array([indeg.get(a, 0) for a in addr], dtype=np.float32)
    gout = np.array([outdeg.get(a, 0) for a in addr], dtype=np.float32)
    gself = np.array([selfloops.get(a, 0) for a in addr], dtype=np.float32)
    gtotal = gin + gout
    gbalance = (gout - gin) / (gtotal + 1.0)
    G = np.column_stack(
        [np.log1p(gin), np.log1p(gout), np.log1p(gtotal), np.log1p(gself), gbalance]
    ).astype(np.float32)

    srcs, dsts = [], []
    for i, p in enumerate(edge_parts):
        for ch in pd.read_csv(
            p,
            header=0 if i == 0 else None,
            names=None if i == 0 else ["input_address", "output_address"],
            chunksize=300_000,
        ):
            a = ch.iloc[:, 0].astype(str).map(addr_to_wid)
            b = ch.iloc[:, 1].astype(str).map(addr_to_wid)
            m = a.notna() & b.notna()
            if m.any():
                srcs.append(a[m].to_numpy(np.int32))
                dsts.append(b[m].to_numpy(np.int32))

    src, dst = np.concatenate(srcs), np.concatenate(dsts)
    m = src != dst
    s, d = src[m], dst[m]
    out_ptr, out_nbr = csr_from_edges(s, d, nwallet)
    in_ptr, in_nbr = csr_from_edges(d, s, nwallet)
    degree = (out_ptr[1:] - out_ptr[:-1]) + (in_ptr[1:] - in_ptr[:-1])

    N = np.zeros((len(times), 22), dtype=np.float32)
    latest = np.full(nwallet, -1, dtype=np.int64)
    for t in range(1, 50):
        rows = np.flatnonzero(times == t)
        for r in rows:
            w = int(row_wid[r])
            ni = in_nbr[in_ptr[w]:in_ptr[w + 1]]
            if len(ni):
                lr = latest[ni]
                lr = lr[lr >= 0]
                if len(lr):
                    N[r, :K] = Xseq[lr, :K].mean(0)
                    N[r, 20] = np.log1p(len(lr))
            no = out_nbr[out_ptr[w]:out_ptr[w + 1]]
            if len(no):
                lr = latest[no]
                lr = lr[lr >= 0]
                if len(lr):
                    N[r, K:2 * K] = Xseq[lr, :K].mean(0)
                    N[r, 21] = np.log1p(len(lr))
        latest[row_wid[rows]] = rows

    Nh = np.zeros((len(times), 22), dtype=np.float32)
    latest = np.full(nwallet, -1, dtype=np.int64)
    for t in range(1, 50):
        rows = np.flatnonzero(times == t)
        for r in rows:
            w = int(row_wid[r])
            ni = in_nbr[in_ptr[w]:in_ptr[w + 1]]
            if len(ni):
                lr = latest[ni]
                ok = lr >= 0
                if ok.any():
                    uu, rr = ni[ok], lr[ok]
                    ww = 1.0 / np.sqrt(1.0 + degree[uu].astype(np.float32))
                    Nh[r, :K] = (Xseq[rr, :K] * ww[:, None]).mean(0)
                    Nh[r, 20] = np.log1p(len(rr))
            no = out_nbr[out_ptr[w]:out_ptr[w + 1]]
            if len(no):
                lr = latest[no]
                ok = lr >= 0
                if ok.any():
                    uu, rr = no[ok], lr[ok]
                    ww = 1.0 / np.sqrt(1.0 + degree[uu].astype(np.float32))
                    Nh[r, K:2 * K] = (Xseq[rr, :K] * ww[:, None]).mean(0)
                    Nh[r, 21] = np.log1p(len(rr))
        latest[row_wid[rows]] = rows

    train = times <= TRAIN_END

    gm, gs = G[train].mean(0), G[train].std(0)
    gs[gs < 1e-6] = 1
    Gz = np.clip((G - gm) / gs, -10, 10).astype(np.float32)

    nm, ns = N[train].mean(0), N[train].std(0)
    ns[ns < 1e-6] = 1
    Nz = np.clip((N - nm) / ns, -10, 10).astype(np.float32)

    hm, hs = Nh[train].mean(0), Nh[train].std(0)
    hs[hs < 1e-6] = 1
    Nhz = np.clip((Nh - hm) / hs, -10, 10).astype(np.float32)

    X_plain = np.concatenate([Xseq, Gz, Nz], axis=1).astype(np.float32)
    X_hub = np.concatenate([Xseq, Gz, Nhz], axis=1).astype(np.float32)

    np.savez_compressed(
        OUTPUT,
        X_plain=X_plain,
        X_hub=X_hub,
        times=times.astype(np.int16),
        y=y.astype(np.int8),
        prior=prior.astype(np.int16),
        starts=starts.astype(np.int64),
        ends=ends.astype(np.int64),
    )

    print(f"Saved: {OUTPUT}")
    print("X_plain:", X_plain.shape)
    print("X_hub:", X_hub.shape)
    print("Labeled non-self edges:", len(s))


if __name__ == "__main__":
    main()
