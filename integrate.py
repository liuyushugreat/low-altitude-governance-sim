# -*- coding: utf-8 -*-
"""把计算实验章节整合进投稿修订版，生成新文档。"""
import json, re
from copy import deepcopy
from docx import Document
from docx.shared import Pt, Cm, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC = "城市低空安全的分类治理与协同机制_中国行政管理投稿修订版.docx"
DST = "城市低空安全的分类治理与协同机制_仿真检验版.docx"
SIM = "低空治理仿真"

scen = json.load(open(f"{SIM}/results/scenarios_summary.json", encoding="utf-8"))
learn = json.load(open(f"{SIM}/results/learning_summary.json", encoding="utf-8"))
cal = json.load(open(f"{SIM}/results/calibration.json", encoding="utf-8"))
err = [f"{cal['error'][k]*100:.1f}%" for k in ["mu", "beta", "p0", "q"]]

doc = Document(SRC)
ref_tbl = doc.tables[0]

# 插入锚点：原“七、可回退试点与政策学习”
anchor = None
for p in doc.paragraphs:
    if p.style.name == "Heading 1" and p.text.startswith("七、可回退"):
        anchor = p
        break
assert anchor is not None


def norm(t):
    t = str(t)
    t = re.sub(r'(?<=[0-9])[ \t]+(?=[\u4e00-\u9fff])', '', t)
    t = re.sub(r'(?<=[\u4e00-\u9fff])[ \t]+(?=[0-9])', '', t)
    t = re.sub(r'(?<=%)[ \t]+(?=[\u4e00-\u9fff])', '', t)
    t = re.sub(r'(?<=[\u4e00-\u9fff])[ \t]+(?=[A-Za-z])', '', t)
    return t


def _style_run(r, size=None, bold=None, font="宋体"):
    r.font.name = "Times New Roman"
    r._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), font)
    if size:
        r.font.size = Pt(size)
    if bold is not None:
        r.bold = bold


def para(text, style="Normal", indent=True, size=None, bold=False,
         align=WD_ALIGN_PARAGRAPH.JUSTIFY, before=None, after=None, font="宋体"):
    p = doc.add_paragraph(style=style)
    p.alignment = align
    if indent:
        p.paragraph_format.first_line_indent = Emu(266700)
    if before is not None:
        p.paragraph_format.space_before = Pt(before)
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    r = p.add_run(norm(text))
    _style_run(r, size=size, bold=bold, font=font)
    anchor._p.addprevious(p._p)
    return p


def para_lead(lead, rest):
    p = doc.add_paragraph(style="Normal")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.first_line_indent = Emu(266700)
    r1 = p.add_run(norm(lead)); _style_run(r1, bold=True)
    r2 = p.add_run(norm(rest)); _style_run(r2)
    anchor._p.addprevious(p._p)
    return p


def caption(text):
    return para(text, style="Caption", indent=False, size=10, bold=True,
                align=WD_ALIGN_PARAGRAPH.CENTER, before=7, after=3)


def note(text):
    return para(text, indent=False, size=9, align=WD_ALIGN_PARAGRAPH.LEFT, after=8)


def table(rows, widths, center_cols=None, font_size=9):
    nrow, ncol = len(rows), len(rows[0])
    t = doc.add_table(rows=nrow, cols=ncol)
    t._tbl.replace(t._tbl.tblPr, deepcopy(ref_tbl._tbl.tblPr))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    if t._tbl.tblPr.find(qn("w:tblLayout")) is None:
        lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed")
        t._tbl.tblPr.append(lay)
    grid = t._tbl.tblGrid
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
        gc.set(qn("w:w"), str(int(w * 567)))
    tw = t._tbl.tblPr.find(qn("w:tblW"))
    if tw is None:
        tw = OxmlElement("w:tblW"); t._tbl.tblPr.append(tw)
    tw.set(qn("w:type"), "dxa"); tw.set(qn("w:w"), str(int(sum(widths) * 567)))
    for ci, w in enumerate(widths):
        t.columns[ci].width = Cm(w)
        for cell in t.columns[ci].cells:
            cell.width = Cm(w)
    center_cols = center_cols or []
    for ri, row in enumerate(rows):
        for ci, txt in enumerate(row):
            cell = t.cell(ri, ci)
            ref_tcPr = deepcopy(ref_tbl.rows[min(ri, len(ref_tbl.rows) - 1)].cells[0]._tc.tcPr)
            if cell._tc.tcPr is not None:
                cell._tc.remove(cell._tc.tcPr)
            cell._tc.insert(0, ref_tcPr)
            tcW = ref_tcPr.find(qn("w:tcW"))
            if tcW is None:
                tcW = OxmlElement("w:tcW"); ref_tcPr.append(tcW)
            tcW.set(qn("w:w"), str(int(widths[ci] * 567)))
            tcW.set(qn("w:type"), "dxa")
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(1)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if (ci in center_cols or ri == 0) else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(norm(txt))
            _style_run(r, size=font_size, bold=(ri == 0))
        trPr = t.rows[ri]._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        if ri == 0:
            trPr.append(OxmlElement("w:tblHeader"))
    anchor._p.addprevious(t._tbl)
    return t


def figure(path, width=13.6):
    doc.add_picture(path, width=Cm(width))
    p = doc.paragraphs[-1]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    anchor._p.addprevious(p._p)


def f(x, n=2):
    return f"{x:.{n}f}"


# ==================== 新章节正文 ====================
H1 = "七、机制检验：计算实验的设计与结果"
H2 = ["（一）检验思路与模型设定", "（二）结果：工具匹配与协同效应",
      "（三）边界条件与敏感性", "（四）风险校准与制度学习",
      "（五）参数校准与可检验含义", "（六）讨论"]

S = scen
inc = lambda k: S[k]["inc_per_10k"]["mean"]
comp = lambda k: S[k]["completion"]["mean"] * 100
una = lambda k: S[k]["unauth_rate"]["mean"] * 100
delay = lambda k: S[k]["mean_delay"]["mean"]
dup = lambda k: S[k]["duplicates_per_cross"]["mean"]
intr = lambda k: S[k]["interrupt_rate"]["mean"] * 100
cost = lambda k: S[k]["cost_per_1k"]["mean"]

blocks = []

blocks.append(("h1", H1))
blocks.append(("h2", H2[0]))
blocks.append(("p", "前文三个命题都是机制性判断，其检验需要运行暴露量与事件记录，而公开材料尚不具备。为此，本文构建任务级计算实验：在给定参数下模拟任务流、审批队列、违规行为与事件发生，观察命题所推断的关系是否出现，以及在何种条件下反转。计算实验不能替代实证评估，它的作用是检验机制的自洽性、识别边界条件，并为后续数据采集提供指标设计。"))
blocks.append(("p", "模型将第四部分的六类情境设为一个相互通勤的辖区系统，各辖区在安全约束、需求密度与治理能力上取值不同。每日生成 1500 个飞行任务，风险等级按低、中、高 6∶3∶1 分布，约 18% 跨越辖区。需申请的任务进入所在辖区队列，按容量与风险优先序处理；预计等待超过 12 小时者，60% 选择强行飞行，40% 取消。事件概率由基准率、风险倍数、地面暴露、治理能力、违规状态、空域拥挤与能力匹配七项相乘决定，其中能力匹配仅在采用风险优先与差异化保障的情景中生效。跨区任务未建立互认时须在目的辖区重复申请，并有 18% 的交接中断概率。"))
blocks.append(("p", "参数设定遵循三条原则：规模参数取自公开统计，2025 年全国无人机飞行 4530.29 万小时、注册 328.7 万架，深圳 2025 年建成起降点 1284 个、开通货运航线 310 条[34]；事件率量级参照地面风险模型与 SORA 的评估区间[14,15]；审批容量、等待容忍与强行飞行比例缺少公开数据，取设定值并在敏感性分析中变动（表7）。全部结果基于虚拟数据，用于情景比较，不代表现实预测。"))
blocks.append(("caption", "表7　计算实验的主要参数设定"))
blocks.append(("table", ([
    ["参数", "设定", "依据或说明"],
    ["辖区与情境", "6 类", "对应第四部分六类情境"],
    ["日任务量", "1500 架次", "按城市群规模缩放"],
    ["风险等级分布", "低 60%、中 30%、高 10%", "场景结构设定"],
    ["跨区任务比例", "18%", "设定值；敏感性 5%—35%"],
    ["等待容忍与强飞比例", "12 小时；60%", "敏感性 6—24 小时；40%—80%"],
    ["基准事件率", "3 起/10 万架次", "地面风险模型量级[14,15]"],
    ["风险倍数", "1∶3∶10", "参照 SORA 分级思路[15]"],
    ["治理能力", "0.30—0.75", "按情境设定；重复 200 次"],
], [3.8, 5.0, 7.4], None, 8.8)))
blocks.append(("note", "注：模型为作者构建，参数用于机制比较；事件率与审批时延缺乏直接观测，不构成对现实水平的估计。"))
blocks.append(("h2", H2[1]))

blocks.append(("p", f"表8 报告七种情景在 200 次重复下的均值。全域从严（S1）每万架次事件 {f(inc('S1'))} 起、完成率 {f(comp('S1'),1)}%、违规率 {f(una('S1'),1)}%，单位治理成本 {f(cost('S1'),1)} 万元/千架次；当审批容量与能力同步扩张（S1+）时，事件率降至 {f(inc('S1p'))} 起、违规率降至 {f(una('S1p'),1)}%、成本降至 {f(cost('S1p'),1)} 万元，完成率升至 {f(comp('S1p'),1)}%。同一管控工具，仅因能力配置不同，事件率相差约36%，完成率相差11.6个百分点。管控工具的效果并不取决于其严厉程度，而取决于其与治理能力的匹配，命题1由此得到支持。"))
blocks.append(("p", f"单纯扩容（S2）完成率 {f(comp('S2'),1)}%、事件率 {f(inc('S2'))} 起；在投入相同的情况下（S2+），事件率降至 {f(inc('S2p'))} 起；分类治理（S3）进一步降至 {f(inc('S3'))} 起，完成率不变。与等量投入的扩容相比，分类治理的事件率低约 24%，且 95% 置信区间不重叠（图3）。其机制不是减少飞行，而是把有限能力配置到高后果任务：高风险任务的保护强度提高，中低风险任务的审批负担下降。"))
blocks.append(("p", f"分类治理与分类协同（S4）的差别仅在跨区安排。协同使重复申请由每项跨区任务 {f(dup('S3'))} 次降为 {f(dup('S4'))} 次，交接中断由 {f(intr('S3'),1)}% 降至 {f(intr('S4'),1)}%，完成率由 {f(comp('S3'),1)}% 升至 {f(comp('S4'),1)}%，单位治理成本由 {f(cost('S3'),1)} 万元降至 {f(cost('S4'),1)} 万元；事件率差异在统计上不显著。协同的主要收益是服务可靠性与治理成本，而非直接的安全改善。命题2所预期的“减少重复申报与交接中断”得到支持，但不能据此认为协同可以替代分类。"))

blocks.append(("caption", "表8　七种治理情景的模拟结果（200次重复的均值）"))
rows = [["情景", "事件率(起/万)", "完成率(%)", "违规率(%)",
         "时延(小时)", "重复申请(次)", "成本(万元/千)"]]
name = {"S0": "S0 基准", "S1": "S1 全域从严", "S1p": "S1+ 从严+能力",
        "S2": "S2 单纯扩容", "S2p": "S2+ 扩容+投入", "S3": "S3 分类治理",
        "S4": "S4 分类+协同"}
for k in ["S0", "S1", "S1p", "S2", "S2p", "S3", "S4"]:
    rows.append([name[k], f(inc(k)), f(comp(k), 1), f(una(k), 1),
                 f(delay(k), 1), f(dup(k)), f(cost(k), 1)])
blocks.append(("table", (rows, [3.2, 2.4, 2.0, 2.0, 2.0, 2.4, 2.4], [1, 2, 3, 4, 5, 6])))
blocks.append(("note", "注：事件率按每万飞行架次计；成本含事件损失、行政、等待、查处与跨区中断成本；仿真程序与逐次结果可向作者索取。"))
blocks.append(("figure", (f"{SIM}/figures/fig3_scenarios.png", 12.8)))
blocks.append(("caption", "图3　不同治理情景的安全—服务组合（均值与 95% 置信区间）"))

blocks.append(("h2", H2[2]))
blocks.append(("p", "图4 给出治理能力与审批容量组合下，分类治理相对等量扩容的事件率改进。改进在所有组合中均为正，但幅度随容量放宽而收窄：容量为基准 0.6 倍时平均约 0.20 起/万架次，1.2 倍时约 0.15 起。审批资源越紧张，风险优先排序的价值越大；容量充裕时，分类的安全边际主要来自差异化保障而非排队秩序。"))
blocks.append(("figure", (f"{SIM}/figures/fig4_grid.png",)))
blocks.append(("caption", "图4　等量投入下分类治理相对扩容的事件率改进（起/万架次）"))
blocks.append(("p", "成本方向相反。分类治理每千架次增加约 2.9 万至 6.4 万元行政与等待成本，容量越紧成本越高。这意味着分类不是无条件的改进：它需要审批容量与监测能力的配套；在容量严重不足时，分类可能只是把排队成本转移给运营者。"))
blocks.append(("p", f"敏感性分析（图5）显示：全域从严情景下，超时强行飞行比例由 40% 升至 80%，事件率由 0.73 升至 0.85 起，完成率由 69.7% 升至 88.3%——表面服务改善伴随风险上升；等待容忍由 6 小时延长至 24 小时，违规率由 47.9% 降至 4.0%，事件率由 0.98 降至 0.54 起。跨区任务占比由 5% 升至 35% 时，协同的完成率优势由不足 1 个百分点扩大至 4.6 个百分点。"))
blocks.append(("figure", (f"{SIM}/figures/fig5_sensitivity.png",)))
blocks.append(("caption", "图5　关键参数的敏感性"))

blocks.append(("h2", H2[3]))
blocks.append(("p", "第二个模型模拟监管者对三类任务风险倍数的估计过程：初始估计系统性低估高风险任务，通过监测与事件报告按贝叶斯规则更新。无监测与“仅监测、不进入规则”两种情形下，估计误差在整个观察期保持 0.43 不变；按周反馈并更新规则时，第 30 日误差降至 0.08，第 180 日降至 0.03；按日反馈并纠错时可降至 0.02（表9、图6）。因低估高风险而产生的额外事件相应由 1836 起降至 184 起。监测本身不产生校准，只有进入规则并形成纠错闭环的数据才改变判断，命题3关于反馈机制的部分由此得到支持；停止条件未纳入模型检验。"))
blocks.append(("caption", "表9　不同反馈机制下的风险校准结果"))
lrows = [["反馈机制", "第 30 日", "第 90 日", "第 180 日", "额外事件（起）"]]
for k in learn:
    v = learn[k]
    lrows.append([k, f(v["err30"]), f(v["err90"]), f(v["err180"]), f"{v['excess']:.0f}"])
blocks.append(("table", (lrows, [5.6, 2.6, 2.6, 2.6, 3.2], [1, 2, 3, 4])))
blocks.append(("note", "注：误差为三类任务风险倍数估计的相对误差均值（MAE）；L0 与 L1 曲线完全重合。额外事件为模型设定暴露下的期望值，仅用于机制比较。"))
blocks.append(("figure", (f"{SIM}/figures/fig6_learning.png",)))
blocks.append(("caption", "图6　不同反馈机制下的风险校准过程"))

blocks.append(("h2", H2[4]))
blocks.append(("p", f"模型参数并非只能设定。四类在试点中可采集的观测量与四个关键参数一一对应（表10）：审批系统日志给出平均时延，查处与告警记录给出违规率，事件与事故报告给出每万架次事件率，跨区任务跟踪给出交接中断率。校准采用矩匹配：固定其余参数，对单个参数做二分搜索，使模拟均值逼近观测值，两轮迭代以减弱参数交互。为检验接口的可用性，本文以一组留出的参数生成观测值（视为试点观测），再由校准程序反推。结果显示，四个参数的反推误差分别为 {err[0]}、{err[1]}、{err[2]} 和 {err[3]}，模拟值与观测值的相对偏差均在 8% 以内。这说明模型具备可校准性；但校准只提高参数的现实贴合度，不能把计算实验变成因果识别。"))
blocks.append(("caption", "表10　观测量与模型参数的校准接口"))
blocks.append(("table", ([
    ["观测量", "对应参数", "采集来源", "校准判据"],
    ["平均审批时延（小时）", "审批容量倍数", "审批系统日志", "相对误差≤10%"],
    ["违规率（%）", "超时后强行飞行比例", "查处记录、平台告警", "同上"],
    ["每万架次事件率", "基准事件率", "事件与事故报告", "同上"],
    ["跨区交接中断率（%）", "交接中断概率", "跨区任务跟踪", "同上"],
], [4.8, 4.4, 4.2, 3.0], None, 8.8)))
blocks.append(("note", "注：校准不改变模型结构，只调整参数；判据为模拟均值与观测值的相对偏差。"))

blocks.append(("h2", H2[5]))
blocks.append(("p", "计算实验支持三个命题的主要机制，同时给出两点限定。第一，分类治理的安全收益依赖能力与容量配套，缺少审批能力扩张的分类可能加重运营者负担。第二，协同的收益集中在服务与成本，安全效应不显著，因而不能以平台互联替代风险分级。这两点印证了前文的判断：治理工具之间不是替代关系，而是匹配关系。"))
blocks.append(("p", "模型不能证明现实效果。参数取自公开统计与文献区间，事件率、违规行为与审批时延缺乏直接观测；模型未纳入载人运行、恶意攻击、军地协调等要素。其价值在于把制度设计转化为可复核的机制假设：若在试点中采集申请时延、违规率、事件率与跨区中断数据，即可校准参数，并对本文推断作出证伪。"))

# 依次插入
for kind, payload in blocks:
    if kind == "h1":
        para(payload, style="Heading 1", indent=False, align=WD_ALIGN_PARAGRAPH.LEFT, before=12, after=6)
    elif kind == "h2":
        para(payload, style="Heading 2", indent=False, align=WD_ALIGN_PARAGRAPH.LEFT, before=8, after=4)
    elif kind == "p":
        para(payload)
    elif kind == "pb":
        para_lead(*payload)
    elif kind == "caption":
        caption(payload)
    elif kind == "note":
        note(payload)
    elif kind == "table":
        table(*payload)
    elif kind == "figure":
        figure(payload[0], *payload[1:])

# ==================== 章节编号调整 ====================
for p in doc.paragraphs:
    if p.style.name == "Heading 1":
        if p.text.startswith("七、可回退试点与政策学习"):
            p.runs[0].text = "八、可回退试点与政策学习"
        elif p.text.startswith("八、结论与讨论"):
            p.runs[0].text = "九、结论与讨论"

# ==================== 摘要与结论修订 ====================
abs_new = ("[摘　要] 城市低空运行扩张使空域管理与属地公共安全之间的衔接问题更加突出。基于 2023—2026 年国家制度文本及北京、天津、深圳、东莞等地公开资料，"
           "采用结构化定性比较、情境建构与计算实验方法，考察不同管控安排的适用对象、空间边界和服务机制。比较表明，适飞扩容、全域管制与产业促进分别作用于不同治理环节，"
           "不能以开放程度直接评价治理绩效。据此构建“情境识别—能力配置—跨区域协同”框架，将典型风险情境与能力优先序、实施条件和评价指标相连接。"
           "城市低空安全规划应通过明确权限与责任接口、配置可持续运行能力、建立信息互认和可回退试点，衔接统一规则与地方差异。"
           "任务级计算实验显示，管控工具的效果取决于其与治理能力的匹配，同等投入下分类治理可降低事件率，跨区域协同主要改善服务连续性与治理成本，"
           "而仅有监测、不进入规则并不产生风险校准。上述结果支持框架的机制自洽性；本文进一步给出四类观测量与关键参数的校准接口，参数仍须以试点数据校准。")
p = doc.paragraphs[1]
assert p.text.startswith("[摘　要]")
p.runs[0].text = abs_new
for r in p.runs[1:]:
    r.text = ""

eng_old = "The framework is an institutional design proposal whose effects require testing with operational data."
eng_new = ("A task-level computational experiment supports the mechanism: the effect of control instruments depends on their fit with governance capacity; "
           "classification lowers incident rates under equal investment; coordination mainly improves service continuity and reduces governance cost; "
           "and monitoring without rule feedback does not improve risk calibration. These results support the framework's internal consistency. "
           "A calibration interface linking four observable indicators to key parameters is provided for future pilot data, while the parameters themselves remain to be calibrated.")
for p in doc.paragraphs:
    if eng_old in p.text:
        p.runs[0].text = p.text.replace(eng_old, eng_new)
        for r in p.runs[1:]:
            r.text = ""
        break

# 引言：补充计算实验说明
for p in doc.paragraphs:
    if p.text.startswith("本文围绕一个核心问题展开"):
        p.runs[0].text = p.text.replace(
            "研究采用公开制度文本的结构化定性比较，并据此构造典型治理情境。",
            "研究采用公开制度文本的结构化定性比较，据此构造典型治理情境，并以任务级计算实验检验机制命题。")
        for r in p.runs[1:]:
            r.text = ""
        break

# 结论：补充仿真结论
for p in doc.paragraphs:
    if p.text.startswith("相对于分别讨论飞行风险、产业政策或平台建设"):
        p.runs[0].text = p.text + "计算实验进一步显示，分类治理的安全收益取决于能力与容量的匹配，协同的收益主要体现为服务连续性与治理成本。"
        for r in p.runs[1:]:
            r.text = ""
        break

# 局限修订
for p in doc.paragraphs:
    if p.text.startswith("研究局限在于材料来自目的性选择"):
        p.runs[0].text = ("研究局限在于材料来自目的性选择的公开文件及报道，不能代表全国政策实践；城市之间并非同质样本，缺少足以比较安全绩效的运行暴露和事件数据。"
                          "本文以任务级计算实验对三个机制命题作了检验，结果显示分类治理与跨区域协同的效应均以能力配置为条件；但仿真参数为设定值，"
                          "事件率、违规行为与审批时延缺乏直接观测，结果只具有比较意义，不能视为政策效果的估计。"
                          "后续研究可在相似任务和可比条件下收集申请流程、设施利用、告警处置与事故损害数据，对参数进行校准并检验本文推断；校准接口与回测结果见附录。"
                          "将规划转化为实践，应以权限明确、风险可评估、过程可记录和措施可回退为前提。")
        for r in p.runs[1:]:
            r.text = ""
        break

# ==================== 附录 ====================
ref_head = None
for p in doc.paragraphs:
    if p.style.name == "Heading 1" and p.text.strip() == "参考文献":
        ref_head = p
        break
assert ref_head is not None
anchor = ref_head

app = [("h1", "附录　计算实验的局限与回应")]
app.append(("pb", ("一、虚拟数据的性质。",
    "本文报告情景间的相对差异与置信区间，不报告事件率的绝对水平。表8的数值不应理解为对任一城市的预测；其用途是检验“工具—能力匹配”“协同—服务”“反馈—校准”三组关系是否成立、在何处反转。")))
app.append(("pb", ("二、参数设定的任意性。",
    "审批容量、等待容忍与强飞比例缺少公开数据，只能取设定值。对此作两项处理：核心参数在敏感性分析中变动（图5），并给出校准接口与回测（表10）。结果显示结论方向稳健、幅度对参数敏感：强飞比例上升会同时推高事件率与表观完成率，说明完成率不能单独作为治理绩效指标。")))
app.append(("pb", ("三、外部效度。",
    "六类情境是典型化构造，不是城市样本；模型未纳入载人运行、恶意攻击、军地协调与跨境飞行。载人运行的风险倍数与后果远高于载货，若纳入，分类治理的收益可能更大，但对适航、保险与责任规则的要求也更高。")))
app.append(("pb", ("四、与实证研究的关系。",
    "计算实验不能替代因果识别。它的作用是把制度设计拆成可复核的机制假设，明确需要采集的指标，并预设证伪条件：若试点数据显示分类治理未降低事件率，或协同未改善交接，相应命题即应修正。")))
app.append(("pb", ("五、模型简化的代价。",
    "模型把审批简化为队列、把违规简化为概率选择、把事件简化为独立抽样，忽略了运营主体的策略互动与相互学习。若引入主体间的博弈与模仿，违规可能呈非线性扩散，事件分布的尾部会更厚。这是后续扩展的方向。")))
app.append(("pb", ("六、可复现性。",
    "模型代码、随机种子、逐次结果与绘图脚本随文提供，参数与情景可整体替换，便于第三方复核。")))

for kind, payload in app:
    if kind == "h1":
        para(payload, style="Heading 1", indent=False, align=WD_ALIGN_PARAGRAPH.LEFT, before=12, after=6)
    elif kind == "pb":
        para_lead(*payload)
    elif kind == "p":
        para(payload)

# 表格与表题保持同页
for t in doc.tables:
    nrow = len(t.rows)
    for ri, row in enumerate(t.rows):
        if ri == nrow - 1:
            continue
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.keep_with_next = True
for p in doc.paragraphs:
    if p.style.name == "Caption" and p.text.strip().startswith("表"):
        p.paragraph_format.keep_with_next = True

doc.save(DST)
print("saved", DST)
