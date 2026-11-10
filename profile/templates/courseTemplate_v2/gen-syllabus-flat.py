#!/usr/bin/env python3
"""默认大纲模板平铺化重建（用户决策 2026-09-12：能平的都平 + 默认换平铺）。

基底 = 当前 syllabus.docx（循环版，列宽/边框已调优）。行克隆法：
克隆循环模板行 N 份，第 i 份字段改名（{{field|type}} → {{prefixN_field|type}}），
首份剥 {{#list}}、末份剥 {{/list}}——保留原行格式/边框/列宽。

转换目标（表3 课程进程层级表保持循环——单元数不可控）：
- tbl 支撑关系表   optionStrengthList → optStr1..8（5 字段）
- tbl 实验项目表   coursepracticeList → prac1..10（7 字段，desc 保持 sys:html）
- tbl 思政元素表   courseunitDescList → ideo1..12（2 字段）
- {{examineGoalMatrix|sys:table}} 标记段落 → 8目标×5环节平铺矩阵表（含合计行）

可重跑：每次从循环版基底重新生成（基底固定为 syllabus-loop-base.docx 备份）。
"""
import zipfile, re, shutil, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(DIR, 'syllabus-loop-base.docx')   # 循环版基底（只读备份）
DST = os.path.join(DIR, 'syllabus.docx')

if not os.path.exists(BASE):
    shutil.copy(DST, BASE)
    print('已创建循环版基底备份:', os.path.basename(BASE))

xml = zipfile.ZipFile(BASE).read('word/document.xml').decode('utf8')
body_open = xml.find('<w:body>') + len('<w:body>')
body_close = xml.rfind('</w:body>')
head, body, tail = xml[:body_open], xml[body_open:body_close], xml[body_close:]


def runs_text(frag):
    return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', frag))


def flat_row(template_row_xml, prefix, n, field_map, first, last):
    """克隆循环模板行：字段改名 + 循环标记整行剥除（平铺后无循环语义；
    模板行只此一份含标记，所有克隆行都必须去掉，否则残留标记破坏渲染）"""
    out = template_row_xml
    for src, dst in field_map.items():
        out = re.sub(r'\{\{' + src + r'(\|[\w:]+)?\}\}',
                     '{{' + dst % n + r'\1}}', out)
    out = out.replace('{{#' + LIST_OF_PREFIX[prefix] + '}}', '')
    out = out.replace('{{/' + LIST_OF_PREFIX[prefix] + '}}', '')
    return out


LIST_OF_PREFIX = {
    'optStr': 'optionStrengthList',
    'prac': 'coursepracticeList',
    'ideo': 'courseunitDescList',
}

CONVERSIONS = [
    # (定位签名: 表头行文本前缀, prefix, cap, 字段映射 src→dst 模板)
    ('课程目标（CO）毕业要求指标点', 'optStr', 8, {
        'courseGoal': 'optStr%d_courseGoal', 'goalName': 'optStr%d_goalName',
        'optionDesc': 'optStr%d_optionDesc', 'supportStrength': 'optStr%d_strength',
        'goalApproach': 'optStr%d_way',
    }),
    ('序号实验项目名称', 'prac', 10, {
        'serial': 'prac%d_serial', 'practiceName': 'prac%d_name',
        'practiceDesc': 'prac%d_desc', 'practiceType': 'prac%d_type',
        'creditHour': 'prac%d_hour', 'peopleNum': 'prac%d_people',
        'requiredFlag': 'prac%d_flag',
    }),
    ('教学内容拟融入的课程思政元素', 'ideo', 12, {
        'unitName': 'ideo%d_unit', 'unitDesc': 'ideo%d_desc',
    }),
]

# ── OOXML 平铺矩阵构件（与 blockLibrary.makeFlatMatrixTable 同构）──

def mrun(text, bold=False):
    rpr = '<w:rPr><w:b/></w:rPr>' if bold else ''
    t = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return f'<w:r>{rpr}<w:t xml:space="preserve">{t}</w:t></w:r>'

def mpara(content):
    return f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr>{content}</w:p>'

def mcell(paras, w, shade=False):
    shd = '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>' if shade else ''
    b = '<w:tcBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tcBorders>'
    return f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{shd}{b}<w:vAlign w:val="center"/></w:tcPr>{paras}</w:tc>'

def mrow(cells, header=False):
    trPr = '<w:trPr><w:tblHeader/></w:trPr>' if header else ''
    return f'<w:tr>{trPr}{"".join(cells)}</w:tr>'


def make_flat_matrix(goals=8, examines=5):
    """平铺考核矩阵：1+M+1 列。宽度归一 ~9026 dxa"""
    coln = 1 + examines + 1
    w = [2416] + [1102] * examines + [1102]
    borders = ('<w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
               '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
               '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
               '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
               '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
               '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tblBorders>')
    grid = ''.join(f'<w:gridCol w:w="{x}"/>' for x in w)
    rows = [mrow([
        mcell(mpara(mrun('课程目标', bold=True)), w[0], shade=True),
        *[mcell(mpara(mrun('{{exam%d_name|sys:text}}' % (m + 1), bold=True)), w[1 + m], shade=True)
          for m in range(examines)],
        mcell(mpara(mrun('合计', bold=True)), w[-1], shade=True),
    ], header=True)]
    for n in range(1, goals + 1):
        rows.append(mrow([
            mcell(mpara(mrun('{{goal%d_name|sys:text}}' % n)), w[0]),
            *[mcell(mpara(mrun('{{goal%d_exam%d_pop|sys:text}}' % (n, m + 1))), w[1 + m])
              for m in range(examines)],
            mcell(mpara(mrun('{{goal%d_totalPop|sys:text}}' % n)), w[-1]),
        ]))
    rows.append(mrow([
        mcell(mpara(mrun('合计', bold=True)), w[0], shade=True),
        *[mcell(mpara(mrun('{{exam%d_total|sys:text}}' % (m + 1))), w[1 + m], shade=True)
          for m in range(examines)],
        mcell(mpara(mrun('{{matrix_total|sys:text}}')), w[-1], shade=True),
    ]))
    tbl = (f'<w:tbl><w:tblPr>{borders}<w:tblW w:w="{sum(w)}" w:type="dxa"/>'
           f'<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>{grid}</w:tblGrid>'
           + ''.join(rows) + '</w:tbl><w:p/>')
    return tbl


# ── 逐表转换 ──
parts = re.split(r'(<w:tbl>.*?</w:tbl>)', body, flags=re.S)
converted = 0
for idx in range(0, len(parts)):
    frag = parts[idx]
    if not frag.startswith('<w:tbl>'):
        continue
    rows = re.findall(r'<w:tr\b.*?</w:tr>', frag, re.S)
    if not rows:
        continue
    header_text = re.sub(r'\s+', '', runs_text(rows[0]))
    for sig, prefix, cap, field_map in CONVERSIONS:
        if not header_text.startswith(sig):
            continue
        # 循环模板行 = 含 {{#list}} 的行
        tpl_rows = [r for r in rows if '{{#' + LIST_OF_PREFIX[prefix] + '}}' in r]
        if not tpl_rows:
            print(f'!! 表[{sig}] 未找到循环模板行，跳过')
            continue
        tpl = tpl_rows[0]
        new_rows = ''.join(
            flat_row(tpl, prefix, i + 1, field_map, i == 0, i == cap - 1)
            for i in range(cap))
        # 用表头+平铺行重组（原表里循环模板行之外的行保留——一般只有表头）
        kept = [r for r in rows if r != tpl]
        parts[idx] = frag.replace(''.join(rows), ''.join(kept) + new_rows) \
            if ''.join(rows) in frag else frag
        converted += 1
        print(f'OK 表[{sig[:12]}…] → {cap} 平铺行')
        break

body = ''.join(parts)

# ── 补齐大纲编辑器的标量展示位 ──
# 基底为历史 Word 排版，早期未放入这些字段；若没有占位符，前端即使保存成功，
# docx 渲染也没有可替换的位置。这里在语义相邻章节补齐，随后统一写入默认模板。
def text_para(text, bold=False):
    rpr = '<w:rPr><w:b/></w:rPr>' if bold else ''
    return f'<w:p><w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'

method_block = text_para('教学方式') + text_para('{{teachMethod|sys:html}}')
practice_block = text_para('实践环节描述') + text_para('{{practiceDesc|sys:html}}')

# 标题展示大纲名称（课程名称仍保留在“课程基本信息”表内）。
body = body.replace('{{courseName|sys:text}}》课程教学大纲', '{{outlineName|sys:text}}》课程教学大纲', 1)
# 教学方式紧邻考核方式；实践描述紧邻实验实训表。课程目标保持原有支撑关系表版式。
# 考核方式所在段落带有较复杂的 Word 样式，必须在整个段落前插入；不能只替换
# w:t 内的占位文本，否则会把 w:p 嵌入 w:t，docxtemplater 会报 Malformed xml。
# 定位：从占位符位置向前找最近的段落开标签（<w:p> / <w:p 带>取更近者）。
# 不能用 re.search(r'<w:p\b.*?占位符.*?</w:p>', re.S)——search 从全文第一个 <w:p
# 起配、.*? 在 re.S 下跨段懒扩展，start() 落在文档顶端（曾致「教学方式」插到大标题前）。
def insert_before_para_containing(body, placeholder, block):
    pos = body.find(placeholder)
    if pos < 0:
        return body, False
    p_start = max(body.rfind('<w:p>', 0, pos), body.rfind('<w:p ', 0, pos))
    if p_start < 0:
        return body, False
    return body[:p_start] + block + body[p_start:], True

body, ok_method = insert_before_para_containing(body, '{{examineMethod|sys:html}}', method_block)
print('OK 教学方式插入考核方式段前' if ok_method else '!! 未找到考核方式占位符')
# 平铺转换后循环标记已被移除，按实验实训表头定位该表再插入说明段。
practice_table = next((m for m in re.finditer(r'<w:tbl\b.*?</w:tbl>', body, re.S)
                       if re.sub(r'\s+', '', runs_text(m.group())).startswith('序号实验项目名称')), None)
if practice_table:
    body = body[:practice_table.start()] + practice_block + body[practice_table.start():]

# ── 矩阵标记 → 平铺矩阵表 ──
marker_re = re.compile(r'<w:p\b(?:(?!<w:p\b).)*?\{\{examineGoalMatrix\|sys:table\}\}.*?</w:p>', re.S)
m = marker_re.search(body)
if m:
    body = body[:m.start()] + make_flat_matrix() + body[m.end():]
    print('OK 考核矩阵标记 → 8×5 平铺矩阵表')
else:
    print('!! 未找到矩阵标记')

# ── 附件静态示例表 → examineAppendix 标记（渲染期生成汇总窄表+分环节子表）──
# 静态表示例数字写死（5 目标/5 作业/5 实训/期末三段式），换课程不随数据更新；
# 改为 sys:table 标记后由前端 buildExamineAppendixTablesXml 按计算依据表数据动态生成。
tbls_apx = [t for t in re.finditer(r'<w:tbl>.*?</w:tbl>', body, re.S)
            if runs_text(t.group()).startswith('课程目标考核项/评价贡献值')]
if tbls_apx:
    t = tbls_apx[0]
    apx_marker = ('<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
                  '<w:r><w:t xml:space="preserve">{{examineAppendix|sys:table}}</w:t></w:r></w:p>')
    body = body[:t.start()] + apx_marker + body[t.end():]
    print('OK 附件静态示例表 → examineAppendix 标记')

    # 注释段重写：口径①公式（旧示例注释「实训1—实训5」等随静态表失效）
    note_m = re.search(r'<w:p\b(?:(?!</w:p>).)*?上表中(?:(?!</w:p>).)*?</w:p>', body, re.S)
    if note_m:
        note_text = ('注：（1）环节汇总＝该环节各考核项在对应课程目标上的分值合计（与「课程达成度计算依据表」的合计列同源）；'
                     '（2）评价贡献值＝环节汇总×（环节权重÷100）；'
                     '（3）正文表6为支撑权重口径（目标分值视角），与本表评价贡献值语义不同。')
        body = body[:note_m.start()] + \
            f'<w:p><w:r><w:t xml:space="preserve">{note_text}</w:t></w:r></w:p>' + body[note_m.end():]
        print('OK 附件注释段重写为口径①公式')

    # 分节统一竖版：删附件前的段内分节符（原横版附件区起点），文档末分节转竖版
    marker_pos = body.find('{{examineAppendix|sys:table}}')
    sect_paras = [sp for sp in re.finditer(
        r'<w:p\b[^>]*>(?:(?!</w:p>).)*?<w:sectPr(?:(?!</w:p>).)*?</w:p>', body, re.S)
        if sp.end() < marker_pos]
    if sect_paras:
        sp = sect_paras[-1]
        body = body[:sp.start()] + body[sp.end():]
        print('OK 删除附件前段内分节符')
    tail_land = re.search(r'<w:pgSz w:w="16838" w:h="11906"( w:orient="landscape")?/>', body)
    if tail_land:
        body = body[:tail_land.start()] + '<w:pgSz w:w="11906" w:h="16838"/>' + body[tail_land.end():]
        print('OK 文档末分节转竖版（附件区与正文一致）')
elif '{{examineAppendix|sys:table}}' in body:
    print('SKIP 附件表已是标记版（幂等重跑）')
else:
    print('!! 未找到附件静态示例表')

out = head + body + tail

# ── 校验与写出 ──
from xml.etree import ElementTree as ET
ET.fromstring(out.encode('utf8'))
src = zipfile.ZipFile(BASE)
with zipfile.ZipFile(DST, 'w', zipfile.ZIP_DEFLATED) as z:
    for n in src.namelist():
        z.writestr(n, out if n == 'word/document.xml' else src.read(n))
print('WROTE', DST)
ph = re.findall(r'\{\{[^}]{1,80}\}\}', out)
loops = [p for p in ph if '{{#' in p or '{{/' in p]
print(f'placeholders={len(ph)} unique={len(set(ph))} 剩余循环标记={sorted(set(loops))}')
