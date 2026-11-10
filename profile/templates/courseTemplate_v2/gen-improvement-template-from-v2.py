#!/usr/bin/env python3
"""以 v2 真实评价报告为基底重建 improvement.docx 默认模板（占位符手术）。

数据分级原则（用户 2026-09-12 确定）：
- 通用可自动提取 → |sys:text（学期/课程/教师/目标/矩阵/成绩分布/图表…）
- 每次评价各异的叙事 → |text 手动填空（考核方式/考试方式/审核人/评价依据/
  评价时间/平台/内容/量规/自洽性/合理性说明/结果分析/改进措施…）

方法：v2 整篇是 1 个外层大表（58 行）+ 7 个嵌套表。按表签名定位各嵌套表
做位置替换；基本信息按行内 label→value 替换；7.2/八/九 按段落状态机。
可重跑：每次从原始 v2 文档重新生成。
"""
import zipfile, re, copy
from lxml import etree

SRC = '03_2025-2026学年-《操作系统原理》课程目标达成情况评价报告-软件24级_v2.docx'
DST = 'docker/profile/templates/courseTemplate_v2/improvement.docx'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'

root = etree.fromstring(zipfile.ZipFile(SRC).read('word/document.xml'))
body = root.find(W + 'body')


def ptext(el):
    return ''.join(t.text or '' for t in el.iter(W + 't')).strip()


def norm(s):
    return re.sub(r'\s+', '', s or '')


def first_rpr(el):
    for r in el.iter(W + 'r'):
        rpr = r.find(W + 'rPr')
        if rpr is not None:
            return copy.deepcopy(rpr)
    return None


def new_run(rpr, text):
    r = etree.Element(W + 'r')
    if rpr is not None:
        r.append(copy.deepcopy(rpr))
    t = etree.SubElement(r, W + 't')
    t.set(XML_SPACE, 'preserve')
    t.text = text
    return r


def keep_ppr(p):
    """清空段落内容但保留 pPr，返回 (p, rPr)"""
    rpr = first_rpr(p)
    for child in list(p):
        if etree.QName(child).localname != 'pPr':
            p.remove(child)
    return rpr


def set_para(p, text):
    rpr = keep_ppr(p)
    p.append(new_run(rpr, text))


def set_cell(tc, text):
    """整格替换：保 tcPr 与首个 pPr，段落重建为单段"""
    rpr = first_rpr(tc)
    ppr = None
    for p in tc.iter(W + 'p'):
        pr = p.find(W + 'pPr')
        if pr is not None:
            ppr = copy.deepcopy(pr)
        break
    for child in list(tc):
        if etree.QName(child).localname != 'tcPr':
            tc.remove(child)
    p = etree.SubElement(tc, W + 'p')
    if ppr is not None:
        p.append(ppr)
    p.append(new_run(rpr, text))


def rows_of(tbl):
    return tbl.findall(W + 'tr')


def cells_of(tr):
    return tr.findall(W + 'tc')


log = []


def rep(what, val):
    log.append(f'OK  {what} -> {val}')


# ══════════ 0. 标题 ══════════
for p in body.findall(W + 'p'):
    if norm(ptext(p)).startswith('软件工程24级《操作系统原理》课程目标'):
        set_para(p, '{{className}}《{{courseName}}》课程目标')
        rep('title', '{{className}}《{{courseName}}')
        break

outer = body.find(W + 'tbl')
nested = [t for t in outer.findall(f'.//{W}tbl') if t != outer]

# ══════════ 1. 一、课程基本信息：外层表行内 label→value ══════════
BASIC = {
    '开课时间': '{{semesterName|sys:text}}',
    '考核方式': '{{assessmentMethod|text}}',
    '课程性质': '{{courseNature|sys:text}}',
    '考试方式': '{{examType|text}}',
    '学时': '{{creditHour|sys:text}}',
    '学分': '{{creditScore|sys:text}}',
    '授课对象': '{{className|sys:text}}',
    '考核人数': '{{studentNum|sys:text}}人',
    '任课教师': '{{teacherNames|sys:text}}',
    '课程负责人': '{{teacherName|sys:text}}',
    '命题人': '{{testDesignerName|sys:text}}',
    '审核人': '{{reviewerName|text}}',
    '评价依据': '{{evaluationCriteria|text}}',
    '评价时间': '{{evaluationTime|text}}',
}
# 只处理嵌套表[0]之前的行（基本信息区）
first_nested_row_parent = nested[0].getparent()  # 外层某行的 tc
done_labels = set()
for tr in outer.findall(W + 'tr'):
    if tr in [first_nested_row_parent.getparent() if first_nested_row_parent is not None else None]:
        break
    cells = cells_of(tr)
    for i, c in enumerate(cells):
        label = norm(ptext(c))
        if label in BASIC and label not in done_labels and i + 1 < len(cells):
            set_cell(cells[i + 1], BASIC[label])
            done_labels.add(label)
            rep('basic:' + label, BASIC[label])
missing = set(BASIC) - done_labels
if missing:
    print('!! 基本信息未命中:', missing)

# ══════════ 2. 二、支撑关系表 nested[0]：5 行 × 4 格 ══════════
t = nested[0]
STRENGTHS = ['H', 'H', 'M', 'H', 'L']
for g, tr in zip(range(1, 6), rows_of(t)[1:]):
    cs = cells_of(tr)
    set_cell(cs[0], '{{goal%d_gname|sys:text}}' % g)
    set_cell(cs[1], '{{goal%d_option|sys:text}}' % g)
    set_cell(cs[2], '{{goal%d_option_strength|sys:text}}' % g)
    set_cell(cs[3], '{{goal%d_way|sys:text}}' % g)
    rep('support row%d' % g, '4 cells')

# ══════════ 3. 三、3.1 考核环节构成 nested[1]：3 行 × 5 格 ══════════
t = nested[1]
for m, tr in zip(range(1, 4), rows_of(t)[1:]):
    cs = cells_of(tr)
    set_cell(cs[0], '{{examine%d_name|sys:text}}' % m)
    set_cell(cs[1], '{{total_examine%d_pop|sys:text}}%%' % m)
    set_cell(cs[2], '{{examine%d_platform|text}}' % m)
    set_cell(cs[3], '{{examine%d_content|text}}' % m)
    set_cell(cs[4], '{{examine%d_examineBasis|sys:text}}' % m)
    rep('exam31 row%d' % m, '5 cells')

# ══════════ 4. 四、4.1 矩阵 nested[2]：表头 + 5 行 + 合计 ══════════
t = nested[2]
hdr = cells_of(rows_of(t)[0])
set_cell(hdr[1], '{{examine1_name|sys:text}}（{{total_examine1_pop|sys:text}}%）')
set_cell(hdr[2], '{{examine2_name|sys:text}}（{{total_examine2_pop|sys:text}}%）')
set_cell(hdr[3], '{{examine3_name|sys:text}}（{{total_examine3_pop|sys:text}}%）')
for g, tr in zip(range(1, 6), rows_of(t)[1:6]):
    cs = cells_of(tr)
    set_cell(cs[0], '{{goal%d_name|sys:text}}' % g)
    set_cell(cs[1], '{{goal%d_examine1_pop|sys:text}}' % g)
    set_cell(cs[2], '{{goal%d_examine2_pop|sys:text}}' % g)
    set_cell(cs[3], '{{goal%d_examine3_pop|sys:text}}' % g)
    set_cell(cs[4], '{{goal%d_total_pop|sys:text}}' % g)
    rep('matrix41 row%d' % g, '5 cells')
tot = cells_of(rows_of(t)[6])
set_cell(tot[1], '{{total_examine1_pop|sys:text}}')
set_cell(tot[2], '{{total_examine2_pop|sys:text}}')
set_cell(tot[3], '{{total_examine3_pop|sys:text}}')
set_cell(tot[4], '{{total_pop|sys:text}}')
rep('matrix41 total', '4 cells')

# ══════════ 5. 四、4.2 自洽性 nested[3]：5 行 × 4 格 ══════════
t = nested[3]
for g, tr in zip(range(1, 6), rows_of(t)[1:]):
    cs = cells_of(tr)
    set_cell(cs[0], '{{goal%d_name|sys:text}}' % g)
    set_cell(cs[1], '{{goal%d_option_strength|sys:text}}' % g)
    set_cell(cs[2], '{{goal%d_total_pop|sys:text}}%%' % g)
    set_cell(cs[3], '{{goal%d_selfJudge|text}}' % g)
    rep('self42 row%d' % g, '4 cells')

# ══════════ 6. 五、量规 nested[4]：5 行 × 7 格 ══════════
t = nested[4]
for g, tr in zip(range(1, 6), rows_of(t)[1:]):
    cs = cells_of(tr)
    set_cell(cs[0], '{{goal%d_name|sys:text}}' % g)
    set_cell(cs[1], '{{goal%d_dim|text}}' % g)
    for lv in range(1, 6):
        set_cell(cs[1 + lv], '{{goal%d_lv%d|text}}' % (g, lv))
    rep('rubric row%d' % g, '7 cells')

# ══════════ 7. 六、合理性确认 nested[5]：每目标 5 行 ══════════
t = nested[5]
for g in range(1, 6):
    base = (g - 1) * 5
    heading_cell = cells_of(rows_of(t)[base])[0]
    # 标题格含两段：短名 + 完整描述
    ps = heading_cell.findall(W + 'p')
    if len(ps) >= 2:
        set_para(ps[0], '{{goal%d_name|sys:text}}' % g)
        set_para(ps[1], '{{goal%d_gname|sys:text}}' % g)
        for extra in ps[2:]:
            heading_cell.remove(extra)
    else:
        set_cell(heading_cell, '{{goal%d_gname|sys:text}}' % g)
    for m, tr in zip(range(1, 4), rows_of(t)[base + 2: base + 5]):
        cs = cells_of(tr)
        set_cell(cs[0], '{{examine%d_name|sys:text}}（{{goal%d_examine%d_pop|sys:text}}%%）' % (m, g, m))
        set_cell(cs[1], '{{goal%d_reason%d|text}}' % (g, m))
    rep('six goal%d' % g, 'heading + 3 rows')

# ══════════ 8. 七、7.1 成绩分布 nested[6]：3 行 ══════════
t = nested[6]
r_people, r_prop = cells_of(rows_of(t)[1]), cells_of(rows_of(t)[2])
for i in range(1, 6):
    set_cell(r_people[i], '{{people_num%d|sys:text}}' % i)
    set_cell(r_prop[i], '{{proportion_num%d|sys:text}}%%' % i)
rep('dist71', '10 cells')

# ══════════ 9. 段落状态机：7.1 intro / 7.2 结果 / 八 / 九 ══════════
leaf_paras = [p for p in root.iter(W + 'p')
              if p.find('.//' + W + 'tbl') is None and p.find('.//' + W + 'drawing') is None]

# 7.1 intro
for p in leaf_paras:
    if norm(ptext(p)).startswith('全年级成绩分布（'):
        set_para(p, '全年级成绩分布（{{studentNum|sys:text}}人，及格率 {{passRate|text}}%，平均分 {{avgScore|text}}）：')
        rep('dist71 intro', 'passRate/avgScore')
        break

# 7.2：'课程目标N' → 3×(依据名,题号静态注,avg,pop,weighted[,ev首行])
# 题号列放静态参照注（v2 原始设计）——不放 questionSerial 占位（虚拟班聚合无题号）。
# 2026-09-29 修订：此前漏掉题号列内容导致 avg 左移错位到"对应考核项/题号"列，
# 现每子行 examineName 后补一段静态文本占住题号列。
QNUM_NOTE = '见"课程达成度计算依据表"'
seq = []  # 按文档顺序的占位符串
for g in range(1, 6):
    seq.append('课程目标%d' % g)
    for m in range(1, 4):
        seq.append('{{goal%d_child%d_examineName|sys:text}}' % (g, m))
        seq.append(QNUM_NOTE)
        seq.append('{{goal%d_child%d_avgScore|sys:text}}' % (g, m))
        seq.append('{{goal%d_examine%d_pop|sys:text}}' % (g, m))
        seq.append('{{goal%d_child%d_weightedScore|sys:text}}' % (g, m))
        if m == 1:
            seq.append('{{goal%d_evaluationResult|sys:text}}' % g)

EXPECT = {  # 文档顺序期望文本（norm 后精确匹配）
    '课程目标%d' % g: g for g in range(1, 6)}
si = 0
in_72 = False
consumed72 = 0
for p in leaf_paras:
    txt = norm(ptext(p))
    if txt == '7.2课程目标达成度评价结果':
        in_72 = True
        continue
    if txt.startswith('说明：'):
        in_72 = False
        continue
    if not in_72 or not txt or si >= len(seq):
        continue
    # 同一段按序消费：依据名 / 数字
    while si < len(seq):
        want = seq[si]
        if want.startswith('课程目标'):
            if txt == want:
                set_para(p, '{{goal%s_name|sys:text}}' % want[-1])
                si += 1
                consumed72 += 1
            break  # 不匹配则等下一段
        if not want.startswith('{{'):
            # 静态注段（题号列）：原样保留，占住列位
            si += 1
            consumed72 += 1
            break
        set_para(p, want)
        si += 1
        consumed72 += 1
        break
print('7.2 consumed:', consumed72, '/', len(seq))

# 八、结果分析
CHARTS = ['{{GoalChartAll|sys:chart}}'] + ['{{GoalScatterChart%d|sys:chart}}' % i for i in range(1, 6)]
ANALYSIS_PREFIX = ['该目标主要反映学生能否掌握操作系统基本概念',
                   '该目标主要考查学生能否识别、分析并解决操作系统常见问题',
                   '该目标主要评估学生能否通过定性与定量方式分析',
                   '该目标主要衡量学生的工程实践能力',
                   '该目标主要考查学生的终身学习意识与前沿技术追踪能力']
# intro
for p in leaf_paras:
    if norm(ptext(p)).startswith('本学期共有149名软件24级的同学选修该课程'):
        set_para(p, '{{result_analysis|text}}')
        rep('eight intro', 'result_analysis')
        break
# 图表槽（含 drawing 的段落）
chart_i = 0
for p in root.iter(W + 'p'):
    if p.find('.//' + W + 'drawing') is None:
        continue
    rpr = first_rpr(p)
    for child in list(p):
        if etree.QName(child).localname != 'pPr':
            p.remove(child)
    p.append(new_run(rpr, CHARTS[chart_i]))
    chart_i += 1
    if chart_i >= len(CHARTS):
        break
print('charts replaced:', chart_i)
# 分析行（课程目标N 标记 + 长文本）
agg = 0
for idx, p in enumerate(leaf_paras):
    txt = norm(ptext(p))
    m = re.fullmatch(r'课程目标([1-5])', txt)
    if not m:
        continue
    g = int(m.group(1))
    # 向后找最近的分析前缀段
    for q in leaf_paras[idx + 1: idx + 6]:
        t2 = norm(ptext(q))
        if any(t2.startswith(pre) for pre in ANALYSIS_PREFIX):
            set_para(p, '{{goal%d_name|sys:text}}' % g)
            set_para(q, '{{goal%d_analysis|text}}' % g)
            agg += 1
            break
        if re.fullmatch(r'课程目标[1-5]', t2) or t2.startswith(('八、', '九、')):
            break
print('eight analysis rows:', agg)

# 九、持续改进措施
for p in leaf_paras:
    if norm(ptext(p)).startswith('本学期以“随堂考核'):
        set_para(p, '{{continuous_improvement_measures|text}}')
        rep('nine intro', 'continuous_improvement_measures')
        break
DELETED = 0
for pre in ['一是深化随堂考核改革', '二是强化工程实践考核', '三是优化期末命题结构',
            '四是融入新标准要求', '五是优化考核环节对课程目标的支撑权重结构']:
    for p in list(root.iter(W + 'p')):
        if norm(ptext(p)).startswith(pre):
            p.getparent().remove(p)
            DELETED += 1
            break
print('nine deleted sample paras:', DELETED)
MEASURE_PREFIX = ['本目标达成度较高', '关键问题在于期末综合应用得分偏低', '关键问题在于非工具环境下的分析能力不足',
                  '该目标达成度仅0.663', '关键问题在于期末前沿知识得分低']
mcount = 0
for idx, p in enumerate(leaf_paras):
    txt = norm(ptext(p))
    m = re.fullmatch(r'课程目标([1-5])', txt)
    if not m:
        continue
    g = int(m.group(1))
    for q in leaf_paras[idx + 1: idx + 4]:
        t2 = norm(ptext(q))
        if any(t2.startswith(pre) for pre in MEASURE_PREFIX):
            set_para(p, '{{goal%d_name|sys:text}}' % g)
            set_para(q, '{{goal%d_measures|text}}' % g)
            mcount += 1
            break
        if re.fullmatch(r'课程目标[1-5]', t2):
            break
print('nine measure rows:', mcount)

# ══════════ 写回（去样例图） ══════════
out = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
zsrc = zipfile.ZipFile(SRC)
RNS = '{http://schemas.openxmlformats.org/package/2006/relationships}'
with zipfile.ZipFile(DST, 'w', zipfile.ZIP_DEFLATED) as z:
    for n in zsrc.namelist():
        if n == 'word/document.xml':
            z.writestr(n, out)
        elif n.startswith('word/media/'):
            continue
        elif n == 'word/_rels/document.xml.rels':
            rels = etree.fromstring(zsrc.read(n))
            for rel in list(rels):
                if (rel.get('Target') or '').startswith('media/'):
                    rels.remove(rel)
            z.writestr(n, etree.tostring(rels, xml_declaration=True, encoding='UTF-8', standalone=True))
        else:
            z.writestr(n, zsrc.read(n))
print('WROTE', DST)

# 统计占位符
txt = ''.join(t.text or '' for t in root.iter(W + 't'))
ph = re.findall(r'\{\{[^}]+\}\}', txt)
sys_n = sum(1 for x in ph if '|sys:' in x)
print(f'placeholders={len(ph)} (sys={sys_n}, manual={len(ph)-sys_n}), unique={len(set(ph))}')
