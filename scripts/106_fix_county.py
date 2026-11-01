# -*- coding: utf-8 -*-
"""修正第四批名录的县名提取：CTY_RE 原为 {2,}? 最少两汉字，
导致单字名县（歙县、黟县、泾县等）漏配，county 为空。
改为 {1,}? 并加合法性校验；重解析后重建逐村匹配表。
"""
import csv, re, sys, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OFF = ROOT / 'data' / 'tcv_funding' / 'official'

PROVS = ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区', '辽宁省', '吉林省', '黑龙江省',
         '上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '河南省', '湖北省',
         '湖南省', '广东省', '广西壮族自治区', '海南省', '重庆市', '四川省', '贵州省', '云南省',
         '西藏自治区', '陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区',
         '新疆生产建设兵团']
PROV_LINE = re.compile(r'^(?:[一二三四五六七八九十]+、)?\s*(' + '|'.join(PROVS) + r')\s*[（(]\s*(\d+)\s*个')
MUNI = {'北京市', '天津市', '上海市', '重庆市'}
CITY_RE = re.compile(r'^([\u4e00-\u9fa5]{2,}?(?:自治州|市|州|地区|盟))')
# 关键修正：{1,}? 允许单字名县（歙县、黟县、泾县……）
CTY_RE = re.compile(r'^([\u4e00-\u9fa5]{1,8}?(?:自治县|自治旗|林区|特区|新区|县|市|区|旗))')
TWP_RE = re.compile(r'^([\u4e00-\u9fa5]{1,8}?(?:街道办事处|办事处|管理委员会|管委会|民族乡|苏木|镇|乡|街道))')


def parse(txt, source):
    prov, declared, out = None, None, []
    for raw in re.split(r'[\r\n\u000b\u000c\u0085\u2028\u2029]+', txt):
        line = raw.strip().replace('\u3000', '').replace(' ', '')
        if not line:
            continue
        m = PROV_LINE.match(line)
        if m:
            prov, declared = m.group(1), int(m.group(2))
            continue
        if prov is None or len(line) < 4:
            continue
        if re.search(r'(名录的村落名单|^附件$|^注[:：]|合计|共\d+个)', line):
            continue
        if re.search(r'[（(]\s*\d+\s*个[）)]', line):
            continue
        if re.search(r'(MERGEFORMAT|PAGE|\*\\\\?|PAGE\\\\|TOC\\\\|PAGEREF)', line, flags=re.I):
            continue
        if not re.search(r'[\u4e00-\u9fa5]{3,}', line):
            continue
        rest, city, county, town = line, None, None, None
        if prov in MUNI:
            mc = CTY_RE.match(rest)
            if mc and rest[len(mc.group(1)):len(mc.group(1)) + 1] not in ('镇', '乡'):
                county = mc.group(1)
                rest = rest[len(county):]
        else:
            mc = CITY_RE.match(rest)
            if mc:
                city = mc.group(1)
                rest = rest[len(city):]
            mc2 = CTY_RE.match(rest)
            if mc2:
                county = mc2.group(1)
                rest = rest[len(county):]
        mt = TWP_RE.match(rest)
        if mt:
            town = mt.group(1)
            rest = rest[len(town):]
        if not county and city:          # 县级市、州直辖等：以市/州名兜底为县级单位
            county = city
        out.append(dict(source=source, prov=prov, declared_prov_n=declared, city=city or '',
                        county=county or '', township=town or '', village=rest, full=line))
    return out


def main():
    txt = (OFF / 'batch4.txt').read_text(encoding='utf-8')
    rows = parse(txt, 'batch4.doc')
    byp = collections.Counter(r['prov'] for r in rows)
    print('解析村数 %d' % len(rows))
    print('county 为空 %d 条（修正前 139）' % sum(1 for r in rows if not r['county']))
    for p in PROVS:
        if p in byp:
            print('   %-12s %4d' % (p, byp[p]))
    bad = [r for r in rows if not r['county']]
    if bad:
        print('--- 仍为空的样本 ---')
        for r in bad[:15]:
            print('   ', r['prov'], r['full'])
    with (OFF / 'roster_official.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['source', 'prov', 'declared_prov_n', 'city',
                                          'county', 'township', 'village', 'full'])
        w.writeheader()
        w.writerows(rows)

    # 重建逐村匹配（support_national.csv 不动）
    sup = list(csv.DictReader((OFF / 'support_national.csv').open(encoding='utf-8-sig')))
    idx = collections.defaultdict(set)
    for s in sup:
        idx[s['key']].add(s['batch'])
    order = {'2017': 0, '2018-1': 1, '2018-2': 2, '2019': 3}
    res = []
    for r in rows:
        f = r['full'].replace(' ', '')
        keys = {f, re.sub(r'[（）()]', '', f)}
        bs = set()
        for k in keys:
            bs |= idx.get(k, set())
        bs = sorted(bs, key=lambda b: order[b])
        res.append(dict(prov=r['prov'], city=r['city'], county=r['county'], township=r['township'],
                        village=r['village'], full=r['full'],
                        first_batch=bs[0] if bs else '', n_batch=len(bs), batches='|'.join(bs)))
    with (OFF / 'batch4_matched_2019.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(res[0].keys()))
        w.writeheader()
        w.writerows(res)
    hit = sum(1 for r in res if r['first_batch'])
    print('全国匹配 %d/%d = %.1f%%' % (hit, len(res), 100 * hit / len(res)))


if __name__ == '__main__':
    main()
