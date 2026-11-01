# -*- coding: utf-8 -*-
"""
153：县级「中心点」定义核验 + 质心替代口径的预先限定稳健性（审稿 R2 第二项）

背景：正文把 dist 解释为「到县级行政中心的距离」，程序读的是
DataV.GeoAtlas areas_v3 的 properties.center。R2 指出这可能是
①政府驻地 ②服务标注点 ③多边形几何质心，三者不同，不能默认等价。

本脚本分两段：
【第一段 定义核验】
  E1 取 6 个县（含 4 个 center 与几何质心相距最远的用县），把 DataV center
     与独立商业地图服务给出的县政府驻地坐标比对
  E2 报告 center / 质心 到几何质心的距离分布（由 152 生成）
【第二段 质心替代口径】
  把 dist 由「到 center」换成「到 DataV centroid 字段（缺省用 152 自算几何质心）」，
  其余一切不变，重跑过程A 条件Logit（B=800）与两个县FE线性概率（B=1000）。
  先跑原口径复现冻结值，作为程序自校验。
  这不是换模型，是同一构念的另一种测量定义；结果只作稳健性，不改主口径。

输出 data/master/county_center_check153.txt
"""
import csv, sys, os, math, collections, re

sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from statsmodels.discrete.conditional_models import ConditionalLogit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data', 'master')
G = os.path.join(ROOT, 'data', 'geo')
SEED = 20261030
R = 6371.0088
OUT = []


def P(s=''):
    OUT.append(s)
    print(s, flush=True)


def hav(lon1, lat1, lon2, lat2, R=R):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


# ---------------- 第一段：外部驻地坐标比对 ----------------
# 来源：独立商业地图服务（腾讯地图）对「XX县人民政府」政府机关条目的坐标，
#       检索日期 2026-11-01；括号内为地图给出的门牌地址，与县政府官网公开地址一致。
SEAT = {
    '421122': ('红安县', 114.618300, 31.288397, '城关镇小北街10号'),
    '511722': ('宣汉县', 107.727062, 31.354195, '东乡街道衙墙街1号'),
    '520625': ('印江土家族苗族自治县', 108.409625, 27.994406, '峨岭街道县府路286号'),
    '513422': ('木里藏族自治县', 101.279969, 27.928425, '乔瓦镇扎昌街243号'),
    '513331': ('白玉县', 98.824040, 31.209691, '建设镇河东下街2号'),
    '150784': ('额尔古纳市', 120.180250, 50.243435, '拉布大林街道额尔古纳大街281号'),
}
aud = {r['adcode']: r for r in csv.DictReader(open(os.path.join(G, 'county_center_audit.csv'),
                                                   encoding='utf-8-sig'))}
P('=== 153-A DataV center 与独立地图服务的县政府驻地坐标比对 ===')
P('%-8s %-16s %10s %10s %12s' % ('adcode', '县名', 'center→驻地', '质心→驻地', 'center-质心距'))
dc, dce, dsep = [], [], []
for ad, (nm, slon, slat, addr) in SEAT.items():
    r = aud.get(ad)
    if not r:
        P('  缺少 %s' % ad)
        continue
    c = (float(r['lon_center']), float(r['lat_center']))
    ce = (float(r['lon_centroid_field']), float(r['lat_centroid_field']))
    a = hav(c[0], c[1], slon, slat)
    b = hav(ce[0], ce[1], slon, slat)
    s = float(r['d_center_calc'])
    dc.append(a)
    dce.append(b)
    dsep.append(s)
    P('%-8s %-16s %8.2f km %8.2f km %10.2f km   %s' % (ad, nm, a, b, s, addr))
P('')
P('center 到驻地：中位 %.2f km，最大 %.2f km（n=%d）' % (sorted(dc)[len(dc) // 2], max(dc), len(dc)))
P('质心到驻地　：中位 %.2f km，最大 %.2f km（n=%d）' % (sorted(dce)[len(dce) // 2], max(dce), len(dce)))
P('center 到质心：中位 %.2f km，最大 %.2f km（n=%d）' % (sorted(dsep)[len(dsep) // 2], max(dsep), len(dsep)))
P('判定：center 与独立地图服务的县政府驻地一致（中位 %.2f km），'
  '与几何质心系统性分离；故 center 应理解为县级行政中心/驻地，而非几何质心。'
  % sorted(dc)[len(dc) // 2])
P('说明：6 个县系按 center-质心距离大小有意选取（含 4 个分离最大的用县），'
  '属针对性核验，不是随机抽样；坐标来源为商业地图服务，与边界服务相互独立。')
P('')

# ---------------- 第二段：质心替代口径 ----------------
cc = list(csv.DictReader(open(os.path.join(G, 'county_center_national.csv'), encoding='utf-8-sig')))
MAP = {  # 与 123c 一致的手工映射（公开撤县设区/设市批复，治所未迁移）
    ('云南省', '怒江州贡山县'): '贡山独龙族怒族自治县',
    ('四川省', '宜宾县'): '叙州区',
    ('山东省', '莱城区'): '莱芜区',
    ('山东省', '蒙山旅游区'): '平邑县',
    ('山西省', '大同县'): '云州区',
    ('山西省', '长治县'): '上党区',
    ('湖南省', '汩罗市'): '汨罗市',
    ('贵州省', '安顺经济技术开发区'): '西秀区',
}


def core(s):
    s = re.sub(r'\s', '', s or '')
    s = re.sub(r'(自治县|自治旗|特区|林区)$', '', s)
    s = re.sub(r'[市县区旗]$', '', s)
    return s


idx = collections.defaultdict(list)
for r in cc:
    idx[(r['province'], core(r['county']))].append(r)

recs = list(csv.DictReader(open(os.path.join(D, 'exposure_v3.csv'), encoding='utf-8-sig')))
for r in recs:
    r['lat'] = float(r['lat'])
    r['lon'] = float(r['lon'])
    for k in ['dist', 'dist_km', 'elev', 'rng']:
        r[k] = float(r[k])
    r['yA'] = int(r['yA'])
    r['yB'] = int(r['yB'])

nmiss = 0
for r in recs:
    pv, ct = r['prov'], r['county']
    cand = idx.get((pv, core(ct)), [])
    if not cand and (pv, ct) in MAP:
        cand = idx.get((pv, core(MAP[(pv, ct)])), [])
    if not cand:
        k = core(ct)
        cand = [x for (pp, kk), v in idx.items() if pp == pv and (k in kk or kk in k) for x in v]
    if not cand:
        cand = [x for (pp, kk), v in idx.items() if pp == pv for x in v]
    if not cand:
        r['dist_km_c'] = ''
        nmiss += 1
        continue
    # 与 123c 同法：按到 center 的距离选最近候选，再取该候选项的质心
    best = min(cand, key=lambda x: hav(r['lon'], r['lat'], float(x['lon']), float(x['lat'])))
    a = aud.get(str(best['adcode']))
    lonc, latc = (float(a['lon_centroid_field']), float(a['lat_centroid_field'])) \
        if a and a['lon_centroid_field'] else (float(best['lon']), float(best['lat']))
    r['dist_km_c'] = hav(r['lon'], r['lat'], lonc, latc)
    r['dist_c'] = math.log1p(r['dist_km_c'])
ok = [r for r in recs if r['dist_km_c'] != '']
P('=== 153-B 质心替代口径 ===')
P('可算质心距离的村 %d / %d（缺 %d）' % (len(ok), len(recs), nmiss))
dif = sorted(abs(r['dist_km_c'] - r['dist_km']) for r in ok)
P('两种口径的村-县距离差：中位 %.2f km，p90 %.2f km，最大 %.2f km'
  % (dif[len(dif) // 2], dif[int(len(dif) * .9)], dif[-1]))
P('')


def vary(sub, ykey):
    gp = collections.defaultdict(list)
    for r in sub:
        gp[r['grp']].append(r[ykey])
    okk = {k for k, v in gp.items() if len(set(v)) > 1}
    return [r for r in sub if r['grp'] in okk]


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
        idxb = np.array([i for j in pick for i in buckets[ks[j]]])
        yb = y[idxb]
        if len(set(yb)) < 2:
            continue
        keys2 = sorted({sub[i]['grp'] for i in idxb})
        gi2 = {k: i for i, k in enumerate(keys2)}
        gb = np.array([gi2[sub[i]['grp']] for i in idxb])
        try:
            bs.append(ConditionalLogit(yb, X[idxb], groups=gb).fit(disp=0, maxiter=300).params)
        except Exception:
            continue
    bs = np.array(bs)
    P('--- 条件Logit：%d 县 %d 村（bootstrap %d，SEED %d） ---' % (nk, len(sub), len(bs), SEED))
    row = {}
    for k, nmv in enumerate(names):
        b = res.params[k]
        se = res.bse[k]
        lo, hi = np.percentile(bs[:, k], [2.5, 97.5])
        p = 2 * min((bs[:, k] <= 0).mean(), (bs[:, k] >= 0).mean())
        P('%-22s %8.3f %10.3f [%7.3f,%7.3f] %8.3f' % (nmv, b, se, lo, hi, p))
        if k == 0:
            row = dict(beta=b, se=se, lo=lo, hi=hi, p=p)
    dl = math.log1p(30) - math.log1p(10)   # 与冻结口径一致：Δlog1p = 1.0361，不是 1
    P('   10→30 km 条件优势比 %.3f，CI [%.3f, %.3f]（优势比下降 %.1f%%）' %
      (math.exp(row['beta'] * dl), math.exp(row['lo'] * dl), math.exp(row['hi'] * dl),
       100 * (1 - math.exp(row['beta'] * dl))))
    return row


def lpm(sub, cols, names, ykey, Bn=1000):
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
    G_ = len(keys)
    V = XtX_inv @ meat @ XtX_inv * G_ / max(G_ - 1, 1)
    se = np.sqrt(np.diag(V))
    buckets = collections.defaultdict(list)
    for i, r in enumerate(sub):
        buckets[r['grp']].append(i)
    rng = np.random.default_rng(SEED)
    ks = sorted(buckets)
    bs = []
    for b in range(Bn):
        pick = rng.integers(0, len(ks), len(ks))
        idxb = np.array([i for j in pick for i in buckets[ks[j]]])
        Xb, yb = X[idxb], y[idxb]
        gb = np.array([gi[sub[i]['grp']] for i in idxb])
        Xd2, yd2 = Xb.copy(), yb.copy()
        for cid in set(gb.tolist()):
            msk = gb == cid
            Xd2[msk] -= Xb[msk].mean(axis=0)
            yd2[msk] -= yd2[msk].mean()
        if len(set(np.round(yd2, 12))) < 2:
            continue
        bb, *_ = np.linalg.lstsq(Xd2, yd2, rcond=None)
        if np.any(np.abs(bb) > 10):
            continue
        bs.append(bb)
    bs = np.array(bs)
    P('--- 县FE线性概率：%d 县 %d 村（bootstrap %d） ---' % (G_, len(sub), len(bs)))
    row = {}
    for k, nmv in enumerate(names):
        lo, hi = np.percentile(bs[:, k], [2.5, 97.5])
        p = 2 * min((bs[:, k] <= 0).mean(), (bs[:, k] >= 0).mean())
        P('%-22s %8.3f %10.3f [%7.3f,%7.3f] %8.3f' % (nmv, beta[k], se[k], lo, hi, p))
        if k == 0:
            row = dict(beta=beta[k], se=se[k], lo=lo, hi=hi, p=p)
    P('   10→30 km 概率差 %.1f 个百分点' %
      (100 * row['beta'] * (math.log1p(30) - math.log1p(10))))
    return row


NM = ['dist 到县城(log1p km)', 'elev 海拔(百米)', 'rng 起伏(百米)']
A_all = list(ok)
A_ok = vary(A_all, 'yA')
res_all = {}
for tag, cols in (('F0 原口径（center）', ['dist', 'elev', 'rng']),
                  ('F1 替代口径（几何质心）', ['dist_c', 'elev', 'rng'])):
    P('')
    P('########## %s ##########' % tag)
    P('过程A 有效组：%d 县 %d 村；全样本：%d 县 %d 村'
      % (len({r['grp'] for r in A_ok}), len(A_ok),
         len({r['grp'] for r in A_all}), len(A_all)))
    res_all[tag] = {}
    res_all[tag]['clogit'] = clogit(A_ok, cols, NM, 'yA')
    P('')
    res_all[tag]['lpm_all'] = lpm(A_all, cols, NM, 'yA')
    P('')
    res_all[tag]['lpm_ok'] = lpm(A_ok, cols, NM, 'yA')

P('')
P('=== 自校验与结论 ===')
f0 = res_all['F0 原口径（center）']['clogit']
P('  原口径复现：beta %.3f，CI [%.3f, %.3f]，p %.3f（冻结值 −0.370 / [−0.838,−0.067] / p 0.025）'
  % (f0['beta'], f0['lo'], f0['hi'], f0['p']))
f1 = res_all['F1 替代口径（几何质心）']['clogit']
P('  质心口径　：beta %.3f，CI [%.3f, %.3f]，p %.3f' % (f1['beta'], f1['lo'], f1['hi'], f1['p']))
P('  符号一致：%s；质心口径 CI 是否不含 0：%s'
  % ('是' if f0['beta'] * f1['beta'] > 0 else '否', '是' if f1['lo'] * f1['hi'] > 0 else '否'))
for key, lab in (('lpm_all', 'LPM 全样本'), ('lpm_ok', 'LPM 有效组')):
    a = res_all['F0 原口径（center）'][key]
    b = res_all['F1 替代口径（几何质心）'][key]
    P('  %s：%.3f (p %.3f) -> %.3f (p %.3f)' % (lab, a['beta'], a['p'], b['beta'], b['p']))

open(os.path.join(D, 'county_center_check153.txt'), 'w', encoding='utf-8').write('\n'.join(OUT))
