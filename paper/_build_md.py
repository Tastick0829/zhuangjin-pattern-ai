# -*- coding: utf-8 -*-
"""把论文 docx 转为可在线预览的 markdown，并压缩其中的插图。

根因：docx 体积 100% 来自嵌入的 PNG（main 18 张 9.71MB / early 15 张 6.78MB），
      GitHub 既不能预览 docx，大文件也会触发 "can't show files that are this big"。
方案：① 生成 markdown 正文（GitHub 原生渲染）；② 图片压缩后放 assets/ 供 md 引用。
"""
import sys, io, os, re, zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

BASE = r"D:\wendang\GitHub\zhuangjin-pattern-ai\paper"
ASSETS = os.path.join(BASE, "assets")
os.makedirs(ASSETS, exist_ok=True)

MAX_W = 1400          # 插图最大宽度
JPEG_Q = 88           # JPEG 质量

# 老版 .doc 转 .docx 后图片使用 VML 格式，需单独处理
VML_IMAGEDATA = '{urn:schemas-microsoft-com:vml}imagedata'
R_NS_ID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def is_heading(t):
    """判断段落是否为标题，返回 markdown 前缀"""
    if re.match(r'^[一二三四五六七八九十]+[、.．]', t):
        return "## "
    if re.match(r'^（[一二三四五六七八九十]+）', t):
        return "### "
    if re.match(r'^\d+\s*[.．]\s*\S', t) and len(t) < 40:
        return "#### "
    return ""


def conv_image(part, fig_no, prefix):
    """把 docx 内嵌图片压缩输出到 assets，返回相对路径"""
    blob = part.blob
    tmp = io.BytesIO(blob)
    try:
        im = Image.open(tmp)
    except Exception as e:
        print(f"    [!] 图 {fig_no} 无法解析: {e}")
        return None
    w, h = im.size
    if w > MAX_W:
        nh = int(h * MAX_W / w)
        im = im.resize((MAX_W, nh), Image.LANCZOS)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGB")
    out = os.path.join(ASSETS, f"{prefix}-fig-{fig_no:02d}.jpg")
    im.save(out, "JPEG", quality=JPEG_Q, optimize=True, progressive=True)
    return f"./assets/{prefix}-fig-{fig_no:02d}.jpg", os.path.getsize(out), (w, h), im.size


def convert(docx_name, md_name, title, prefix):
    path = os.path.join(BASE, docx_name)
    if not os.path.exists(path):
        print(f"跳过（不存在）: {docx_name}")
        return
    doc = Document(path)
    md = [f"# {title}", "",
          "> 本文件是论文的 Markdown 版本，供在线直接阅读。",
          "> 完整排版版（含原始高清插图）见 [{}](./{})　·　[PDF](./{})".format(
              docx_name, docx_name, docx_name.replace(".docx", ".pdf")),
          "", "---", ""]

    fig_no = 0
    stats = []
    tbl_no = 0

    for child in doc.element.body.iterchildren():
        tag = child.tag
        if tag == qn('w:p'):
            p = Paragraph(child, doc)
            # 收集本段的图片 rId（兼容 DrawingML 与老版 VML 两种格式）
            # 说明：本论文由老版 .doc 转换而来，图片用 VML（<w:pict> + <v:imagedata r:id>）
            rids = []
            for blip in p._element.findall('.//' + qn('a:blip')):
                rid = blip.get(qn('r:embed'))
                if rid:
                    rids.append(rid)
            for im in p._element.findall('.//' + VML_IMAGEDATA):
                rid = im.get(R_NS_ID)
                if rid:
                    rids.append(rid)

            for rId in rids:
                try:
                    part = doc.part.related_parts[rId]
                except KeyError:
                    continue
                fig_no += 1
                res = conv_image(part, fig_no, prefix)
                if res:
                    rel, sz, orig, new = res
                    stats.append((fig_no, orig, new))
                    md.append(f"![图 {fig_no}]({rel})")
                    md.append("")
            t = p.text.strip()
            if t:
                # 注意：变量名不能叫 prefix —— 会遮蔽函数参数 prefix（图片文件名前缀）
                h_prefix = is_heading(t)
                md.append(f"{h_prefix}{t}" if h_prefix else t)
                md.append("")
        elif tag == qn('w:tbl'):
            tbl = Table(child, doc)
            tbl_no += 1
            rows = []
            for row in tbl.rows:
                cells = [c.text.strip().replace("\n", " ").replace("|", "\\|") for c in row.cells]
                rows.append(cells)
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                md.append(f"**表 {tbl_no}**")
                md.append("")
                md.append("| " + " | ".join(rows[0]) + " |")
                md.append("| " + " | ".join(["---"] * width) + " |")
                for r in rows[1:]:
                    md.append("| " + " | ".join(r) + " |")
                md.append("")

    out = os.path.join(BASE, md_name)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md))

    print(f"\n【{docx_name}】-> {md_name}")
    print(f"  输出: {len(md)} 行 / {os.path.getsize(out)/1024:.1f} KB")
    print(f"  图片: {fig_no} 张，表格: {tbl_no} 个")
    if stats:
        o_mp = sum(s[1][0] * s[1][1] for s in stats) / 1e6
        n_mp = sum(s[2][0] * s[2][1] for s in stats) / 1e6
        ratio = (1 - n_mp / o_mp) * 100 if o_mp else 0
        print(f"  插图总像素: {o_mp:.1f} MP -> {n_mp:.1f} MP（降采样 {ratio:.0f}%）")
        print("  详细:")
        for no, orig, new in stats[:20]:
            print(f"    {prefix}-fig-{no:02d}: {orig[0]}x{orig[1]} -> {new[0]}x{new[1]}")


if __name__ == "__main__":
    convert("paper-main.docx", "paper-main.md",
            "AI赋能非遗新生：广西壮锦数字化纹样创新生成系统的设计与实践研究",
            "main")
    convert("paper-early.docx", "paper-early.md",
            "AI赋能非遗新生：广西壮锦数字化纹样创新生成系统的设计与实践研究（早期版）",
            "early")
    print("\n=== assets/ 目录 ===")
    files = sorted(os.listdir(ASSETS))
    total = 0
    for f in files:
        s = os.path.getsize(os.path.join(ASSETS, f))
        total += s
        print(f"  {f:<16} {s/1024:7.1f} KB")
    print(f"  合计 {len(files)} 个文件 / {total/1048576:.2f} MB")
