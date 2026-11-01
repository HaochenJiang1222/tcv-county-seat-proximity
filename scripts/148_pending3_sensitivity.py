# -*- coding: utf-8 -*-
"""148：2017 公告未匹配 3 条记录的预先限定误分类敏感性（第十七轮，任务一后半）

为什么只跑这一组：147 已证明 3 条未解决公告条目都是潜在漏匹配阳性
（第四批名录同县同名村唯一，且前三批名录全国无同名村），并已取得公开的
乡镇建制调整依据。因此可以预先限定唯一的对照：三条全不接受 vs 三条全接受。
不做逐条挑选，不据此更换主规格，也不重新寻找"更好的结果"。

变体：
  V0 冻结口径：三条一律不计入 2017 年公告（现 mother file 的 yA/yB）
  V1 全接受：787 -> A_2017（在 2017 支持名单），1190 / 1301 -> B_2018promised

两套模型都用两套推断：县聚类 se + 县级 block bootstrap（SEED=20261030）
  条件 Logit B=800（与冻结主结果一致）；线性概率模型 B=1000

输入  data/master/exposure_v3.csv        冻结分析文件
输出  data/master/pending3_sensitivity.txt
"""
import csv, sys, os, math, collections, time

sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from statsmodels.discrete.conditional_models import ConditionalLogit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data', 'master')
SEED = 20261030

# ---- 三条 ER 记录：vid -> (新 yA, 新 yB, 依据) ----
PEND = {
    '787': (1, 1, '红安县八里镇陡山村 = 2017 名单"八里湾镇陡山村"（乡镇名全称/简称差异，'
                  '红安县自 1987 年撤区设镇起仅有八里湾镇一个以"八里"开头的乡镇建制）'),
    '1190': (1, 0, '宣汉县马渡乡百丈村 = 2018 拟支持名单"马渡关镇百丈村"'
                   '（川府民政〔2016〕14 号 2016-10-25 批准、达市府函〔2016〕230 号 2016-12-05 批复，'
                   '撤销马渡乡设立马渡关镇，行政区域不变）'),
    '1301': (1, 0, '印江自治县新寨乡乐洋村 = 2018 拟支持名单"新寨镇乐洋村"'
                   '（黔府函〔2015〕50 号 2015-03-18，撤销新寨乡设置新寨镇；'
                   '划归峨岭街道的五个村为小云、大云、黔溪、上槽、小泽，不含乐洋村）'),
}

recs = list(csv.DictReader(open(os.path.join(D, 'exposure_v3.csv'), encoding='utf-8-sig')))
for r in recs:
    for k in ['dist', 'elev', 'rng', 'dist_km', 'bdist']:
        r[k] = float(r[k])
    r['yA'] = int(r['yA'])
    r['yB'] = int(r['yB'])
OUT = []


def P(s=''):
    OUT.append(s)
    print(s, flush=True)


def vary(sub, ykey):
    gp = collections.defaultdict(list)
    for r in sub:
        gp[r['grp']].append(r[ykey])
    ok = {k for k, v in gp.items() if len(set(v)) > 1}
    return [r for r in sub if r['grp'] in ok]


def build(sub, cols, ykey):
    keys = sorted({r['grp'] for r in sub})
    gi = {k: i for i, k in enumerate(keys)}
    X = np.array([[r[c] for c in cols] for r in sub], dtype=float)
    g = np.array([gi[r['grp']] for r in sub])
    y = np.array([r[ykey] for r in sub], dtype=float)
    return X, g, y, len(keys)


def clogit(sub, cols, names, ykey, Bn=800):
    X, g, y, nk = build(sub, cols, ykey)
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
        keys2 = sorted({sub[i]['grp'] for i in idx})
        gi2 = {k: i for i, k in enumerate(keys2)}
        gb = np.array([gi2[sub[i]['grp']] for i in idx])
        try:
            bs.append(ConditionalLogit(yb, X[idx], groups=gb).fit(disp=0, maxiter=300).params)
        except Exception:
            continue
    bs = np.array(bs)
    P('--- 条件 Logit：%d 县 %d 村（bootstrap %d） ---' % (nk, len(sub), len(bs)))
    P('%-22s %8s %8s %10s %18s %8s' % ('变量', 'beta', 'OR', '聚类se', 'boot 95%CI', 'boot p'))
    row = {}
    for k, nm in enumerate(names):
        b = res.params[k]
        se = res.bse[k]
        lo, hi = np.percentile(bs[:, k], [2.5, 97.5])
        p = 2 * min((bs[:, k] <= 0).mean(), (bs[:, k] >= 0).mean())
        P('%-22s %8.3f %8.3f %10.3f [%7.3f,%7.3f] %8.3f' % (nm, b, math.exp(b), se, lo, hi, p))
        if k == 0:
            row = dict(beta=b, se=se, lo=lo, hi=hi, p=p)
    P('   OR 口径换算：10→30 km 条件优势比 %.3f，CI [%.3f, %.3f]（优势比下降 %.1f%%）'
      % (math.exp(row['beta']), math.exp(row['lo']), math.exp(row['hi']),
         100 * (1 - math.exp(row['beta']))))
    return row


def lpm(sub, cols, names, ykey, Bn=2000):
    X = np.array([[r[c] for c in cols] for r in sub], dtype=float)
    y = np.array([r[ykey] for r in sub], dtype=float)
    keys = sorted({r['grp'] for r in sub})
    gi = {k: i for i, k in enumerate(keys)}
    g = np.array([gi[r['grp']] for r in sub])
    Xd, yd = X.copy(), y.copy()
    for k in keys:
        msk = g == gi[k]
        Xd[msk] -= X[msk].mean(axis=0)
        yd[msk] -= yd[msk].mean()
    beta, *_ = np.linalg.lstsq(Xd, yd, rcond=None)
    e = yd - Xd @ beta
    XtX_inv = np.linalg.pinv(Xd.T @ Xd)
    meat = np.zeros((Xd.shape[1], Xd.shape[1]))
    for k in keys:
        msk = g == gi[k]
        u = Xd[msk].T @ e[msk]
        meat += np.outer(u, u)
    G = len(keys)
    V = XtX_inv @ meat @ XtX_inv * G / max(G - 1, 1)
    se = np.sqrt(np.diag(V))
    buckets = collections.defaultdict(list)
    for i, r in enumerate(sub):
        buckets[r['grp']].append(i)
    rng = np.random.default_rng(SEED)
    ks = sorted(buckets)
    bs = []
    for b in range(Bn):
        pick = rng.integers(0, len(ks), len(ks))
        idx = np.array([i for j in pick for i in buckets[ks[j]]])
        Xb, yb = X[idx], y[idx]
        # 组内离差：必须用整数组码，字符串与整数比较会全部判否导致漏demean
        gb = np.array([gi[sub[i]['grp']] for i in idx])
        Xd2, yd2 = Xb.copy(), yb.copy()
        for cid in set(gb.tolist()):
            msk = gb == cid
            Xd2[msk] -= Xb[msk].mean(axis=0)
            yd2[msk] -= yd2[msk].mean()
        if len(set(np.round(yd2, 12))) < 2:
            continue
        try:
            bb, *_ = np.linalg.lstsq(Xd2, yd2, rcond=None)
        except Exception:
            continue
        if np.any(np.abs(bb) > 10):
            continue
        bs.append(bb)
    bs = np.array(bs)
    P('--- 县FE线性概率：%d 县 %d 村（bootstrap %d） ---' % (G, len(sub), len(bs)))
    P('%-22s %8s %10s %18s %8s' % ('变量', 'beta', '聚类se', 'boot 95%CI', 'boot p'))
    row = {}
    for k, nm in enumerate(names):
        lo, hi = np.percentile(bs[:, k], [2.5, 97.5])
        p = 2 * min((bs[:, k] <= 0).mean(), (bs[:, k] >= 0).mean())
        P('%-22s %8.3f %10.3f [%7.3f,%7.3f] %8.3f' % (nm, beta[k], se[k], lo, hi, p))
        if k == 0:
            row = dict(beta=beta[k], se=se[k], lo=lo, hi=hi, p=p)
    P('   概率尺度：10→30 km 相差 %.1f 个百分点' % (100 * row['beta'] * (math.log1p(30) - math.log1p(10))))
    return row


BASE = ['dist', 'elev', 'rng']
NM = ['dist 到县城(log1p km)', 'elev 海拔(百米)', 'rng 起伏(百米)']

P('=== 2017 公告未匹配 3 条记录：预先限定的误分类敏感性 ===')
P('变体 V0 = 三条全不接受（冻结口径，即正文主结果所用样本）')
P('变体 V1 = 三条全部接受（依据见下方逐条来源）')
P('')
for vid, (a, b, ev) in sorted(PEND.items(), key=lambda x: int(x[0])):
    P('  vid %s  V1 处理 yA=%d yB=%d  %s' % (vid, a, b, ev))
P('')

variants = {}
variants['V0'] = [dict(r) for r in recs]
v1 = [dict(r) for r in recs]
for r in v1:
    if r['vid'] in PEND:
        r['yA'], r['yB'] = PEND[r['vid']][0], PEND[r['vid']][1]
variants['V1'] = v1

summary = {}
for tag in ('V0', 'V1'):
    rows = variants[tag]
    A_all = list(rows)
    B_all = [r for r in rows if r['yA'] == 1]
    A_ok = vary(A_all, 'yA')
    B_ok = vary(B_all, 'yB')
    P('')
    P('########## 变体 %s ##########' % tag)
    P('过程A 有效组：%d 县 %d 村；过程B 有效组：%d 县 %d 村'
      % (len({r['grp'] for r in A_ok}), len(A_ok), len({r['grp'] for r in B_ok}), len(B_ok)))
    P('')
    P('[过程A] 进入 2017 年支持安排')
    summary[(tag, 'A_clogit')] = clogit(A_ok, BASE, NM, 'yA')
    P('')
    P('[过程B] 当年支持 vs 拟次年支持')
    summary[(tag, 'B_clogit')] = clogit(B_ok, BASE, NM, 'yB')
    P('')
    P('[过程A] 县FE线性概率，全样本')
    summary[(tag, 'A_lpm_all')] = lpm(A_all, BASE, NM, 'yA')
    P('')
    P('[过程A] 县FE线性概率，有效组')
    summary[(tag, 'A_lpm_ok')] = lpm(A_ok, BASE, NM, 'yA')

P('')
P('=== 结论核对（自动化判断，不含人为挑选）===')
a0, a1 = summary[('V0', 'A_clogit')], summary[('V1', 'A_clogit')]
P('  过程A 条件Logit dist：V0 %.3f (CI %.3f~%.3f, p %.3f) -> V1 %.3f (CI %.3f~%.3f, p %.3f)'
  % (a0['beta'], a0['lo'], a0['hi'], a0['p'], a1['beta'], a1['lo'], a1['hi'], a1['p']))
P('  符号是否一致：%s；V1 CI 是否仍不含 0：%s'
  % ('是' if a0['beta'] * a1['beta'] > 0 else '否',
     '是' if a1['lo'] * a1['hi'] > 0 else '否'))
for key, lab in (('A_lpm_all', '过程A LPM 全样本'), ('A_lpm_ok', '过程A LPM 有效组'),
                 ('B_clogit', '过程B 条件Logit')):
    s0, s1 = summary[('V0', key)], summary[('V1', key)]
    P('  %s：%.3f (p %.3f) -> %.3f (p %.3f)'
      % (lab, s0['beta'], s0['p'], s1['beta'], s1['p']))

open(os.path.join(D, 'pending3_sensitivity.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
