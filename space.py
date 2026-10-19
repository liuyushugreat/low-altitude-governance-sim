"""
补充实验：地面暴露与需求的"空间集中度"如何影响分类治理的相对收益。

设计要点
--------
分类治理（S3）与等量投入的单纯扩容（S2+）投入相同，差别在于是否按风险优先
配置审批与保障能力。若风险并非均匀分布于城市空间，则能力"投在哪里"应当重要。
本实验在**平均暴露量保持不变**的前提下，改变六个辖区的需求/暴露分布：

    d_k = D ** k  , 再线性缩放使 mean(d_k) = mean(D)

k = 0 为完全均匀分布，k = 1 为基准分布（与主实验一致），k 越大表示需求与地面
暴露越集中于少数空间单元。对每个 k，用同一随机种子配对运行 S2+ 与 S3，
报告事件率差值（扩容 − 分类）与单位治理成本差值。

注意：全部结果为虚拟仿真数据，仅用于机制比较，不代表任何城市的现实水平。
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from sim_core import D, REGIMES, Params, Regime, simulate

KS = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]
REPS = 50
OUT = "results"
os.makedirs(OUT, exist_ok=True)

# 与主实验一致：S2+ 为"扩容 + 等量投入"，S3 为"分类治理（同等投入）"
S2P = Regime("S2+ 扩容+等量投入", (0.02, 0.15, 0.60), 1.4, 0.12, 1.15, False, False, False)
S3 = REGIMES[3]


def exposure_profile(k: float) -> np.ndarray:
    """在保持平均暴露不变的前提下改变空间集中度。"""
    d = np.power(D, k)
    return d / d.mean() * D.mean()


def concentration(d: np.ndarray) -> float:
    """集中度指标：变异系数，用于横轴标注。"""
    return float(d.std() / d.mean())


def main() -> None:
    rows, diffs = [], []
    for k in KS:
        dk = exposure_profile(k)
        cv = concentration(dk)
        inc2, inc3, cost2, cost3 = [], [], [], []
        for rep in range(REPS):
            p = Params(seed=1000 + rep)
            r2 = simulate(S2P, p, d_override=dk)
            r3 = simulate(S3, p, d_override=dk)
            inc2.append(r2["inc_per_10k"])
            inc3.append(r3["inc_per_10k"])
            cost2.append(r2["cost_per_1k"])
            cost3.append(r3["cost_per_1k"])
            rows.append(dict(k=k, cv=cv, rep=rep,
                             inc_s2p=r2["inc_per_10k"], inc_s3=r3["inc_per_10k"],
                             cost_s2p=r2["cost_per_1k"], cost_s3=r3["cost_per_1k"],
                             comp_s2p=r2["completion"], comp_s3=r3["completion"]))
        inc2, inc3 = np.array(inc2), np.array(inc3)
        cost2, cost3 = np.array(cost2), np.array(cost3)
        d_inc = inc2 - inc3
        d_cost = cost2 - cost3
        diffs.append(dict(
            k=k, cv=cv,
            inc_s2p=inc2.mean(), inc_s3=inc3.mean(),
            d_inc=d_inc.mean(), d_inc_se=d_inc.std(ddof=1) / np.sqrt(REPS),
            inc_gain_pct=d_inc.mean() / inc2.mean() * 100,
            cost_s2p=cost2.mean(), cost_s3=cost3.mean(),
            d_cost=d_cost.mean(), d_cost_se=d_cost.std(ddof=1) / np.sqrt(REPS),
        ))
        print(f"k={k:<4} cv={cv:.2f}  扩容={inc2.mean():.3f}  分类={inc3.mean():.3f}  "
              f"差值={d_inc.mean():+.3f} ({d_inc.mean()/inc2.mean()*100:+.1f}%)  "
              f"成本差={d_cost.mean():+.1f}万元/千架次")

    pd.DataFrame(rows).to_csv(f"{OUT}/space_raw.csv", index=False)
    df = pd.DataFrame(diffs)
    df.to_csv(f"{OUT}/space.csv", index=False)
    json.dump(
        dict(ks=KS, reps=REPS,
             note="保持平均暴露不变，改变需求/暴露的空间集中度；差异为配对样本均值"),
        open(f"{OUT}/space_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved results/space.csv")


if __name__ == "__main__":
    main()
