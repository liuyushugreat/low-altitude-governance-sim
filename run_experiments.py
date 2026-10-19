"""运行全部计算实验，输出 CSV 与汇总 JSON。"""
import json, os
from dataclasses import replace

import numpy as np
import pandas as pd

from sim_core import Regime, Params, simulate, calibrate, REGIMES, MU

OUT = "results"
os.makedirs(OUT, exist_ok=True)

S1P = Regime("S1+ 从严+能力同步", (1.00, 1.00, 1.00), 1.5, 0.12, 0.75, False, False, False)
S2P = Regime("S2+ 扩容+等量投入", (0.02, 0.15, 0.60), 1.4, 0.12, 1.15, False, False, False)

SCEN = [
    ("S0", "基准（混合）", REGIMES[0]),
    ("S1", "全域从严（能力不变）", REGIMES[1]),
    ("S1p", "从严+能力同步", S1P),
    ("S2", "单纯扩容（能力不变）", REGIMES[2]),
    ("S2p", "扩容+等量投入", S2P),
    ("S3", "分类治理（同等投入）", REGIMES[3]),
    ("S4", "分类+协同", REGIMES[4]),
]


def mc(regime, reps=200, seed0=1000):
    return pd.DataFrame([{k: v for k, v in simulate(regime, Params(seed=seed0 + s)).items()
                          if k != "daily"} for s in range(reps)])


def summarize(df):
    cols = ["inc_per_10k", "cas_per_10k", "completion", "unauth_rate", "cancel_rate",
            "mean_delay", "p95_delay", "duplicates_per_cross", "interrupt_rate",
            "cost_per_1k", "detect_rate"]
    out = {}
    for c in cols:
        m, sd, n = df[c].mean(), df[c].std(ddof=1), len(df)
        se = sd / np.sqrt(n)
        out[c] = dict(mean=float(m), sd=float(sd), se=float(se),
                      lo=float(m - 1.96 * se), hi=float(m + 1.96 * se))
    return out


def main():
    summary, all_rows = {}, []
    for code, name, rg in SCEN:
        df = mc(rg, 200)
        df["code"] = code
        all_rows.append(df)
        summary[code] = dict(name=name, n=len(df), **summarize(df))
        print(code, name, "done", flush=True)

    pd.concat(all_rows, ignore_index=True).to_csv(f"{OUT}/scenarios_raw.csv", index=False)
    json.dump(summary, open(f"{OUT}/scenarios_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # ---------- 能力 × 审批容量 网格（等量投入下，S2+ 与 S3 仅差分配方式） ----------
    grid = []
    for cm in [0.40, 0.55, 0.70, 0.85]:
        for mm in [0.6, 0.8, 1.0, 1.2]:
            c_over = np.full(6, cm); mu_over = MU * mm
            for code, rg in [("S2p", S2P), ("S3", REGIMES[3])]:
                vals = [simulate(rg, Params(seed=5000 + s), c_override=c_over, mu_override=mu_over)
                        for s in range(40)]
                d = pd.DataFrame(vals)
                grid.append(dict(c=cm, mu=mm, regime=code,
                                 inc=d.inc_per_10k.mean(),
                                 completion=d.completion.mean(),
                                 unauth=d.unauth_rate.mean(),
                                 cost=d.cost_per_1k.mean()))
    pd.DataFrame(grid).to_csv(f"{OUT}/grid.csv", index=False)
    print("grid done", flush=True)

    # ---------- 敏感性 ----------
    sens = []

    def sweep(code, rg, param, values, reps=40):
        for v in values:
            if param == "demand":
                rg2, pkw = replace(rg, demand=v), {}
            else:
                rg2, pkw = rg, {param: v}
            vals = [simulate(rg2, Params(seed=7000 + s, **pkw)) for s in range(reps)]
            d = pd.DataFrame(vals)
            sens.append(dict(regime=code, param=param, value=v,
                             inc=d.inc_per_10k.mean(), completion=d.completion.mean(),
                             unauth=d.unauth_rate.mean(), cost=d.cost_per_1k.mean()))

    sweep("S1", REGIMES[1], "abandon_unauth", [0.40, 0.60, 0.80], reps=80)
    sweep("S1", REGIMES[1], "tau_hours", [6.0, 12.0, 24.0], reps=80)
    sweep("S3", REGIMES[3], "tau_hours", [6.0, 12.0, 24.0], reps=80)
    sweep("S3", REGIMES[3], "cross_share", [0.05, 0.18, 0.35], reps=80)
    sweep("S4", REGIMES[4], "cross_share", [0.05, 0.18, 0.35], reps=80)
    sweep("S2", REGIMES[2], "demand", [1.05, 1.15, 1.30], reps=80)

    pd.DataFrame(sens).to_csv(f"{OUT}/sensitivity.csv", index=False)
    print("sensitivity done", flush=True)

    # ---------- 风险校准 ----------
    learn, rows = {}, []
    for code, kw in [
        ("L0 无监测", dict(coverage=0.0, update=False)),
        ("L1 仅监测无反馈", dict(coverage=0.5, update=False)),
        ("L2 监测+报告（周反馈）", dict(coverage=0.6, update=True, update_every=7)),
        ("L3 监测+报告+纠错（日反馈）", dict(coverage=0.85, update=True, update_every=1)),
    ]:
        r = calibrate(reps=300, seed=99, **kw)
        learn[code] = dict(err30=float(r["err30"]), err90=float(r["err90"]),
                           err180=float(r["err180"]), excess=float(r["excess_expect"]))
        for d, e in enumerate(r["err"]):
            rows.append(dict(regime=code, day=d + 1, err=e))
    pd.DataFrame(rows).to_csv(f"{OUT}/learning_series.csv", index=False)
    json.dump(learn, open(f"{OUT}/learning_summary.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("learning done", flush=True)


if __name__ == "__main__":
    main()
