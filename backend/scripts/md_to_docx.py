#!/usr/bin/env python3
"""Convert a markdown resume file to a formatted ATS-friendly Word document.

Usage:
    python scripts/md_to_docx.py <input.md> [output.docx]
    # Output defaults to same path with .docx extension if not specified
"""

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

BLUE = RGBColor(0x1F, 0x49, 0x7D)


def _bottom_border(paragraph, color_hex: str = "1F497D", sz: int = 4):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(sz))
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color_hex)
    pBdr.append(bottom)
    pPr.append(pBdr)


def _spacing(paragraph, before: int = 0, after: int = 0):
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(after)


def _parse_inline(paragraph, text: str, base_size: float = 10.0):
    """Add runs handling **bold** markers and stripping [label](url) links."""
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    parts = re.split(r"\*\*(.+?)\*\*", text)
    for idx, part in enumerate(parts):
        if not part:
            continue
        run = paragraph.add_run(part)
        run.font.size = Pt(base_size)
        if idx % 2 == 1:
            run.bold = True


def convert(input_path: Path, output_path: Path) -> None:
    doc = Document()

    # Margins: 0.75" top/bottom, 0.85" sides — gives room without looking cramped
    for sec in doc.sections:
        sec.top_margin = Inches(0.75)
        sec.bottom_margin = Inches(0.75)
        sec.left_margin = Inches(0.85)
        sec.right_margin = Inches(0.85)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)

    raw_lines = input_path.read_text(encoding="utf-8").splitlines()

    # Strip the agent metadata block (# Resume — ... up to first ---)
    start = 0
    if raw_lines and raw_lines[0].startswith("# Resume"):
        for i, ln in enumerate(raw_lines):
            if ln.strip() == "---":
                start = i + 1
                break

    lines = raw_lines[start:]

    after_name = False   # next bold-only line is the tagline
    in_header = True     # True until we hit the first ## section heading

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        i += 1

        if not line:
            continue

        # ── Horizontal rule ─────────────────────────────────────────────────
        if line == "---":
            p = doc.add_paragraph()
            _spacing(p, before=2, after=4)
            _bottom_border(p, color_hex="CCCCCC", sz=6)
            after_name = False
            continue

        # ── H1 = Name ───────────────────────────────────────────────────────
        if re.match(r"^# (?!#)", line):
            name = line[2:].strip()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _spacing(p, before=0, after=2)
            run = p.add_run(name)
            run.bold = True
            run.font.size = Pt(18)
            after_name = True
            continue

        # ── H2 = Section heading ────────────────────────────────────────────
        if line.startswith("## "):
            heading = line[3:].strip().upper()
            p = doc.add_paragraph()
            _spacing(p, before=8, after=2)
            run = p.add_run(heading)
            run.bold = True
            run.font.size = Pt(11)
            run.font.color.rgb = BLUE
            _bottom_border(p, color_hex="1F497D", sz=4)
            after_name = False
            in_header = False
            continue

        # ── H3 = Company / institution ──────────────────────────────────────
        if line.startswith("### "):
            company = line[4:].strip()
            p = doc.add_paragraph()
            _spacing(p, before=6, after=1)
            run = p.add_run(company)
            run.bold = True
            run.font.size = Pt(10.5)
            after_name = False
            continue

        # ── Bullet point ────────────────────────────────────────────────────
        if line.startswith("- "):
            content = line[2:]
            p = doc.add_paragraph(style="List Bullet")
            _spacing(p, before=1, after=1)
            p.paragraph_format.left_indent = Inches(0.2)
            _parse_inline(p, content)
            after_name = False
            continue

        # ── Bold-only line ─────────────────────────────────────────────────
        # Matches **entire line bold** with exactly two ** delimiters
        m = re.match(r"^\*\*(.+)\*\*$", line)
        if m and line.count("**") == 2:
            content = m.group(1)
            p = doc.add_paragraph()
            if after_name:
                # Tagline: centered, slightly larger
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _spacing(p, before=1, after=2)
                run = p.add_run(content)
                run.bold = True
                run.font.size = Pt(10.5)
                after_name = False
            else:
                # Job title line that happens to be fully bold (rare)
                _spacing(p, before=1, after=1)
                run = p.add_run(content)
                run.bold = True
                run.font.size = Pt(10)
            continue

        # ── Line starting with ** (job title / competency line) ─────────────
        if line.startswith("**"):
            p = doc.add_paragraph()
            _spacing(p, before=1, after=1)
            _parse_inline(p, line)
            after_name = False
            continue

        # ── Plain text ───────────────────────────────────────────────────────
        # In the header block (name / contact area): centered, small
        # Inside a section (summary paragraph, etc.): left-aligned, normal size
        clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)
        p = doc.add_paragraph()
        if in_header:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _spacing(p, before=1, after=3)
            p.add_run(clean).font.size = Pt(9.5)
        else:
            _spacing(p, before=2, after=2)
            _parse_inline(p, clean)
        after_name = False

    doc.save(output_path)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/md_to_docx.py <input.md> [output.docx]")
        sys.exit(1)

    inp = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) >= 3 else inp.with_suffix(".docx")
    convert(inp, out)
