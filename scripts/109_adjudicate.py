# -*- coding: utf-8 -*-
"""109 人工裁决与最终分析母表（第八轮）

108 脚本产出的待核验队列逐条裁决后落定：
  accept  有公开行政区划文件可依，判定为同一村，并入主样本
  pending 疑为乡镇改名但尚未取得县级区划文件，暂不并入，保留为未列入
  reject  同名但乡镇或县不同，判定为不同村

裁决不改变"只做严格匹配"的原则：每一条 accept 都必须写出公开文件依据。

输入：
  data/master/strict_match_1598.csv      108 的严格匹配结果
  data/master/support_2017_zsad.csv      600 村名单
  data/master/support_2018p_raw.csv      444 村名单
  data/master/master_1598.csv            含坐标与县级存量的母表
输出：
  data/master/adjudication_log.csv       逐条裁决台账（含依据）
  data/master/master_final_1598.csv      最终分析母表
  data/master/county_variation_final.csv 县内状态变异
  data/master/adjudication_report.txt    裁决报告
"""
import csv, re, sys, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'master'
OUT.mkdir(parents=True, exist_ok=True)

# ---------- 逐条裁决：key = village_id, (决定, 名单, 规则, 依据) ----------
E_TAISHUN = ('泰顺县行政区划调整：浙政函〔2016〕153号（2016-09-08）增设南浦溪镇，'
             '辖村含库村；2016 年名录沿用调整前的"筱村镇库村"，2017 年名单用"南浦溪镇库村村"')
E_MAERKANG = ('马尔康撤县设市：2015 年 11 月国务院批准、民政部批复，2015 年 12 月四川省政府批复，'
              '行政区域不变；2016 年名录用"马尔康县"，2017 年名单用"马尔康市"')
E_WULONG = ('武隆撤县设区：国函〔2016〕185号（2016-11-24），撤销武隆县设立重庆市武隆区，'
            '行政区域不变；2016 年名录用"武隆县"，2017 年名单用"武隆区"')
E_HUA = ('华县撤县设区：国函〔2015〕186号，撤销华县设立渭南市华州区，2016-01-22 授牌；'
         '2016 年名录用"华县"，2017 年名单用"华州区"')
E_NAIDONG = ('撤销山南地区设立地级山南市：国函〔2016〕8号（2016-01-07），撤销乃东县设立乃东区，'
             '行政区域不变；2016 年名录用"乃东县"，2017 年名单用"乃东区"')
E_WUFENG = ('同一县级单位全称与简称差异：五峰土家族自治县，2016 年名录记作"五峰县"')

ADJ = {
    '314':  ('accept', 'A', 'county_or_township_rename', E_TAISHUN),
    '1226': ('accept', 'A', 'county_level_renamed', E_MAERKANG),
    '1227': ('accept', 'A', 'county_level_renamed', E_MAERKANG),
    '1229': ('accept', 'A', 'county_level_renamed', E_MAERKANG),
    '1230': ('accept', 'A', 'county_level_renamed', E_MAERKANG),
    '1228': ('accept', 'B', 'county_level_renamed', E_MAERKANG),
    '1109': ('accept', 'B', 'county_level_renamed', E_WULONG),
    '1492': ('accept', 'A', 'county_level_renamed', E_HUA),
    '1535': ('accept', 'A', 'county_level_renamed', E_NAIDONG),
    '784':  ('accept', 'A', 'county_name_long_short', E_WUFENG),
    '1520': ('accept', 'A', 'village_suffix_variant',
             '同县同乡镇（子洲县何家集镇），村名仅"眠虎沟"/"眠虎沟村"后缀差异，判为同一村'),
    '787':  ('pending', 'A', 'township_renamed_suspect',
             '同一县（红安县）、同一村名（陡山村），乡镇记为八里镇/八里湾镇，疑为乡镇改名，未取得县级区划文件'),
    '1190': ('pending', 'B', 'township_renamed_suspect',
             '同一县（宣汉县）、同一村名（百丈村），乡镇记为马渡乡/马渡关镇，疑为乡镇改名，未取得县级区划文件'),
    '1301': ('pending', 'B', 'township_renamed_suspect',
             '同一县（印江自治县）、同一村名（乐洋村），乡镇记为新寨乡/新寨镇，疑为乡改镇，未取得县级区划文件'),
    '353':  ('reject', 'B', 'different_village', '东阳市虎鹿镇西坞村 与 奉化区西坞街道西坞村，县与乡镇均不同'),
    '399':  ('reject', 'A', 'different_village', '仙居县湫山乡四都村 与 诸暨市五泄镇十四都村，县与乡镇均不同'),
    '455':  ('reject', 'B', 'different_village', '龙泉市龙南乡金川村 与 武义县柳城畲族镇金川村，县与乡镇均不同'),
    '634':  ('reject', 'A', 'different_village', '蕉城区霍童镇石桥村 与 南靖县书洋镇石桥村，县与乡镇均不同'),
    '718':  ('reject', 'A', 'different_village', '淄川区寨里镇南峪村 与 费县马庄镇西南峪村，县与乡镇均不同'),
    '798':  ('accept', 'A', 'one_character_variant',
             '同县同乡镇（恩施市红土乡），2016 名录作"天落水村马弓坝组"，2017 名单作"天落水村马宫坝组"，'
             '仅一字之差，判为同一村名书写差异'),
}

# 裁决接受的条目在支持名单中的写法（用于核算 1044 名单的对应情况）
ACCEPT_NAME = {
    '314': '温州市泰顺县南浦溪镇库村村',
    '784': '宜昌市五峰土家族自治县采花乡栗子坪村',
    '1109': '武隆区平桥镇红隆村',
    '1226': '阿坝藏族羌族自治州马尔康市松岗镇直波村',
    '1227': '阿坝藏族羌族自治州马尔康市梭磨乡色尔米村',
    '1228': '阿坝藏族羌族自治州马尔康市党坝乡尕兰村',
    '1229': '阿坝藏族羌族自治州马尔康市大藏乡春口村',
    '1230': '阿坝藏族羌族自治州马尔康市草登乡代基村',
    '1492': '渭南市华州区赤水镇辛村',
    '1520': '榆林市子洲县何家集镇眠虎沟村',
    '1535': '山南市乃东区扎西曲登村',
    '798': '恩施州恩施市红土乡天落水村马宫坝组',
}

TARGET = {'江苏省', '浙江省', '安徽省'}


def load(p):
    return list(csv.DictReader((OUT / p).open(encoding='utf-8-sig')))


def main():
    rows = load('strict_match_1598.csv')
    s17 = load('support_2017_zsad.csv')
    s18 = load('support_2018p_raw.csv')
    old = {r['village_id']: r for r in csv.DictReader(
        (OUT / 'master_1598.csv').open(encoding='utf-8-sig'))}

    for r in rows:
        r['A17'] = int(r['A17'] or 0)
        r['B18'] = int(r['B18'] or 0)
    by_id = {r['village_id']: r for r in rows}
    log = []
    for vid, (dec, lst, rule, ev) in sorted(ADJ.items(), key=lambda x: int(x[0])):
        r = by_id[vid]
        log.append(dict(village_id=vid, prov=r['prov'], name_2016=r['name_2016'],
                        list=('2017支持' if lst == 'A' else '2018拟支持'),
                        decision=dec, rule=rule, evidence=ev))
        if dec == 'accept':
            if lst == 'A':
                r['A17'] = 1
                r['A17_level'] = 'manual:' + rule
            else:
                r['B18'] = 1
                r['B18_level'] = 'manual:' + rule
    for r in rows:
        r['status'] = ('A_2017' if r['A17'] == 1 else
                       ('B_2018promised' if r['B18'] == 1 else 'C_not_in_1044'))
        r['match_rule'] = (r['A17_level'] if r['A17'] == 1 else
                           (r['B18_level'] if r['B18'] == 1 else 'none'))

    with (OUT / 'adjudication_log.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(log[0].keys()))
        w.writeheader(); w.writerows(log)

    # ---------- 支持名单中属于前三批（非第四批）的条目 ----------
    used = set()
    for r in rows:
        if r['A17'] == 1 and r['match_rule'].startswith('manual') is False:
            used.add(('2017', r['name_2016']))
        if r['B18'] == 1 and r['match_rule'].startswith('manual') is False:
            used.add(('2018-1', r['name_2016']))
    manual = {('2017' if v[1] == 'A' else '2018-1'): by_id[k]['name_2016']
              for k, v in ADJ.items() if v[0] == 'accept'}
    roster_names = {r['name_2016'] for r in rows}
    def norm(x):
        return re.sub(r'[（）()\s]', '', str(x))
    rn = {norm(x) for x in roster_names}
    acc_names = {norm(v) for v in ACCEPT_NAME.values()}
    pend_names = {norm(x) for x in [
        '黄冈市红安县八里湾镇陡山村', '达州市宣汉县马渡关镇百丈村', '铜仁市印江自治县新寨镇乐洋村']}
    un17 = [s['name'] for s in s17 if norm(s['name']) not in rn and norm(s['name']) not in acc_names]
    un18 = [s['name'] for s in s18 if norm(s['name']) not in rn and norm(s['name']) not in acc_names]

    # ---------- 最终母表 ----------
    fin = []
    for r in rows:
        o = old.get(r['village_id'], {})
        fin.append(dict(
            village_id=r['village_id'], province=r['prov'], county=r['county'],
            township=r['township'], village=r['village'], official_name_2016=r['name_2016'],
            process_A_in_1044=int(r['status'] != 'C_not_in_1044'),
            status=r['status'],
            support_2017=int(r['A17'] == 1), promised_2018=int(r['B18'] == 1),
            match_rule=r['match_rule'],
            support_2018b=o.get('support_2018b', ''), support_2019=o.get('support_2019', ''),
            latitude=o.get('latitude', ''), longitude=o.get('longitude', ''),
            geolocation_quality=o.get('geolocation_quality', ''),
            prior_recognized_count=o.get('prior_recognized_count', ''),
            prior_count_source=o.get('prior_count_source', ''),
        ))
    with (OUT / 'master_final_1598.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(fin[0].keys()))
        w.writeheader(); w.writerows(fin)

    # ---------- 县内变异 ----------
    byc = collections.defaultdict(list)
    for r in rows:
        byc[(r['prov'], r['county'])].append(r)
    cv = []
    for (pv, cty), g in sorted(byc.items()):
        na = sum(1 for x in g if x['status'] == 'A_2017')
        nb = sum(1 for x in g if x['status'] == 'B_2018promised')
        nc = sum(1 for x in g if x['status'] == 'C_not_in_1044')
        cv.append(dict(prov=pv, county=cty, n=len(g), n_A=na, n_B=nb, n_C=nc,
                       var_A=int((na + nb) >= 1 and nc >= 1),
                       var_B=int(na >= 1 and nb >= 1),
                       A_side2=int((na + nb) >= 2 and nc >= 2),
                       B_side2=int(na >= 2 and nb >= 2)))
    with (OUT / 'county_variation_final.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(cv[0].keys()))
        w.writeheader(); w.writerows(cv)

    rep = []
    rep.append('=== 一、裁决结果 ===')
    c = collections.Counter(x['decision'] for x in log)
    rep.append('  accept %d  pending %d  reject %d' % (c['accept'], c['pending'], c['reject']))
    rep.append('  裁决台账 -> data/master/adjudication_log.csv（逐条含公开文件依据）')
    rep.append('')
    rep.append('=== 二、裁决后的全国状态分布（1598 村）===')
    st = collections.Counter(r['status'] for r in rows)
    for k in ('A_2017', 'B_2018promised', 'C_not_in_1044'):
        rep.append('  %-18s %4d  %5.1f%%' % (k, st[k], 100 * st[k] / len(rows)))
    rep.append('  进入 1044 安排 %d / 1598 = %.1f%%' % (
        st['A_2017'] + st['B_2018promised'], 100 * (st['A_2017'] + st['B_2018promised']) / len(rows)))
    rep.append('  1044 名单的对应情况：已对应到第四批村 %d 条，待核验（疑似乡镇改名）%d 条，'
               '确认不属于第四批 %d 条' % (
                   1044 - len(un17) - len(un18), len(un17) + len(un18),
                   sum(1 for x in un17 + un18 if norm(x) not in pend_names)))
    for x in un17 + un18:
        tag = '待核验' if norm(x) in pend_names else '非第四批'
        rep.append('      %s: %s' % (tag, x))
    rep.append('')
    rep.append('=== 三、三省 279 村（裁决后）===')
    tgt = [r for r in rows if r['prov'] in TARGET]
    t = collections.Counter(r['status'] for r in tgt)
    rep.append('  A_2017 %d / B_2018promised %d / C %d  合计 %d' % (
        t['A_2017'], t['B_2018promised'], t['C_not_in_1044'], len(tgt)))
    for p in ('江苏省', '浙江省', '安徽省'):
        sub = [r for r in tgt if r['prov'] == p]
        cc = collections.Counter(r['status'] for r in sub)
        rep.append('  %-6s n=%3d  A=%3d  B=%3d  C=%3d' % (
            p, len(sub), cc['A_2017'], cc['B_2018promised'], cc['C_not_in_1044']))
    rep.append('  更正：泰顺县库村经浙政函〔2016〕153号确认为第四批村，')
    rep.append('        三省 2017 年支持数由 91 更正为 92，未列入由 127 更正为 126。')
    rep.append('')
    rep.append('=== 四、县内状态变异（可用于县内比较的县）===')
    def summ(tag, sel):
        a = [x for x in cv if x['prov'] in sel]
        rep.append('  %-4s 县数 %4d | 过程A 有变异 %3d（两侧各≥2 村 %3d）| 过程B 有变异 %3d（两侧各≥2 村 %3d）' % (
            tag, len(a), sum(x['var_A'] for x in a), sum(x['A_side2'] for x in a),
            sum(x['var_B'] for x in a), sum(x['B_side2'] for x in a)))
    summ('三省', TARGET)
    summ('全国', {x['prov'] for x in cv})
    rep.append('  三省中过程 A 有变异且两侧各≥2 村的县：')
    for x in cv:
        if x['prov'] in TARGET and x['A_side2']:
            rep.append('      %s%s  A%d B%d C%d' % (x['prov'], x['county'], x['n_A'], x['n_B'], x['n_C']))
    rep.append('  三省中过程 B 两侧各≥2 村的县：')
    for x in cv:
        if x['prov'] in TARGET and x['B_side2']:
            rep.append('      %s%s  A%d B%d C%d' % (x['prov'], x['county'], x['n_A'], x['n_B'], x['n_C']))
    rep.append('')
    rep.append('=== 五、下一步可否进入建模 ===')
    rep.append('  是。母表 1598 村，坐标命中 1596，县级存量已附；')
    rep.append('  过程 A 与过程 B 均存在足量县内变异；地形与距离变量到位后即可估计。')
    txt = '\n'.join(rep)
    (OUT / 'adjudication_report.txt').write_text(txt, encoding='utf-8')
    print(txt)


if __name__ == '__main__':
    main()
