"""生成《城市发展研究》投稿版插图（中文标签，印刷尺寸）。"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import rcParams

rcParams["font.sans-serif"] = ["SimHei"]
rcParams["axes.unicode_minus"] = False
rcParams["font.size"] = 9
rcParams["axes.linewidth"] = 0.7
rcParams["xtick.major.width"] = 0.7
rcParams["ytick.major.width"] = 0.7
rcParams["savefig.dpi"] = 400
rcParams["savefig.bbox"] = "tight"

R, OUT = "results", "figures"
os.makedirs(OUT, exist_ok=True)

LB = {"S0": "S0 基准", "S1": "S1 全域从严", "S1p": "S1+ 从严+能力",
      "S2": "S2 单纯扩容", "S2p": "S2+ 扩容+投入", "S3": "S3 分类治理",
      "S4": "S4 分类+协同"}
CL = {"S0": "#7f7f7f", "S1": "#b03a2e", "S1p": "#e59866", "S2": "#2874a6",
      "S2p": "#7fb3d5", "S3": "#1e8449", "S4": "#145a32"}
MK = {"S0": "o", "S1": "o", "S1p": "o", "S2": "s", "S2p": "s", "S3": "^", "S4": "^"}


def fig1():
    s = json.load(open(f"{R}/journal_scenarios.json", encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    order = ["S0", "S1", "S1p", "S2", "S2p", "S3", "S4"]
    for code in order:
        v = s[code]
        x = v["completion"]["mean"] * 100
        y = v["inc_per_10k"]["mean"]
        ax.errorbar(x, y, xerr=v["completion"]["se"] * 100 * 1.96,
                    yerr=v["inc_per_10k"]["se"] * 1.96, fmt=MK[code], ms=5.5,
                    capsize=2.4, lw=1.0, color=CL[code], label=LB[code])
    ax.set_xlabel("任务完成率 / %")
    ax.set_ylabel("每万架次事件数 / 起")
    ax.set_xlim(77, 101.5)
    ax.set_ylim(0.30, 0.87)
    ax.grid(alpha=0.25, ls="--", lw=0.6)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=4,
              fontsize=7.6, frameon=False, handletextpad=0.5, columnspacing=1.1)
    fig.savefig(f"{OUT}/j_fig1_scenarios.png")
    plt.close(fig)


def fig2():
    d = pd.read_csv(f"{R}/journal_space.csv")
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.35),
                             gridspec_kw=dict(wspace=0.42))

    ax = axes[0]
    ax.errorbar(d.cv, d.inc_s2p, yerr=d.d_inc_se * 1.96, fmt="s-", ms=4, lw=1.1,
                capsize=2.2, color="#2874a6", label="等量扩容")
    ax.errorbar(d.cv, d.inc_s3, yerr=d.d_inc_se * 1.96, fmt="^-", ms=4, lw=1.1,
                capsize=2.2, color="#1e8449", label="分类治理")
    ax.set_xticks(d.cv)
    ax.set_xticklabels([f"{v:.2f}" for v in d.cv], fontsize=7.6)
    ax.set_xlabel("暴露空间集中度（变异系数）")
    ax.set_ylabel("每万架次事件数 / 起")
    ax.set_title("(a) 两类配置的事件率", fontsize=9)
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax.grid(alpha=0.25, ls="--", lw=0.6)

    ax = axes[1]
    ax.bar(d.cv, d.gain_pct, width=0.13, color="#1e8449", alpha=0.85)
    for x, y in zip(d.cv, d.gain_pct):
        ax.text(x, y + 0.35, f"{y:.1f}", ha="center", fontsize=7.6)
    ax.set_xticks(d.cv)
    ax.set_xticklabels([f"{v:.2f}" for v in d.cv], fontsize=7.6)
    ax.set_xlabel("暴露空间集中度（变异系数）")
    ax.set_ylabel("分类治理的事件率降幅 / %")
    ax.set_title("(b) 相对降幅", fontsize=9)
    ax.set_ylim(20, 30)
    ax.grid(alpha=0.25, ls="--", axis="y", lw=0.6)
    fig.savefig(f"{OUT}/j_fig2_space.png")
    plt.close(fig)


if __name__ == "__main__":
    fig1()
    fig2()
    print("figures saved")
