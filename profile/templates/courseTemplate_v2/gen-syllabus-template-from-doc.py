#!/usr/bin/env python3
"""以真实大纲文档为基底重建 syllabus.docx 默认模板（占位符手术）。
可重跑：每次从原始文档重新生成。"""
import zipfile, re, shutil, sys

SRC = '操作系统原理24版-教学大纲-计科JX031013-20260623v27-李少勇.docx'
DST = 'docker/profile/templates/courseTemplate_v2/syllabus.docx'

z = zipfile.ZipFile(SRC)
xml = z.read('word/document.xml').decode('utf8')
body_open = xml.find('<w:body>') + len('<w:body>')
body_close = xml.rfind('</w:body>')
head, body, tail = xml[:body_open], xml[body_open:body_close], xml[body_close:]

# ── 工具 ──
def runs_text(fragment):
    return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', fragment))

def first_rpr(cell_xml):
    m = re.search(r'<w:rPr>.*?</w:rPr>', cell_xml, re.S)
    return m.group(0) if m else ''

def make_run(rpr, text):
    t = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return f'<w:r>{rpr}<w:t xml:space="preserve">{t}</w:t></w:r>'

def set_cell_text(cell_xml, text):
    """保留 cell 结构（tcPr），段落重建为单 run（沿用首个 run 的 rPr）"""
    rpr = first_rpr(cell_xml)
    tcpr = re.search(r'<w:tcPr>.*?</w:tcPr>', cell_xml, re.S)
    tcpr = tcpr.group(0) if tcpr else ''
    return f'<w:tc>{tcpr}<w:p>{make_run(rpr, text)}</w:p></w:tc>'

def replace_row_cells(row_xml, cell_map):
    """cell_map: {cell_idx: 新文本}；重建指定 cell，其余原样"""
    cells = re.findall(r'<w:tc>.*?</w:tc>', row_xml, re.S)
    out = []
    for i, c in enumerate(cells):
        out.append(set_cell_text(c, cell_map[i]) if i in cell_map else c)
    # 行 XML = 前缀(trPr) + cells
    prefix = row_xml[:row_xml.find('<w:tc>')]
    return prefix + ''.join(out) + '</w:tr>'

def drop_cells(row_xml, drop_idx):
    cells = re.findall(r'<w:tc>.*?</w:tc>', row_xml, re.S)
    prefix = row_xml[:row_xml.find('<w:tc>')]
    kept = ''.join(c for i, c in enumerate(cells) if i not in drop_idx)
    return prefix + kept + '</w:tr>'

def set_grid(tbl_xml, widths):
    grid = ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    return re.sub(r'<w:tblGrid>.*?</w:tblGrid>', f'<w:tblGrid>{grid}</w:tblGrid>', tbl_xml, flags=re.S)

# ── 顶层元素序列（gap+item 交替：间隙里的 sectPr/bookmark 等顶层杂项原样保留）──
items = []
pos = 0
for m in re.finditer(r'<w:tbl>.*?</w:tbl>|<w:p\b.*?</w:p>', body, re.S):
    if body[pos:m.start()].strip():
        items.append(body[pos:m.start()])  # gap 段（不以 <w:tbl>/<w:p 开头）
    items.append(m.group(0))
    pos = m.end()
if body[pos:].strip():
    items.append(body[pos:])

def para_text(p):
    return runs_text(p).strip()

def is_item_tbl(x):
    return x.startswith('<w:tbl>')

# ── 手术开始：items 复制后按序修改 ──
out_items = list(items)

def find_para(prefix, start=0):
    for i in range(start, len(out_items)):
        if not is_item_tbl(out_items[i]) and para_text(out_items[i]).startswith(prefix):
            return i
    raise SystemExit(f'段落未找到: {prefix}')

def find_tbl_after(idx):
    for i in range(idx, len(out_items)):
        if is_item_tbl(out_items[i]):
            return i
    raise SystemExit(f'表格未找到 after {idx}')

def replace_with_placeholder_para(idx, ph):
    """用占位符段替换 items[idx]（沿用其段落属性）"""
    p = out_items[idx]
    rpr = re.search(r'<w:rPr>.*?</w:rPr>', p, re.S)
    rpr = ('<w:rPr>' + rpr.group(0) + '</w:rPr>') if rpr else ''
    run = make_run(rpr if rpr else '', ph)
    # 去掉原 runs，塞入占位 run
    p2 = re.sub(r'(<w:pPr>.*?</w:pPr>)', r'\1', p, count=1, flags=re.S)
    p2 = re.sub(r'<w:r>.*?</w:r>', '', p2, flags=re.S)
    p2 = p2.replace('</w:p>', run + '</w:p>')
    out_items[idx] = p2

def delete_item(idx):
    # gap（顶层杂项）不可删，只删段落项
    if out_items[idx].lstrip().startswith('<w:p') or out_items[idx].lstrip().startswith('<w:tbl'):
        out_items[idx] = ''

# ── A. 标题 ──
i_title = find_para('长沙学院《操作系统原理》')
out_items[i_title] = out_items[i_title].replace(
    '长沙学院《操作系统原理》课程教学大纲',
    '长沙学院《{{courseName|sys:text}}》课程教学大纲')

# ── B. 表1 课程基本信息 ──
i_t1 = find_tbl_after(i_title)
t1_rows = re.findall(r'<w:tr\b.*?</w:tr>', out_items[i_t1], re.S)
rows_new = list(t1_rows)
# 行0 制定依据
rows_new[0] = replace_row_cells(rows_new[0], {1: '根据{{majorName|sys:text}}专业{{programName|sys:text}}制定'})
# 行1 中文名/英文名
rows_new[1] = replace_row_cells(rows_new[1], {1: '{{courseName|sys:text}}', 3: '{{courseNameEn|sys:text}}'})
# 行2 编号/学时
rows_new[2] = replace_row_cells(rows_new[2], {1: '{{courseCode|sys:text}}',
    3: '总学时：{{totalCreditHour|sys:text}} 其中理论学时：{{teachCreditHour|sys:text}} 实践学时：{{practiceCreditHour|sys:text}}'})
# 行3 类别/性质
rows_new[3] = replace_row_cells(rows_new[3], {1: '{{courseCategory|sys:text}}', 3: '{{courseRequired|sys:text}}'})
# 行4 学分
rows_new[4] = replace_row_cells(rows_new[4], {1: '{{courseCredit|sys:text}} 学分'})
# 行5 学期（开课单位保留静态）
rows_new[5] = replace_row_cells(rows_new[5], {1: '{{semesters|sys:text}}'})
# 行6 适用专业
rows_new[6] = replace_row_cells(rows_new[6], {1: '{{majorName|sys:text}}'})
# 行7 先修/后续
rows_new[7] = replace_row_cells(rows_new[7], {1: '{{coursePre|sys:text}}', 3: '{{courseSuf|sys:text}}'})
out_items[i_t1] = re.sub(r'<w:tr\b.*?</w:tr>', lambda m: rows_new.pop(0) if rows_new else m.group(0),
                         out_items[i_t1], count=8, flags=re.S) if False else out_items[i_t1]
# 上面 lambda 方式复杂，直接拼接重建表格
t1_xml = out_items[i_t1]
t1_prefix = t1_xml[:t1_xml.find('<w:tr')]
out_items[i_t1] = t1_prefix + ''.join(rows_new) + '</w:tbl>'

# ── C. 二章：富文本段替换 ──
i_c2 = find_para('本课程为计算机科学与技术专业的一门必修')
replace_with_placeholder_para(i_c2, '{{coursePosition|sys:html}}')
delete_item(find_para('本课程从资源管理的角度出发'))
delete_item(find_para('OBE 理念声明'))
i_obe = find_para('本课程遵循 OBE')
delete_item(i_obe)

# ── D. 表2（支撑关系，6行4列）循环化 ──
i_s31 = find_para('3.1 课程目标')
i_t2 = find_tbl_after(i_s31)
t2_rows = re.findall(r'<w:tr\b.*?</w:tr>', out_items[i_t2], re.S)
tpl_row = replace_row_cells(t2_rows[1], {
    0: '{{#optionStrengthList}}{{courseGoal|sys:text}}{{goalName|sys:text}}',
    1: '{{optionDesc|sys:text}}',
    2: '{{supportStrength|sys:text}}',
    3: '{{goalApproach|sys:text}}{{/optionStrengthList}}',
})
t2_prefix = out_items[i_t2][:out_items[i_t2].find('<w:tr')]
out_items[i_t2] = t2_prefix + t2_rows[0] + tpl_row + '</w:tbl>'

# ── E. 3.2 CEP 表静态保留；典型问题段静态 ──

# ── F. 表4（进程表，11行7列→5列）层级循环化 ──
i_s41 = find_para('4.1 课程进程表')
i_t4 = find_tbl_after(find_para('表3 课程进程表'))
t4 = out_items[i_t4]
t4_rows = re.findall(r'<w:tr\b.*?</w:tr>', t4, re.S)
DROP = {4, 5}  # 教学形式/考核要求
hdr = drop_cells(t4_rows[0], DROP)
parent = drop_cells(t4_rows[1], DROP)
child = drop_cells(t4_rows[2], DROP)
# 父行：序号(嵌外层open)/知识单元/学时/预期效果/目标
parent = replace_row_cells(parent, {
    0: '{{#courseunitList}}{{serial|sys:text}}',
    1: '{{unitName|sys:text}}',
    2: '{{recommendHour|sys:text}}',
    3: '{{first_expectedEffect|sys:text}}',
    4: '{{courseGoals|sys:text}}',
})
# 子行：序号(内层open)/知识点/学时(空)/预期效果(嵌内层close)/目标(空+外层close)
child = replace_row_cells(child, {
    0: '{{#restChildren}}',
    1: '{{knowledgePoint|sys:text}}',
    2: '',
    3: '{{expectedEffect|sys:text}}{{/restChildren}}',
    4: '{{/courseunitList}}',
})
t4_prefix = t4[:t4.find('<w:tr')]
out_items[i_t4] = set_grid(t4_prefix, [639, 1936, 656, 3415, 1218]) + hdr + parent + child + '</w:tbl>'
# set_grid 应作用于表格整体——重写：
t4_new = t4_prefix + hdr + parent + child + '</w:tbl>'
t4_new = set_grid(t4_new, [639, 1936, 656, 3415, 1218])
out_items[i_t4] = t4_new

# ── G. 表5（实验，7行7列）循环化 ──
i_t5 = find_tbl_after(find_para('表4 实验项目表'))
t5_rows = re.findall(r'<w:tr\b.*?</w:tr>', out_items[i_t5], re.S)
tpl5 = replace_row_cells(t5_rows[1], {
    0: '{{#coursepracticeList}}{{serial|sys:text}}',
    1: '{{practiceName|sys:text}}',
    2: '{{practiceDesc|sys:html}}',
    3: '{{practiceType|sys:text}}',
    4: '{{creditHour|sys:text}}',
    5: '{{peopleNum|sys:text}}',
    6: '{{requiredFlag|sys:text}}{{/coursepracticeList}}',
})
t5_prefix = out_items[i_t5][:out_items[i_t5].find('<w:tr')]
out_items[i_t5] = t5_prefix + t5_rows[0] + tpl5 + '</w:tbl>'

# ── H. 表6（思政，7行3列→2列）循环化 ──
i_t6 = find_tbl_after(find_para('表5 拟融入的课程思政元素表'))
t6 = out_items[i_t6]
t6_rows = re.findall(r'<w:tr\b.*?</w:tr>', t6, re.S)
hdr6 = drop_cells(t6_rows[0], {0})
tpl6 = drop_cells(t6_rows[1], {0})
tpl6 = replace_row_cells(tpl6, {
    0: '{{#courseunitDescList}}{{unitName|sys:text}}',
    1: '{{unitDesc|sys:text}}{{/courseunitDescList}}',
})
t6_prefix = t6[:t6.find('<w:tr')]
t6_new = t6_prefix + hdr6 + tpl6 + '</w:tbl>'
t6_new = set_grid(t6_new, [2054, 5652])
out_items[i_t6] = t6_new

# ── I. 6.2 考核段落 → examineMethod ──
delete_item(find_para('本课程注重过程考核，坚持平时考核'))
delete_item(find_para('总评成绩 = 平时成绩'))
i_p = find_para('平时成绩由 5 次平时作业决定')
replace_with_placeholder_para(i_p, '{{examineMethod|sys:html}}')

# ── J. 表7（矩阵）→ 标记段 ──
i_s71 = find_para('7.1 各考核环节对课程目标的支撑')
i_t7 = find_tbl_after(find_para('表6 各考核环节对课程目标的支撑权重绝对值'))
replace_with_placeholder_para(i_t7 - 0, '') if False else None
# 用矩阵标记段替换整个表格项
p_ref = out_items[i_t7 - 1]  # 表题段，借用其段落属性
rpr = re.search(r'<w:rPr>.*?</w:rPr>', p_ref, re.S)
rpr = rpr.group(0) if rpr else ''
out_items[i_t7] = re.sub(r'<w:r>.*?</w:r>', '', out_items[i_t7 - 1], flags=re.S)  # 先清空引用段? 不动它
matrix_p = '<w:p>' + make_run(rpr, '{{examineGoalMatrix|sys:table}}') + '</w:p>'
out_items[i_t7] = matrix_p

# ── K. 7.3 → goalFinishDesc ──
replace_with_placeholder_para(find_para('各课程目标的达成度评价基于多源证据'), '{{goalFinishDesc|sys:html}}')

# ── L. 八章教材 → reference ──
i_l1 = find_para('1. 建议教材')
i_l2 = find_para('（执笔人')
replace_with_placeholder_para(i_l1, '{{reference|sys:html}}')
for i in range(i_l1 + 1, i_l2):
    if not is_item_tbl(out_items[i]):
        out_items[i] = ''

# ── 重打包 ──
new_body = ''.join(x for x in out_items if x != '')
xml_new = head + new_body + tail
with zipfile.ZipFile(DST + '.new', 'w', zipfile.ZIP_DEFLATED) as zo:
    for item in z.infolist():
        data = z.read(item.filename)
        if item.filename == 'word/document.xml':
            data = xml_new.encode('utf8')
        zo.writestr(item, data)
z.close()
shutil.move(DST + '.new', DST)
print('模板重建完成:', DST, 'document.xml', len(xml), '->', len(xml_new))

# ── 校验 ──
z2 = zipfile.ZipFile(DST)
x2 = z2.read('word/document.xml').decode('utf8')
for k in ['{{#optionStrengthList}}', '{{/optionStrengthList}}', '{{#courseunitList}}', '{{/courseunitList}}',
          '{{#restChildren}}', '{{/restChildren}}', '{{#coursepracticeList}}', '{{#courseunitDescList}}',
          '{{examineGoalMatrix|sys:table}}', '{{coursePosition|sys:html}}', '{{examineMethod|sys:html}}',
          '{{reference|sys:html}}', '{{goalFinishDesc|sys:html}}', '{{courseName|sys:text}}']:
    n = x2.count(k)
    flag = '✓' if n == 1 else f'✗×{n}'
    print(f'  {flag} {k}')
