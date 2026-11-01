# -*- coding: utf-8 -*-
"""147：2017 公告未匹配 3 条记录的定向裁决（第十七轮，任务一）

目标不是找更好的回归结果，而是把 Appendix A.2 里"3 条未解决"定性：
对每一条未解决公告条目，回答三个二选一问题
  Q1 该条目是否可能对应第四批名录中的某个村（即潜在漏匹配的阳性记录）
  Q2 该条目是否可能对应前三批名录中的某个村（即根本不属于本次研究母表）
  Q3 若 Q1 为真，候选是否唯一（唯一 -> 分类；不唯一 -> 只能做包围）

检验手段全部是预先限定的：
  T1 名录内同县同名村检索（村名去"村"后缀）
  T2 前三批 2550 点位同名村检索
  T3 该条公告所属县的其余条目是否全部闭合（排除整段解析错误）
  T4 候选村是否落在冻结的有效估计组内（决定是否可能影响主系数）

输入：
  data/master/support_2017_zsad.csv       600 村名单（独立重建）
  data/master/support_2018p_raw.csv       444 村名单（独立重建）
  data/master/master_final_1598.csv       第四批母表（冻结）
  data/master/adjudication_log.csv        既有裁决台账
  data/master/geo_points_pre2555_v4.csv   前三批 2550 点位
  data/master/exposure_v3.csv             冻结分析文件
输出：
  data/master/pending3_report.txt         逐条裁决报告
  data/master/pending3_candidates.csv     候选清单（含跨库证据）
"""
import csv, sys, os, re, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'data', 'master')


def load(p):
    return list(csv.DictReader(open(os.path.join(D, p), encoding='utf-8-sig')))


def nz(x):
    return re.sub(r'[\s（）()]', '', str(x))


def vcore(x):
    """村名核心：去行政区划后缀与'村'字"""
    x = nz(x)
    x = re.sub(r'(村民委员会|村委会|村委)$', '', x)
    return re.sub(r'村$', '', x)


def main():
    rep, cands = [], []
    m = load('master_final_1598.csv')
    s17 = load('support_2017_zsad.csv')
    s18 = load('support_2018p_raw.csv')
    pre = load('geo_points_pre2555_v4.csv')
    exp = {r['vid']: r for r in load('exposure_v3.csv')}

    # ---------- 0. 复算未解决集合（与 109 完全同口径） ----------
    rn = {nz(r['official_name_2016']) for r in m}
    acc = {'温州市泰顺县南浦溪镇库村村', '宜昌市五峰土家族自治县采花乡栗子坪村',
           '武隆区平桥镇红隆村', '阿坝藏族羌族自治州马尔康市松岗镇直波村',
           '阿坝藏族羌族自治州马尔康市梭磨乡色尔米村', '阿坝藏族羌族自治州马尔康市党坝乡尕兰村',
           '阿坝藏族羌族自治州马尔康市大藏乡春口村', '阿坝藏族羌族自治州马尔康市草登乡代基村',
           '渭南市华州区赤水镇辛村', '榆林市子洲县何家集镇眠虎沟村', '山南市乃东区扎西曲登村',
           '恩施州恩施市红土乡天落水村马宫坝组'}
    accn = {nz(x) for x in acc}
    un17 = [s for s in s17 if nz(s['name']) not in rn and nz(s['name']) not in accn]
    un18 = [s for s in s18 if nz(s['name']) not in rn and nz(s['name']) not in accn]
    unresolved = [('2017支持', s) for s in un17] + [('2018拟支持', s) for s in un18]

    rep.append('=== 一、公告侧账目复算 ===')
    rep.append('2017 名单 %d 条，2018 拟支持名单 %d 条，合计 %d 条' % (len(s17), len(s18), len(s17) + len(s18)))
    rep.append('其中已与第四批名录（含 12 条人工裁决）对应：%d 条' % (len(s17) + len(s18) - len(unresolved)))
    rep.append('未解决：%d 条' % len(unresolved))
    for lab, s in unresolved:
        rep.append('  [%s] %s | %s | %s | %s' % (lab, s['prov'], s['county'], s['township'], s['village']))

    # ---------- 1. 逐条检验 ----------
    by_prov_cty = collections.defaultdict(list)
    for r in m:
        by_prov_cty[(r['province'], r['county'])].append(r)
    pre_idx = collections.defaultdict(list)
    for p in pre:
        pre_idx[(p['prov'], p['dist'])].append(p)

    rep.append('')
    rep.append('=== 二、逐条裁决 ===')
    verdict = {}
    for lab, s in unresolved:
        pv, ct, tw, vl = s['prov'], s['county'], s['township'], s['village']
        rep.append('')
        rep.append('--- %s：%s%s%s ---' % (lab, pv, ct, tw + vl))

        # T1 第四批名录内同交所涉"县级单位"的同名村（只用村名核心，不看乡镇）
        same_cty = [r for r in by_prov_cty.get((pv, ct), []) if vcore(r['village']) == vcore(vl)]
        rep.append('  T1 第四批名录同县同名村：%d 个 -> %s' % (
            len(same_cty), '、'.join('%s(%s)' % (r['village'], r['township']) for r in same_cty[:6])))

        # T2 前三批 2550 点位中的同名村
        pre_same = [p for p in pre_idx.get((pv, ct), []) if vcore(p['vill']) == vcore(vl)]
        pre_any = [p for p in pre if vcore(p['vill']) == vcore(vl)]
        rep.append('  T2 前三批点位同县同名村：%d 个；全国同名村：%d 个' % (
            len(pre_same), len(pre_any)))

        # T3 该县其余公告条目是否闭合
        pool = s17 if lab == '2017支持' else s18
        same_cty_entries = [x for x in pool if x['prov'] == pv and x['county'] == ct]
        closed = [x for x in same_cty_entries
                  if nz(x['name']) in rn or nz(x['name']) in accn]
        rep.append('  T3 该县本批公告条目 %d 条，其中已闭合 %d 条' % (len(same_cty_entries), len(closed)))

        for r in same_cty:
            e = exp.get(r['village_id'])
            insample = '是' if e else '否（无坐标或已剔除）'
            cands.append(dict(list=lab, entry=s['name'], entry_county=ct, entry_township=tw,
                              candidate_vid=r['village_id'], candidate_name=r['official_name_2016'],
                              candidate_township=r['township'], roster_status=r['status'],
                              pre_cohort_same_county=len(pre_same),
                              pre_cohort_anywhere=len(pre_any),
                              in_analysis_file=insample,
                              grp=(e['grp'] if e else ''), yA=(e['yA'] if e else ''),
                              dist_km=(e['dist_km'] if e else '')))

        if len(same_cty) == 1 and not pre_same:
            call = '唯一候选：第四批名录中同县同名村恰有 1 个，且前三批点位中该县无同名村'
            typ = '潜在漏匹配阳性（Q1 真 / Q2 假）'
        elif len(same_cty) == 1 and pre_same:
            call = '同县同名村在第四批与前三批同时存在'
            typ = '候选不唯一，需外部名录'
        elif not same_cty:
            call = '第四批名录该县无同名村'
            typ = '倾向不属于第四批母表'
        else:
            call = '第四批名录该县有多个同名村'
            typ = '候选不唯一'
        rep.append('  判定：%s —— %s' % (typ, call))
        verdict[(lab, s['name'])] = typ

    # ---------- 2. 候选是否落在有效估计组 ----------
    rep.append('')
    rep.append('=== 三、候选村是否进入过程 A 的有效估计组（95 县 560 村）===')
    by_grp = collections.defaultdict(list)
    for r in exp.values():
        by_grp[r['grp']].append(r)
    info = {g for g, v in by_grp.items() if 1 <= sum(int(x['yA']) for x in v) <= len(v) - 1}
    n_in = sum(len(by_grp[g]) for g in info)
    rep.append('  有效组：%d 县，%d 村（复算，应与冻结值一致）' % (len(info), n_in))
    ids = [c['candidate_vid'] for c in cands]
    for vid in ids:
        e = exp.get(vid)
        if not e:
            rep.append('  vid %s：不在分析文件内' % vid)
            continue
        rep.append('  vid %-5s %-28s grp=%-12s yA=%s %s' % (
            vid, e['village'], e['grp'], e['yA'],
            '在有效组内' if e['grp'] in info else '不在有效组内（该县 yA 无县内变异）'))

    txt = '\n'.join(rep)
    open(os.path.join(D, 'pending3_report.txt'), 'w', encoding='utf-8').write(txt)
    if cands:
        keys = list(cands[0].keys())
        with open(os.path.join(D, 'pending3_candidates.csv'), 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(cands)
    print(txt)


if __name__ == '__main__':
    main()
