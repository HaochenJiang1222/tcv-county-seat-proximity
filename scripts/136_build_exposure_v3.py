# -*- coding: utf-8 -*-
"""
136：双截点行政状态分类 + 第三版暴露变量（第三十九部分任务一、二）

状态定义（不使用未来信息）
  截点 C1 = 2015-12-31
    cur1  已公布当年支持安排（首次公告日 ≤ C1，且非 2015att2 未来承诺）
    pro1  已公布未来支持承诺（2015att2，86 村，公告日 2015-08-10，对应 2016 年度）
    non1  截至 C1 尚未公布任何支持安排（其后可能入选，含 2016 年公布的）
  截点 C2 = 2016-12-09（第四批国家认定当日）
    cur2  此前已公布当年支持安排（公告日 ≤ 2016-12-09，非 2015att2）
           = 2014-1 / 2014-2 / 2015-1 / 2015-2(2016-03-24) / 2016-1(2016-05-25)
    pro2  同 pro1（86 村）
    non2  此前尚未公布支持安排：2016-12-28 的 219 村 + 从未进入公告者
          注：2016-12-28 公告在认定日之后，不得倒填为 C2 之前已公布

未连接公告的 15 条
    上海 5 村：六份公开名单均无上海 → 判 never（单列，不并入 late）
    其余 10 条：公告侧有等量孤儿记录（14 条中扣除猛种村木耳堡子与 3 条同镇候选后余 10 条）
                但村名无法一一对应 → 判 unknown，三规格处理
      M0 主规格：unknown 不进入 cur/non 分组（不影响暴露），仍计入 n_pre 总数
      M2 保守：unknown 全部视为 non
      M3 激进：unknown 全部视为 cur

输出
  data/master/exposure_v3.csv            暴露变量（第四批有坐标村 × 三规格）
  data/master/analysis_national_v3.csv   完整分析样本（y / 地形 / audit 一并带上）
  data/master/status_v3.txt              分类对账
"""
import csv, os, sys, math, collections
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')
C1 = '2015-12-31'
C2 = '2016-12-09'

pre = list(csv.DictReader(open(os.path.join(D, 'master', 'geo_points_pre2555_v4.csv'),
                               encoding='utf-8-sig')))
m = list(csv.DictReader(open(os.path.join(D, 'master', 'master_final_1598.csv'),
                             encoding='utf-8-sig')))
el = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'elev_national.csv'), encoding='utf-8-sig'))}
dc = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'dist_county_national.csv'), encoding='utf-8-sig'))}
ga = {r['village_id']: r for r in csv.DictReader(
    open(os.path.join(D, 'master', 'geo_audit_national.csv'), encoding='utf-8-sig'))}

lines = []


def P(s=''):
    print(s)
    lines.append(s)


P('=== 136 双截点状态分类与暴露变量 ===')
P('前三批点位 %d；第四批 %d' % (len(pre), len(m)))

SHANGHAI = {'260', '261', '262', '263', '264'}

# ---- 状态分类 ----
def classify(r):
    fd = r['first_announce_date']
    precom = r['precommitted_future_year'] == '1'
    if r['fid'] in SHANGHAI:
        return 'never'
    if not fd:
        return 'unknown'
    if precom:
        return 'pro'
    if fd <= C1:
        return 'cur1'
    if fd <= C2:
        return 'cur2only'          # 2015-2 / 2016-1：C1 之后、C2 之前公布
    return 'non2'                  # 2016-12-28 公告，C2 之后


for r in pre:
    r['_st'] = classify(r)

cnt = collections.Counter(r['_st'] for r in pre)
P('')
P('--- 原始状态计数 ---')
for k in ['cur1', 'cur2only', 'pro', 'non2', 'never', 'unknown']:
    P('   %-9s %d' % (k, cnt[k]))
P('   合计 %d' % sum(cnt.values()))

# 截点分组（三规格）
def groups_for(spec):
    """返回 {gname: [点位索引]}"""
    g = collections.defaultdict(list)
    for i, r in enumerate(pre):
        st = r['_st']
        if spec == 'M0':
            if st == 'cur1':
                g['cur1'].append(i)
                g['cur2'].append(i)      # C2 之前同样已公布
            elif st in ('cur2only', 'non2'):
                g['non1'].append(i)   # C1 时点尚未公布
                if st == 'cur2only':
                    g['cur2'].append(i)
                else:
                    g['non2'].append(i)
            elif st == 'pro':
                g['pro'].append(i)
        elif spec == 'M2':            # unknown → non
            if st == 'cur1':
                g['cur1'].append(i)
                g['cur2'].append(i)
            elif st == 'cur2only':
                g['non1'].append(i)
                g['cur2'].append(i)
            elif st == 'pro':
                g['pro'].append(i)
            else:                     # non2 / never / unknown
                g['non1'].append(i)
                g['non2'].append(i)
        elif spec == 'M3':            # unknown → cur
            if st == 'cur1':
                g['cur1'].append(i)
                g['cur2'].append(i)
            elif st == 'cur2only':
                g['non1'].append(i)
                g['cur2'].append(i)
            elif st == 'pro':
                g['pro'].append(i)
            elif st == 'unknown':
                g['cur1'].append(i)
                g['cur2'].append(i)
            else:                     # non2 / never
                g['non1'].append(i)
                g['non2'].append(i)
    return g


for spec in ['M0', 'M2', 'M3']:
    g = groups_for(spec)
    P('')
    P('--- 规格 %s 分组计数 ---' % spec)
    for k in ['cur1', 'non1', 'cur2', 'non2', 'pro']:
        P('   %-5s %d' % (k, len(g.get(k, []))))
    P('   截点C1 合计 %d；截点C2 合计 %d（不含 pro %d）' %
      (len(g.get('cur1', [])) + len(g.get('non1', [])),
       len(g.get('cur2', [])) + len(g.get('non2', [])), len(g.get('pro', []))))
P('')
P('理论值：C1 → cur 1091 / non 1378 / pro 86（non 含后来进入 2016 名单的 1373 与上海 5）')
P('        C2 → cur 2245 / non 224  / pro 86（non = 2016-12-28 的 219 + 上海 5）')

# ---- 几何 ----
plat = np.array([float(r['lat']) for r in pre])
plon = np.array([float(r['lon']) for r in pre])
m4 = [r for r in m if r['latitude'] and r['longitude']]
mlat = np.array([float(r['latitude']) for r in m4])
mlon = np.array([float(r['longitude']) for r in m4])
P('')
P('第四批有坐标 %d' % len(m4))


def hav(la1, lo1, la2, lo2):
    R = 6371.0088
    p1, p2 = np.radians(la1), np.radians(la2)
    dp = p2 - p1
    dl = np.radians(lo2 - lo1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


Dall = hav(mlat[:, None], mlon[:, None], plat[None, :], plon[None, :])
P('距离矩阵 %s' % (Dall.shape,))

GS = {s: groups_for(s) for s in ['M0', 'M2', 'M3']}
RADII = [10]

rows = []
for j, r in enumerate(m4):
    v = r['village_id']
    x, d, g0 = el.get(v), dc.get(v), ga.get(v, {})
    if not x or not d:
        continue
    if not (d['dist_km'] and x['elev_srtm']):
        continue
    rec = {'vid': v, 'grp': r['province'] + '|' + r['county'], 'prov': r['province'],
           'county': r['county'], 'township': r['township'], 'village': r['village'],
           'lat': r['latitude'], 'lon': r['longitude'], 'status': r['status'],
           'dist': round(math.log1p(float(d['dist_km'])), 6),
           'dist_km': round(float(d['dist_km']), 3),
           'elev': round(float(x['elev_srtm']) / 100.0, 6),
           'rng': round(float(x['elev_range_srtm']) / 100.0, 6),
           'audit': g0.get('result', 'unknown'),
           'bdist': float(g0['dist_km']) if g0.get('dist_km') not in ('', None) else -1.0,
           'yA': 1 if r['status'] in ('A_2017', 'B_2018promised') else 0,
           'yB': 1 if r['status'] == 'A_2017' else (0 if r['status'] == 'B_2018promised' else -1)}
    rec['n_pre_10'] = int((Dall[j] <= 10).sum())
    rec['d_pre'] = round(float(Dall[j].min()), 3)
    for spec, g in GS.items():
        for k in ['cur1', 'non1', 'cur2', 'non2', 'pro']:
            idx = g.get(k, [])
            if not idx:
                rec['d_%s_%s' % (spec, k)] = ''
                rec['n_%s_%s' % (spec, k)] = ''
                continue
            dd = Dall[j][idx]
            rec['d_%s_%s' % (spec, k)] = round(float(dd.min()), 3)
            rec['n_%s_%s' % (spec, k)] = int((dd <= 10).sum())
    rows.append(rec)

P('分析样本 %d' % len(rows))

with open(os.path.join(D, 'master', 'exposure_v3.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# ---- 独立变异诊断 ----
def corr(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10:
        return float('nan')
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


P('')
P('--- 独立变异诊断（log1p 距离型相关，规格 M0）---')
for a, b in [('d_M0_cur1', 'd_M0_non1'), ('d_M0_cur2', 'd_M0_non2'),
             ('d_M0_cur1', 'd_pre'), ('d_M0_non1', 'd_pre')]:
    va = [float(r[a]) for r in rows if r[a] != '']
    vb = [float(r[b]) for r in rows if r[b] != '']
    P('   corr(%s, %s) = %.3f' % (a, b, corr(va, vb)))
P('--- 计数型 10km 相关 ---')
for a, b in [('n_M0_cur1', 'n_M0_non1'), ('n_M0_cur2', 'n_M0_non2')]:
    P('   corr(%s, %s) = %.3f' % (a, b, corr([r[a] for r in rows], [r[b] for r in rows])))

P('')
P('--- 暴露覆盖（10km 内至少 1 个，M0）---')
for k in ['cur1', 'non1', 'cur2', 'non2', 'pro']:
    n = sum(1 for r in rows if r['n_M0_%s' % k] != '' and r['n_M0_%s' % k] > 0)
    P('   %-5s %d / %d（%.1f%%）' % (k, n, len(rows), 100.0 * n / len(rows)))

open(os.path.join(D, 'master', 'status_v3.txt'), 'w', encoding='utf-8').write('\n'.join(lines))
print()
print('写出 exposure_v3.csv / status_v3.txt')
