# -*- coding: utf-8 -*-
"""
从住建部官网附件（老式 .doc，OLE2）提取各批中国传统村落名录，结构化到 省/市/县/乡镇/村。
用法： python dofile/102_official_roster.py
输入： data/tcv_funding/official/batch<N>.doc
输出： data/tcv_funding/official/batch<N>.txt        原始文本
       data/tcv_funding/official/roster_official.csv 结构化名录
"""
import re, sys, csv, struct
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
import olefile

OFF = Path('data/tcv_funding/official')
OFF.mkdir(parents=True, exist_ok=True)

PROVS = ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区', '辽宁省', '吉林省', '黑龙江省',
         '上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '河南省', '湖北省',
         '湖南省', '广东省', '广西壮族自治区', '海南省', '重庆市', '四川省', '贵州省', '云南省',
         '西藏自治区', '陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区',
         '新疆生产建设兵团']
PROV_LINE = re.compile(r'^(?:[一二三四五六七八九十]+、)?\s*(' + '|'.join(PROVS) + r')\s*[（(]\s*(\d+)\s*个')
MUNI = {'北京市', '天津市', '上海市', '重庆市'}
CITY_RE = re.compile(r'^([\u4e00-\u9fa5]{2,}?市|[\u4e00-\u9fa5]{2,}?自治州|[\u4e00-\u9fa5]{2,}?地区|[\u4e00-\u9fa5]{2,}?盟)')
CTY_RE = re.compile(r'^([\u4e00-\u9fa5]{2,}?(?:县|市|区|旗|自治县|自治旗|特区|林区))')
TWP_RE = re.compile(r'^([\u4e00-\u9fa5]{2,}?(?:镇|乡|街道|苏木|办事处|管理委员会|管委会|民族乡))')


def extract_text(doc_path: Path):
    ole = olefile.OleFileIO(str(doc_path))
    stream = None
    for n in ole.listdir():
        if 'WordDocument' in '/'.join(n):
            stream = '/'.join(n)
            break
    data = ole.openstream(stream).read()
    ole.close()
    try:
        fcMin, fcMac = struct.unpack('<II', data[0x18:0x20])
        body = data[fcMin:fcMac] if 0 < fcMin < fcMac <= len(data) else data
    except Exception:
        body = data
    best = (0, '', '')
    for enc in ('utf-16-le', 'gb18030', 'cp936'):
        s = body.decode(enc, errors='ignore')
        cjk = len(re.findall(r'[\u4e00-\u9fa5]', s))
        if cjk > best[0]:
            best = (cjk, s, enc)
    return best[1], best[2]


def parse(txt: str, source: str):
    prov, declared = None, None
    out = []
    for raw in re.split(r'[\r\n\u000b\u000c\u0085\u2028\u2029]+', txt):
        line = raw.strip().replace('\u3000', '').replace(' ', '')
        if not line:
            continue
        m = PROV_LINE.match(line)
        if m:
            prov, declared = m.group(1), int(m.group(2))
            continue
        if '第四批' in line and '名录' in line and len(line) < 30:
            continue
        if '附件' in line and len(line) < 10:
            continue
        if prov is None:
            continue
        if len(line) < 4:
            continue
        # 排除文档结构行（目录/标题/说明），村落条目一律保留
        if re.search(r'(名录的村落名单|^附件\$|^注[:：]|合计|共\d+个)', line):
            continue
        if re.search(r'[（(]\s*\d+\s*个[）)]', line):
            continue
        if re.search(r'(MERGEFORMAT|PAGE|\*\\\\?|PAGE\\\\|TOC\\\\|PAGEREF)', line, flags=re.I):
            continue
        if not re.search(r'[\u4e00-\u9fa5]{3,}', line):
            continue
        rest = line
        city = county = town = None
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
        out.append(dict(source=source, prov=prov, declared_prov_n=declared,
                        city=city, county=county, township=town,
                        village=rest, full=line))
    return out


def main():
    docs = sorted({p.resolve() for p in OFF.iterdir() if p.suffix.lower() == '.doc'})
    if not docs:
        print('无待解析 doc')
        return
    allrows = []
    for p in docs:
        txt, enc = extract_text(p)
        (OFF / (p.stem + '.txt')).write_text(txt, encoding='utf-8')
        rows = parse(txt, p.stem)
        allrows += rows
        cnt = {}
        for r in rows:
            cnt[r['prov']] = cnt.get(r['prov'], 0) + 1
        print('== %s  编码=%s  解析村数=%d' % (p.name, enc, len(rows)))
        dec = {}
        for r in rows:
            if r['declared_prov_n']:
                dec[r['prov']] = r['declared_prov_n']
        bad = 0
        for k in PROVS:
            if k in cnt or k in dec:
                flag = '' if cnt.get(k) == dec.get(k) else '  <-- 差%d' % ((dec.get(k, 0) - cnt.get(k, 0)))
                if flag:
                    bad += 1
                print('   %-12s 解析%4d / 声明%4d%s' % (k, cnt.get(k, 0), dec.get(k, 0), flag))
        print('   合计 解析%d / 声明%d，不符省份%d个' % (len(rows), sum(dec.values()), bad))
    out = OFF / 'roster_official.csv'
    with out.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['source', 'prov', 'declared_prov_n', 'city', 'county', 'township', 'village', 'full'])
        w.writeheader()
        w.writerows(allrows)
    print('写出', out, len(allrows), '条')


if __name__ == '__main__':
    main()
