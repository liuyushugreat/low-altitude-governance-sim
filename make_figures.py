"""根据计算结果生成论文插图（中文标签）。"""
import json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams["font.sans-serif"] = ["Arial Unicode MS", "Hiragino Sans GB", "STHeiti"]
rcParams["axes.unicode_minus"] = False
rcParams["font.size"] = 10.5
rcParams["axes.linewidth"] = 0.8
rcParams["figure.dpi"] = 300
rcParams["savefig.dpi"] = 300
rcParams["savefig.bbox"] = "tight"

OUT = "figures"
os.makedirs(OUT, exist_ok=True)
R = "results"

LABEL = {"S0": "S0 基准", "S1": "S1 全域从严", "S1p": "S1+ 从严+能力",
         "S2": "S2 单纯扩容", "S2p": "S2+ 扩容+投入", "S3": "S3 分类治理",
         "S4": "S4 分类+协同"}
COLOR = {"S0": "#8c8c8c", "S1": "#c0392b", "S1p": "#e08a7f",
         "S2": "#2e86c1", "S2p": "#7fb3d5", "S3": "#1e8449", "S4": "#145a32"}


def fig_scenarios():
    s = json.load(open(f"{R}/scenarios_summary.json", encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    off = {"S0": (8, 4), "S1": (8, 4), "S1p": (8, -14), "S2": (8, 4),
           "S2p": (8, -14), "S3": (-24, 9), "S4": (8, -4)}
    for code, v in s.items():
        x = v["completion"]["mean"] * 100
        y = v["inc_per_10k"]["mean"]
        xe = v["completion"]["se"] * 100
        ye = v["inc_per_10k"]["se"]
        ax.errorbar(x, y, xerr=xe, yerr=ye, fmt="o", ms=7, capsize=3,
                    color=COLOR.get(code, "k"), label=LABEL.get(code, code))
        ax.annotate(code, (x, y), textcoords="offset points",
                    xytext=off.get(code, (7, 5)), fontsize=9.5, color=COLOR.get(code, "k"))
    ax.set_xlabel("任务完成率（%）")
    ax.set_ylabel("每万架次事件数")
    ax.set_xlim(77, 101)
    ax.grid(alpha=.25, ls="--")
    ax.legend(loc="upper center", ncol=4, fontsize=8.5, frameon=False,
              bbox_to_anchor=(0.5, -0.26))
    fig.savefig(f"{OUT}/fig3_scenarios.png")
    plt.close(fig)


def fig_grid():
    g = pd.read_csv(f"{R}/grid.csv")
    p2 = g[g.regime == "S2p"].pivot(index="c", columns="mu", values="inc")
    p3 = g[g.regime == "S3"].pivot(index="c", columns="mu", values="inc")
    diff = p2 - p3           # >0 表示分类治理事件更少
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    im = ax.imshow(diff.values, cmap="RdYlGn", origin="lower", aspect="auto")
    ax.set_xticks(range(len(diff.columns)))
    ax.set_xticklabels([f"{v:.1f}×" for v in diff.columns])
    ax.set_yticks(range(len(diff.index)))
    ax.set_yticklabels([f"{v:.2f}" for v in diff.index])
    ax.set_xlabel("审批容量（相对基准）")
    ax.set_ylabel("治理能力 c")
    for i in range(diff.shape[0]):
        for j in range(diff.shape[1]):
            ax.text(j, i, f"{diff.values[i, j]:+.2f}", ha="center", va="center", fontsize=9)
    cb = fig.colorbar(im, ax=ax, shrink=.85)
    cb.set_label("事件率差值（扩容－分类）")
    fig.savefig(f"{OUT}/fig4_grid.png")
    plt.close(fig)


def fig_learning():
    d = pd.read_csv(f"{R}/learning_series.csv")
    styles = {"L0 无监测": ("-", "#c0392b"), "L1 仅监测无反馈": ("--", "#e67e22"),
              "L2 监测+报告（周反馈）": ("-.", "#2e86c1"),
              "L3 监测+报告+纠错（日反馈）": ("-", "#1e8449")}
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    for name, g in d.groupby("regime"):
        ls, c = styles.get(name, ("-", "k"))
        ax.plot(g.day, g.err, ls=ls, color=c, lw=1.8, label=name)
    ax.set_xlabel("运行日")
    ax.set_ylabel("风险倍数估计的相对误差（MAE）")
    ax.grid(alpha=.25, ls="--")
    ax.legend(fontsize=8.5, frameon=False)
    ax.set_ylim(0, 0.5)
    fig.savefig(f"{OUT}/fig6_learning.png")
    plt.close(fig)


def fig_sensitivity():
    s = pd.read_csv(f"{R}/sensitivity.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.2))

    ax = axes[0]
    d = s[(s.regime == "S1") & (s.param == "abandon_unauth")].sort_values("value")
    base_inc, base_comp = d.inc.iloc[0], d.completion.iloc[0]
    ax.plot(d.value, d.inc / base_inc * 100, "o-", color="#c0392b", label="事件率指数")
    ax.plot(d.value, d.completion / base_comp * 100, "s--", color="#2e86c1", label="完成率指数")
    ax.set_xlabel("超时后强行飞行比例")
    ax.set_ylabel("相对 0.4 情形的指数（=100）")
    ax.set_title("(a) 全域从严：强飞比例的影响", fontsize=10)
    ax.grid(alpha=.2, ls="--")
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")

    ax = axes[1]
    for code, c, mk, ls in [("S3", "#1e8449", "o", "-"), ("S4", "#1f4e79", "s", "--")]:
        d = s[(s.regime == code) & (s.param == "cross_share")].sort_values("value")
        ax.plot(d.value, d.completion * 100, marker=mk, ls=ls, color=c, label=LABEL[code])
    ax.set_xlabel("跨区任务占比")
    ax.set_ylabel("任务完成率（%）")
    ax.set_title("(b) 跨区占比与协同完成率", fontsize=10)
    ax.grid(alpha=.2, ls="--")
    ax.legend(fontsize=8.5, frameon=False)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig5_sensitivity.png")
    plt.close(fig)


if __name__ == "__main__":
    fig_scenarios()
    fig_grid()
    fig_learning()
    fig_sensitivity()
    print("figures done")
