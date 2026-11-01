# -*- coding: utf-8 -*-
"""
123c：第四批 1598 村 -> 所属县城距离（认定前已确定的区位条件）
输出 data/master/dist_county_national.csv，并列出未匹配与异常远（>60 km）的记录
"""
import csv, sys, os, re, math, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data')

cc = list(csv.DictReader(open(os.path.join(D, 'geo', 'county_center_national.csv'),
                              encoding='utf-8-sig')))
m = list(csv.DictReader(open(os.path.join(D, 'master', 'master_final_1598.csv'),
                            encoding='utf-8-sig')))


def core(s):
    s = re.sub(r'\s', '', s or '')
    s = re.sub(r'(自治县|自治旗|特区|林区)$', '', s)
    s = re.sub(r'[市县区旗]$', '', s)
    return s


idx = collections.defaultdict(list)
for r in cc:
    idx[(r['province'], core(r['county']))].append(r)

# 手工映射：名录（2016）县名 -> 现行区划名。依据为公开撤县设区/设市批复，治所未迁移。
MAP = {
    ('云南省', '怒江州贡山县'): '贡山独龙族怒族自治县',   # 怒江傈僳族自治州贡山独龙族怒族自治县
    ('四川省', '宜宾县'): '叙州区',                      # 2018 撤县设区，治所柏溪
    ('山东省', '莱城区'): '莱芜区',                      # 2019 莱芜市撤市设区
    ('山东省', '蒙山旅游区'): '平邑县',                  # 非建制区，主体在平邑县
    ('山西省', '大同县'): '云州区',                      # 2018 撤县设区，治所西坪
    ('山西省', '长治县'): '上党区',                      # 2018 撤县设区，治所韩店
    ('湖南省', '汩罗市'): '汨罗市',                      # 名录字形差异
    ('贵州省', '安顺经济技术开发区'): '西秀区',          # 非建制区，位于西秀区
}


def hav(a1, o1, a2, o2):
    R = 6371.0088
    p1, p2 = math.radians(a1), math.radians(a2)
    dp = p2 - p1
    dl = math.radians(o2 - o1)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1, math.sqrt(x)))


rows, miss, far = [], [], []
for r in m:
    if not r['latitude']:
        rows.append({'village_id': r['village_id'], 'dist_km': '', 'rule': 'no_coord'})
        continue
    la, lo = float(r['latitude']), float(r['longitude'])
    pv, ct = r['province'], r['county']
    cand = idx.get((pv, core(ct)), [])
    rule = 'core'
    if not cand and (pv, ct) in MAP:
        cand = idx.get((pv, core(MAP[(pv, ct)])), [])
        rule = 'manual'
    if not cand:
        k = core(ct)
        cand = [x for (pp, kk), v in idx.items() if pp == pv and (k in kk or kk in k)
                for x in v]
        rule = 'fuzzy'
    if not cand:
        # 省内最近县中心兜底
        cand = [x for (pp, kk), v in idx.items() if pp == pv for x in v]
        if not cand:
            rows.append({'village_id': r['village_id'], 'dist_km': '', 'rule': 'miss'})
            miss.append((pv, ct))
            continue
        rule = 'prov_nearest'
    best = min(cand, key=lambda x: hav(la, lo, float(x['lat']), float(x['lon'])))
    d = hav(la, lo, float(best['lat']), float(best['lon']))
    rows.append({'village_id': r['village_id'], 'dist_km': round(d, 3),
                 'rule': rule, 'center_used': best['county']})
    if d > 60:
        far.append((pv, ct, r['village'], round(d, 1), best['county']))

with open(os.path.join(D, 'master', 'dist_county_national.csv'), 'w', newline='',
          encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=['village_id', 'dist_km', 'rule', 'center_used'])
    w.writeheader()
    w.writerows(rows)

ok = [r for r in rows if r['dist_km'] != '']
print('距离有效 %d / %d' % (len(ok), len(rows)))
print('匹配规则', collections.Counter(r['rule'] for r in rows))
print('未匹配县', len(miss), miss[:10])
ds = sorted(float(r['dist_km']) for r in ok)
print('距离分位：中位 %.1f km，90%% %.1f km，最大 %.1f km' % (
    ds[len(ds) // 2], ds[int(len(ds) * .9)], ds[-1]))
print('距县城 >60 km 的村 %d 条' % len(far))
for x in far[:15]:
    print('   ', x)
