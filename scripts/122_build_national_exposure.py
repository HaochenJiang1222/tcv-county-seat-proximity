# -*- coding: utf-8 -*-
"""
122：全国历史财政支持经验暴露变量

输入
  data/geo/geodoi/points2555.csv          前三批 2555 村点位（含 prov/city/dist/town/vill/lon/lat）
  data/tcv_funding/official_pre/support_national_all.csv   六份全国支持名单（121 产出）
  data/master/master_final_1598.csv       第四批 1598 村母表（含 status/lat/lon）

输出
  data/master/geo_points_pre2555.csv      前三批点位 + 支持状态（首次公告日期、批次）
  data/master/exposure_national.csv       第四批村的历史暴露变量

两种历史口径（用户第三十七部分第二节）
  strict_pre  严格认定前暴露：公告日期 < 2016-12-09（第四批认定日）
  experience  实施经验暴露：公告日期 <= 2015-12-31（留出项目实施与经验积累时间）
"""
import csv, sys, math, os, re, unicodedata, collections

sys.stdout.reconfigure(encoding='utf-8')
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')

RECOG_DATE = '2016-12-09'      # 第四批认定日


def norm(s):
    return re.sub(r'[\s·、，,]', '', unicodedata.normalize('NFKC', s or ''))


def hav(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ---------- 1. 读名单 ----------
sup = list(csv.DictReader(open(os.path.join(D, 'tcv_funding', 'official_pre',
                                            'support_national_all.csv'), encoding='utf-8-sig')))
print('支持名单条目 %d' % len(sup))
print(collections.Counter(r['batch'] for r in sup).most_common())

# ---------- 2. 读前三批点位 ----------
pre = list(csv.DictReader(open(os.path.join(D, 'geo', 'geodoi', 'points2555.csv'), encoding='utf-8-sig')))
for r in pre:
    r['lat'] = float(r['lat'])
    r['lon'] = float(r['lon'])
print('前三批点位 %d' % len(pre))

# ---------- 3. 匹配：支持名单 -> 点位 ----------
# 索引：省 -> 县 -> 村名
idx_prov = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_prov[r['prov']].append(i)
idx_cty = collections.defaultdict(list)
for i, r in enumerate(pre):
    idx_cty[(r['prov'], norm(r['dist']))].append(i)

hit_rule = collections.Counter()
assigned = {}       # 点位下标 -> (batch, announce_date)
for s in sup:
    pv = s['prov']
    cty = norm(s['county'])
    vl = norm(s['village'])
    if pv not in idx_prov:
        hit_rule['prov_miss'] += 1
        continue
    cand = idx_cty.get((pv, cty), [])
    # L1 省+县+村名精确
    m = [i for i in cand if norm(pre[i]['vill']) == vl]
    if len(m) == 1:
        i = m[0]
        rule = 'L1'
    elif len(m) > 1:
        i, rule = m[0], 'L1_multi'
    else:
        # L2 省+县+村名前 2 字
        m2 = [i for i in cand if norm(pre[i]['vill'])[:2] == vl[:2]] if len(vl) >= 2 else []
        if len(m2) == 1:
            i, rule = m2[0], 'L2'
        else:
            # L3 省内村名精确
            m3 = [i for i in idx_prov[pv] if norm(pre[i]['vill']) == vl]
            if len(m3) == 1:
                i, rule = m3[0], 'L3'
            else:
                # L4 县内村名互相包含
                m4 = [i for i in cand if norm(pre[i]['vill']) and
                      (norm(pre[i]['vill']) in vl or vl in norm(pre[i]['vill']))]
                if len(m4) == 1:
                    i, rule = m4[0], 'L4'
                else:
                    hit_rule['miss'] += 1
                    continue
    hit_rule[rule] += 1
    prev = assigned.get(i)
    if prev is None or s['announce_date'] < prev[1]:
        assigned[i] = (s['batch'], s['announce_date'])

print()
print('== 支持名单与前三批点位匹配 ==')
for k, v in hit_rule.most_common():
    print('   %-10s %d' % (k, v))
print('   已赋支持状态的点位 %d / %d（%.1f%%）' % (
    len(assigned), len(pre), 100 * len(assigned) / len(pre)))
print('   未匹配名单条目 %d（%.1f%%）' % (hit_rule['miss'], 100 * hit_rule['miss'] / len(sup)))

with open(os.path.join(D, 'master', 'geo_points_pre2555.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['fid', 'prov', 'city', 'dist', 'town', 'vill', 'lon', 'lat',
                'support_batch', 'first_announce_date'])
    for i, r in enumerate(pre):
        b, d = assigned.get(i, ('', ''))
        w.writerow([r['fid'], r['prov'], r['city'], r['dist'], r['town'], r['vill'],
                    r['lon'], r['lat'], b, d])

# ---------- 4. 两种历史口径 ----------
def flag(date):
    if not date:
        return False
    return date < RECOG_DATE


sup_strict = [i for i, (b, d) in assigned.items() if flag(d)]              # 严格认定前
sup_exp = [i for i, (b, d) in assigned.items() if d and d <= '2015-12-31']  # 实施经验
notsup = [i for i in range(len(pre)) if i not in assigned]                  # 认定但未见于名单
print()
print('严格认定前已获支持的历史村 %d；2015 年底前已获支持 %d；未见于名单 %d' % (
    len(sup_strict), len(sup_exp), len(notsup)))

# ---------- 5. 第四批村的暴露变量 ----------
m = list(csv.DictReader(open(os.path.join(D, 'master', 'master_final_1598.csv'), encoding='utf-8-sig')))
m4 = [r for r in m if r['latitude'] and r['longitude']]
print('第四批有坐标村 %d / %d' % (len(m4), len(m)))

plat = np.array([r['lat'] for r in pre])
plon = np.array([r['lon'] for r in pre])
RADII = [5, 10, 20]

def dist_to(idx):
    if not idx:
        return None
    la = plat[idx]
    lo = plon[idx]
    return hav(mlat[:, None], mlon[:, None], la[None, :], lo[None, :])


mlat = np.array([float(r['latitude']) for r in m4])
mlon = np.array([float(r['longitude']) for r in m4])

Dsup = dist_to(sup_strict)
Dexp = dist_to(sup_exp)
Dnot = dist_to(notsup)
Dall = hav(mlat[:, None], mlon[:, None], plat[None, :], plon[None, :])

rows = []
for j, r in enumerate(m4):
    rec = {'village_id': r['village_id'], 'province': r['province'], 'county': r['county'],
           'township': r['township'], 'village': r['village'],
           'latitude': r['latitude'], 'longitude': r['longitude'], 'status': r['status']}
    for R in RADII:
        rec['n_pre_%d' % R] = int((Dall[j] <= R).sum())
        rec['n_sup_%d' % R] = int((Dsup[j] <= R).sum()) if Dsup is not None else ''
        rec['n_exp_%d' % R] = int((Dexp[j] <= R).sum()) if Dexp is not None else ''
        rec['n_notsup_%d' % R] = int((Dnot[j] <= R).sum()) if Dnot is not None else ''
    rec['d_nearest_sup'] = round(float(Dsup[j].min()), 3) if Dsup is not None else ''
    rec['d_nearest_exp'] = round(float(Dexp[j].min()), 3) if Dexp is not None else ''
    rec['d_nearest_notsup'] = round(float(Dnot[j].min()), 3) if Dnot is not None else ''
    rec['d_nearest_pre'] = round(float(Dall[j].min()), 3)
    rows.append(rec)

outp = os.path.join(D, 'master', 'exposure_national.csv')
with open(outp, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)


def corr(a, b):
    a = np.array([float(x) for x in a])
    b = np.array([float(x) for x in b])
    return float(np.corrcoef(a, b)[0, 1])


print()
print('== 共线诊断（全国 1596 村）==')
for R in RADII:
    print('%2d km：corr(n_sup, n_pre) = %.3f   corr(n_sup, n_notsup) = %.3f' % (
        R, corr([x['n_sup_%d' % R] for x in rows], [x['n_pre_%d' % R] for x in rows]),
        corr([x['n_sup_%d' % R] for x in rows], [x['n_notsup_%d' % R] for x in rows])))
print('corr(d_nearest_sup, d_nearest_notsup) = %.3f' % (
    corr([x['d_nearest_sup'] for x in rows], [x['d_nearest_notsup'] for x in rows])))
print()
print('== 暴露变异 ==')
for R in [10]:
    a = sum(1 for x in rows if x['n_sup_%d' % R] > 0)
    b = sum(1 for x in rows if x['n_notsup_%d' % R] > 0)
    print('%d km 内有已支持历史村的第四批村 %d / %d；有未支持历史村的 %d / %d' % (
        R, a, len(rows), b, len(rows)))
print()
print('写出：%s' % outp)
