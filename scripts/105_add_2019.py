# -*- coding: utf-8 -*-
"""
补入 2019 年中央财政支持名单（建办村函〔2019〕360号，600村）苏浙皖三省部分，
重算第四批三省 279 村的 2017—2019 支持时序。
来源：住建部办公厅附件 PDF（扫描件，文本由官方公布文本核对录入）
用法： python dofile/105_add_2019.py
"""
import re, sys, csv, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
OFF = Path('data/tcv_funding/official')

V_JS = ["苏州市吴中区金庭镇蒋东村后埠村"]

V_ZJ = """温州市文成县岔口镇东方村
温州市泰顺县罗阳镇洲滨村
绍兴市嵊州市石璜镇楼家村
金华市浦江县杭坪镇杭坪村
金华市浦江县杭坪镇石宅村
金华市浦江县檀溪镇潘周家村
金华市浦江县岩头镇礼张村
金华市磐安县冷水镇朱山村
金华市兰溪市永昌街道永昌村
金华市义乌市赤岸镇朱店村
金华市东阳市虎鹿镇西坞村
金华市永康市石柱镇塘里村
衢州市柯城区航埠镇北二村
衢州市江山市廿八都镇浔里村
衢州市江山市塘源口乡洪福村
衢州市江山市峡口镇柴村村
衢州市江山市峡口镇枫石村
衢州市江山市峡口镇广渡村
衢州市江山市峡口镇三卿口村
台州市天台县街头镇后岸村
台州市仙居县步路乡西炉村
台州市仙居县埠头镇埠头村
台州市仙居县大战乡白岩下村
台州市仙居县大战乡大战索村
台州市仙居县淡竹乡尚仁村
台州市仙居县淡竹乡油溪村
台州市仙居县广度乡祖庙村
台州市仙居县横溪镇苍岭坑村
台州市仙居县横溪镇上江垟村
台州市仙居县横溪镇溪头村
台州市仙居县湫山乡四都村
台州市仙居县双庙乡上王村
台州市仙居县田市镇公盂村
台州市仙居县溪港乡仁庄村
台州市仙居县朱溪镇兴隆村
台州市仙居县朱溪镇朱溪村
台州市温岭市石塘镇东海村
台州市临海市白水洋镇前塘村
台州市临海市白水洋镇西洋庄村
台州市临海市东塍镇呈歧村
台州市临海市东塍镇坦头村
台州市临海市河头镇下湾村
台州市临海市汇溪镇善家洋村
台州市临海市桃渚镇城里村
台州市临海市小芝镇桥头村石牛坑自然村
台州市临海市小芝镇胜坑村
台州市临海市沿江镇南蒋村
丽水市青田县祯旺乡牛路坑村
丽水市缙云县新碧街道黄碧虞村
丽水市遂昌县应村乡竹溪村斋堂下自然村
丽水市庆元县官塘乡白柘洋村
丽水市庆元县官塘乡横坑村
丽水市庆元县松源街道九漈村
丽水市庆元县五大堡乡西川村
丽水市庆元县张村乡后溪村
丽水市庆元县张村乡南阳村
丽水市景宁畲族自治县鹤溪街道东弄村
丽水市景宁畲族自治县鹤溪街道周湖村
丽水市景宁畲族自治县毛垟乡库头村
丽水市景宁畲族自治县英川镇隆川村
丽水市龙泉市城北乡盛山后村
丽水市龙泉市兰巨乡梅地村
丽水市龙泉市龙南乡金川村
丽水市龙泉市龙南乡上南坑村
丽水市龙泉市龙南乡杨山头村
丽水市龙泉市屏南镇石玄铺村
丽水市龙泉市屏南镇垟顺村
丽水市龙泉市小梅镇黄南村""".split('\n')

V_AH = """安庆市潜山市官庄镇官庄村
黄山市歙县岔口镇祝筒坦村
黄山市歙县杞梓里镇杞梓里村
黄山市歙县杞梓里镇滩培村
黄山市歙县上丰乡蕃村
黄山市黟县碧阳镇柏山立川村
黄山市黟县宏村镇横断村
黄山市黟县西递镇霭峰上村
黄山市黟县渔亭镇桃源村青岭山
六安市金寨县汤家汇镇斗林村李家湾
池州市青阳县陵阳镇上章村
宣城市宣州区水东镇东胜村小胡村
宣城市泾县榔桥镇溪头村
宣城市泾县茂林镇潘村村
宣城市泾县桃花潭镇厚岸村
宣城市泾县桃花潭镇龙潭村
宣城市绩溪县伏岭镇伏岭村
宣城市绩溪县上庄镇石家村
宣城市宁国市港口镇山门村""".split('\n')
PROVS = ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区', '辽宁省', '吉林省', '黑龙江省',
         '上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '河南省', '湖北省',
         '湖南省', '广东省', '广西壮族自治区', '海南省', '重庆市', '四川省', '贵州省', '云南省',
         '西藏自治区', '陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区']


def norm(v: str) -> str:
    v = str(v).replace(' ', '').replace('\u3000', '')
    v = re.sub(r'^(?:' + '|'.join(PROVS) + r')', '', v)
    v = re.sub(r'[（）()\[\]【】]', '', v)
    return re.sub(r'(村委|村委会)$', '', v)


def main():
    new = []
    for p, lst, n in [('江苏省', V_JS, 1), ('浙江省', V_ZJ, 68), ('安徽省', V_AH, 19)]:
        lst = [x.strip() for x in lst if x.strip()]
        print('%s 录入 %d / 声明 %d' % (p, len(lst), n))
        for v in lst:
            new.append(dict(batch='2019', prov=p, raw=v, key=norm(v)))
    sup = list(csv.DictReader((OFF / 'support_national.csv').open(encoding='utf-8-sig')))
    sup += new
    with (OFF / 'support_national.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['batch', 'prov', 'raw', 'key'])
        w.writeheader()
        w.writerows(sup)
    print('支持名单合计', len(sup))

    # 重匹配
    ros = list(csv.DictReader((OFF / 'roster_official.csv').open(encoding='utf-8-sig')))
    idx = collections.defaultdict(list)
    for s in sup:
        idx[s['key']].append(s['batch'])
    order = {'2017': 0, '2018-1': 1, '2018-2': 2, '2019': 3}
    rows = []
    for r in ros:
        bs = sorted(set(idx.get(norm(r['full']), [])), key=lambda b: order[b])
        rows.append(dict(prov=r['prov'], city=r['city'], county=r['county'], township=r['township'],
                         village=r['village'], full=r['full'],
                         first_batch=bs[0] if bs else '', n_batch=len(bs), batches='|'.join(bs)))
    OUT = OFF / 'batch4_matched_2019.csv'
    with OUT.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('逐村结果写出', OUT)
    hit = sum(1 for r in rows if r['first_batch'])
    print('全国 匹配 %d / %d = %.1f%%' % (hit, len(rows), 100 * hit / len(rows)))

    print()
    print('%-8s %5s %5s %5s %5s %5s %5s %7s' % ('省', '村数', '2017', '2018-1', '2018-2', '2019', '未列入', '覆盖率'))
    byp = collections.defaultdict(collections.Counter)
    for r in rows:
        byp[r['prov']][r['first_batch'] or 'D'] += 1
    for p in ('江苏省', '浙江省', '安徽省'):
        c = byp[p]
        tot = sum(c.values())
        print('%-8s %5d %5d %5d %5d %5d %5d %6.1f%%' % (p, tot, c['2017'], c['2018-1'], c['2018-2'], c['2019'], c['D'],
                                                        100 * (tot - c['D']) / tot))
    print()
    for kw in ['松阳县', '歙县']:
        s = [r for r in rows if kw in r['full']]
        g = collections.defaultdict(list)
        for r in s:
            g[r['first_batch'] or 'D'].append(r['village'])
        print('==', kw, len(s), '村')
        for k in ['2017', '2018-1', '2018-2', '2019', 'D']:
            if k in g:
                print('   %-8s %2d  %s' % (k, len(g[k]), '、'.join(g[k])))


if __name__ == '__main__':
    main()
