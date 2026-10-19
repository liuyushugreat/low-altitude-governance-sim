"""
解构实验：把"分类治理的优势"拆成可以分别检验的两部分。

背景
----
原文将 S3（分类治理）与 S2+（扩容+等量投入）比较，报告事件率低 26.7%。但两者
在模型里同时改变了多个因素：需申请概率、需求水平、排队优先序、以及是否启用
分层保护因子 φ(r)（高风险 1−0.45ε、中风险 1−0.20ε）。因此无法判断改进来自
"把能力配置到高风险任务"，还是来自"预设的保护折减"。

本脚本做两件事：

1. 2×2 因子对照：固定 S3 的全部其他参数，只切换 priority（是否按风险优先排队）
   与 matched（是否启用 φ），得到四个变体。于是
     排序收益 = (无φ, 有排序) − (无φ, 无排序)
     保护收益 = (有φ, 有排序) − (无φ, 有排序)
   两者之和即 S3 相对"同等配置但不排序不保护"的总改进。

2. 保护强度敏感性：令 φ_H = 1 − s·0.45、φ_M = 1 − s·0.20，令 s ∈ {0, 0.25,
   0.5, 0.75, 1.0}，观察 s=1 时的改进有多少比例依赖该设定。

3. 审批容量与等待容忍的敏感性：这两项是参数表里"无公开数据、取设定值"的部分。

输出
----
results/ablation_factorial.csv     2×2 四变体的均值与配对差值
results/ablation_protection.csv    保护强度扫描
results/ablation_capacity.csv      审批容量倍数扫描
results/ablation_tau.csv           等待容忍扫描
results/ablation_summary.json      汇总（供论文引用）

全部为虚拟仿真数据，仅用于机制比较。
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

import sim_core
from sim_core import REGIMES, Params, Regime, simulate

OUT = "results"
os.makedirs(OUT, exist_ok=True)

DAYS = 180
REPS = 100

# S3 的参数基线（与主实验一致）
S3 = REGIMES[3]
S2P = Regime("S2+ 扩容+等量投入", (0.02, 0.15, 0.60), 1.4, 0.12, 1.15,
             False, False, False)

KEYS = ["inc_per_10k", "completion", "unauth_rate", "mean_delay",
        "duplicates_per_cross", "interrupt_rate", "cost_per_1k"]


def variant(name: str, priority: bool, matched: bool) -> Regime:
    """S3 的同一资源水平，只切换分配规则的两个开关。"""
    return Regime(name, S3.req, S3.mu_mult, S3.c_add, S3.demand,
                  S3.coord, priority, matched)


def run(regime: Regime, reps: int, seed0: int = 2000):
    """同一批随机种子下重复运行，返回逐次结果矩阵与汇总。"""
    rows = {k: [] for k in KEYS}
    for r in range(reps):
        p = Params(days=DAYS, seed=seed0 + r)
        out = simulate(regime, p)
        for k in KEYS:
            rows[k].append(out[k])
    arr = {k: np.asarray(v, dtype=float) for k, v in rows.items()}
    summ = {k: dict(mean=float(v.mean()),
                    se=float(v.std(ddof=1) / np.sqrt(reps)))
            for k, v in arr.items()}
    return arr, summ


def paired(a, b, key: str):
    """a − b 的配对差值与 95% 置信区间。"""
    d = a[key] - b[key]
    m = float(d.mean())
    se = float(d.std(ddof=1) / np.sqrt(len(d)))
    return dict(diff=m, se=se, lo=m - 1.96 * se, hi=m + 1.96 * se,
                rel_pct=m / float(b[key].mean()) * 100)


def main() -> None:
    print("=== 1. 2×2 因子对照 (priority × matched) ===")
    cells = {
        "P0M0 不排序不保护": variant("P0M0", False, False),
        "P1M0 仅排序": variant("P1M0", True, False),
        "P0M1 仅保护": variant("P0M1", False, True),
        "P1M1 排序+保护(=S3)": variant("P1M1", True, True),
    }
    arrs, sums = {}, {}
    for name, rg in cells.items():
        arrs[name], sums[name] = run(rg, REPS)
        s = sums[name]
        print(f"  {name:<22} 事件率={s['inc_per_10k']['mean']:.3f} "
              f"(±{1.96*s['inc_per_10k']['se']:.3f})  "
              f"完成率={s['completion']['mean']*100:.1f}%  "
              f"成本={s['cost_per_1k']['mean']:.1f}")

    base = arrs["P0M0 不排序不保护"]
    sort_eff = paired(arrs["P1M0 仅排序"], base, "inc_per_10k")
    prot_eff = paired(arrs["P1M1 排序+保护(=S3)"], arrs["P1M0 仅排序"], "inc_per_10k")
    total_eff = paired(arrs["P1M1 排序+保护(=S3)"], base, "inc_per_10k")
    print(f"\n  排序收益 (P1M0−P0M0) : {sort_eff['diff']:+.3f} 起/万架次 "
          f"[{sort_eff['lo']:+.3f},{sort_eff['hi']:+.3f}]  相对 {sort_eff['rel_pct']:+.1f}%")
    print(f"  保护收益 (P1M1−P1M0) : {prot_eff['diff']:+.3f} 起/万架次 "
          f"[{prot_eff['lo']:+.3f},{prot_eff['hi']:+.3f}]  相对 {prot_eff['rel_pct']:+.1f}%")
    print(f"  合计     (P1M1−P0M0) : {total_eff['diff']:+.3f} 起/万架次 "
          f"[{total_eff['lo']:+.3f},{total_eff['hi']:+.3f}]  相对 {total_eff['rel_pct']:+.1f}%")
    share = prot_eff["diff"] / total_eff["diff"] * 100 if total_eff["diff"] else float("nan")
    print(f"  保护系数贡献占比     : {share:.1f}%")

    pd.DataFrame([
        dict(cell=k, **{f"{m}_{s}": v for m, v in sums[k].items()})
        for k in sums
    ]).to_csv(f"{OUT}/ablation_factorial.csv", index=False)

    print("\n=== 2. 保护强度敏感性 ===")
    prot_rows = []
    orig_h, orig_m = sim_core.PROT_HIGH, sim_core.PROT_MID
    for s in (0.0, 0.25, 0.5, 0.75, 1.0):
        sim_core.PROT_HIGH, sim_core.PROT_MID = orig_h * s, orig_m * s
        a, sm = run(cells["P1M1 排序+保护(=S3)"], REPS)
        d = paired(a, base, "inc_per_10k")
        prot_rows.append(dict(s=s, inc=sm["inc_per_10k"]["mean"],
                              diff_vs_P0M0=d["diff"], lo=d["lo"], hi=d["hi"],
                              rel_pct=d["rel_pct"]))
        print(f"  s={s:<5} 事件率={sm['inc_per_10k']['mean']:.3f}  "
              f"相对 P0M0 改进={d['rel_pct']:+.1f}%  [{d['lo']:+.1f},{d['hi']:+.1f}]")
    sim_core.PROT_HIGH, sim_core.PROT_MID = orig_h, orig_m
    pd.DataFrame(prot_rows).to_csv(f"{OUT}/ablation_protection.csv", index=False)

    print("\n=== 3. 审批容量敏感性 (S3 vs S2+) ===")
    cap_rows = []
    for mult in (1.0, 1.2, 1.4, 1.6, 1.8):
        s3 = Regime("S3", S3.req, mult, S3.c_add, S3.demand, False, True, True)
        s2 = Regime("S2+", S2P.req, mult, S2P.c_add, S2P.demand, False, False, False)
        a3, m3 = run(s3, 50)
        a2, m2 = run(s2, 50)
        d = paired(a3, a2, "inc_per_10k")
        cap_rows.append(dict(mu_mult=mult,
                             s3=m3["inc_per_10k"]["mean"], s2p=m2["inc_per_10k"]["mean"],
                             diff=d["diff"], lo=d["lo"], hi=d["hi"],
                             rel_pct=d["rel_pct"],
                             s3_unauth=m3["unauth_rate"]["mean"],
                             s2p_unauth=m2["unauth_rate"]["mean"]))
        print(f"  μ×{mult:<4} S3={m3['inc_per_10k']['mean']:.3f}  "
              f"S2+={m2['inc_per_10k']['mean']:.3f}  差={d['diff']:+.3f} "
              f"[{d['lo']:+.3f},{d['hi']:+.3f}]  相对 {d['rel_pct']:+.1f}%")
    pd.DataFrame(cap_rows).to_csv(f"{OUT}/ablation_capacity.csv", index=False)

    print("\n=== 4. 等待容忍敏感性 (S3 vs S2+) ===")
    tau_rows = []
    for tau in (6.0, 9.0, 12.0, 18.0, 24.0):
        def run_tau(rg, reps=50):
            rows = {k: [] for k in KEYS}
            for r in range(reps):
                p = Params(days=DAYS, seed=2000 + r, tau_hours=tau)
                o = simulate(rg, p)
                for k in KEYS:
                    rows[k].append(o[k])
            arr = {k: np.asarray(v, dtype=float) for k, v in rows.items()}
            return arr, {k: float(v.mean()) for k, v in arr.items()}
        a3, m3 = run_tau(Regime("S3", S3.req, S3.mu_mult, S3.c_add, S3.demand, False, True, True))
        a2, m2 = run_tau(Regime("S2+", S2P.req, S2P.mu_mult, S2P.c_add, S2P.demand, False, False, False))
        d = paired(a3, a2, "inc_per_10k")
        tau_rows.append(dict(tau_h=tau, s3=m3["inc_per_10k"], s2p=m2["inc_per_10k"],
                             diff=d["diff"], lo=d["lo"], hi=d["hi"], rel_pct=d["rel_pct"]))
        print(f"  τ={tau:<5}h S3={m3['inc_per_10k']:.3f}  S2+={m2['inc_per_10k']:.3f}  "
              f"相对改进={d['rel_pct']:+.1f}%  [{d['lo']:+.1f},{d['hi']:+.1f}]")
    pd.DataFrame(tau_rows).to_csv(f"{OUT}/ablation_tau.csv", index=False)

    json.dump(dict(
        days=DAYS, reps_factorial=REPS, reps_sweep=50,
        cells={k: v for k, v in sums.items()},
        sort_effect=sort_eff, protection_effect=prot_eff,
        total_effect=total_eff,
        protection_share_pct=share,
        protection_sweep=prot_rows,
        capacity_sweep=cap_rows,
        tau_sweep=tau_rows,
        note="2×2 对照固定 S3 的资源水平（mu_mult=1.4, c_add=0.12, demand=1.05, "
             "req 同 S3），只切换 priority 与 matched；差值为同种子配对差值。",
    ), open(f"{OUT}/ablation_summary.json", "w", encoding="utf-8"),
        ensure_ascii=False, indent=2, default=float)
    print("\nsaved results/ablation_*.csv|csv|csv|csv|json")


if __name__ == "__main__":
    main()


def sorting_benefit_vs_load() -> None:
    """排序收益是否只在审批队列真正溢出时才出现？

    2×2 对照显示，在 S3 的基准参数下违规率为 0（审批容量充裕、队列从不溢出），
    因此"按风险优先排队"对事件率没有任何影响。这里把审批容量从上到下收紧，
    使队列开始溢出，再重复 P1M0 − P0M0 的比较，观察排序收益是否随负载出现。
    """
    print("\n=== 5. 排序收益随审批容量收紧的变化 (P1M0 − P0M0) ===")
    rows = []
    for mult in (1.4, 1.0, 0.7, 0.5, 0.35, 0.25):
        s3_hi = Regime("P1M0", S3.req, mult, S3.c_add, S3.demand, False, True, False)
        s3_lo = Regime("P0M0", S3.req, mult, S3.c_add, S3.demand, False, False, False)
        a_hi, m_hi = run(s3_hi, 60)
        a_lo, m_lo = run(s3_lo, 60)
        d = paired(a_hi, a_lo, "inc_per_10k")
        rows.append(dict(mu_mult=mult,
                         sort_inc=m_hi["inc_per_10k"]["mean"],
                         nosort_inc=m_lo["inc_per_10k"]["mean"],
                         diff=d["diff"], lo=d["lo"], hi=d["hi"],
                         rel_pct=d["rel_pct"],
                         sort_unauth=m_hi["unauth_rate"]["mean"],
                         nosort_unauth=m_lo["unauth_rate"]["mean"]))
        print(f"  μ×{mult:<5} 有排序={m_hi['inc_per_10k']['mean']:.3f}  "
              f"无排序={m_lo['inc_per_10k']['mean']:.3f}  "
              f"排序收益={d['diff']:+.4f} [{d['lo']:+.4f},{d['hi']:+.4f}]  "
              f"相对={d['rel_pct']:+.1f}%  违规率 有/无="
              f"{m_hi['unauth_rate']['mean']:.3f}/{m_lo['unauth_rate']['mean']:.3f}")
    pd.DataFrame(rows).to_csv(f"{OUT}/ablation_sorting_load.csv", index=False)
    with open(f"{OUT}/ablation_sorting_load.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=float)
    print("  saved results/ablation_sorting_load.csv")


if __name__ == "__main__":
    sorting_benefit_vs_load()
