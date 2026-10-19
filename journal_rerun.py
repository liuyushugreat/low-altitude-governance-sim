"""
《城市发展研究》投稿版的计算实验：延长模拟期以降低蒙特卡洛噪声。

原稿模拟期为 30 日，每次重复的期望事件数仅约 1.5 起，事件率估计对随机种子
敏感。本脚本将模拟期延长至 180 日，并在相同的任务流下对情景做配对比较
（同一 seed 对应同一组随机任务），输出：

  results/journal_scenarios.json   七种情景的均值、标准误与配对差值
  results/journal_space.csv        暴露空间集中度扫描结果
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from sim_core import CITIES, D, REGIMES, Params, Regime, simulate

OUT = "results"
os.makedirs(OUT, exist_ok=True)

DAYS = 180
REPS = 100

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

KEYS = ["inc_per_10k", "completion", "unauth_rate", "mean_delay",
        "duplicates_per_cross", "interrupt_rate", "cost_per_1k"]


def run(regime, reps=REPS, d_override=None):
    rows = []
    for s in range(reps):
        r = simulate(regime, Params(seed=1000 + s, days=DAYS), d_override=d_override)
        rows.append({k: r[k] for k in KEYS})
    return pd.DataFrame(rows)


def stat(x):
    x = np.asarray(x, float)
    m, se = x.mean(), x.std(ddof=1) / np.sqrt(len(x))
    return dict(mean=float(m), se=float(se), lo=float(m - 1.96 * se), hi=float(m + 1.96 * se))


def main():
    df_all, summary = {}, {}
    for code, name, rg in SCEN:
        df = run(rg)
        df_all[code] = df
        summary[code] = dict(name=name, n=len(df), **{k: stat(df[k]) for k in KEYS})
        print(f"{code:<4} 事件/万={summary[code]['inc_per_10k']['mean']:.3f} "
              f"完成={summary[code]['completion']['mean']*100:.1f}% "
              f"成本={summary[code]['cost_per_1k']['mean']:.1f}", flush=True)

    # 配对差值：S2+ 与 S3（投入相同，仅分配方式不同）
    for a, b in [("S2p", "S3"), ("S2", "S3"), ("S3", "S4"), ("S1", "S1p")]:
        d = df_all[a]["inc_per_10k"] - df_all[b]["inc_per_10k"]
        summary[f"diff_{a}_{b}"] = stat(d)
        dc = df_all[a]["cost_per_1k"] - df_all[b]["cost_per_1k"]
        summary[f"diffcost_{a}_{b}"] = stat(dc)
        print(f"diff {a}-{b}: 事件率 {d.mean():+.3f} (t={d.mean()/(d.std(ddof=1)/np.sqrt(len(d))):.1f})", flush=True)

    json.dump(summary, open(f"{OUT}/journal_scenarios.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # ---------- 暴露的空间集中度 ----------
    rows = []
    for k in [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]:
        dk = np.power(D, k)
        dk = dk / dk.mean() * D.mean()
        cv = float(dk.std() / dk.mean())
        a = run(S2P, d_override=dk)
        b = run(REGIMES[3], d_override=dk)
        d = a["inc_per_10k"] - b["inc_per_10k"]
        dc = a["cost_per_1k"] - b["cost_per_1k"]
        rows.append(dict(k=k, cv=cv,
                         inc_s2p=a["inc_per_10k"].mean(), inc_s3=b["inc_per_10k"].mean(),
                         d_inc=d.mean(), d_inc_se=d.std(ddof=1) / np.sqrt(REPS),
                         gain_pct=d.mean() / a["inc_per_10k"].mean() * 100,
                         cost_s2p=a["cost_per_1k"].mean(), cost_s3=b["cost_per_1k"].mean(),
                         d_cost=dc.mean(), d_cost_se=dc.std(ddof=1) / np.sqrt(REPS)))
        print(f"k={k:<4} cv={cv:.2f} 扩容={rows[-1]['inc_s2p']:.3f} 分类={rows[-1]['inc_s3']:.3f} "
              f"差={d.mean():+.3f} ({rows[-1]['gain_pct']:+.1f}%)", flush=True)
    pd.DataFrame(rows).to_csv(f"{OUT}/journal_space.csv", index=False)
    print("done")


if __name__ == "__main__":
    main()
