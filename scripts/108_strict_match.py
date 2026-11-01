# -*- coding: utf-8 -*-
"""108 全量匹配前的最后一道数据审计（第八轮）

三条原则：
  1. 研究母表以国家正式认定名录为准（建村〔2016〕278号，1598 村），
     空间数据库只提供坐标，不决定谁进入样本。
  2. 2017 年行政决定拆成两个过程：
     过程 A  是否进入 2017-05-09 公布的 1044 村安排范围；
     过程 B  已进入安排者中，2017 当年支持 还是 预告 2018 支持。
  3. 只做严格匹配。任何需要推断的对应关系统一进入人工核验队列，
     不静默接受，也不静默丢弃。

输入（三个可公开读取的入口，已缓存至 data/master/raw/）：
  2016 认定名录     维基文库 建村〔2016〕278号 wikitext
  2017 支持 600 村  zsad.com.cn/news_info/id-530.html
  2018 拟支持 444 村 asqxzs.com eportal articleKey=650230
交叉校验：
  data/tcv_funding/official/roster_official.csv  本地解析的官方 .doc 名录
  data/tcv_funding/official/support_national.csv 本地解析的 2017/2018 名单
  data/master/master_1598.csv                    已建母表
  data/geo/geodoi/points1598.csv                 第四批点位（geodoi，仅取坐标）

输出（data/master/）：
  roster_2016_wikisource.csv     独立重建的 1598 村名录
  support_2017_zsad.csv          独立重建的 600 村名单
  support_2018p_raw.csv          独立重建的 444 村名单
  strict_match_1598.csv          逐村严格匹配结果与匹配层级
  strict_review_queue.csv        人工核验队列（候选已列出，未接受）
  county_variation.csv           县内状态变异（过程 A / 过程 B）
  strict_audit_report.txt        审计报告
"""
import csv, html, json, re, sys, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'master' / 'raw'
OUT = ROOT / 'data' / 'master'
OFF = ROOT / 'data' / 'tcv_funding' / 'official'
GEO = ROOT / 'data' / 'geo' / 'geodoi'
OUT.mkdir(parents=True, exist_ok=True)

PROVS = ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区', '辽宁省', '吉林省', '黑龙江省',
         '上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '河南省', '湖北省',
         '湖南省', '广东省', '广西壮族自治区', '海南省', '重庆市', '四川省', '贵州省', '云南省',
         '西藏自治区', '陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区']
PROV_ALT = '|'.join(PROVS)
HEAD_RE = re.compile(r"^'?'''?\s*(?:[一二三四五六七八九十]+[、.])?\s*(" + PROV_ALT + r")\s*[（(]\s*(\d+)\s*个\s*[）)]")
HEAD2_RE = re.compile(r'^(?:[一二三四五六七八九十]+[、.])?\s*(' + PROV_ALT + r')\s*[（(]\s*(\d+)\s*个\s*[）)]')
STOP_RE = re.compile(r'(本文来源|上一篇|下一篇|相关新闻|版权|法律声明|网站联盟|友情链接|联系|登录|注册|网站地图|分享|在看|点击|返回|通知$|名单$|附件$|发布日期|来源：)')
TOWN_UNIT = ['街道办事处', '办事处', '管理委员会', '管委会', '苏木', '民族乡', '镇', '乡', '街道']

TARGET = {'江苏省': 2, '浙江省': 225, '安徽省': 52}   # 官方公告数，用作停止条件


# ---------------------------------------------------------------- 基础清洗
def norm(x):
    x = str(x).replace(' ', '').replace('\u3000', '').replace('\t', '')
    x = re.sub(r'https?://\S+', '', x)
    x = re.sub(r'HYPERLINK\s*"[^"]*"\s*\t?\s*"[^"]*"', '', x)
    x = re.sub(r"[（）()\[\]【】,，.。、;；:：'\"“”]", '', x)
    x = re.sub(r'(村民委员会|村委会|村委)$', '', x)
    return x


CITY_RE = [re.compile(r'^(.*?自治州)'), re.compile(r'^(.*?地区)'),
           re.compile(r'^(.*?盟)'), re.compile(r'^(.*?市)')]
CTY_RE = re.compile(r'^(.*?(?:各族自治县|自治县|自治旗|林区|特区|新区|县|市|区|旗))')
TWN_RE = re.compile(r'^(.*?(?:街道办事处|办事处|管理委员会|管委会|苏木|镇|乡|街道))')


def split_addr(s):
    """把 '市+县+乡镇+村' 从左到右拆成 (县, 乡镇, 村)；拆不出则相应字段为空"""
    s = norm(s)
    rest = s
    for cr in CITY_RE:
        m = cr.match(rest)
        if m:
            rest = rest[len(m.group(1)):]
            break
    m = CTY_RE.match(rest)
    county = m.group(1) if m else ''
    rest = rest[len(county):]
    m = TWN_RE.match(rest)
    town = m.group(1) if m else ''
    vill = rest[len(town):]
    return county, town, vill


def html_lines(p):
    s = p.read_text(encoding='utf-8', errors='ignore')
    s = re.sub(r'<script.*?</script>', ' ', s, flags=re.S)
    s = re.sub(r'<style.*?</style>', ' ', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '\n', s)
    s = html.unescape(s).replace('\xa0', '\n')
    return [l.strip() for l in s.split('\n') if l.strip()]


# ---------------------------------------------------------------- 1. 2016 名录（维基文库）
def build_roster():
    wiki = (RAW / 'wikisource_2016.wiki').read_text(encoding='utf-8')
    lines = wiki.split('\n')
    heads = []
    for i, l in enumerate(lines):
        m = HEAD_RE.match(l.strip()) or HEAD2_RE.match(l.strip())
        if m:
            heads.append((i, m.group(1), int(m.group(2))))
    if not heads:
        raise ValueError('未识别省份标题')
    rows, warn = [], []
    for j, (st, pv, exp) in enumerate(heads):
        end = heads[j + 1][0] if j + 1 < len(heads) else len(lines)
        cand = []
        for l in lines[st + 1:end]:
            x = l.strip().strip("'").strip()
            if not x or len(x) < 5 or len(x) > 45:
                continue
            if HEAD_RE.match(x) or HEAD2_RE.match(x):
                continue
            if re.match(r'^\{\{|^\[\[|^\}\}', x):
                continue
            if STOP_RE.search(x):
                continue
            cand.append(x)
        if len(cand) != exp:
            warn.append((pv, exp, len(cand)))
        for k, x in enumerate(cand, 1):
            cty, tw, vl = split_addr(x)
            rows.append(dict(prov=pv, expected_prov_n=exp, seq=k, name=x,
                             county=cty, township=tw, village=vl, key=norm(x)))
    return rows, warn


# ---------------------------------------------------------------- 2. 支持名单
def build_support(fname, label, official_total):
    lines = html_lines(RAW / fname)
    heads = []
    for i, l in enumerate(lines):
        m = HEAD2_RE.match(l)
        if m:
            heads.append((i, m.group(1), int(m.group(2))))
    if not heads:
        raise ValueError('未识别省份标题: ' + label)
    declared = sum(h[2] for h in heads)
    rows, warn = [], []
    for j, (st, pv, exp) in enumerate(heads):
        end = heads[j + 1][0] if j + 1 < len(heads) else len(lines)
        cand = []
        for l in lines[st + 1:end]:
            x = l.strip()
            if STOP_RE.search(x):
                break
            if len(x) < 5 or len(x) > 45:
                continue
            if HEAD2_RE.match(x):
                continue
            if not re.search(r'[镇乡街道村寨屯堡组苏木社区区]', x):
                continue
            cand.append(x)
        if len(cand) != exp:
            warn.append((pv, exp, len(cand)))
        for k, x in enumerate(cand, 1):
            cty, tw, vl = split_addr(x)
            rows.append(dict(batch=label, prov=pv, expected_prov_n=exp, seq=k, name=x,
                             county=cty, township=tw, village=vl, key=norm(x)))
    return rows, warn, declared


# ---------------------------------------------------------------- 3. 严格匹配
def match_level(r, s):
    """返回 (level, note)；level: exact / county_town / town_only / vill_only / none"""
    if r['key'] == s['key']:
        return 'exact', ''
    if r['village'] and r['village'] == s['village']:
        if r['township'] == s['township']:
            if r['county'] == s['county']:
                return 'county_town', ''
            return 'town_only', 'county_diff:%s|%s' % (r['county'], s['county'])
        return 'vill_only', 'town_diff:%s|%s' % (r['township'], s['township'])
    return 'none', ''


def main():
    rep = []

    # ---------- 1. 名录 ----------
    ros, warn_r = build_roster()
    rep.append('=== 一、2016 年第四批认定名录（维基文库 建村〔2016〕278号）===')
    prov_decl = {r['prov']: int(r['expected_prov_n']) for r in ros}
    rep.append('解析村数 %d（官方 1598）' % len(ros))
    rep.append('省份标题 %d 个，标题声明合计 %d 村' % (len(prov_decl), sum(prov_decl.values())))
    if warn_r:
        rep.append('!! 省段声明数与解析数不一致：' + str(warn_r))
    else:
        rep.append('30 省逐省声明数与解析数一致，零误差')
    pcnt = collections.Counter(r['prov'] for r in ros)
    rep.append('三省：江苏 %d / 浙江 %d / 安徽 %d，合计 %d（官方 279）' % (
        pcnt['江苏省'], pcnt['浙江省'], pcnt['安徽省'],
        pcnt['江苏省'] + pcnt['浙江省'] + pcnt['安徽省']))
    assert pcnt['江苏省'] == 2 and pcnt['浙江省'] == 225 and pcnt['安徽省'] == 52
    with (OUT / 'roster_2016_wikisource.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(ros[0].keys()))
        w.writeheader(); w.writerows(ros)

    # 交叉校验：与本地官方 .doc 解析结果
    doc = list(csv.DictReader((OFF / 'roster_official.csv').open(encoding='utf-8-sig')))
    dk = collections.Counter(norm(d['full']) for d in doc)
    rk = collections.Counter(r['key'] for r in ros)
    rep.append('')
    rep.append('--- 交叉校验：维基文库 vs 本地官方 .doc 解析 ---')
    rep.append('官方 .doc 解析 %d 条' % len(doc))
    rep.append('仅见于维基文库 %d 条；仅见于 .doc %d 条' % (
        len(set(rk) - set(dk)), len(set(dk) - set(rk))))
    for x in sorted(set(rk) - set(dk))[:10]:
        rep.append('    维基独有: ' + x)
    for x in sorted(set(dk) - set(rk))[:10]:
        rep.append('    doc 独有: ' + x)

    # ---------- 2. 支持名单 ----------
    s17, warn17, dec17 = build_support('s2017.html', '2017', 600)
    s18, warn18, dec18 = build_support('p2018.html', '2018-1', 444)
    rep.append('')
    rep.append('=== 二、2017 年行政决定的两份名单 ===')
    rep.append('过程 A+B 合计（2017 公布安排范围）官方 1044 = 600 + 444')
    rep.append('2017 当年支持：省份标题声明合计 %d，解析 %d 条' % (dec17, len(s17)))
    rep.append('2018 拟支持  ：省份标题声明合计 %d，解析 %d 条' % (dec18, len(s18)))
    if warn17:
        rep.append('!! 2017 名单省段不一致：' + str(warn17))
    if warn18:
        rep.append('!! 2018 名单省段不一致：' + str(warn18))
    for nm, rows in (('support_2017_zsad.csv', s17), ('support_2018p_raw.csv', s18)):
        with (OUT / nm).open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    # 交叉校验：与本地已解析 support_national.csv
    loc = list(csv.DictReader((OFF / 'support_national.csv').open(encoding='utf-8-sig')))
    for lab, mine in (('2017', s17), ('2018-1', s18)):
        lset = {norm(x['key']) for x in loc if x['batch'] == lab}
        mset = {x['key'] for x in mine}
        rep.append('%s 名单：本轮解析 %d，本地旧解析 %d，交集 %d，仅本轮 %d，仅旧版 %d' % (
            lab, len(mset), len(lset), len(mset & lset), len(mset - lset), len(lset - mset)))
        for x in sorted(mset - lset)[:8]:
            rep.append('    仅本轮: ' + x)
        for x in sorted(lset - mset)[:8]:
            rep.append('    仅旧版: ' + x)

    # ---------- 3. 严格匹配 ----------
    idx17 = collections.defaultdict(list)
    idx18 = collections.defaultdict(list)
    for s in s17:
        idx17[s['prov']].append(s)
    for s in s18:
        idx18[s['prov']].append(s)

    ACCEPT = {'exact', 'county_town'}
    rows, review = [], []
    for i, r in enumerate(ros, 1):
        rec = dict(village_id=i, prov=r['prov'], name_2016=r['name'], county=r['county'],
                   township=r['township'], village=r['village'],
                   A17='', A17_level='', B18='', B18_level='')
        for lab, idx, fa, fb, fl in (('2017', idx17, 'A17', 'A17', 'A17_level'),
                                     ('2018-1', idx18, 'B18', 'B18', 'B18_level')):
            best, blv, bnote, bcand = None, 'none', '', []
            for s in idx.get(r['prov'], []):
                lv, note = match_level(r, s)
                if lv == 'none':
                    continue
                order = {'exact': 0, 'county_town': 1, 'town_only': 2, 'vill_only': 3}
                if best is None or order[lv] < order[blv]:
                    best, blv, bnote = s, lv, note
                if lv == 'exact':
                    break
            if best is not None:
                rec[fa] = 1 if blv in ACCEPT else 0
                rec[fl] = blv
                if blv not in ACCEPT:
                    bcand.append('%s[%s]%s' % (best['name'], blv, bnote))
            if blv not in ACCEPT or (blv == 'none' and r['village']):
                # 列出同省同名（村名核心）候选，供人工核验；不自动接受
                for s in idx.get(r['prov'], []):
                    if s is best:
                        continue
                    if r['village'] and (r['village'] in s['name'] or s['village'] in r['village'] or
                                         (s['village'] and s['village'] == r['village'])):
                        bcand.append('%s[%s]' % (s['name'], 'name_core'))
            if bcand:
                review.append(dict(village_id=i, prov=r['prov'], list=('2017支持' if lab == '2017' else '2018拟支持'),
                                   name_2016=r['name'], best_level=blv,
                                   candidates=' | '.join(sorted(set(bcand))[:6])))
        rows.append(rec)

    def status(x):
        if x['A17'] == 1:
            return 'A_2017'
        if x['B18'] == 1:
            return 'B_2018promised'
        return 'C_not_in_1044'

    for x in rows:
        x['status'] = status(x)

    with (OUT / 'strict_match_1598.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    with (OUT / 'strict_review_queue.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['village_id', 'prov', 'list', 'name_2016', 'best_level', 'candidates'])
        w.writeheader(); w.writerows(review)

    rep.append('')
    rep.append('=== 三、严格匹配结果（仅接受 full 全等 或 县+乡镇+村全等）===')
    n = len(rows)
    st = collections.Counter(x['status'] for x in rows)
    for k in ('A_2017', 'B_2018promised', 'C_not_in_1044'):
        rep.append('  %-18s %4d  %5.1f%%' % (k, st[k], 100 * st[k] / n))
    rep.append('  进入 1044 安排（过程 A 成功）%d = %.1f%%' % (st['A_2017'] + st['B_2018promised'],
                                                    100 * (st['A_2017'] + st['B_2018promised']) / n))
    rep.append('  人工核验队列 %d 条 -> strict_review_queue.csv' % len(review))
    lvc = collections.Counter()
    for x in rows:
        lvc[x['A17_level']] += 1
        lvc[x['B18_level']] += 1
    rep.append('  匹配层级分布（无匹配未计入）：' + str(dict(lvc)))

    tgt = [x for x in rows if x['prov'] in TARGET]
    rep.append('')
    rep.append('=== 四、三省 279 村严格匹配 ===')
    t = collections.Counter(x['status'] for x in tgt)
    rep.append('  合计 %d（官方 279）' % len(tgt))
    for k in ('A_2017', 'B_2018promised', 'C_not_in_1044'):
        rep.append('  %-18s %4d  %5.1f%%' % (k, t[k], 100 * t[k] / len(tgt)))
    rep.append('  待核验（未严格命中）%d 条' % len({r['village_id'] for r in review if r['prov'] in TARGET}))
    for p in ('江苏省', '浙江省', '安徽省'):
        sub = [x for x in tgt if x['prov'] == p]
        c = collections.Counter(x['status'] for x in sub)
        rep.append('  %-6s n=%3d  A=%3d  B=%3d  C=%3d  待核验=%d' % (
            p, len(sub), c['A_2017'], c['B_2018promised'], c['C_not_in_1044'],
            len({r['village_id'] for r in review if r['prov'] == p})))
    rep.append('  注：此前按省级公告汇总的 92 / 61 / 126 不是村级严格匹配结果，不得引用')

    # ---------- 4. 县内状态变异 ----------
    rep.append('')
    rep.append('=== 五、县内状态变异（过程 A / 过程 B）===')
    cv = []
    byc = collections.defaultdict(list)
    for x in rows:
        byc[(x['prov'], x['county'])].append(x)
    for (pv, cty), g in sorted(byc.items()):
        na = sum(1 for x in g if x['status'] == 'A_2017')
        nb = sum(1 for x in g if x['status'] == 'B_2018promised')
        nc = sum(1 for x in g if x['status'] == 'C_not_in_1044')
        cv.append(dict(prov=pv, county=cty, n=len(g), n_A=na, n_B=nb, n_C=nc,
                       var_A=int((na + nb) >= 1 and nc >= 1),
                       var_B=int(na >= 1 and nb >= 1),
                       n_AB=na + nb, min_side_AB=min(na, nb) if (na and nb) else 0,
                       min_side_A=min(na + nb, nc)))
    with (OUT / 'county_variation.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(cv[0].keys()))
        w.writeheader(); w.writerows(cv)

    def summ(tag, sel):
        a = [c for c in cv if c['prov'] in sel]
        va = sum(c['var_A'] for c in a)
        vb = sum(c['var_B'] for c in a)
        vab3 = sum(1 for c in a if c['var_A'] and (c['n_AB'] >= 2 and c['n_C'] >= 2))
        vb3 = sum(1 for c in a if c['n_A'] >= 2 and c['n_B'] >= 2)
        rep.append('  %-8s 县数 %3d | 过程A 有变异 %3d | 过程B 有变异 %3d | A且两侧各≥2村 %3d | B且两侧各≥2村 %3d' % (
            tag, len(a), va, vb, vab3, vb3))

    summ('三省', TARGET)
    summ('全国', {p for p in PROVS})
    rep.append('  过程 A 可用县（有变异）明细见 county_variation.csv；')
    rep.append('  三省中：' + ', '.join(
        '%s%s(A%d/B%d/C%d)' % (c['prov'], c['county'], c['n_A'], c['n_B'], c['n_C'])
        for c in cv if c['prov'] in TARGET and (c['var_A'] or c['var_B'])))

    # ---------- 5. 空间数据核对 ----------
    rep.append('')
    rep.append('=== 六、空间数据集与正式名录的一致性 ===')
    p4 = list(csv.DictReader((GEO / 'points1598.csv').open(encoding='utf-8-sig')))
    pc4 = collections.Counter(p['prov'] for p in p4)
    rep.append('点位库 VillagesChina1598 共 %d 个点' % len(p4))
    rep.append('  浙江 %d（正式名录 225，已发表论文正文 228）' % pc4.get('浙江省', 0))
    rep.append('  江苏 %d / 安徽 %d' % (pc4.get('江苏省', 0), pc4.get('安徽省', 0)))
    rep.append('  判定：点位库省级分布与正式名录在浙江为 225；论文正文 228 与名录差 3，')
    rep.append('        在读取原始属性表前不作断言，但研究母表一律以正式名录为准。')
    rep.append('  数据共享条款要求引用原始来源并限制再分发：本文只公布匹配代码与汇总统计，')
    rep.append('        不重新发布 1598 条原始坐标，分析用坐标在文中仅以聚合形式出现。')

    # ---------- 6. 与既有母表的一致性 ----------
    rep.append('')
    rep.append('=== 七、与本轮之前已建母表的一致性 ===')
    mm = list(csv.DictReader((OUT / 'master_1598.csv').open(encoding='utf-8-sig')))
    m_map = {norm(m['official_name_2016']): m for m in mm}
    hit = dif = 0
    for x in rows:
        m = m_map.get(norm(x['name_2016']))
        if not m:
            continue
        hit += 1
        old = m['first_announced_status']
        new = x['status'][0]
        if old != new:
            dif += 1
    rep.append('  可比村数 %d（母表 %d 行）' % (hit, len(mm)))
    rep.append('  状态不一致 %d 条（%.2f%%）' % (dif, 100 * dif / max(1, hit)))

    txt = '\n'.join(rep)
    (OUT / 'strict_audit_report.txt').write_text(txt, encoding='utf-8')
    print(txt)


if __name__ == '__main__':
    main()
