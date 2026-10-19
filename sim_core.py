"""
城市低空安全分类治理的计算实验模型（core simulation）

两个子模型：
  A. 治理情景模型（agent-based, 任务级）：检验命题1、命题2
  B. 风险校准模型（Bayesian learning）：检验命题3

说明：参数取自公开统计与文献区间的设定值，结果用于机制比较，
不构成对现实效果的预测。
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass

CITIES = ["首都核心", "枢纽群", "市场化", "山地", "边海", "低密度"]

S = np.array([0.95, 0.75, 0.55, 0.60, 0.70, 0.30])   # 安全约束强度
D = np.array([0.35, 0.95, 1.00, 0.60, 0.45, 0.20])   # 需求密度
C = np.array([0.70, 0.65, 0.75, 0.45, 0.50, 0.30])   # 治理能力（感知+处置）
MU = np.array([120.0, 400.0, 450.0, 250.0, 200.0, 80.0])  # 日审批容量
W = D / D.sum()

# 分层保护因子的折减上限（模块级常量，便于敏感性分析；见 journal_ablation.py）
PROT_HIGH = 0.45   # 高风险任务的最大折减
PROT_MID = 0.20    # 中风险任务的最大折减

RISK_SHARE = np.array([0.60, 0.30, 0.10])
RISK_MULT = np.array([1.0, 3.0, 10.0])


@dataclass
class Params:
    days: int = 30
    n_per_day: int = 1500
    p0: float = 3e-5
    cross_share: float = 0.18
    tau_hours: float = 12.0
    abandon_unauth: float = 0.60
    interrupt_base: float = 0.18
    det_base: float = 0.55
    incident_cost: float = 30.0
    casualty_prob: float = 0.10
    casualty_cost: float = 300.0
    admin_cost: float = 0.02
    delay_cost: float = 0.003
    penalty: float = 0.5
    interrupt_cost: float = 0.15
    seed: int = 0


@dataclass
class Regime:
    name: str
    req: tuple = (0.10, 0.60, 1.00)
    mu_mult: float = 1.0
    c_add: float = 0.0
    demand: float = 1.0
    coord: bool = False
    priority: bool = False
    matched: bool = False


REGIMES = [
    Regime("S0 基准（混合）", (0.10, 0.60, 1.00), 1.0, 0.00, 1.00, False, False, False),
    Regime("S1 全域从严", (1.00, 1.00, 1.00), 0.9, 0.05, 0.75, False, False, False),
    Regime("S2 单纯扩容", (0.02, 0.15, 0.60), 1.2, 0.00, 1.15, False, False, False),
    Regime("S3 分类治理", (0.05, 0.40, 1.00), 1.4, 0.12, 1.05, False, True, True),
    Regime("S4 分类+协同", (0.05, 0.40, 1.00), 1.4, 0.12, 1.05, True, True, True),
]


def simulate(regime: Regime, p: Params, c_override=None, mu_override=None, d_override=None):
    rng = np.random.default_rng(p.seed)
    c_vec = np.clip(C + regime.c_add, 0, 1) if c_override is None else np.clip(np.asarray(c_override), 0, 1)
    mu_vec = MU * regime.mu_mult if mu_override is None else np.asarray(mu_override, float)
    # 需求与地面暴露的空间分布；d_override 用于改变暴露的空间集中度（见 space.py）
    d_vec = D if d_override is None else np.asarray(d_override, dtype=float)
    w_vec = d_vec / d_vec.sum()
    req = np.array(regime.req)

    tot = dict(attempted=0, flights=0, incidents=0.0, casualties=0.0, applications=0,
               duplicates=0, served=0, unauth=0, cancel=0, detected=0,
               interrupted=0, cross=0, delays=[], completed=0, cost=0.0)
    daily = []

    for day in range(p.days):
        n = rng.poisson(p.n_per_day * regime.demand)
        city = rng.choice(len(CITIES), size=n, p=w_vec)
        risk = rng.choice(3, size=n, p=RISK_SHARE)
        cross = rng.random(n) < p.cross_share
        dest = np.where(cross, (city + rng.integers(1, len(CITIES), size=n)) % len(CITIES), city)

        need = rng.random(n) < req[risk]
        dup = cross & need & (not regime.coord)

        app_need = np.zeros(n, dtype=int)
        app_served = np.zeros(n, dtype=int)
        app_lost = np.zeros(n, dtype=int)
        lost_unauth = np.zeros(n, dtype=bool)
        waits = np.zeros(n)

        city_apps = [[] for _ in CITIES]
        for i in np.where(need)[0]:
            city_apps[city[i]].append((risk[i], i))
            app_need[i] += 1
            if dup[i]:
                city_apps[dest[i]].append((risk[i], i))
                app_need[i] += 1

        for ci in range(len(CITIES)):
            queue = city_apps[ci]
            if not queue:
                continue
            arr = np.array([q[0] for q in queue]); ids = np.array([q[1] for q in queue])
            order = np.argsort(-arr, kind="stable") if regime.priority else np.arange(len(arr))
            arr, ids = arr[order], ids[order]
            cap = max(int(mu_vec[ci]), 1)
            w_h = np.arange(len(arr)) / cap * 24.0
            ok = w_h <= p.tau_hours
            if ok.any():
                np.add.at(app_served, ids[ok], 1)
                np.maximum.at(waits, ids[ok], w_h[ok])
            if (~ok).any():
                lost_ids = ids[~ok]
                np.add.at(app_lost, lost_ids, 1)
                flag = rng.random(len(lost_ids)) < p.abandon_unauth
                lost_unauth[lost_ids[flag]] = True

        status = np.zeros(n, dtype=int)
        status[(app_need > 0) & (app_served == app_need) & (app_lost == 0)] = 1
        status[(app_lost > 0) & lost_unauth] = 2
        status[(app_lost > 0) & (~lost_unauth)] = 3

        flying = (status == 0) | (status == 1) | (status == 2)
        unauth = status == 2
        interrupted = flying & cross & (rng.random(n) < (0.05 if regime.coord else p.interrupt_base))

        cap_air = 250 + 900 * d_vec
        load = np.zeros(n)
        for ci in range(len(CITIES)):
            m = city == ci
            if m.any():
                load[m] = m.sum() / max(cap_air[ci], 1)

        p_inc = (p.p0 * RISK_MULT[risk] * (0.6 + 0.8 * d_vec[city])
                 * (1 - 0.6 * c_vec[city]) * (1 + 3.0 * unauth)
                 * (1 + 0.7 * np.maximum(0, load - 0.8)))
        if regime.matched:
            eff = np.clip(c_vec[city] / 0.75, 0, 1.2)
            prot = np.where(risk == 2, 1 - PROT_HIGH * eff,
                            np.where(risk == 1, 1 - PROT_MID * eff, 1.0))
            p_inc = p_inc * prot
        hit = (rng.random(n) < p_inc) & flying & (~interrupted)
        detected = unauth & (rng.random(n) < p.det_base * c_vec[city])
        hit = hit & (~detected)
        cas = hit & (rng.random(n) < p.casualty_prob)

        tot["attempted"] += n
        tot["flights"] += int(flying.sum())
        tot["completed"] += int((flying & (~interrupted)).sum())
        tot["incidents"] += float(hit.sum())
        tot["casualties"] += float(cas.sum())
        tot["applications"] += int(app_need.sum())
        tot["duplicates"] += int(dup.sum())
        tot["served"] += int((status == 1).sum())
        tot["unauth"] += int((status == 2).sum())
        tot["cancel"] += int((status == 3).sum())
        tot["detected"] += int(detected.sum())
        tot["interrupted"] += int(interrupted.sum())
        tot["cross"] += int(cross.sum())
        tot["delays"].extend(waits[status == 1].tolist())

        sev = np.array([20.0, 50.0, 120.0])[risk]
        cost = ((sev[hit].sum() if hit.any() else 0.0) + cas.sum() * p.casualty_cost
                + app_need.sum() * p.admin_cost + waits[status == 1].sum() * p.delay_cost
                + detected.sum() * p.penalty + interrupted.sum() * p.interrupt_cost)
        tot["cost"] += float(cost)
        daily.append((day, int(flying.sum()), float(hit.sum()), int(app_need.sum())))

    n_fl = max(tot["flights"], 1)
    w = np.array(tot["delays"]) if tot["delays"] else np.array([0.0])
    return {
        "regime": regime.name,
        "flights": tot["flights"],
        "inc_per_10k": tot["incidents"] / n_fl * 1e4,
        "cas_per_10k": tot["casualties"] / n_fl * 1e4,
        "completion": tot["completed"] / max(tot["attempted"], 1),
        "unauth_rate": tot["unauth"] / max(tot["attempted"], 1),
        "cancel_rate": tot["cancel"] / max(tot["attempted"], 1),
        "detect_rate": tot["detected"] / n_fl,
        "duplicates_per_cross": tot["duplicates"] / max(tot["cross"], 1),
        "interrupt_rate": tot["interrupted"] / max(tot["cross"], 1),
        "mean_delay": float(w.mean()),
        "p95_delay": float(np.percentile(w, 95)),
        "cost_per_1k": tot["cost"] / max(tot["attempted"], 1) * 1000,
        "applications": tot["applications"],
        "daily": daily,
    }


# ======================= 模型B：风险校准 =======================
def calibrate(days=180, coverage=0.0, update=True, reset_every=0, update_every=1, reps=400, seed=1,
              base=0.01, strength=15.0, prior_mult=np.array([0.55, 1.7, 6.0])):
    rng = np.random.default_rng(seed)
    n_cls = np.array([1200, 600, 180])
    errs = np.zeros((reps, days))
    excess = np.zeros(reps)
    for r in range(reps):
        a = prior_mult * strength
        b = np.full(3, strength)
        acc_a = np.zeros(3); acc_b = np.zeros(3)
        for d in range(days):
            lam = base * RISK_MULT * n_cls
            y = rng.poisson(lam)
            obs = rng.binomial(y, coverage) if coverage > 0 else np.zeros(3)
            if update:
                acc_a += obs
                acc_b += n_cls * base * max(coverage, 1e-9)
                if (d + 1) % update_every == 0:
                    a = a + acc_a
                    b = b + acc_b
                    acc_a = np.zeros(3); acc_b = np.zeros(3)
            est = a / b
            errs[r, d] = np.mean(np.abs(est - RISK_MULT) / RISK_MULT)
            under = np.maximum(0, RISK_MULT - est) / RISK_MULT
            excess[r] += float(np.sum(lam * under * 0.5))
    return dict(err=errs.mean(axis=0), err_p90=np.percentile(errs, 90, axis=0),
                err30=errs[:, 29].mean(), err90=errs[:, 89].mean(), err180=errs[:, -1].mean(),
                excess_expect=excess.mean())


if __name__ == "__main__":
    for rg in REGIMES:
        r = simulate(rg, Params(seed=42))
        print(f"{r['regime']:<12} 事件/万={r['inc_per_10k']:.2f} 完成率={r['completion']:.3f} "
              f"违规={r['unauth_rate']:.3f} 时延={r['mean_delay']:.1f}h "
              f"重复={r['duplicates_per_cross']:.2f} 中断={r['interrupt_rate']:.2f}")


