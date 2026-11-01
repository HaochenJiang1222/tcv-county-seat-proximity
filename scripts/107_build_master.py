# -*- coding: utf-8 -*-
"""构建第四批 1598 村研究母表。

输入：
  data/tcv_funding/official/roster_official.csv      第四批官方名录（1598）
  data/tcv_funding/official/support_national.csv     2017-2019 支持名单
  data/geo/geodoi/points1598.csv                     第四批点位（geodoi DOI 10.3974/geodb.2019.01.19.V1）
  data/geo/geodoi/points2555.csv                     前三批点位（geodoi Id=910）
输出：
  data/master/master_1598.csv                        研究母表
  data/master/match_report.txt                       匹配质量报告
  data/manual_check.csv                              人工核验队列
"""
import csv, re, sys, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OFF = ROOT / 'data' / 'tcv_funding' / 'official'
GEO = ROOT / 'data' / 'geo' / 'geodoi'
OUT = ROOT / 'data' / 'master'
OUT.mkdir(parents=True, exist_ok=True)

PROVS = ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区', '辽宁省', '吉林省', '黑龙江省',
         '上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '河南省', '湖北省',
         '湖南省', '广东省', '广西壮族自治区', '海南省', '重庆市', '四川省', '贵州省', '云南省',
         '西藏自治区', '陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区',
         '新疆生产建设兵团']
PROV_RE = re.compile(r'^(' + '|'.join(PROVS) + r')')


HYPER = re.compile(r'HYPERLINK\s*"[^"]*"\s*\t?\s*"[^"]*"')


def norm(x):
    """清洗 Word 域代码残留并规范化"""
    x = HYPER.sub('', str(x))
    x = re.sub(r'https?://\S+', '', x)
    return re.sub(r'[（）()\s\u3000\t]', '', x)


def county_core(x):
    """县名核心字：去掉行政区划后缀，用于跨时期县名变更匹配"""
    return re.sub(r'(自治县|自治旗|各族自治县|林区|特区|新区|县|市|区|旗)$', '', norm(x))


def strip_prov(x):
    return PROV_RE.sub('', norm(x))


def load(p):
    return list(csv.DictReader((p).open(encoding='utf-8-sig')))


def main():
    ros = load(OFF / 'roster_official.csv')
    sup = load(OFF / 'support_national.csv')
    p4 = load(GEO / 'points1598.csv')
    p3 = load(GEO / 'points2555.csv')

    # 支持名单索引
    B = collections.defaultdict(set)
    for s in sup:
        B[s['batch']].add(norm(s['key']))

    # 第四批点位索引：全名 -> 候选；县乡村 -> 候选
    by_name = collections.defaultdict(list)
    by_dtv = collections.defaultdict(list)
    for p in p4:
        by_name[norm(p['name'])].append(p)
        by_dtv[norm(p['dist'] + p['town'] + p['vill'])].append(p)

    # 前三批县级存量：精确 -> 县名核心字 -> 确认为零（不得用市级兜底）
    prior = collections.Counter()
    prior_core = collections.Counter()
    prov_dist = collections.defaultdict(set)
    for p in p3:
        k = (p['prov'], norm(p['dist']))
        prior[k] += 1
        prov_dist[p['prov']].add(norm(p['dist']))
    for (pv, ds), n in prior.items():
        prior_core[(pv, county_core(ds))] += n
    dist_core_set = {pv: {county_core(d) for d in ds} for pv, ds in prov_dist.items()}

    master, check = [], []
    stat = collections.Counter()
    for i, r in enumerate(ros, 1):
        full = norm(r['full'])
        sp = strip_prov(r['full'])
        # 支持状态
        keys = {full, re.sub(r'[（）()]', '', full)}
        in17 = any(k in B['2017'] for k in keys)
        in18 = any(k in B['2018-1'] for k in keys)
        in182 = any(k in B['2018-2'] for k in keys)
        in19 = any(k in B['2019'] for k in keys)
        status = 'A' if in17 else ('B' if in18 else 'C')
        # 点位匹配
        cands = by_name.get(sp, [])
        if not cands:
            cands = by_dtv.get(norm(r['county'] + r['township'] + r['village']), [])
            method = 'fallback_dtv' if cands else 'unmatched'
        elif len(cands) > 1:
            same = [c for c in cands if norm(c['dist']) == norm(r['county'])
                    and norm(c['town']) == norm(r['township'])]
            if len(same) == 1:
                cands, method = same, 'exact_after_town_disambiguation'
            else:
                method = 'ambiguous'
        else:
            method = 'exact'
        stat[method] += 1
        pt = cands[0] if (cands and method in ('exact', 'fallback_dtv', 'exact_after_town_disambiguation')) else None
        if method in ('ambiguous', 'unmatched'):
            check.append(dict(village_id=i, prov=r['prov'], official_name_2016=r['full'],
                              issue=method, n_candidates=len(cands),
                              candidates='|'.join(c['name'] for c in cands[:5])))
        # 县级存量：精确 -> 核心字 -> 该县在 2555 中确无记录则记 0
        ck = (r['prov'], norm(norm(r['county']) and re.sub(r'HYPERLINK.*', '', r['county'])))
        ck = (r['prov'], norm(r['county']))
        core = county_core(r['county'])
        if ck in prior:
            pc, pc_src = prior[ck], 'county_exact'
        elif (r['prov'], core) in prior_core:
            pc, pc_src = prior_core[(r['prov'], core)], 'county_core'
        else:
            pc, pc_src = 0, ('county_absent_in_2555' if dist_core_set.get(r['prov']) else 'prov_absent')
        master.append(dict(
            village_id=i,
            official_name_2016=r['full'],
            province_2016=r['prov'],
            city_2016=r['city'],
            county_2016=r['county'],
            township_2016=r['township'],
            village_2016=r['village'],
            support_2017=int(in17),
            promised_2018=int(in18),
            support_2018b=int(in182),
            support_2019=int(in19),
            first_announced_status=status,
            first_effective_year={True: 2017}.get(in17) or ({True: 2018}.get(in18 or in182) or ({True: 2019}.get(in19) or '')),
            latitude=(pt['lat'] if pt else ''),
            longitude=(pt['lon'] if pt else ''),
            geolocation_quality=('matched' if pt else 'missing'),
            prior_recognized_count=pc,
            prior_count_source=pc_src,
        ))

    with (OUT / 'master_1598.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(master[0].keys()))
        w.writeheader()
        w.writerows(master)
    with (OUT / 'manual_check.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['village_id', 'prov', 'official_name_2016', 'issue',
                                          'n_candidates', 'candidates'])
        w.writeheader()
        w.writerows(check)

    n = len(master)
    print('母表行数 %d' % n)
    print()
    print('=== 点位匹配方法分布 ===')
    for k, v in stat.most_common():
        print('  %-34s %4d  %5.1f%%' % (k, v, 100 * v / n))
    got = sum(1 for m in master if m['geolocation_quality'] == 'matched')
    print('  取得坐标 %d/%d = %.1f%%' % (got, n, 100 * got / n))
    print()
    print('=== 支持状态 ===')
    c = collections.Counter(m['first_announced_status'] for m in master)
    for k in 'ABC':
        print('  %s %4d %5.1f%%' % (k, c[k], 100 * c[k] / n))
    print()
    print('=== 县级历史认定存量（2016年前）===')
    vals = [m['prior_recognized_count'] for m in master]
    print('  有存量数据的村 %d' % sum(1 for v in vals if v))
    print('  存量中位数 %.1f  均值 %.1f  最大 %d' % (
        sorted(vals)[len(vals) // 2], sum(vals) / len(vals), max(vals)))
    zero = sum(1 for v in vals if v == 0)
    print('  存量=0 的村 %d (%.1f%%)' % (zero, 100 * zero / n))
    print('  来源: ' + str(collections.Counter(m['prior_count_source'] for m in master)))
    print()
    print('=== 存量与2017支持状态（描述）===')
    for k in 'ABC':
        sub = [m['prior_recognized_count'] for m in master if m['first_announced_status'] == k]
        sub.sort()
        print('  %s  中位 %3d  均值 %5.1f  n=%d' % (k, sub[len(sub) // 2], sum(sub) / len(sub), len(sub)))
    print()
    print('人工核验队列 %d 条 -> data/master/manual_check.csv' % len(check))


if __name__ == '__main__':
    main()
