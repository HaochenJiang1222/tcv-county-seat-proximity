# -*- coding: utf-8 -*-
"""
137：全国重估 v3（第三十九部分任务二）

与 131 的区别
  1 分组由模糊的 early/late 改为两个时间截点的行政状态
     C1 = 2015-12-31：cur1 已公布当年支持 / non1 尚未公布 / pro 已公布未来承诺
     C2 = 2016-12-09：cur2 此前已公布当年支持 / non2 此前尚未公布（含 2016-12-28 的 219 村）
  2 上海 5 村单列 never，不并入"尚未公布"后再当作早晚对比的一端
  3 未裁决的 10 条用三规格包围：M0 不参与 / M2 全部视为尚未公布 / M3 全部视为已公布
  4 系数采用中心化参数化：d_mean 控制总体距离，d_dif = d_non − d_cur 即早晚暴露系数差
    直接报告 d_dif / n_dif 的置信区间，不挑选单项显著结果

推断：县分层条件 Logit（精确条件似然）+ 县级 block bootstrap（SEED=20261030）
用法  python dofile/137_national_main_v3.py [B]
"""
import csv, sys, os, math, collections, time
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from statsmodels.discrete.conditional_models import ConditionalLogit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
B = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SEED = 20261030

exp = list(csv.DictReader(open(os.path.join(D, 'master', 'exposure_v3.csv'),
                               encoding='utf-8-sig')))
print('读入 %d 行' % len(exp))

recs = [r for r in exp if r['dist'] not in ('', None) and r['elev'] not in ('', None)]
for r in recs:
    for k in ['dist', 'elev', 'rng', 'dist_km', 'bdist']:
        r[k] = float(r[k])
    r['yA'] = int(r['yA'])
    r['yB'] = int(r['yB'])
print('可用样本 %d' % len(recs))

SUSPECT = {r['vid'] for r in recs if r['audit'] == 'outside' and r['bdist'] > 5}
print('坐标可疑 %d 条；通过县界检验 %d 条' %
      (len(SUSPECT), sum(1 for r in recs if r['audit'] == 'inside')))


def make(spec, cut):
    """构造该规格/截点下的分析记录"""
    out = []
    for r in recs:
        dc, dn = r['d_%s_cur%s' % (spec, cut)], r['d_%s_non%s' % (spec, cut)]
        nc, nn = r['n_%s_cur%s' % (spec, cut)], r['n_%s_non%s' % (spec, cut)]
        if dc in ('', None) or dn in ('', None):
            continue
        rr = dict(r)
        rr['d_cur'] = math.log1p(float(dc))
        rr['d_non'] = math.log1p(float(dn))
        rr['d_mean'] = (rr['d_cur'] + rr['d_non']) / 2.0
        rr['d_dif'] = rr['d_non'] - rr['d_cur']
        rr['n_cur'] = float(nc)
        rr['n_non'] = float(nn)
        rr['n_mean'] = (rr['n_cur'] + rr['n_non']) / 2.0
        rr['n_dif'] = rr['n_non'] - rr['n_cur']
        out.append(rr)
    return out


def vary(sub, ykey):
    gp = collections.defaultdict(list)
    for r in sub:
        gp[r['grp']].append(r[ykey])
    ok = {k for k, v in gp.items() if len(set(v)) > 1}
    return [r for r in sub if r['grp'] in ok]


def build(sub, cols):
    keys = sorted({r['grp'] for r in sub})
    gi = {k: i for i, k in enumerate(keys)}
    X = np.array([[r[c] for c in cols] for r in sub], dtype=float)
    g = np.array([gi[r['grp']] for r in sub])
    return X, g, keys


def fit_once(sub, cols, ykey):
    X, g, keys = build(sub, cols)
    y = np.array([r[ykey] for r in sub], dtype=float)
    return ConditionalLogit(y, X, groups=g).fit(disp=0, maxiter=300), len(keys)


def boot(sub, cols, ykey, Bn):
    X, g, keys = build(sub, cols)
    y = np.array([r[ykey] for r in sub], dtype=float)
    buckets = collections.defaultdict(list)
    for i, r in enumerate(sub):
        buckets[r['grp']].append(i)
    rng = np.random.default_rng(SEED)
    ks = sorted(buckets)
    out = []
    for b in range(Bn):
        pick = rng.integers(0, len(ks), len(ks))
        idx = np.array([i for j in pick for i in buckets[ks[j]]])
        yb = y[idx]
        if len(set(yb)) < 2:
            continue
        keys2 = sorted({sub[i]['grp'] for i in idx})
        gi2 = {k: i for i, k in enumerate(keys2)}
        gb = np.array([gi2[sub[i]['grp']] for i in idx])
        try:
            res = ConditionalLogit(yb, X[idx], groups=gb).fit(disp=0, maxiter=300)
        except Exception:
            continue
        out.append(res.params)
        if b % 500 == 499:
            print('   bootstrap %d/%d' % (b + 1, Bn), flush=True)
    return np.array(out)


def report(tag, sub, cols, names, ykey, Bn=B):
    t0 = time.time()
    res, nk = fit_once(sub, cols, ykey)
    bs = boot(sub, cols, ykey, Bn)
    lines = ['--- %s：%d 县 %d 村 ---' % (tag, nk, len(sub))]
    lines.append('%-16s %8s %8s %10s %18s %8s' %
                 ('变量', 'beta', 'OR', '聚类se', 'boot 95%CI', 'boot p'))
    for k, nm in enumerate(names):
        b = res.params[k]
        se = res.bse[k] if hasattr(res, 'bse') else float('nan')
        lo, hi = np.percentile(bs[:, k], [2.5, 97.5])
        p = 2 * min((bs[:, k] <= 0).mean(), (bs[:, k] >= 0).mean())
        lines.append('%-16s %8.3f %8.3f %10.3f [%7.3f,%7.3f] %8.3f'
                     % (nm, b, math.exp(b), se, lo, hi, p))
    txt = '\n'.join(lines)
    print(txt + '   (%.0fs)' % (time.time() - t0), flush=True)
    return res, bs, txt


BASE = ['dist', 'elev', 'rng']
XD = BASE + ['d_mean', 'd_dif']
XN = BASE + ['n_mean', 'n_dif']
ND = ['dist 到县城(log1p km)', 'elev 海拔(百米)', 'rng 起伏(百米)', 'd_mean 总体距离', 'd_dif 尚未公布−已公布']
NN = ['dist 到县城(log1p km)', 'elev 海拔(百米)', 'rng 起伏(百米)', 'n_mean 总体密度', 'n_dif 尚未公布−已公布']

out = []
out.append('=== 全国重估 v3（县分层条件Logit，县级 block bootstrap B=%d，SEED=%d）===' % (B, SEED))
out.append('')
out.append('分组：C1 截点 2015-12-31；C2 截点 2016-12-09（第四批认定当日）')
out.append('规格：M0 未裁决 10 条不参与分组 / M2 全部视为尚未公布 / M3 全部视为已公布')
out.append('')

MAIN = make('M0', '1')
A_sub = [r for r in MAIN if r['status'] in ('A_2017', 'B_2018promised', 'C_not_in_1044')]
B_sub = [r for r in MAIN if r['status'] in ('A_2017', 'B_2018promised')]
A_ok, B_ok = vary(A_sub, 'yA'), vary(B_sub, 'yB')
print('过程A 有县内变异 %d 村；过程B %d 村' % (len(A_ok), len(B_ok)))

out.append('[主规格 M0 / 截点 C1]')
out.append('')
out.append('[过程A] 是否进入 2017 年支持安排')
_, _, t = report('A 基准(距离+地形)', A_ok, BASE, ND[:3], 'yA')
out.append(t)
_, _, t = report('A 暴露(距离型)', A_ok, XD, ND, 'yA')
out.append(t)
_, _, t = report('A 暴露(计数型 10km)', A_ok, XN, NN, 'yA')
out.append(t)
out.append('')
out.append('[过程B] 当年支持 vs 拟次年支持')
_, _, t = report('B 基准(距离+地形)', B_ok, BASE, ND[:3], 'yB')
out.append(t)
_, _, t = report('B 暴露(距离型)', B_ok, XD, ND, 'yB')
out.append(t)
_, _, t = report('B 暴露(计数型 10km)', B_ok, XN, NN, 'yB')
out.append(t)

# ---- 规格敏感性 ----
out.append('')
out.append('=== 敏感性：未裁决 10 条的归属（截点 C1，距离型）===')
for spec in ['M2', 'M3']:
    S = make(spec, '1')
    a = vary([r for r in S if r['status'] in ('A_2017', 'B_2018promised', 'C_not_in_1044')], 'yA')
    b = vary([r for r in S if r['status'] in ('A_2017', 'B_2018promised')], 'yB')
    _, _, t = report('%s 过程A' % spec, a, XD, ND, 'yA')
    out.append(t)
    _, _, t = report('%s 过程B' % spec, b, XD, ND, 'yB')
    out.append(t)

# ---- 截点 C2 ----
out.append('')
out.append('=== 截点 C2 = 2016-12-09（认定当日已知信息，M0，距离型）===')
S2d = make('M0', '2')
a2 = vary([r for r in S2d if r['status'] in ('A_2017', 'B_2018promised', 'C_not_in_1044')], 'yA')
b2 = vary([r for r in S2d if r['status'] in ('A_2017', 'B_2018promised')], 'yB')
_, _, t = report('C2 过程A', a2, XD, ND, 'yA')
out.append(t)
_, _, t = report('C2 过程B', b2, XD, ND, 'yB')
out.append(t)

# ---- 坐标质量 ----
out.append('')
out.append('=== 敏感性：坐标质量（M0 / C1 / 距离型）===')
a_s1 = vary([r for r in A_sub if r['vid'] not in SUSPECT], 'yA')
b_s1 = vary([r for r in B_sub if r['vid'] not in SUSPECT], 'yB')
_, _, t = report('S1 剔坐标可疑 过程A', a_s1, XD, ND, 'yA', B)
out.append(t)
_, _, t = report('S1 剔坐标可疑 过程B', b_s1, XD, ND, 'yB', B)
out.append(t)
a_s2 = vary([r for r in A_sub if r['audit'] == 'inside'], 'yA')
b_s2 = vary([r for r in B_sub if r['audit'] == 'inside'], 'yB')
_, _, t = report('S2 仅通过县界检验 过程A', a_s2, XD, ND, 'yA', B)
out.append(t)
_, _, t = report('S2 仅通过县界检验 过程B', b_s2, XD, ND, 'yB', B)
out.append(t)

# ---- 省份逐一剔除（聚类 se，不重复 bootstrap）----
out.append('')
out.append('=== 敏感性：省份逐一剔除（M0 / C1 / 距离型，dist 系数）===')
for tag, sub, ykey in [('A', A_ok, 'yA'), ('B', B_ok, 'yB')]:
    provs = sorted({r['prov'] for r in sub})
    vals = []
    for p in provs:
        s = vary([r for r in sub if r['prov'] != p], ykey)
        try:
            res, nk = fit_once(s, XD, ykey)
            vals.append((p, res.params[0], len(s)))
        except Exception:
            pass
    bs = [v[1] for v in vals]
    out.append('%s：%d 省依次剔除，dist β ∈ [%.3f, %.3f]，符号恒定 %s'
               % (tag, len(vals), min(bs), max(bs),
                  '是' if (max(bs) < 0 or min(bs) > 0) else '否'))
    vals.sort(key=lambda x: abs(x[1]))
    out.append('   影响最大的省：' + '；'.join('%s β=%.3f(n=%d)' % v for v in vals[:3]))

# ---- 县逐一剔除 ----
out.append('')
out.append('=== 敏感性：县逐一剔除（M0 / C1 / 距离型，dist 系数）===')
for tag, sub, ykey in [('A', A_ok, 'yA'), ('B', B_ok, 'yB')]:
    counties = sorted({r['grp'] for r in sub})
    same = 0
    tot = 0
    vals = []
    for c in counties:
        s = vary([r for r in sub if r['grp'] != c], ykey)
        if len(s) < 20:
            continue
        try:
            res, nk = fit_once(s, XD, ykey)
        except Exception:
            continue
        tot += 1
        vals.append(res.params[0])
        if (res.params[0] < 0) == (np.sign(fit_once(sub, XD, ykey)[0].params[0]) < 0):
            same += 1
    out.append('%s：%d 县逐一剔除，与全样本同号 %d / %d（%.0f%%），β ∈ [%.3f, %.3f]'
               % (tag, tot, same, tot, 100.0 * same / max(tot, 1), min(vals), max(vals)))

# ---- 县等权 ----
out.append('')
out.append('=== 县等权比较（每县内 进入组−未进入组 的到县城距离均值差，单位 km）===')
def county_equal(sub, ykey, Bn=4000):
    gp = collections.defaultdict(list)
    for r in sub:
        if r[ykey] in (0, 1):
            gp[r['grp']].append(r)
    dif = {}
    for k, v in gp.items():
        a = [r['dist_km'] for r in v if r[ykey] == 1]
        b = [r['dist_km'] for r in v if r[ykey] == 0]
        if a and b:
            dif[k] = float(np.mean(a) - np.mean(b))
    ks = sorted(dif)
    arr = np.array([dif[k] for k in ks])
    rng = np.random.default_rng(SEED)
    bs = np.array([arr[rng.integers(0, len(arr), len(arr))].mean() for _ in range(Bn)])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    p = 2 * min((bs <= 0).mean(), (bs >= 0).mean())
    return len(ks), arr.mean(), lo, hi, p, int((arr < 0).sum())


for tag, sub, ykey in [('过程A', A_sub, 'yA'), ('过程B', B_sub, 'yB')]:
    n, m, lo, hi, p, neg = county_equal(sub, ykey)
    out.append('%s：%d 县，县等权均值差 %.2f km，95%%CI [%.2f, %.2f]，p %.3f，负向县 %d/%d'
               % (tag, n, m, lo, hi, p, neg, n))

# ---- 距离尺度换算 ----
out.append('')
out.append('=== dist 尺度说明 ===')
res, _ = fit_once(A_ok, XD, 'yA')
b_dist = res.params[0]
out.append('dist = log1p(到县城 km)，系数 %.3f 为"log1p 距离每增加 1"的效应' % b_dist)
for a, bb in [(5, 15), (10, 30), (5, 30)]:
    dl = math.log1p(bb) - math.log1p(a)
    out.append('   %2d km → %2d km：Δlog1p = %.3f，OR = %.3f（%.1f%%）'
               % (a, bb, dl, math.exp(b_dist * dl), 100 * (math.exp(b_dist * dl) - 1)))

p = os.path.join(D, 'master', 'national_results_v3.txt')
open(p, 'w', encoding='utf-8').write('\n'.join(out))
print()
print('写出 %s' % p)
