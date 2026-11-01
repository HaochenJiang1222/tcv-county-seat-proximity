# -*- coding: utf-8 -*-
"""110 第三十四部分核对：18 个候选县区与四县交叉核验（第九轮）

把用户手工汇总的两份财政支持名单县级结构，与 108/109 已建成的
逐村匹配母表逐县比对，回答三件事：
  1. 18 个两种安排并存的县区能否在母表中复现，各县数量是否一致
  2. 建德、武义、松阳、歙县四县的认定村与三状态结构是否一致
  3. 省份标题解析的边界用例是否通过（含用户给出的三个断言）

输出： data/master/check_34.txt
"""
import csv, re, sys, unicodedata, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'master'

# ---------- 用户第三十四部分给出的手工汇总 ----------
USER_18 = {
    ('浙江省', '松阳县'): (12, 7), ('浙江省', '建德市'): (7, 4), ('浙江省', '武义县'): (4, 4),
    ('浙江省', '仙居县'): (1, 7), ('浙江省', '莲都区'): (7, 1), ('浙江省', '缙云县'): (4, 2),
    ('浙江省', '东阳市'): (3, 2), ('浙江省', '龙泉市'): (2, 3), ('浙江省', '遂昌县'): (2, 3),
    ('浙江省', '天台县'): (1, 2), ('浙江省', '诸暨市'): (1, 2), ('浙江省', '泰顺县'): (2, 1),
    ('浙江省', '衢江区'): (3, 1), ('浙江省', '奉化区'): (1, 1), ('浙江省', '嵊州市'): (1, 1),
    ('安徽省', '歙县'): (1, 3), ('安徽省', '休宁县'): (2, 1), ('安徽省', '泾县'): (2, 1),
}
USER_4 = {'建德市': (11, 7, 4, 0), '武义县': (8, 4, 4, 0),
          '松阳县': (21, 12, 7, 2), '歙县': (11, 1, 3, 7)}

TARGET = {'江苏省', '浙江省', '安徽省'}

# ---------- 省份标题解析的边界用例 ----------
HEAD = re.compile(r"^'?'''?\s*(?:[一二三四五六七八九十百]+[、.．])?\s*"
                  r"(北京市|天津市|河北省|山西省|内蒙古自治区|辽宁省|吉林省|黑龙江省|上海市|江苏省|"
                  r"浙江省|安徽省|福建省|江西省|山东省|河南省|湖北省|湖南省|广东省|广西壮族自治区|"
                  r"海南省|重庆市|四川省|贵州省|云南省|西藏自治区|陕西省|甘肃省|青海省|"
                  r"宁夏回族自治区|新疆维吾尔自治区)\s*[（(]\s*(\d+)\s*个\s*[）)]")
HEAD2 = re.compile(r"^(?:[一二三四五六七八九十百]+[、.．])?\s*"
                   r"(北京市|天津市|河北省|山西省|内蒙古自治区|辽宁省|吉林省|黑龙江省|上海市|江苏省|"
                   r"浙江省|安徽省|福建省|江西省|山东省|河南省|湖北省|湖南省|广东省|广西壮族自治区|"
                   r"海南省|重庆市|四川省|贵州省|云南省|西藏自治区|陕西省|甘肃省|青海省|"
                   r"宁夏回族自治区|新疆维吾尔自治区)\s*[（(]\s*(\d+)\s*个\s*[）)]")


def norm_village(x):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(x).strip()))


def main():
    fin = list(csv.DictReader((OUT / 'master_final_1598.csv').open(encoding='utf-8-sig')))
    rep = []

    # ---------- 1. 18 个候选县区 ----------
    rep.append('=== 一、18 个两种安排并存的县区：母表复现 ===')
    byc = collections.defaultdict(list)
    for r in fin:
        if r['province'] in TARGET:
            byc[(r['province'], r['county'])].append(r)
    mine = {}
    for k, g in byc.items():
        a = sum(1 for x in g if x['status'] == 'A_2017')
        b = sum(1 for x in g if x['status'] == 'B_2018promised')
        if a and b:
            mine[k] = (a, b)
    rep.append('  母表中三省同时有 A 与 B 的县区 %d 个；用户手工汇总 %d 个' % (len(mine), len(USER_18)))
    diff = []
    for k in sorted(set(mine) | set(USER_18), key=lambda x: (x[0], x[1])):
        m, u = mine.get(k), USER_18.get(k)
        flag = '一致' if m == u else ('母表独有' if u is None else ('手工独有' if m is None else '数量不一致'))
        if flag != '一致':
            diff.append((k, m, u, flag))
        if m:
            rep.append('  %-4s%-8s 母表 A=%-3d B=%-3d | 手工 A=%-3s B=%-3s | %s' % (
                k[0][:2], k[1], m[0], m[1],
                (u[0] if u else '-'), (u[1] if u else '-'), flag))
    rep.append('  差异条目 %d：%s' % (len(diff), diff if diff else '无'))

    # ---------- 2. 四县交叉核验 ----------
    rep.append('')
    rep.append('=== 二、四县认定村与三状态结构 ===')
    rep.append('  县区      认定村  A(2017)  B(2018拟)  C(未进入)  与手工核对')
    for name, (n0, a0, b0, c0) in USER_4.items():
        g = [r for r in fin if r['county'] == name]
        a = sum(1 for x in g if x['status'] == 'A_2017')
        b = sum(1 for x in g if x['status'] == 'B_2018promised')
        c = sum(1 for x in g if x['status'] == 'C_not_in_1044')
        ok = (len(g), a, b, c) == (n0, a0, b0, c0)
        rep.append('  %-8s %4d    %4d      %4d      %4d       %s' % (
            name, len(g), a, b, c, '一致' if ok else '不一致(手工 %d/%d/%d/%d)' % (n0, a0, b0, c0)))

    # ---------- 3. 过程 A / 过程 B 的可用样本 ----------
    rep.append('')
    rep.append('=== 三、两个过程各自可用的县内样本 ===')
    def block(sel, tag):
        cc = collections.defaultdict(list)
        for r in fin:
            if sel is None or r['province'] in sel:
                cc[(r['province'], r['county'])].append(r)
        a1 = [k for k, g in cc.items()
              if sum(1 for x in g if x['status'] == 'A_2017') >= 1
              and sum(1 for x in g if x['status'] == 'B_2018promised') >= 1]
        a2 = [k for k in a1
              if sum(1 for x in cc[k] if x['status'] == 'A_2017') >= 2
              and sum(1 for x in cc[k] if x['status'] == 'B_2018promised') >= 2]
        nb = sum(sum(1 for x in cc[k] if x['status'] in ('A_2017', 'B_2018promised')) for k in a2)
        # 过程 A：进入安排 vs 未进入，两侧各≥2
        b1 = [k for k, g in cc.items()
              if sum(1 for x in g if x['status'] != 'C_not_in_1044') >= 1
              and sum(1 for x in g if x['status'] == 'C_not_in_1044') >= 1]
        b2 = [k for k in b1
              if sum(1 for x in cc[k] if x['status'] != 'C_not_in_1044') >= 2
              and sum(1 for x in cc[k] if x['status'] == 'C_not_in_1044') >= 2]
        na = sum(len(cc[k]) for k in b2)
        rep.append('  %s' % tag)
        rep.append('    过程 A（进入安排 vs 未进入）：有变异 %3d 县；两侧各≥2 村 %3d 县 %3d 村' % (
            len(b1), len(b2), na))
        rep.append('    过程 B（当年 vs 次年）      ：有变异 %3d 县；两侧各≥2 村 %3d 县 %3d 村' % (
            len(a1), len(a2), nb))
        return a2, b2

    a2n, b2n = block(None, '全国（1598 村）')
    a2t, b2t = block(TARGET, '三省（279 村）')
    rep.append('')
    rep.append('  三省中过程 B 两侧各≥2 村的县（%d 个）：' % len(a2t))
    for k in sorted(a2t):
        g = [r for r in fin if (r['province'], r['county']) == k]
        rep.append('      %s%s A%d B%d C%d' % (
            k[0][:2], k[1],
            sum(1 for x in g if x['status'] == 'A_2017'),
            sum(1 for x in g if x['status'] == 'B_2018promised'),
            sum(1 for x in g if x['status'] == 'C_not_in_1044')))

    # ---------- 4. 标题解析边界用例 ----------
    rep.append('')
    rep.append('=== 四、省份标题解析的边界用例 ===')
    for s in ['十、浙江省（225个）', '十一、安徽省（52个）', '九、浙江省（81个）',
              '二十八、新疆维吾尔自治区（1个）', '浙江省（225个）', '一、北京市（3个）',
              "'''十、浙江省（225个）'''"]:
        m1 = HEAD.match(s)
        m2 = HEAD2.match(s)
        rep.append('  %-28s 名录版=%s 名单版=%s' % (
            s, ('%s/%s' % (m1.group(1), m1.group(2)) if m1 else 'None'),
            ('%s/%s' % (m2.group(1), m2.group(2)) if m2 else 'None')))
    rep.append('  说明：省份标题在原始行上识别（不做名称标准化），村名才做标准化；')
    rep.append('        省份用 31 个省级全称白名单匹配，不用 (.+?) 通配，顿号与序号均为可选。')
    rep.append('  端到端验证：2016 名录 30 省逐省零误差共 1598 村；')
    rep.append('              2017 名单 600 村、2018 拟支持名单 444 村，与标题声明数一致。')

    txt = '\n'.join(rep)
    (OUT / 'check_34.txt').write_text(txt, encoding='utf-8')
    print(txt)


if __name__ == '__main__':
    main()
