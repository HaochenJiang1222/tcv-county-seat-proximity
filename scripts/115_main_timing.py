# -*- coding: utf-8 -*-
"""主检验：同等国家认定资格下的支持时序排序（过程 B），扩展检验：是否进入安排（过程 A）

模型：条件 Logit（= 带县固定效应的 Poisson，Chamberlain 等价；组内 y 之和为条件充分统计量）
推断：县级 block bootstrap（有放回重抽县，重估完整模型），5000 次，百分位 CI + 中心化双尾 p
      同时报告县聚类稳健 se 供核对（18 个聚类，仅作参考，不作主推断）
敏感性：坐标异常剔除口径、省份范围、高程数据集、逐县删除、县等权 / 村等权
"""
import csv, sys, os, math, collections
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)
SEED = 20261030
rng = np.random.default_rng(SEED)
NB = 5000

rows = list(csv.DictReader(open('data/master/geo_vars_sample.csv', encoding='utf-8-sig')))
for r in rows:
    r['elev'] = float(r['elev_srtm30'])
    r['elev_a'] = float(r['elev_aster30'])
    r['dist'] = float(r['dist_county_km'])
    r['relief'] = float(r['elev_range_1km_srtm30'])
    r['relief_a'] = float(r['elev_range_1km_aster30'])

# 坐标异常标记（到所属县界距离 > 5 km 的界外点，见 114b）
BAD_COORD = {('建德市', '建南村章家自然村'): 42.68, ('绩溪县', '霞水村'): 17.03}
EDGE_COORD = {('东阳市', '李宅村'): 2.09, ('歙县', '萌坑村'): 0.43}
for r in rows:
    k = (r['county'], r['village'])
    r['bad'] = 1 if k in BAD_COORD else 0
    r['edge'] = 1 if k in EDGE_COORD else 0


def design(rows_sub, varcols, weight_by_county=False):
    y = np.array([1.0 if r['status'] == 'A_2017' else 0.0 for r in rows_sub])
    Xv = np.array([[float(r[c]) / 100.0 if c in ('elev', 'elev_a', 'relief', 'relief_a')
                    else (math.log1p(float(r[c])) if c == 'dist' else float(r[c]))
                    for c in varcols] for r in rows_sub], float)
    ctys = sorted({r['province'] + '|' + r['county'] for r in rows_sub})
    idx = {c: i for i, c in enumerate(ctys)}
    D = np.zeros((len(rows_sub), len(ctys)))
    for i, r in enumerate(rows_sub):
        D[i, idx[r['province'] + '|' + r['county']]] = 1.0
    X = np.hstack([Xv, D])
    w = np.ones(len(rows_sub))
    if weight_by_county:
        n = collections.Counter(r['province'] + '|' + r['county'] for r in rows_sub)
        w = np.array([1.0 / n[r['province'] + '|' + r['county']] for r in rows_sub])
    grp = np.array([idx[r['province'] + '|' + r['county']] for r in rows_sub])
    return y, X, w, grp, ctys


def fit(y, X, w, iters=60):
    k = X.shape[1]
    beta = np.zeros(k)
    for it in range(iters):
        eta = X @ beta
        eta = np.clip(eta, -30, 30)
        mu = np.exp(eta)
        W = w * mu
        W = np.maximum(W, 1e-10)
        z = eta + (y - mu) / np.maximum(mu, 1e-10)
        XtW = X.T * W
        A = XtW @ X
        b = XtW @ z
        try:
            step = np.linalg.solve(A + 1e-10 * np.eye(k), b)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(A, b, rcond=None)[0]
        new = beta + step
        if np.max(np.abs(step)) < 1e-8:
            beta = new
            break
        beta = new
    eta = np.clip(X @ beta, -30, 30)
    mu = np.exp(eta)
    return beta, mu


def cluster_se(y, X, w, beta, grp):
    mu = np.exp(np.clip(X @ beta, -30, 30))
    u = y - mu
    XtW = (X.T * (w * mu))
    A = XtW @ X
    Ainv = np.linalg.pinv(A)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in np.unique(grp):
        m = grp == g
        s = (X[m] * (w[m] * u[m])[:, None]).sum(axis=0)
        meat += np.outer(s, s)
    V = Ainv @ meat @ Ainv
    G = len(np.unique(grp))
    corr = G / max(G - 1, 1)
    return np.sqrt(np.maximum(np.diag(V), 0) * corr)


def boot_ci(rows_sub, varcols, nb=NB, weight_by_county=False):
    ctys = sorted({r['province'] + '|' + r['county'] for r in rows_sub})
    buckets = collections.defaultdict(list)
    for r in rows_sub:
        buckets[r['province'] + '|' + r['county']].append(r)
    out = []
    for b in range(nb):
        pick = rng.integers(0, len(ctys), len(ctys))
        sub = []
        for j, c in enumerate(ctys):
            for r in buckets[c]:
                rr = dict(r)
                rr['province'] = r['province'] + '#%d' % j   # 复制县赋予新 id
                sub.append(rr)
            # pick[j] 可能为其它县 -> 用 pick 索引决定复制来源
        # 重新构造：按 pick 抽县
        sub = []
        for j in range(len(ctys)):
            src = ctys[pick[j]]
            for r in buckets[src]:
                rr = dict(r)
                rr['province'] = r['province'] + '#%d' % j
                sub.append(rr)
        try:
            y, X, w, grp, _ = design(sub, varcols, weight_by_county)
            beta, _ = fit(y, X, w)
            out.append(beta[:len(varcols)])
        except Exception:
            continue
        if b % 1000 == 0:
            print('   bootstrap %d/%d' % (b, nb))
    return np.array(out)


def report(name, rows_sub, varcols, weight_by_county=False, nb=NB, do_boot=True):
    y, X, w, grp, ctys = design(rows_sub, varcols, weight_by_county)
    beta, mu = fit(y, X, w)
    k = len(varcols)
    se_cl = cluster_se(y, X, w, beta, grp)
    print()
    print('===== %s =====' % name)
    print('样本：%d 村 / %d 县；事件（A_2017）%d' % (len(rows_sub), len(ctys), int(y.sum())))
    print('%-14s %8s %8s %8s %10s %10s %8s' % ('变量', 'beta', 'se_clu', 'OR', 'boot_CI', '', 'boot_p'))
    B = None
    if do_boot:
        B = boot_ci(rows_sub, varcols, nb=nb, weight_by_county=weight_by_county)
    for i, c in enumerate(varcols):
        b = beta[i]
        if B is not None and len(B):
            lo, hi = np.percentile(B[:, i], [2.5, 97.5])
            # 中心化双尾 p
            d = B[:, i] - B[:, i].mean()
            p = 2 * min((d <= -abs(b)).mean(), (d >= abs(b)).mean())
            p = min(1.0, max(p, 1.0 / len(B)))
            cis = '[%.3f, %.3f]' % (lo, hi)
            ps = '%.3f' % p
        else:
            cis, ps = '-', '-'
        print('%-14s %8.4f %8.4f %8.3f %10s %10s %8s' % (
            c, b, se_cl[i], math.exp(b), '', cis, ps))
    return beta, se_cl, B, varcols


# ================= 主检验：过程 B（已进入安排者中，2017 当年 vs 拟 2018）=================
VAR = ['elev', 'dist', 'relief']
mix = [r for r in rows if r['status'] in ('A_2017', 'B_2018promised')]
cty_mix = collections.Counter(r['province'] + '|' + r['county'] for r in mix)
abc = collections.defaultdict(lambda: [0, 0, 0])
for r in rows:
    key = r['province'] + '|' + r['county']
    abc[key][{'A_2017': 0, 'B_2018promised': 1, 'C_not_in_1044': 2}[r['status']]] += 1
mixed = {k for k, v in abc.items() if v[0] and v[1]}
main = [r for r in mix if (r['province'] + '|' + r['county']) in mixed and not r['bad']]
print('主检验样本（剔除坐标明显错误 1 条）：%d 村 / %d 县' % (
    len(main), len({r['province'] + '|' + r['county'] for r in main})))
print('其中 A %d / B %d' % (sum(1 for r in main if r['status'] == 'A_2017'),
                          sum(1 for r in main if r['status'] == 'B_2018promised')))

# 描述性
print()
print('== 描述性（主检验样本）==')
for st in ('A_2017', 'B_2018promised'):
    g = [r for r in main if r['status'] == st]
    e = sorted(r['elev'] for r in g); d = sorted(r['dist'] for r in g); rg = sorted(r['relief'] for r in g)
    print('%s n=%d 海拔中位 %.0f m；到县城中位 %.1f km；1km起伏中位 %.0f m' % (
        st, len(g), e[len(e) // 2], d[len(d) // 2], rg[len(rg) // 2]))
# 县内均值差（县等权）
diffs = []
for k in sorted(mixed):
    g = [r for r in main if r['province'] + '|' + r['county'] == k]
    a = [r for r in g if r['status'] == 'A_2017']; b = [r for r in g if r['status'] == 'B_2018promised']
    if a and b:
        diffs.append((k, np.mean([r['elev'] for r in a]) - np.mean([r['elev'] for r in b]),
                      np.mean([r['dist'] for r in a]) - np.mean([r['dist'] for r in b]),
                      np.mean([r['relief'] for r in a]) - np.mean([r['relief'] for r in b])))
print('县内均值差（A−B，县等权，n=%d 县）：海拔 %.1f m；距离 %.2f km；起伏 %.1f m' % (
    len(diffs), np.mean([d[1] for d in diffs]), np.mean([d[2] for d in diffs]), np.mean([d[3] for d in diffs])))

beta, se, B, vc = report('主检验：过程 B（县分层条件 Logit）', main, VAR)

# ================= 敏感性 =================
print()
print('== 敏感性 ==')
sens = {}
sens['不剔除坐标异常（102 条含建德建南村章家）'] = [r for r in mix if (r['province'] + '|' + r['county']) in mixed]
sens['同时剔除 4 条县界外点'] = [r for r in main if not r['edge']]
sens['仅浙江 15 县'] = [r for r in main if r['province'] == '浙江省']
sens['高程与起伏改用 ASTER 30m'] = main
sens['加入 1km 高程标准差以外的地形：仅海拔+距离'] = main
for name, sub in sens.items():
    vcx = ['elev_a', 'dist', 'relief_a'] if 'ASTER' in name else (['elev', 'dist'] if '仅海拔' in name else VAR)
    b, s, Bb, vc2 = report('敏感性：' + name, sub, vcx, do_boot=True, nb=2000)

# 县等权
print()
b2, s2, B2, _ = report('敏感性：县等权（每县权重 1/n）', main, VAR, weight_by_county=True, nb=2000)

# 逐县删除
print()
print('== 逐县删除（jackknife，主检验样本）==')
ctys = sorted({r['province'] + '|' + r['county'] for r in main})
jk = collections.defaultdict(list)
for c in ctys:
    sub = [r for r in main if r['province'] + '|' + r['county'] != c]
    y, X, w, grp, _ = design(sub, VAR)
    beta_j, _ = fit(y, X, w)
    for i, v in enumerate(VAR):
        jk[v].append(beta_j[i])
for v in VAR:
    a = np.array(jk[v])
    print('%-8s 删除后 beta 范围 [%.4f, %.4f]，符号稳定：%s' % (
        v, a.min(), a.max(), '是' if (a > 0).all() or (a < 0).all() else '否'))

# ================= 扩展检验：过程 A（是否进入 2017 年安排）=================
print()
print('===== 扩展检验：过程 A（A+B vs C，三省 279 村）=====')
var_cty = collections.defaultdict(lambda: [0, 0])
for r in rows:
    key = r['province'] + '|' + r['county']
    var_cty[key][0 if r['status'] in ('A_2017', 'B_2018promised') else 1] += 1
keep = {k for k, v in var_cty.items() if v[0] and v[1]}
subA = [r for r in rows if (r['province'] + '|' + r['county']) in keep and not r['bad']]
for r in subA:
    r['_y'] = 1.0 if r['status'] in ('A_2017', 'B_2018promised') else 0.0
print('有组内变异的县 %d，样本 %d 村（事件 %d）' % (
    len(keep), len(subA), sum(1 for r in subA if r['_y'] == 1)))
# 复用 design/fit：临时把 status 映射
subA2 = []
for r in subA:
    rr = dict(r)
    rr['status'] = 'A_2017' if r['_y'] == 1 else 'B_2018promised'
    subA2.append(rr)
bA, sA, BA, _ = report('扩展检验：是否进入 2017 年安排（县分层条件 Logit）', subA2, VAR, nb=2000)

print()
print('完成。种子 SEED=%d，bootstrap 次数主检验 %d。' % (SEED, NB))
