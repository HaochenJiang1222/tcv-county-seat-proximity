# -*- coding: utf-8 -*-
"""155：投稿前章节归位（第二十轮）

两处排版缺陷，都与研究内容无关：
  A 参考文献被截断：1-17 挂在 ## References 下，第 18 条（空间点位数据集）
    被上一轮程序化重排追加到文末声明之后，正文里它是被引用的
  B 后辅文位置颠倒：Author Contributions ... Declaration 整段落在 ## References
    之后，而 Land 模板的顺序是
        正文 → 后辅文 → Appendix A → References
    （顺序取自 data/mdpi_template/land_template.docx 的样式序列）

归位目标：
  ... 6. Conclusions → Tables → Figures → Author Contributions → Funding →
  Data Availability Statement → Acknowledgments → Conflicts of Interest →
  Declaration of Generative AI → Appendix A → References（1-18 连续）

安全性：逐行多重集比对，任何内容丢失即中止；原稿先备份。

用法：python dofile/155_reorder_submission.py v1.6
"""
import os, re, sys, shutil, collections, datetime

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER = sys.argv[1] if len(sys.argv) > 1 else 'v1.6'
SRC = os.path.join(ROOT, 'output', 'manuscript_TCV_EN_%s.md' % VER)
BAK = os.path.join(ROOT, 'output', 'manuscript_TCV_EN_%s_before_reorder.md' % VER)

t = open(SRC, encoding='utf-8').read()
shutil.copy2(SRC, BAK)
print('原稿已备份 %s' % os.path.basename(BAK))

fail = []
lines = t.split('\n')
# 按一级/二级标题切块；## 为块起点
idx = [i for i, l in enumerate(lines) if re.match(r'^## ', l)]
blocks = []          # (heading_line, [content lines])
pre = lines[:idx[0]]
for j, i in enumerate(idx):
    end = idx[j + 1] if j + 1 < len(idx) else len(lines)
    blocks.append((lines[i], lines[i + 1:end]))
print('二级块 %d 个：' % len(blocks))
for h, _ in blocks:
    print('   %s' % h)

# ---------- A 参考文献归拢 ----------
ref_i = [k for k, (h, _) in enumerate(blocks) if h.strip() == '## References']
if len(ref_i) != 1:
    fail.append('## References 块数量为 %d，脚本终止' % len(ref_i))
    raise SystemExit('参考文献块异常')
k = ref_i[0]
ref_head, ref_body = blocks[k]

entries = {}          # 编号 -> 整条（可能多行）
loose = []
cur = None
for l in ref_body:
    m = re.match(r'^(\d+)\.\s', l)
    if m:
        cur = int(m.group(1))
        entries[cur] = [l]
    elif cur is not None and l.strip() and not re.match(r'^## ', l):
        entries[cur].append(l)
    elif re.match(r'^## ', l):
        loose.append(l)
        cur = None
# 文末孤立条目：只在 References 块之后的块里找，避免误伤正文或附录的编号列表
for kk in range(k + 1, len(blocks)):
    h, body = blocks[kk]
    keep = []
    cur2 = None
    for l in body:
        m = re.match(r'^(\d+)\.\s', l)
        if m and int(m.group(1)) not in entries:
            entries[int(m.group(1))] = [l]
            cur2 = int(m.group(1))
        elif cur2 is not None and l.strip() and not re.match(r'^## ', l):
            entries[cur2].append(l)
        else:
            if re.match(r'^## ', l):
                cur2 = None
            keep.append(l)
    blocks[kk] = (h, keep)
print('\n参考文献条目 %d 条：%s' % (len(entries), sorted(entries)))
if sorted(entries) != list(range(1, max(entries) + 1)):
    fail.append('参考文献编号不连续：%s' % sorted(entries))
ref_lines = []
for n in sorted(entries):
    ref_lines.extend(entries[n])
    ref_lines.append('')
ref_lines = ref_lines[:-1] if ref_lines and ref_lines[-1] == '' else ref_lines

# ---------- B 章节归位 ----------
ORDER = ['## Author Contributions', '## Funding', '## Data Availability Statement',
         '## Acknowledgments', '## Conflicts of Interest',
         '## Declaration of Generative AI and AI-Assisted Technologies in the Writing Process']
APPX = [h for h, _ in blocks if h.startswith('## Appendix A')]
REFS = '## References'
byhead = {}
for h, b in blocks:
    byhead[h.strip()] = (h, b)
for need in ORDER + [REFS] + APPX:
    if need not in byhead:
        fail.append('缺少章节 %s' % need)
if fail:
    raise SystemExit('；'.join(fail))

head_names = [h.strip() for h, _ in blocks]
# 正文中除后辅文/附录/参考文献之外的块，保持原相对顺序
front = [(h, b) for h, b in blocks
         if h.strip() not in ORDER and h.strip() != REFS and not h.startswith('## Appendix A')]
tail = [byhead[n] for n in ORDER] + [byhead[a] for a in APPX] + [(REFS, ref_lines)]
new_blocks = front + tail
print('\n归位后顺序：')
for h, _ in new_blocks:
    print('   %s' % h)

# ---------- 写回 ----------
out = list(pre)
for h, b in new_blocks:
    out.append(h)
    out.extend(b)
    if b and b[-1] != '':
        out.append('')
new = '\n'.join(out)
new = re.sub(r'\n{4,}', '\n\n\n', new)

# ---------- 校验：内容一行不少 ----------
c0 = collections.Counter(l.strip() for l in t.split('\n') if l.strip())
c1 = collections.Counter(l.strip() for l in new.split('\n') if l.strip())
if c0 != c1:
    lost = c0 - c1
    gained = c1 - c0
    fail.append('内容多重集不一致，丢失 %d 行 / 新增 %d 行' % (sum(lost.values()), sum(gained.values())))
    for l, n in list(lost.items())[:5]:
        print('   丢失：%s' % l[:100])
    for l, n in list(gained.items())[:5]:
        print('   新增：%s' % l[:100])
else:
    print('\n内容逐行多重集一致（%d 行）' % sum(c1.values()))

# ---------- 校验：参考文献连续且位于末尾 ----------
seg = new.split('## References')[1].strip().split('\n')
nums = [int(m.group(1)) for m in (re.match(r'^(\d+)\.\s', l) for l in seg) if m]
if nums != list(range(1, 19)):
    fail.append('归位后参考文献编号仍不连续：%s' % nums[:20])
else:
    print('参考文献 1-18 连续，且位于全篇末尾')
after = new.split('## References')[1]
for h in ORDER:
    if '## %s' % h[3:] in after:
        fail.append('后辅文仍落在 References 之后：%s' % h)
if not fail:
    print('后辅文全部位于 References 之前；附录 A 位于 References 之前')

print('\n=== 结论 ===')
if fail:
    for f_ in fail:
        print('  [失败] %s' % f_)
    print('  未写回')
else:
    open(SRC, 'w', encoding='utf-8').write(new)
    print('  已写回 %s' % os.path.basename(SRC))
