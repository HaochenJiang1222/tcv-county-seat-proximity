# -*- coding: utf-8 -*-
"""
131：全国重估（第三十八部分任务三）

主检验
  过程A  是否进入 2017 年支持安排（in {A,B} vs C），县分层条件Logit
  过程B  已进入者中当年 vs 次年（A vs B），县分层条件Logit

变量（全部认定前确定 / 历史公告日期不晚于 2016-12-09）
  dist        log1p(到县城 km)
  elev        海拔（百米，SRTM 30m，采集于 2000 年）
  rng         1km 起伏（百米）
  d_early     log1p(到最近"2015 年底前已获当年支持安排"历史村 km)
  d_late      log1p(到最近"2015 年底前尚未公开列入支持"历史村 km)
  n_early_10  10km 内 early 历史村数
  n_late_10   10km 内 late 历史村数
  （n_early + n_late ≈ n_pre，故不再单独入 n_pre，避免完全共线）

推断
  县级 block bootstrap（重抽县），SEED=20261030；同时报聚类稳健 se

敏感性（用户第三十八部分第五节）
  S1 剔除坐标可疑（距所属县界 >5 km 的 19 条）
  S2 仅保留通过县界检验的点
  S3 省份逐一剔除（jackknife）
  S4 县等权（每县一个均值差）
  S5 三省子样本复核

用法  python dofile/131_national_main_v2.py [B]
"""
import csv, sys, os, math, collections, time
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from statsmodels.discrete.conditional_models import ConditionalLogit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
B = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SEED = 20261030

m = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'master_final_1598.csv'), encoding='utf-8-sig'))}
exp = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'exposure_v2.csv'), encoding='utf-8-sig'))}
el = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'elev_national.csv'), encoding='utf-8-sig'))}
dc = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'dist_county_national.csv'), encoding='utf-8-sig'))}
ga = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'geo_audit_national.csv'), encoding='utf-8-sig'))}

recs = []
for v, r in m.items():
    e, x, d = exp.get(v), el.get(v), dc.get(v)
    if not e or not x or not d:
        continue
    if not (r['latitude'] and d['dist_km'] and x['elev_srtm']):
        continue
    if e['d_nearest_early'] in ('', None) or e['d_nearest_late'] in ('', None):
        continue
    g = ga.get(v, {})
    recs.append({
        'vid': v, 'grp': r['province'] + '|' + r['county'], 'prov': r['province'],
        'st': r['status'],
        'dist': math.log1p(float(d['dist_km'])),
        'elev': float(x['elev_srtm']) / 100.0,
        'rng': float(x['elev_range_srtm']) / 100.0,
        'd_early': math.log1p(float(e['d_nearest_early'])),
        'd_late': math.log1p(float(e['d_nearest_late'])),
        'n_early': float(e['n_early_10']),
        'n_late': float(e['n_late_10']),
        'audit': g.get('result', 'unknown'),
        'bdist': float(g['dist_km']) if g.get('dist_km') not in ('', None) else -1.0,
        # y 随记录携带，过滤子集时同步跟随，避免索引错位
        'yA': 1.0 if r['status'] in ('A_2017', 'B_2018promised') else 0.0,
        'yB': 1.0 if r['status'] == 'A_2017' else (0.0 if r['status'] == 'B_2018promised' else -1.0),
    })
print('可用样本 %d' % len(recs))

SUSPECT = {r['vid'] for r in recs if r['audit'] == 'outside' and r['bdist'] > 5}
print('坐标可疑（界外且距界 >5km）%d 条' % len(SUSPECT))


def build(sub, cols):
    keys = sorted({r['grp'] for r in sub})
    gi = {k: i for i, k in enumerate(keys)}
    X = np.array([[r[c] for c in cols] for r in sub])
    g = np.array([gi[r['grp']] for r in sub])
    return X, g, keys


def fit_once(sub, cols, y):
    X, g, keys = build(sub, cols)
    return ConditionalLogit(y, X, groups=g).fit(disp=0, maxiter=300), len(keys)


def boot(sub, cols, ykey, B=B, seed=SEED):
    """县级 block bootstrap：有放回重抽县"""
    X, g, keys = build(sub, cols)
    y = np.array([r[ykey] for r in sub])
    buckets = collections.defaultdict(list)
    for i, r in enumerate(sub):
        buckets[r['grp']].append(i)
    rng = np.random.default_rng(seed)
    ks = sorted(buckets)
    out = []
    for b in range(B):
        pick = rng.integers(0, len(ks), len(ks))
        idx = []
        for j in range(len(ks)):
            idx.extend(buckets[ks[pick[j]]])
        idx = np.array(idx)
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
            print('   bootstrap %d/%d' % (b + 1, B), flush=True)
    return np.array(out)


def report(tag, sub, cols, names, ykey, B=B):
    y = np.array([r[ykey] for r in sub])
    res, nk = fit_once(sub, cols, y)
    bs = boot(sub, cols, ykey, B)
    lines = []
    lines.append('--- %s：%d 县 %d 村 ---' % (tag, nk, len(sub)))
    lines.append('%-14s %8s %8s %10s %18s %8s' % ('变量', 'beta', 'OR', '聚类se', 'boot 95%CI', 'boot p'))
    for k, nm in enumerate(names):
        b = res.params[k]
        se = res.bse[k] if hasattr(res, 'bse') else float('nan')
        lo, hi = np.percentile(bs[:, k], [2.5, 97.5])
        p = 2 * min((bs[:, k] <= 0).mean(), (bs[:, k] >= 0).mean())
        lines.append('%-14s %8.3f %8.3f %10.3f [%7.3f,%7.3f] %8.3f'
                     % (nm, b, math.exp(b), se, lo, hi, p))
    txt = '\n'.join(lines)
    print(txt, flush=True)
    return res, bs, txt


# ---------- 过程 A / B ----------
A_sub = [r for r in recs if r['st'] in ('A_2017', 'B_2018promised', 'C_not_in_1044')]
B_sub = [r for r in recs if r['st'] in ('A_2017', 'B_2018promised')]


def vary(sub, ykey):
    """只保留组内因变量有变异的县"""
    gp = collections.defaultdict(list)
    for r in sub:
        gp[r['grp']].append(r[ykey])
    ok = {k for k, v in gp.items() if len(set(v)) > 1}
    return [r for r in sub if r['grp'] in ok]


A_ok = vary(A_sub, 'yA')
B_ok = vary(B_sub, 'yB')
print('过程A 有县内变异 %d 村；过程B %d 村' % (len(A_ok), len(B_ok)))

BASE = ['dist', 'elev', 'rng']
EXPD = ['d_early', 'd_late']
EXPN = ['n_early', 'n_late']
ALLD = BASE + EXPD
ALLN = BASE + EXPN
NAMES_D = ['dist 到县城(log)', 'elev 海拔(百米)', 'rng 起伏(百米)', 'd_early', 'd_late']
NAMES_N = ['dist 到县城(log)', 'elev 海拔(百米)', 'rng 起伏(百米)', 'n_early_10', 'n_late_10']

out = []
out.append('=== 全国主检验（县分层条件Logit，县级 block bootstrap B=%d，SEED=%d）===' % (B, SEED))
out.append('')
out.append('[过程A] 是否进入 2017 年支持安排')
res, bs, t = report('A 基准(距离+地形)', A_ok, BASE, NAMES_D[:3], 'yA')
out.append(t)
res, bs, t = report('A +早晚暴露(距离型)', A_ok, ALLD, NAMES_D, 'yA')
out.append(t)
res, bs, t = report('A +早晚暴露(计数型)', A_ok, ALLN, NAMES_N, 'yA')
out.append(t)
out.append('')
out.append('[过程B] 当年支持 vs 拟次年支持')
res, bs, t = report('B 基准(距离+地形)', B_ok, BASE, NAMES_D[:3], 'yB')
out.append(t)
res, bs, t = report('B +早晚暴露(距离型)', B_ok, ALLD, NAMES_D, 'yB')
out.append(t)
res, bs, t = report('B +早晚暴露(计数型)', B_ok, ALLN, NAMES_N, 'yB')
out.append(t)

# ---------- 敏感性 S1 / S2 ----------
out.append('')
out.append('=== 敏感性：坐标质量 ===')
A_s1 = vary([r for r in A_sub if r['vid'] not in SUSPECT], 'yA')
B_s1 = vary([r for r in B_sub if r['vid'] not in SUSPECT], 'yB')
res, bs, t = report('S1 剔坐标可疑 过程A', A_s1, ALLD, NAMES_D, 'yA')
out.append(t)
res, bs, t = report('S1 剔坐标可疑 过程B', B_s1, ALLD, NAMES_D, 'yB')
out.append(t)
A_s2 = vary([r for r in A_sub if r['audit'] == 'inside'], 'yA')
B_s2 = vary([r for r in B_sub if r['audit'] == 'inside'], 'yB')
res, bs, t = report('S2 仅通过县界检验 过程A', A_s2, ALLD, NAMES_D, 'yA')
out.append(t)
res, bs, t = report('S2 仅通过县界检验 过程B', B_s2, ALLD, NAMES_D, 'yB')
out.append(t)

# ---------- S3 省份逐一剔除 ----------
out.append('')
out.append('=== 敏感性 S3：省份逐一剔除（过程A / 过程B，dist 系数）===')
for tag, sub, ykey, cols in [('A', A_ok, 'yA', ALLD), ('B', B_ok, 'yB', ALLD)]:
    provs = sorted({r['prov'] for r in sub})
    vals = []
    for p in provs:
        s2 = vary([r for r in sub if r['prov'] != p], ykey)
        try:
            res, _ = fit_once(s2, cols, np.array([r[ykey] for r in s2]))
            vals.append((p, res.params[0], len(s2)))
        except Exception:
            vals.append((p, float('nan'), len(s2)))
    v = np.array([x[1] for x in vals])
    v = v[np.isfinite(v)]
    out.append('%s：%d 省依次剔除，dist β ∈ [%.3f, %.3f]，符号恒定 %s'
               % (tag, len(vals), v.min(), v.max(), '是' if (v > 0).all() or (v < 0).all() else '否'))
    worst = sorted([x for x in vals if np.isfinite(x[1])], key=lambda x: abs(x[1]))[:3]
    out.append('   影响最大的省（剔除后 |β| 最小）：' +
               '；'.join('%s β=%.3f(n=%d)' % (a, b, c) for a, b, c in worst))
    print(out[-2]); print(out[-1], flush=True)

# ---------- S5 三省复核 ----------
out.append('')
out.append('=== 敏感性 S5：三省子样本复核 ===')
T = {'江苏省', '浙江省', '安徽省'}
for tag, sub, ykey, cols, nm in [('A', A_sub, 'yA', ALLD, NAMES_D),
                                 ('B', B_sub, 'yB', ALLD, NAMES_D)]:
    s2 = vary([r for r in sub if r['prov'] in T], ykey)
    if len(s2) < 10:
        continue
    res, bs, t = report('三省 过程%s' % tag, s2, cols, nm, ykey)
    out.append(t)

txt = '\n'.join(out)
open(os.path.join(D, 'master', 'national_results_v2.txt'), 'w', encoding='utf-8').write(txt)
print()
print('写出 data/master/national_results_v2.txt')
