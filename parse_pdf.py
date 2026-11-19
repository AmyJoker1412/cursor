#!/usr/bin/env python3
"""Parse 入党积极分子学习知识题库 PDF into questions.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "source.pdf"
OUT_PATH = ROOT / "data" / "questions.json"

PAGE_NUM_RE = re.compile(r"(?m)^\d{1,3}\s*$")
OPTION_START_RE = re.compile(r"^([A-F])[\.．、]\s*(.*)$")
# Some items omit the dot, e.g. "5 坚持以马克思主义…"
QUESTION_START_RE = re.compile(r"^(\d+)(?:[\.．、]\s*|\s+)(.*)$")
SECTION_RE = re.compile(r"^第[一二三四五六七八九十百零〇两\d]+部分[：:].*")
SOURCE_ERDA = "党的二十大报告题库"
SOURCE_CHARTER = "《中国共产党章程》"
# Answers like （A ） / （ACD ） / ( ABCD ） / （B ）、（C ）
ANSWER_TOKEN_RE = re.compile(
    r"[（(]\s*([A-F](?:\s*[A-F])*)\s*[）)]"
)


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def clean_text(text: str) -> str:
    # Drop TOC: keep from first real body title.
    start = text.find("党的二十大报告题库\n第一部分")
    if start < 0:
        start = text.find("第一部分：过去五年")
    if start >= 0:
        text = text[start:]
    text = PAGE_NUM_RE.sub("", text)
    # Normalize whitespace inside lines but keep newlines.
    lines = []
    for line in text.splitlines():
        line = line.replace("\u3000", " ").strip()
        if not line:
            continue
        lines.append(line)
    return "\n".join(lines)


def normalize_answer_letters(raw: str) -> list[str]:
    letters = re.findall(r"[A-F]", raw.upper())
    # Preserve order, unique
    seen = set()
    out = []
    for ch in letters:
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return out


def extract_answers_from_stem(stem: str) -> tuple[str, list[str]]:
    """Pull answer letters out of stem blanks; return cleaned stem + answers."""
    answers: list[str] = []
    for match in ANSWER_TOKEN_RE.finditer(stem):
        answers.extend(normalize_answer_letters(match.group(1)))
    # Unique preserving order
    uniq = []
    seen = set()
    for a in answers:
        if a not in seen:
            seen.add(a)
            uniq.append(a)

    def repl(m: re.Match[str]) -> str:
        return "（  ）"

    cleaned = ANSWER_TOKEN_RE.sub(repl, stem)
    # Collapse adjacent blank punctuation like （  ）、（  ）、（  ）
    cleaned = re.sub(r"（  ）(?:[、，,]\s*（  ）)+", "（  ）", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, uniq


def parse_options(option_lines: list[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    current_key: str | None = None
    for line in option_lines:
        m = OPTION_START_RE.match(line)
        if m:
            current_key = m.group(1)
            options[current_key] = m.group(2).strip()
        elif current_key is not None:
            options[current_key] = (options[current_key] + line).strip()
    # Normalize spaces
    for k, v in list(options.items()):
        options[k] = re.sub(r"\s+", " ", v).strip()
    return options


def split_blocks(lines: list[str]) -> list[dict]:
    """Walk lines and emit structured question-ish blocks with metadata."""
    blocks: list[dict] = []
    source = SOURCE_ERDA
    section = "未分类"
    qtype = "single"
    buf_num: str | None = None
    buf_lines: list[str] = []

    def flush() -> None:
        nonlocal buf_num, buf_lines
        if buf_num is None:
            return
        blocks.append(
            {
                "num": buf_num,
                "source": source,
                "section": section,
                "type": qtype,
                "lines": buf_lines[:],
            }
        )
        buf_num = None
        buf_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("《中国共产党章程》"):
            flush()
            source = SOURCE_CHARTER
            section = "《中国共产党章程》"
            i += 1
            continue

        if line.startswith("党的二十大报告题库"):
            flush()
            source = SOURCE_ERDA
            i += 1
            continue

        if SECTION_RE.match(line) or line.startswith("第") and "部分" in line[:8]:
            flush()
            # Join wrapped section titles
            title = line
            j = i + 1
            while j < len(lines) and not (
                SECTION_RE.match(lines[j])
                or lines[j] in ("一、单选题", "二、多选题")
                or QUESTION_START_RE.match(lines[j])
                or lines[j].startswith("《中国共产党章程》")
            ):
                # Avoid swallowing options/questions
                if OPTION_START_RE.match(lines[j]):
                    break
                title += lines[j]
                j += 1
            section = re.sub(r"\s+", "", title)
            # Strip trailing count like （24题）
            section = re.sub(r"[（(]\d+\s*题[）)]$", "", section)
            i = j
            continue

        if line in ("一、单选题", "二、多选题"):
            flush()
            qtype = "single" if "单选" in line else "multiple"
            i += 1
            continue

        m = QUESTION_START_RE.match(line)
        if m:
            flush()
            buf_num = m.group(1)
            rest = m.group(2).strip()
            buf_lines = [rest] if rest else []
            i += 1
            continue

        if buf_num is not None:
            buf_lines.append(line)
        i += 1

    flush()
    return blocks


def block_to_question(block: dict, seq: int) -> dict | None:
    lines = block["lines"]
    if not lines:
        return None

    # Split stem vs options: first option start
    opt_idx = None
    for idx, line in enumerate(lines):
        if OPTION_START_RE.match(line):
            opt_idx = idx
            break
    if opt_idx is None:
        return None

    stem_raw = "".join(lines[:opt_idx])
    stem_raw = re.sub(r"\s+", " ", stem_raw).strip()
    stem, answers = extract_answers_from_stem(stem_raw)
    options = parse_options(lines[opt_idx:])

    if not options or not answers:
        return None

    # Validate answers exist in options
    answers = [a for a in answers if a in options]
    if not answers:
        return None

    qtype = block["type"]
    if len(answers) > 1:
        qtype = "multiple"
    elif qtype == "single" and len(answers) == 1:
        qtype = "single"

    slug_source = "erda" if block["source"] == SOURCE_ERDA else "charter"
    qid = f"{slug_source}-{seq:04d}"

    return {
        "id": qid,
        "source": block["source"],
        "section": block["section"],
        "type": qtype,
        "stem": stem,
        "options": options,
        "answer": answers,
        "number": int(block["num"]),
    }


def main() -> None:
    raw = extract_text(PDF_PATH)
    cleaned = clean_text(raw)
    lines = cleaned.splitlines()
    blocks = split_blocks(lines)
    questions = []
    skipped = []
    for i, block in enumerate(blocks, start=1):
        q = block_to_question(block, i)
        if q is None:
            skipped.append(block)
        else:
            questions.append(q)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "title": "入党积极分子学习知识题库",
        "count": len(questions),
        "questions": questions,
    }
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    by_type = {"single": 0, "multiple": 0}
    by_source: dict[str, int] = {}
    sections: dict[str, int] = {}
    for q in questions:
        by_type[q["type"]] = by_type.get(q["type"], 0) + 1
        by_source[q["source"]] = by_source.get(q["source"], 0) + 1
        sections[q["section"]] = sections.get(q["section"], 0) + 1

    print(f"Wrote {len(questions)} questions -> {OUT_PATH}")
    print("by_type", by_type)
    print("by_source", by_source)
    print("sections", len(sections))
    for name, n in sections.items():
        print(f"  {n:3d}  {name}")
    print(f"skipped {len(skipped)}")
    for s in skipped[:10]:
        print(" SKIP", s["num"], s["type"], "".join(s["lines"])[:80])


if __name__ == "__main__":
    main()
