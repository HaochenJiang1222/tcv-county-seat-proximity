# -*- coding: utf-8 -*-
"""151：v1.4 两项交付验收（第十七轮）

一、冻结数值一致性：把 v1.4 正文出现的每一个报告值，回查它是否存在于
   冻结输出文件（national_results_v3.txt / checks_139.txt / pending3_sensitivity.txt /
   source_provenance.txt）。出现即通过，查不到即报错，不断言近似相等。
二、遗留标记清零：R1 审校稿里所有 Editorial verification required 之类的占位，
   v1.4 必须全部消失或明确降级为"作者待填"（仅允许 DOI/URL/模型版本三项）。
三、复现包冒烟测试：直接用 replication/data/analysis_input_public.csv 重跑
   过程A/过程B的条件Logit点估计，必须复现 −0.370 与 0.312，且有效组为 95/560。

用法 python dofile/151_verify_v14.py [版本号，默认 v1.4]
"""
import csv, sys, os, re, collections

sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from statsmodels.discrete.conditional_models import ConditionalLogit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER = sys.argv[1] if len(sys.argv) > 1 else 'v1.4'
MD = os.path.join(ROOT, 'output', 'manuscript_TCV_EN_%s.md' % VER)
D = os.path.join(ROOT, 'data', 'master')
PKG = os.path.join(ROOT, 'replication')
fail, warn, ok = [], [], []


def P(t):
    print(t, flush=True)


def norm_minus(s):
    return s.replace('\u2212', '-').replace('\u2013', '-')


txt = norm_minus(open(MD, encoding='utf-8').read())
SRC = {}
for fn in ('national_results_v3.txt', 'checks_139.txt', 'county_table_v3.txt',
           'contrast_test.txt', 'pending3_sensitivity.txt',
           'source_provenance.txt', 'pending3_report.txt',
           'county_center_check153.txt', 'county_center_audit.txt'):
    p = os.path.join(D, fn)
    SRC[fn] = norm_minus(open(p, encoding='utf-8').read()) if os.path.exists(p) else ''
pool = '\n'.join(SRC.values())

P('=== 一、报告值回查（每一个值都必须能在冻结输出里找到）===')
# (标签, 正文中出现的写法, 冻结输出中的写法)
CHECKS = [
    ('过程A 条件Logit 系数', '-0.370', '-0.370'),
    ('过程A 条件Logit CI 下界', '-0.838', '-0.838'),
    ('过程A 条件Logit CI 上界', '-0.067', '-0.067'),
    ('过程A 条件Logit p', '0.025', '0.025'),
    ('过程A LPM 全样本系数', '-0.034', '-0.034'),
    ('过程A LPM 全样本 CI', '-0.073, 0.002', '-0.073,  0.002'),
    ('过程A LPM 有效组系数', '-0.088', '-0.088'),
    ('过程A LPM 有效组 CI', '-0.180, -0.008', '-0.180, -0.008'),
    ('县等权距离对比', '-1.92', '-1.92'),
    ('县等权距离 CI', '-4.51, 0.63', '-4.51, 0.63'),
    ('县内进入率差', '-0.039', '-0.039'),
    ('尺度换算 OR', '0.683', '0.683'),
    ('过程B 系数', '0.312', '0.312'),
    ('过程B CI', '-0.173, 0.856', '-0.173,  0.856'),
    ('历史暴露距离型差', '0.157', '0.157'),
    ('历史暴露计数型差', '-0.108', '-0.108'),
    ('规模交互', '0.310', '0.310'),
    ('误分类敏感性 系数', '-0.342', '-0.342'),
    ('误分类敏感性 CI', '-0.789, 0.044', '-0.789,  0.044'),
    ('误分类敏感性 p', '0.068', '0.068'),
    ('敏感性下 LPM 全样本', '-0.031', '-0.031'),
    ('敏感性下 LPM 全样本 CI', '-0.070, 0.005', '-0.070,  0.005'),
    ('敏感性下 LPM 有效组', '-0.081', '-0.081'),
    ('敏感性下 LPM 有效组 CI', '-0.165, 0.007', '-0.165,  0.007'),
    ('参考点替代 系数', '-0.170', '-0.170'),
    ('参考点替代 CI', '-0.691, 0.263', '-0.691,  0.263'),
    ('参考点替代 p', '0.445', '0.445'),
    ('参考点替代 LPM 全样本', '-0.015', '-0.015'),
    ('参考点替代 LPM 有效组', '-0.039', '-0.039'),
    ('参考点替代 OR', '0.838', '0.838'),
    ('参考点替代 OR CI', '0.489, 1.314', '0.489, 1.314'),
]
for lab, inms, insrc in CHECKS:
    hit_md = inms in txt
    hit_src = insrc in pool
    if hit_md and hit_src:
        ok.append(lab)
    elif not hit_md:
        fail.append('%s：正文未出现 %s' % (lab, inms))
    else:
        fail.append('%s：冻结输出查不到 %s' % (lab, insrc))
P('  通过 %d / %d' % (len(ok), len(CHECKS)))

P('')
P('=== 二、A.7 溯源表回查 ===')
prov = SRC.get('source_provenance.txt', '')
for h in ('0cf8686208af1a0e', '3fd8808c76c3c1aa', '1ece24a27c1cbdf3', 'e9ca5346d2296a06',
          '93fa924b7f3b702b', 'db972fc4928c9f54', '079dcd1add75a27b', '15f5852dc7b7efd8',
          '0f49e95a1e1c4d7b'):
    if h in txt and h in prov:
        ok.append('校验和 ' + h)
    elif h not in prov:
        fail.append('冻结溯源清单里没有 ' + h)
    else:
        fail.append('A.7 里缺校验和 ' + h)
P('  已核对 9 个文件校验和')

P('')
P('=== 二之二、县中心点定义核验回查 ===')
CCHK = [
    ('自算质心与 centroid 字段', '0.03', '0.027'),
    ('用县 center-质心 中位距离', '11.2', '11.24'),
    ('center-质心 > 1km 的县数', '523', '523'),
    ('用县数（点在多边形内）', '525', '525'),
    ('>5km 占比', '85.7', '85.7'),
    ('center 到驻地 中位', '0.47', '0.47'),
    ('质心到驻地 最大', '157.14', '157.14'),
]
for lab, inms, insrc in CCHK:
    hit_md = inms in txt
    hit_src = insrc in pool
    if hit_md and hit_src:
        ok.append('定义核验 ' + lab)
    elif not hit_md:
        fail.append('%s：正文未出现 %s' % (lab, inms))
    else:
        fail.append('%s：核验输出查不到 %s' % (lab, insrc))
P('  已核对 %d 项定义核验统计' % len(CCHK))

P('')
P('=== 二之三、历史公告官方文号登记 ===')
for doc in ('Jian Cun [2014] No. 106', 'Jian Cun [2014] No. 180', 'Jian Cun [2015] No. 120',
            'Jian Cun [2016] No. 59', 'Jian Cun [2016] No. 99', 'Jian Cun [2016] No. 297'):
    if doc in txt:
        ok.append('文号 ' + doc)
    else:
        fail.append('Table A5 缺少文号 ' + doc)
if 'mohurd.gov.cn' in txt:
    ok.append('部委来源链接已登记')
else:
    fail.append('缺少 mohurd.gov.cn 官方来源链接')
P('  已核对 6 个文号与部委链接')

P('')
P('')
P('=== 二之四、v1.6 定向修改回查 ===')
# 摘要词数
ab = txt.split('## Abstract')[1].split('**Keywords')[0]
ab = ab.split('---')[0].strip()
nw = len(ab.split())
if nw <= 200:
    ok.append('摘要 %d 词（MDPI 上限 200）' % nw)
else:
    fail.append('摘要 %d 词，超过 200 词上限' % nw)

V16 = [
    ('核心表述：特定于县政府驻地',
     'specific to distance from the county government seat', 1),
    ('未做系数差正式检验',
     'without a formal test of their coefficient difference', 1),
    ('市场可达性/交通/聚落混淆',
     'market accessibility, transport infrastructure, settlement patterns', 1),
    ('驻地坐标为当代代理变量',
     'contemporary geographical proxies', 1),
    ('县政府驻地中位分离度',
     '11.24', 1),
    ('两个 525 分母区分（县）',
     '525 audited county units', 1),
    ('两个 525 分母区分（村）',
     '525 villages in 88 counties', 1),
    ('AI 模型标识 GPT-6',
     'GPT-6', 2),
    ('归档版本 v1.0.0',
     'v1.0.0', 1),
    ('出版交付：声明不得把 AI 列为作者',
     'No AI system is credited as an author', 1),
    ('出版交付：归档 DOI 占位为方括号标记',
     'archival DOI: [PUBLISHED ZENODO DOI]', 1),
    ('引用编号占位不得当已发布',
     'a reserved or draft DOI must not be cited as published', 1),
    ('Methods 中 AI 披露小节',
     '### 3.5. Use of Generative AI Tools in Translation and Language Editing', 1),
    ('AI 用途限定为翻译与语言编辑',
     'translating Chinese source material into English', 1),
    ('AI 未参与数据与估计',
     'did not generate the administrative records', 1),
    ('Acknowledgments 不作 AI 贡献',
     'is not acknowledged here as a contribution', 1),
    ('v1.6 最终标题',
     "# Recognition as Eligibility: County-Seat Proximity and Access to Conservation Support Arrangements in China's Traditional Villages", 1),
    ('关键词收窄为驻地邻近',
     'county-seat proximity', 1),
    ('Introduction 研究目标句',
     'This study examines whether proximity to county government seats is associated with entry into publicly announced', 1),
    ('Introduction 边界句',
     'do not establish a uniform national geographical gradient or identify administrative friction as its underlying mechanism', 1),
    ('Discussion 参考点理论句',
     'the choice of geographical reference point matters for interpreting access to announced support arrangements', 1),
    ('Discussion 不宣称机制',
     'do not establish statistically distinct distance effects or identify the administrative mechanisms underlying the association', 1),
]
for bad2 in ('Geography as Friction', 'administrative center'):
    if bad2 in txt:
        fail.append('v1.6 仍残留旧表述：%s' % bad2)
    else:
        ok.append('v1.6 已清除旧表述 %s' % bad2)
for lab, pat, times in V16:
    c = txt.count(pat)
    if c >= times:
        ok.append('v1.6 %s（%d 处）' % (lab, c))
    else:
        fail.append('v1.6 缺 %s：正文出现 %d 处，要求 %d 处' % (lab, c, times))

# 术语统一：旧称必须清零，新称必须足够
if txt.count('county administrative center') == 0:
    ok.append('v1.6 术语统一：旧称 county administrative center 已清零')
else:
    fail.append('v1.6 仍出现旧称 county administrative center %d 处'
                % txt.count('county administrative center'))
if txt.count('county government seat') >= 8:
    ok.append('v1.6 术语统一：county government seat 出现 %d 处'
              % txt.count('county government seat'))
else:
    fail.append('v1.6 county government seat 仅 %d 处'
                % txt.count('county government seat'))
for bad in ('governrative', 'summarised', 'centre'):
    if bad in txt:
        fail.append('v1.6 出现拼写/拼接错误：%s' % bad)
    else:
        ok.append('v1.6 无 %s' % bad)
P('  已核对 %d 项 v1.6 定向修改 + 术语/拼写' % (len(V16) + 7))

P('=== 三、遗留标记清零 ===')
FORBID = ['Editorial verification required',
          'no public replication-repository URL has been provided',
          'No public repository URL is claimed',
          'before submission: identify the exact machine-parsed file',
          'Authors to confirm before submission',
          'code development and debugging',
          'methodological and reproducibility review',
          'manuscript drafting and language revision']
for f in FORBID:
    if f in txt:
        fail.append('仍存在遗留标记：' + f)
ALLOW = ['[VERIFIED GITHUB URL]', '[PUBLISHED ZENODO DOI]']
na = sum(1 for a in ALLOW if a in txt)
if na == 0:
    warn.append('DOI/仓库占位已填（若尚未真实 DOI，请恢复占位）')
else:
    ok.append('DOI/仓库占位保留 %d 处，待作者填写' % na)

P('')
P('=== 四、复现包冒烟测试 ===')
pub = os.path.join(PKG, 'data', 'analysis_input_public.csv')
if not os.path.exists(pub):
    fail.append('复现包缺少 analysis_input_public.csv')
else:
    recs = list(csv.DictReader(open(pub, encoding='utf-8-sig')))
    if any(c in recs[0] for c in ('lat', 'lon', 'latitude', 'longitude')):
        fail.append('公开数据文件仍含经纬度列')
    for r in recs:
        for k in ('dist', 'elev', 'rng', 'dist_km', 'bdist'):
            r[k] = float(r[k])
        r['yA'], r['yB'] = int(r['yA']), int(r['yB'])

    def vary(sub, yk):
        gp = collections.defaultdict(list)
        for r in sub:
            gp[r['grp']].append(r[yk])
        okk = {k for k, v in gp.items() if len(set(v)) > 1}
        return [r for r in sub if r['grp'] in okk]

    def fit(sub, cols, yk):
        keys = sorted({r['grp'] for r in sub})
        gi = {k: i for i, k in enumerate(keys)}
        X = np.array([[r[c] for c in cols] for r in sub], dtype=float)
        y = np.array([r[yk] for r in sub], dtype=float)
        g = np.array([gi[r['grp']] for r in sub])
        return ConditionalLogit(y, X, groups=g).fit(disp=0, maxiter=300), len(keys)

    A = [r for r in recs if r['status'] in ('A_2017', 'B_2018promised', 'C_not_in_1044')]
    B = [r for r in recs if r['yA'] == 1]
    Ao, Bo = vary(A, 'yA'), vary(B, 'yB')
    resA, nkA = fit(Ao, ['dist', 'elev', 'rng'], 'yA')
    resB, nkB = fit(Bo, ['dist', 'elev', 'rng'], 'yB')
    P('  过程A %d 县 %d 村，dist %.3f（冻结 95/560, -0.370）' % (nkA, len(Ao), resA.params[0]))
    P('  过程B %d 县 %d 村，dist %.3f（冻结 109/580, 0.312）' % (nkB, len(Bo), resB.params[0]))
    if (nkA, len(Ao)) != (95, 560):
        fail.append('复现包重算的过程A有效组不是 95/560')
    if abs(resA.params[0] + 0.370) > 5e-4:
        fail.append('复现包重算的过程A系数偏离 -0.370')
    if (nkB, len(Bo)) != (109, 580):
        fail.append('复现包重算的过程B有效组不是 109/580')
    if abs(resB.params[0] - 0.312) > 5e-4:
        fail.append('复现包重算的过程B系数偏离 0.312')
    nscripts = len([f for f in os.listdir(os.path.join(PKG, 'scripts')) if f.endswith('.py')])
    P('  脚本 %d 个；MANIFEST 文件 %d 条' % (
        nscripts, len(list(csv.DictReader(open(os.path.join(PKG, 'MANIFEST.csv'), encoding='utf-8-sig'))))))
    if nscripts < 45:
        fail.append('复现包脚本数偏少')

P('')
P('=== 验收结论 ===')
if fail:
    P('不通过 %d 项：' % len(fail))
    for f in fail:
        P('  ✗ ' + f)
else:
    P('全部通过（通过 %d 项检查，警告 %d 项）' % (len(ok), len(warn)))
for w in warn:
    P('  ! ' + w)
