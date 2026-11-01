# -*- coding: utf-8 -*-
"""
141：Manuscript v1 的两张主图

Figure 1  制度流程与观察边界（国家认定 → 支持安排公告 → 实际拨款与实施）
Figure 2  过程A 的县级近／远组进入率差分布（95 个有效县）
           反映 42 负 / 11 平 / 42 正，避免用全国平均系数掩盖异质性

输出 output/figures/fig1_flow.png, fig2_county_diff.png
"""
import csv, os, sys, collections
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
OUT = os.path.join(ROOT, 'output', 'figures')
os.makedirs(OUT, exist_ok=True)

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#333333'
plt.rcParams['axes.linewidth'] = 0.9

# ============================================================
# Figure 1 制度流程与观察边界
# ============================================================
fig, ax = plt.subplots(figsize=(10.2, 4.6))
ax.set_xlim(0, 102)
ax.set_ylim(0, 46)
ax.axis('off')


def box(x, y, w, h, title, lines, fc='#EAF1F8', ec='#2C5F8A', fs=8.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.5,rounding_size=1.0',
                                facecolor=fc, edgecolor=ec, linewidth=1.3, zorder=2))
    ax.text(x + w / 2, y + h - 2.2, title, ha='center', va='center',
            fontsize=fs + 0.6, fontweight='bold', color='#1B3A57', zorder=3)
    for i, s in enumerate(lines):
        ax.text(x + w / 2, y + h - 4.8 - i * 1.9, s, ha='center', va='center',
                fontsize=fs, color='#22303C', zorder=3)


def arrow(x1, y1, x2, y2, label=''):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                 arrowstyle='-|>', mutation_scale=13,
                                 color='#2C5F8A', linewidth=1.4, zorder=4))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 1.5, label, ha='center', va='center',
                fontsize=8, color='#2C5F8A', style='italic', zorder=4)


# 三个主阶段
box(1.5, 24, 25, 15,
    'Stage 1   National recognition',
    ['Fourth cohort announced', 'December 2016', '1,598 villages',
     'Common designation status'],
    fc='#EAF1F8')
box(38.5, 24, 25, 15,
    'Stage 2   Entry into support schedule',
    ['Notice of May 2017', '600 villages: 2017 support', '444 villages: proposed 2018',
     'Others: not in that announcement'],
    fc='#FDF3E3', ec='#B07A2A')
box(75.5, 24, 25, 15,
    'Stage 3   Disbursement and delivery',
    ['Provincial allocation plans', 'Project filing and funding', 'Implementation',
     'Conservation outcomes'],
    fc='#EFEFEF', ec='#8A8A8A')

arrow(27.5, 31.5, 37.5, 31.5, 'Process A')
arrow(64.5, 31.5, 74.5, 31.5, 'not observed')

# 过程 A / B 标注
ax.text(38.5 + 12.5, 21.6,
        'Process A: entry into either list  |  Process B: 2017 vs. proposed 2018',
        ha='center', va='center', fontsize=8.4, color='#B07A2A')

# 观察边界框
ax.add_patch(FancyBboxPatch((1.0, 19.6), 62.0, 21.8,
                            boxstyle='round,pad=0.6,rounding_size=1.2',
                            facecolor='none', edgecolor='#2C5F8A',
                            linewidth=1.2, linestyle='--', zorder=1))
ax.text(32.0, 43.2, 'Observed in this study (public administrative announcements)',
        ha='center', va='center', fontsize=9, fontweight='bold', color='#2C5F8A')

# 底部说明条
box(1.5, 5.5, 99, 11,
    'Boundary of interpretation',
    ['Announced inclusion is not disbursement.  Support scheduling is not project completion.',
     'Distance to the county administrative center is a locational attribute, not travel cost,',
     'administrative capacity, or a measure of conservation need.'],
    fc='#F7F7F7', ec='#9AA5B1')

ax.text(51, 1.6, 'Figure 1. From national recognition to central conservation support: '
                 'institutional sequence and observational boundary.',
        ha='center', va='center', fontsize=9.2, color='#111111')

fig.tight_layout()
p1 = os.path.join(OUT, 'fig1_flow.png')
fig.savefig(p1, dpi=220, bbox_inches='tight', facecolor='white')
plt.close(fig)
print('写出', p1)

# ============================================================
# Figure 2 县级近／远组进入率差
# ============================================================
rows = [r for r in csv.DictReader(open(os.path.join(D, 'master', 'exposure_v3.csv'),
                                       encoding='utf-8-sig'))
        if r['dist_km'] not in ('', None) and r['status'] in
        ('A_2017', 'B_2018promised', 'C_not_in_1044')]
for r in rows:
    r['dist_km'] = float(r['dist_km'])
    r['yA'] = int(r['yA'])

gp = collections.defaultdict(list)
for r in rows:
    gp[r['grp']].append(r)

per = []
for k, v in gp.items():
    # 与 138 完全一致：县内按到县城距离中位数分组，near = <= med，far = > med
    if len(v) < 2:
        continue
    med = float(np.median([r['dist_km'] for r in v]))
    near = [r for r in v if r['dist_km'] <= med]
    far = [r for r in v if r['dist_km'] > med]
    if not near or not far:
        continue
    if len({r['yA'] for r in v}) < 2:
        continue      # 仅保留条件 Logit 实际使用的县
    pn = np.mean([r['yA'] for r in near])
    pf = np.mean([r['yA'] for r in far])
    per.append(dict(grp=k, n=len(v), d=pf - pn,
                    nkm=np.mean([r['dist_km'] for r in near]),
                    fkm=np.mean([r['dist_km'] for r in far])))
per.sort(key=lambda x: x['d'])
arr = np.array([x['d'] for x in per])
neg = int((arr < 0).sum()); zero = int((arr == 0).sum()); pos = int((arr > 0).sum())

NEG, ZER, POS = '#B23A48', '#9AA5B1', '#2C7A7B'

fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.3))

# --- (a) 直方图 ---
ax = axes[0]
edges = np.arange(-1.25, 1.2501, 0.25)
cnt, _ = np.histogram(arr, bins=edges)
centers = (edges[:-1] + edges[1:]) / 2
for c, x in zip(cnt, centers):
    if c == 0:
        continue
    col = NEG if x < -1e-9 else (POS if x > 1e-9 else ZER)
    ax.bar(x, c, width=0.235, color=col, edgecolor='white', linewidth=0.8)
ax.axvline(arr.mean(), color='#1B3A57', linestyle='--', linewidth=1.5)
ax.set_ylim(0, max(cnt) * 1.30)
ax.set_xlabel('Within-county difference in entry rate\n(farther group minus nearer group)',
              fontsize=8.8)
ax.set_ylabel('Number of counties', fontsize=8.8)
ax.set_title('(a)  Distribution across the 95 informative counties', fontsize=9.4, loc='left')
ax.text(0.98, 0.97,
        'negative %d    tied %d    positive %d\nmean %.3f\n'
        'equal-county 95%% CI [-0.174, 0.096];  p = 0.567' % (neg, zero, pos, arr.mean()),
        transform=ax.transAxes, fontsize=8.3, va='top', ha='right', color='#22303C',
        bbox=dict(facecolor='white', edgecolor='#C9CFD6', alpha=0.92, pad=3.5))
ax.set_xticks(np.arange(-1.0, 1.01, 0.5))
ax.tick_params(labelsize=8.2)
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)

# --- (b) 按县内村数 ---
ax = axes[1]
rng = np.random.default_rng(20261030)
bins = [(2, 3), (4, 5), (6, 9), (10, 99)]
lbl = ['2-3', '4-5', '6-9', '10+']


def bidx(n):
    for i, (a, b) in enumerate(bins):
        if a <= n <= b:
            return i
    return len(bins) - 1


xs = np.array([bidx(x['n']) for x in per], float)
jit = xs + rng.uniform(-0.16, 0.16, len(xs))
for x, y in zip(jit, arr):
    col = NEG if y < -1e-9 else (POS if y > 1e-9 else ZER)
    ax.scatter(x, y, s=26, color=col, alpha=0.82, edgecolor='white', linewidth=0.5)
ax.axhline(0, color='#8A8A8A', linewidth=1.0)
means = []
ncs = []
for (a, b) in bins:
    m = [x['d'] for x in per if a <= x['n'] <= b]
    means.append(np.mean(m))
    ncs.append(len(m))
xs2 = np.arange(len(bins))
ax.plot(xs2, means, 'o--', color='#1B3A57', markersize=6, linewidth=1.3,
        label='group mean', zorder=5)
for x, m, n in zip(xs2, means, ncs):
    dy = 11 if x < 2 else -14
    ax.annotate('%d counties' % n, (x, m), textcoords='offset points',
                xytext=(0, dy), ha='center', fontsize=7.8, color='#1B3A57')
ax.set_xticks(xs2); ax.set_xticklabels(lbl)
ax.set_xlabel('Number of fourth-cohort villages in the county', fontsize=8.8)
ax.set_ylabel('Difference in entry rate', fontsize=8.8)
ax.set_title('(b)  Difference by county cohort size', fontsize=9.4, loc='left')
ax.legend(fontsize=8, frameon=False, loc='lower right')
ax.tick_params(labelsize=8.2)
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)

fig.suptitle('Figure 2. Within-county contrasts between farther and nearer villages, '
             'Process A (95 counties, 560 villages).', fontsize=9.2, y=0.99)
fig.tight_layout(rect=(0, 0, 1, 0.95))
p2 = os.path.join(OUT, 'fig2_county_diff.png')
fig.savefig(p2, dpi=220, bbox_inches='tight', facecolor='white')
plt.close(fig)
print('写出', p2)
print('负 %d / 平 %d / 正 %d，均值 %.3f' % (neg, zero, pos, arr.mean()))
