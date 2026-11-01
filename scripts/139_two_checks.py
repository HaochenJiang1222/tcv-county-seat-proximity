# -*- coding: utf-8 -*-
"""
139：定稿前的两项识别审查（第四十部分第三节）

检验一 县规模异质性（探索性）
  过程A条件Logit加入 dist × log(县内第四批村数)
  目的：判断不同村落规模县的距离梯度是否真正不同
  定位：探索性。6–9村与10村以上的方向差异是看到结果之后发现的，
        不得据此重新划组并挑选显著的一组当作原定理论预测

检验二 全样本与有效组比较
  分别在全部有坐标的第四批村与具有县内结果变化的样本中，报告县固定效应
  线性概率模型（组内离差估计 + 县级 block bootstrap）
  目的：区分"所有认定村落的平均关联"与"条件Logit实际使用样本的关联"

推断：县级 block bootstrap，SEED=20261030
用法  python dofile/139_two_checks.py [B]
"""
import csv, os, sys, math, collections
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from statsmodels.discrete.conditional_models import ConditionalLogit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
B = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SEED = 20261030

exp = list(csv.DictReader(open(os.path.join(D, 'master', 'exposure_v3.csv'),
                               encoding='utf-8-sig')))
m = list(csv.DictReader(open(os.path.join(D, 'master', 'master_final_1598.csv'),
                             encoding='utf-8-sig')))
ncohort = collections.Counter(r['province'] + '|' + r['county'] for r in m)

recs = []
for r in exp:
    if r['dist'] in ('', None) or r['elev'] in ('', None):
        continue
    for k in ['dist', 'elev', 'rng', 'dist_km']:
        r[k] = float(r[k])
    r['yA'] = int(r['yA'])
    r['yB'] = int(r['yB'])
    r['n_cohort'] = ncohort[r['grp']]
    r['lncohort'] = math.log(r['n_cohort'])
    r['d_cur'] = math.log1p(float(r['d_M0_cur1']))
    r['d_non'] = math.log1p(float(r['d_M0_non1']))
    r['d_mean'] = (r['d_cur'] + r['d_non']) / 2.0
    r['d_dif'] = r['d_non'] - r['d_cur']
    r['x_int'] = r['dist'] * r['lncohort']
    recs.append(r)
print('分析样本 %d 村，%d 县' % (len(recs), len({r['grp'] for r in recs})))

A_all = [r for r in recs if r['status'] in ('A_2017', 'B_2018promised', 'C_not_in_1044')]


def vary(sub, ykey='yA'):
    gp = collections.defaultdict(list)
    for r in sub:
        gp[r['grp']].append(r[ykey])
    ok = {k for k, v in gp.items() if len(set(v)) > 1}
    return [r for r in sub if r['grp'] in ok]


A_ok = vary(A_all)
print('过程A 全部 %d 村 %d 县；有县内变异 %d 村 %d 县'
      % (len(A_all), len({r['grp'] for r in A_all}), len(A_ok), len({r['grp'] for r in A_ok})))

out = []


def P(s=''):
    print(s)
    out.append(s)


P('=== 139 定稿前两项识别审查（县级 block bootstrap B=%d，SEED=%d）===' % (B, SEED))
P('')


# ---------- 通用：条件Logit ----------
def clogit_boot(sub, cols, names, ykey='yA', Bn=B):
    keys = sorted({r['grp'] for r in sub})
    gi = {k: i for i, k in enumerate(keys)}
    X = np.array([[r[c] for c in cols] for r in sub], dtype=float)
    g = np.array([gi[r['grp']] for r in sub])
    y = np.array([r[ykey] for r in sub], dtype=float)
    res = ConditionalLogit(y, X, groups=g).fit(disp=0, maxiter=300)
    buckets = collections.defaultdict(list)
    for i, r in enumerate(sub):
        buckets[r['grp']].append(i)
    rng = np.random.default_rng(SEED)
    ks = sorted(buckets)
    bs = []
    for b in range(Bn):
        pick = rng.integers(0, len(ks), len(ks))
        idx = np.array([i for j in pick for i in buckets[ks[j]]])
        yb = y[idx]
        if len(set(yb)) < 2:
            continue
        k2 = sorted({sub[i]['grp'] for i in idx})
        gi2 = {k: i for i, k in enumerate(k2)}
        try:
            r2 = ConditionalLogit(yb, X[idx], groups=np.array([gi2[sub[i]['grp']] for i in idx])
                                  ).fit(disp=0, maxiter=300)
        except Exception:
            continue
        bs.append(r2.params)
        if b % 500 == 499:
            print('   bootstrap %d/%d' % (b + 1, Bn), flush=True)
    bs = np.array(bs)
    P('--- %d 县 %d 村 ---' % (len(keys), len(sub)))
    P('%-22s %8s %10s %18s %8s' % ('变量', 'beta', '聚类se', 'boot 95%CI', 'boot p'))
    for k, nm in enumerate(names):
        lo, hi = np.percentile(bs[:, k], [2.5, 97.5])
        p = 2 * min((bs[:, k] <= 0).mean(), (bs[:, k] >= 0).mean())
        P('%-22s %8.3f %10.3f [%7.3f,%7.3f] %8.3f' % (nm, res.params[k], res.bse[k], lo, hi, p))
    return res, bs


# ---------- 检验一：县规模异质性 ----------
P('[检验一] 县规模异质性：dist × log(县内第四批村数)（探索性）')
P('县内第四批村数分布（过程A有效样本）：中位 %.0f，范围 %d–%d'
  % (np.median([r['n_cohort'] for r in A_ok]),
     min(r['n_cohort'] for r in A_ok), max(r['n_cohort'] for r in A_ok)))
res, bs = clogit_boot(A_ok, ['dist', 'elev', 'rng', 'd_mean', 'd_dif', 'x_int'],
                      ['dist 到县城(log1p km)', 'elev', 'rng', 'd_mean', 'd_dif',
                       'dist × log(县内村数)'], 'yA')
P('')
P('   dist 在不同县规模下的边际效应（β_dist + β_int × log n）')
for n in [2, 3, 5, 9, 15, 25]:
    me = bs[:, 0] + bs[:, 5] * math.log(n)
    lo, hi = np.percentile(me, [2.5, 97.5])
    p = 2 * min((me <= 0).mean(), (me >= 0).mean())
    b = res.params[0] + res.params[5] * math.log(n)
    P('      n=%2d：β %7.3f  OR(log1p+1) %.3f  95%%CI [%6.3f,%6.3f]  p %.3f'
      % (n, b, math.exp(b), lo, hi, p))
P('')
P('   注：该检验为探索性。6–9村与10村以上方向不同是在看到描述结果后发现的，')
P('       不得据此重新划组并把其中显著的一组当作原定理论预测')

# ---------- 检验二：全样本 vs 有效组的县FE线性概率模型 ----------
P('')
P('[检验二] 县固定效应线性概率模型：全样本 vs 有效组')


def lpm_fe(sub, cols, ykey='yA', Bn=2000):
    """组内离差 OLS + 县级 block bootstrap"""
    keys = sorted({r['grp'] for r in sub})
    gi = {k: i for i, k in enumerate(keys)}
    X = np.array([[r[c] for c in cols] for r in sub], dtype=float)
    y = np.array([r[ykey] for r in sub], dtype=float)
    g = np.array([gi[r['grp']] for r in sub])
    # 组内离差
    Xd = X.copy()
    yd = y.copy()
    for k in range(len(keys)):
        msk = g == k
        if msk.sum() == 0:
            continue
        Xd[msk] -= X[msk].mean(axis=0)
        yd[msk] -= y[msk].mean()
    keep = np.abs(yd).sum() > 0
    beta, *_ = np.linalg.lstsq(Xd, yd, rcond=None)
    # 聚类 se
    e = yd - Xd @ beta
    XtX_inv = np.linalg.pinv(Xd.T @ Xd)
    meat = np.zeros((Xd.shape[1], Xd.shape[1]))
    for k in range(len(keys)):
        msk = g == k
        u = Xd[msk].T @ e[msk]
        meat += np.outer(u, u)
    G = len(keys)
    V = XtX_inv @ meat @ XtX_inv * G / max(G - 1, 1)
    se = np.sqrt(np.diag(V))
    # bootstrap
    buckets = collections.defaultdict(list)
    for i, r in enumerate(sub):
        buckets[r['grp']].append(i)
    rng = np.random.default_rng(SEED)
    ks = sorted(buckets)
    bs = []
    for b in range(Bn):
        pick = rng.integers(0, len(ks), len(ks))
        idx = np.array([i for j in pick for i in buckets[ks[j]]])
        Xb, yb, gb = X[idx], y[idx], np.array([r['grp'] for r in [sub[i] for i in idx]])
        k2 = sorted(set(gb))
        gi2 = {k: i for i, k in enumerate(k2)}
        g2 = np.array([gi2[x] for x in gb])
        Xd2 = Xb.copy()
        yd2 = yb.copy()
        for k in range(len(k2)):
            msk = g2 == k
            Xd2[msk] -= Xb[msk].mean(axis=0)
            yd2[msk] -= yb[msk].mean()
        if len(set(np.round(yd2, 12))) < 2:
            continue
        try:
            bb, *_ = np.linalg.lstsq(Xd2, yd2, rcond=None)
        except Exception:
            continue
        if np.any(np.abs(bb) > 10):
            continue
        bs.append(bb)
    return beta, se, np.array(bs), len(keys), len(sub)


COLS = ['dist', 'elev', 'rng']
NM = ['dist 到县城(log1p km)', 'elev', 'rng']
for tag, sub in [('全样本（全部有坐标的第四批村）', A_all),
                 ('有效组（县内结果有变异）', A_ok)]:
    beta, se, bs, nk, nv = lpm_fe(sub, COLS)
    P('')
    P('--- %s：%d 县 %d 村 ---' % (tag, nk, nv))
    P('%-22s %8s %10s %18s %8s' % ('变量', 'beta', '聚类se', 'boot 95%CI', 'boot p'))
    for k, nm in enumerate(NM):
        lo, hi = np.percentile(bs[:, k], [2.5, 97.5])
        p = 2 * min((bs[:, k] <= 0).mean(), (bs[:, k] >= 0).mean())
        P('%-22s %8.3f %10.3f [%7.3f,%7.3f] %8.3f' % (nm, beta[k], se[k], lo, hi, p))
    dl = math.log1p(30) - math.log1p(10)
    P('   dist 系数含义（LPM，概率尺度）：10→30 km 概率变化 %.1f 个百分点'
      % (100 * beta[0] * dl))

P('')
P('   注：县固定效应吸收县内均值，结果全为 0 或全为 1 的县组内离差为 0，')
P('       对斜率无贡献。因此两样本的差别主要来自加权方式而非样本范围；')
P('       条件Logit 与线性概率模型回答的是不同加权下的问题，数值差异不等于模型错误。')

# ---------- 尺度换算核对 ----------
P('')
P('=== dist 尺度换算核对（β = −0.370，CI [−0.838, −0.067]）===')
dl = math.log1p(30) - math.log1p(10)
P('   Δlog1p(10→30 km) = %.3f' % dl)
for b in [-0.370, -0.838, -0.067]:
    P('   β %.3f → OR %.3f' % (b, math.exp(b * dl)))
P('   点估计 OR 0.683（优势比下降 31.7%%）；区间 OR [0.420, 0.933]')
P('   表述规则：是条件优势比下降，不是进入概率下降；县城直线距离衡量空间区位，不等同道路通行成本')

p = os.path.join(D, 'master', 'checks_139.txt')
open(p, 'w', encoding='utf-8').write('\n'.join(out))
print()
print('写出 %s' % p)
