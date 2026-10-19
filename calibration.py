"""参数校准接口：用四类观测量反推四个模型参数，并做回测。

观测量（试点可采集）：
  W  平均审批时延（小时）        -> mu_mult   审批容量倍数
  u  违规率（超时强飞占比）       -> beta      超时后强行飞行比例
  l  每万架次事件率              -> p0        基准事件率
  i  跨区交接中断率              -> q         交接中断概率

方法：固定其余参数，对单个参数做二分搜索，使模拟均值逼近观测值；
两轮迭代以减弱参数间交互。回测用一组留出的“真实参数”生成观测值，
再由校准程序反推，检查能否复原。
"""
import json
import numpy as np
from sim_core import Regime, Params, simulate, MU, REGIMES

BASE = REGIMES[0]


def _metrics(mu_mult, beta, p0, q, reps=12, seed0=9000):
    rows = [simulate(BASE, Params(seed=seed0 + s, abandon_unauth=beta, p0=p0,
                                  interrupt_base=q), mu_override=MU * mu_mult)
            for s in range(reps)]
    return dict(
        delay=float(np.mean([r["mean_delay"] for r in rows])),
        unauth=float(np.mean([r["unauth_rate"] for r in rows])),
        inc=float(np.mean([r["inc_per_10k"] for r in rows])),
        intr=float(np.mean([r["interrupt_rate"] for r in rows])),
    )


def _bisect(f, lo, hi, target, increasing, iters=7):
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        v = f(mid)
        if (v < target) == increasing:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi), v


def calibrate(target, init=None, rounds=2, reps=12):
    mu = init["mu_mult"] if init else 1.0
    beta = init["beta"] if init else 0.6
    p0 = init["p0"] if init else 3e-5
    q = init["q"] if init else 0.18
    hist = []

    for _ in range(rounds):
        mu, _ = _bisect(lambda x: _metrics(x, beta, p0, q, reps)["delay"],
                        0.25, 3.0, target["delay"], increasing=False)
        beta, _ = _bisect(lambda x: _metrics(mu, x, p0, q, reps)["unauth"],
                          0.05, 0.95, target["unauth"], increasing=True)
        p0, _ = _bisect(lambda x: _metrics(mu, beta, x, q, reps)["inc"],
                        2e-6, 2e-4, target["inc"], increasing=True)
        q, _ = _bisect(lambda x: _metrics(mu, beta, p0, x, reps)["intr"],
                       0.01, 0.40, target["intr"], increasing=True)
        hist.append(_metrics(mu, beta, p0, q, reps))

    return dict(mu_mult=mu, beta=beta, p0=p0, q=q), hist[-1]


def main():
    # 留出的“真实参数”，用于生成模拟观测值（视为试点观测）
    true = dict(mu_mult=0.90, beta=0.55, p0=4.0e-5, q=0.12)
    obs = _metrics(true["mu_mult"], true["beta"], true["p0"], true["q"], reps=80)
    print("观测值:", {k: round(v, 4) for k, v in obs.items()})

    est, fit = calibrate(obs)
    print("校准值:", {k: round(v, 5) for k, v in est.items()})
    err = {
        "mu": abs(est["mu_mult"] - true["mu_mult"]) / true["mu_mult"],
        "beta": abs(est["beta"] - true["beta"]) / true["beta"],
        "p0": abs(est["p0"] - true["p0"]) / true["p0"],
        "q": abs(est["q"] - true["q"]) / true["q"],
    }
    print("相对误差:", {k: f"{v*100:.1f}%" for k, v in err.items()})
    print("拟合值:", {k: round(v, 4) for k, v in fit.items()})

    out = dict(true=true, observed=obs, estimated=est, error=err, fitted=fit)
    json.dump(out, open("results/calibration.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
