# -*- coding: utf-8 -*-
"""
121：解析 2014-2016 六份全国中央财政支持名单（含 2015 附件2 的 86 村）
按公告日期打标，输出逐村名单，供全国历史支持经验暴露变量使用。

设计要点
1. 省份标题在【原始行】上识别；网页把标题拆成两行时（"一、北京市（" + "2个）"）先合并再识别。
2. 端到端校验：每个省级标题声明数 == 解析条目数；不相等即写入 REVIEW 清单，不静默截断。
3. 公告日期来自用户第三十七部分核实的六份文件公布日，独立于"支持年度"。
"""
import re, sys, html, csv, os, collections, unicodedata

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'tcv_funding', 'official_pre', 'raw')
OUT = os.path.join(ROOT, 'data', 'tcv_funding', 'official_pre')

PROV = ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区', '辽宁省', '吉林省', '黑龙江省',
        '上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '河南省', '湖北省',
        '湖南省', '广东省', '广西壮族自治区', '海南省', '重庆市', '四川省', '贵州省', '云南省',
        '西藏自治区', '陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区']
PALT = '|'.join(PROV)
HEAD_RE = re.compile(r'^(?:[一二三四五六七八九十百]+[、.])?\s*(' + PALT + r')\s*[（(]\s*(\d+)\s*个\s*[）)]')
HEAD_PART1 = re.compile(r'^(?:[一二三四五六七八九十百]+[、.])?\s*(' + PALT + r')\s*[（(]$')
HEAD_PART2 = re.compile(r'^(\d+)\s*个\s*[）)]$')
STOP_RE = re.compile(r'^(附件|注：|说明|关注|微信|下载|相关|上一篇|下一篇|来源|编辑|责编|分享)')
VILL_HINT = re.compile(r'村|寨|屯|堡|组|社区|嘎查|庄|湾|沟|镇区|街道|自然村|古村|老街|民居')
TOWN_HINT = re.compile(r'镇|乡|街道|苏木|管理区|办事处|区公所|牧场|农场|场')


def to_lines(path):
    t = open(path, encoding='utf-8', errors='ignore').read()
    s = re.sub(r'<script.*?</script>', ' ', t, flags=re.S)
    s = re.sub(r'<style.*?</style>', ' ', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '\n', s)
    s = html.unescape(s).replace('\xa0', '\n').replace('\u3000', '\n')
    lines = [l.strip() for l in s.split('\n') if l.strip()]
    # 网页常把省份标题拆成 2-3 行（"一、北京市（" / "2" / "个）"），先拼接再识别
    merged, i = [], 0
    while i < len(lines):
        a = lines[i]
        if HEAD_PART1.match(a):
            buf, j, done = a, i + 1, False
            while j < len(lines) and j <= i + 3:
                buf += lines[j]
                if re.search(r'\d+\s*个\s*[）)]$', buf):
                    done = True
                    i = j
                    break
                j += 1
            merged.append(buf if done else a)
            i += 1
            continue
        merged.append(a)
        i += 1
    return merged


def parse(path, label, expect_total, announce, scope_year, start_head=None, end_head=None):
    lines = to_lines(path)
    heads = [(i, m.group(1), int(m.group(2))) for i, l in enumerate(lines)
             for m in [HEAD_RE.match(l)] if m]
    if start_head:      # 只取某个附件区间（用于 2015 双列表）
        heads = [h for h in heads if h[0] >= start_head]
    if end_head:
        heads = [h for h in heads if h[0] < end_head]
    rows, review = [], []
    for j, (i, pv, exp_n) in enumerate(heads):
        end = heads[j + 1][0] if j + 1 < len(heads) else (end_head or len(lines))
        cand = []
        for x in lines[i + 1:end]:
            if STOP_RE.search(x) or HEAD_RE.match(x):
                break
            if len(x) < 5 or len(x) > 40:
                continue
            if not VILL_HINT.search(x):
                continue
            if not TOWN_HINT.search(x):      # 排除网页导航噪声（"传统村落网""村落120"等）
                continue
            cand.append(x)
        if len(cand) != exp_n:
            review.append((label, pv, exp_n, len(cand)))
        for x in cand:
            rows.append({'batch': label, 'announce_date': announce, 'scope_year': scope_year,
                         'prov': pv, 'raw': re.sub(r'\s+', '', unicodedata.normalize('NFKC', x))})
    return rows, review, len(heads), sum(h[2] for h in heads)


# ---------- 拆地址：市/县/乡镇/村 ----------
CITY_RE = re.compile(r'^(.*?[市州盟地区])')
TOWN_UNIT = ['街道办事处', '街道', '镇', '乡', '苏木', '管委会', '区公所']


def split_addr(s, prov):
    rest = s
    if prov in ('北京市', '天津市', '上海市', '重庆市'):
        rest = re.sub(r'^' + prov, '', rest)
    else:
        m = CITY_RE.match(rest)
        if m:
            rest = rest[len(m.group(1)):]
    county, town, vill = rest, '', rest
    for u in TOWN_UNIT:
        i = rest.find(u)
        if 1 <= i <= 25:
            county = rest[:i]
            town = rest[:i + len(u)]
            vill = rest[i + len(u):]
            break
    return county, town, vill


def main():
    allrows, allrev, summary = [], [], []
    # 2014 第一批：120 脚本已解析的官方 .doc 结果
    p = os.path.join(OUT, 'support_2014_1.csv')
    if os.path.exists(p):
        prev = list(csv.DictReader(open(p, encoding='utf-8-sig')))
        for r in prev:
            allrows.append({'batch': '2014-1', 'announce_date': '2014-07-16', 'scope_year': '2014',
                            'prov': r.get('prov', ''),
                            'raw': re.sub(r'\s+', '', r.get('village') or r.get('name') or '')})
        summary.append(('2014-1', '2014-07-16', 327, len(prev), len(prev) - 327))

    jobs = [
        ('2014-2', 'f2014_2.html', 273, '2014-12-17', '2014', None, None),
        ('2015-1', 'f2015_1.html', 491, '2015-08-10', '2015', None, 593),
        ('2015-2', 'f2015_2.html', 404, '2016-03-24', '2015', None, None),
        ('2016-1', 'f2016_1.html', 750, '2016-05-25', '2016', None, None),
        ('2016-2', 'f2016_2.html', 219, '2016-12-28', '2016', None, None),
        ('2015att2', 'f2015_1.html', 86, '2015-08-10', '2016', 593, None),
    ]
    for label, fn, exp, ann, sy, s0, s1 in jobs:
        path = os.path.join(RAW, fn)
        if not os.path.exists(path):
            summary.append((label, ann, exp, 0, -exp))
            continue
        rows, rev, nh, decl = parse(path, label, exp, ann, sy, s0, s1)
        allrows += rows
        allrev += rev
        summary.append((label, ann, decl, len(rows), len(rows) - exp))

    # 拆地址
    for r in allrows:
        c, t, v = split_addr(r['raw'], r['prov'])
        r['county'], r['township'], r['village'] = c, t, v

    outp = os.path.join(OUT, 'support_national_all.csv')
    with open(outp, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['batch', 'announce_date', 'scope_year', 'prov',
                                          'county', 'township', 'village', 'raw'])
        w.writeheader()
        w.writerows(allrows)

    print('== 六份名单解析（省级声明数 vs 解析数）==')
    print('%-10s %-12s %6s %6s %6s' % ('批次', '公告日期', '声明', '解析', '差'))
    for lab, ann, decl, got, d in summary:
        print('%-10s %-12s %6d %6d %6d' % (lab, ann, decl, got, d))
    print('总计 %d 条' % len(allrows))

    print()
    print('== 省级声明数与解析数不一致的组（需人工看）== %d 组' % len(allrev))
    for x in allrev[:20]:
        print('   ', x)

    print()
    print('== 跨批次重复（同一村出现在多份名单）==')
    key = collections.Counter((r['prov'], r['raw']) for r in allrows)
    dup = {k: v for k, v in key.items() if v > 1}
    print('村名组合 %d 个，其中重复 %d 个' % (len(key), len(dup)))
    bybatch = collections.defaultdict(list)
    for r in allrows:
        bybatch[(r['prov'], r['raw'])].append(r['batch'])
    for k, v in list(dup.items())[:15]:
        print('   ', k[0], k[1], sorted(bybatch[k]))

    print()
    print('== 地址拆分质量 ==')
    bad = [r for r in allrows if not r['township']]
    print('乡镇为空 %d 条（%.1f%%）' % (len(bad), 100 * len(bad) / max(1, len(allrows))))
    for r in bad[:10]:
        print('   ', r['prov'], r['raw'], '->', r['county'], '|', r['village'])
    print()
    print('写出：%s' % outp)


if __name__ == '__main__':
    main()
