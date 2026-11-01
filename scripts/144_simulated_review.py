# -*- coding: utf-8 -*-
"""
144 模拟审稿自动扫描（不改模型、不改结果）
四类问题：
  R1 估计对象一致性：有效组(95县560村) vs 全样本(1,596) 在摘要/引言贡献段/结果/结论是否一致出现
  R2 政策阶段措辞：是否存在把行政安排写成实际到账的表述
  R3 数据审计可重复性：2,555 / 2,550 / 未可靠定位 / 2016-12-09 截点是否可复核
  R4 排版结构：章节、四表两图、14条参考文献、back matter 是否齐全
输出：data/master/simulated_review_checks.txt
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER = sys.argv[1] if len(sys.argv) > 1 else 'v1.2'
SRC = os.path.join(ROOT, 'output', 'manuscript_TCV_EN_%s.md' % VER)
OUT = os.path.join(ROOT, 'data', 'master', 'simulated_review_checks.txt')

buf = io.StringIO()


def P(s=''):
    buf.write(s + '\n')
    print(s)


t = open(SRC, encoding='utf-8').read()
t_norm = t.replace('\u2212', '-').replace('\u2013', '-')

# 切段
abstract = re.search(r'## Abstract\n\n(.*?)\n\n\*\*Keywords', t, re.S).group(1)
body = t.split('## References')[0]
refs = t.split('## References')[1] if '## References' in t else ''


def sec(name, nxt):
    m = re.search(r'## %s\n(.*?)(?=\n## %s)' % (re.escape(name), re.escape(nxt)), t, re.S)
    return m.group(1) if m else ''


intro = sec('1. Introduction', '2.')
concl = sec('6. Conclusions', 'Acknowledgments')

FAIL = []


def chk(ok, label, note=''):
    P('  [%s] %s%s' % ('PASS' if ok else 'FAIL', label, ('  — ' + note) if note else ''))
    if not ok:
        FAIL.append(label)


# ============ R1 估计对象一致性 ============
P('=' * 78)
P('R1  估计对象一致性：有效组 vs 全样本')
P('=' * 78)
P('--- R1.1 摘要：是否同时出现主系数与两个更弱证据 ---')
a = abstract.replace('\u2212', '-')
chk('-0.370' in a, '摘要含主系数 -0.370')
chk('equal-county' in a.lower(), '摘要含县等权限制')
chk(('broader village sample' in a.lower() or 'broader' in a.lower()
     or '1,596 villages' in a), '摘要含全样本 LPM 限制（定性或样本量）')
P('    摘要词数：%d' % len(abstract.split()))

P('--- R1.2 引言贡献段：是否说明估计对象为有效县层 ---')
i = intro.replace('\u2212', '-')
chk('informative' in i.lower(), '引言出现 informative county strata')
chk('560' in i, '引言出现 560 村样本量', '' if '560' in i else '缺 560')
chk('0.060' in i or '0.136' in i, '引言给出全样本/县等权 p 值',
    '' if ('0.060' in i or '0.136' in i) else '仅定性描述，无数值')
P('    引言命中：informative=%s  560=%s  0.060=%s  0.136=%s'
  % ('informative' in i.lower(), '560' in i, '0.060' in i, '0.136' in i))

P('--- R1.3 结论：是否重复外推边界 ---')
c = concl.replace('\u2212', '-')
chk('informative' in c.lower(), '结论出现 informative county strata')
chk('0.060' in c or '0.136' in c, '结论给出全样本/县等权 p 值')
P('    结论命中：informative=%s  0.060=%s  0.136=%s'
  % ('informative' in c.lower(), '0.060' in c, '0.136' in c))

# ============ R2 政策阶段措辞 ============
P()
P('=' * 78)
P('R2  政策阶段措辞：行政安排 vs 实际到账')
P('=' * 78)
# 违规模式：主语为 villages 的"收到/获得资金"类断言
BAD = [
    (r'villages\s+(?:that\s+)?received\s+(?:central\s+)?(?:funds|funding|money|transfers)', 'villages received funds'),
    (r'received\s+(?:the\s+)?(?:CNY|RMB|funding|funds)\b', 'received funding/CNY'),
    (r'funding\s+(?:was\s+)?(?:delivered|disbursed|transferred)\s+to\s+(?:the\s+)?villages', 'funding disbursed to villages'),
    (r'amount\s+of\s+(?:funding|money)\s+(?:received|disbursed)', 'amount of funding received'),
    (r'financial\s+resources\s+(?:received|obtained)', 'financial resources received'),
    (r'actual\s+(?:funding|disbursement|spending|expenditure)\s+(?:at|by|to)\s+(?:the\s+)?villages', 'actual spending by villages'),
    (r'\bfunds?\s+received\b', 'funds received'),
    (r'\bwere\s+funded\b', 'were funded'),
]
hits = []
for pat, lab in BAD:
    for m in re.finditer(pat, t_norm, re.I):
        s = max(0, m.start() - 130)
        e = min(len(t_norm), m.end() + 130)
        hits.append((lab, t_norm[s:e].replace('\n', ' ')))
if hits:
    for lab, ctx in hits:
        P('  [FAIL] %s' % lab)
        P('         ...%s...' % ctx)
    FAIL.append('政策阶段措辞 %d 处' % len(hits))
else:
    P('  [PASS] 未发现把行政安排写成实际到账的表述')

# 合规但需逐一核对的近似词（列出上下文，人工判定）
NEAR = [r'disburs\w*', r'financial support', r'public support', r'conservation support',
        r'fund(?:ing|s|ed)?\b', r'resource']
P()
P('--- R2.2 近似措辞清单（人工复核，PASS 不等于无需阅读）---')
seen = set()
for pat in NEAR:
    for m in re.finditer(pat, t_norm, re.I):
        s = max(0, m.start() - 95)
        e = min(len(t_norm), m.end() + 95)
        key = t_norm[s:e]
        if key in seen:
            continue
        seen.add(key)
        P('   • ...%s...' % key.replace('\n', ' '))

# ============ R3 数据审计可重复性 ============
P()
P('=' * 78)
P('R3  数据审计可重复性字段核查')
P('=' * 78)
for pat, lab in [(r'2,555', '官方历史认定村数 2,555'),
                 (r'2,550', '去重后空间记录 2,550'),
                 (r'1,596', '有效距离 1,596'),
                 (r'1,598', '第四批认定 1,598'),
                 (r'2016[^\n]{0,12}12[^\n]{0,4}9|9 December 2016', '2016-12-09 截点'),
                 (r'10.3974', '空间数据集 DOI'),
                 (r'2016[^\n]{0,10}No\. 278|Jian Cun \[2016\]', '建村〔2016〕278号'),
                 (r'Jian Cun \[2017\] No\. 109', '建村〔2017〕109号'),
                 (r'Cai Jian \[2017\] No\. 318', '财建〔2017〕318号')]:
    chk(bool(re.search(pat, t)), lab)

# ============ R4 排版结构 ============
P()
P('=' * 78)
P('R4  排版结构完整性')
P('=' * 78)
n_ref = len(re.findall(r'^\d+\.\s', refs, re.M))
chk(n_ref == 14, '参考文献条目数 = 14', '实际 %d' % n_ref)
for k in ['Figure 1', 'Figure 2', 'Table 1', 'Table 2', 'Table 3', 'Table 4']:
    chk(k in body, '正文引用 %s' % k)
for k in ['Author Contributions', 'Funding', 'Data Availability Statement',
          'Conflicts of Interest']:
    chk(k in t, '声明：%s' % k)
chk('AI' in t or 'artificial intelligence' in t.lower(), 'AI 使用披露')
for h in ['1. Introduction', '2. Institutional Background', '3. Materials and Methods',
          '4. Results', '5. Discussion', '6. Conclusions']:
    chk(h in t, '章节标题 %s' % h)

P()
P('=' * 78)
P('结论：%d 项不通过' % len(FAIL))
for f in FAIL:
    P('   - %s' % f)
P('=' * 78)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write(buf.getvalue())
sys.exit(0)
