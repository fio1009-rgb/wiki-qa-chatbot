# -*- coding: utf-8 -*-
"""사내 위키 문서를 검색하고 답변을 만드는 기능입니다."""
import json
import re
import time
from pathlib import Path

import llm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "data" / "docs"
OUTPUT_DIR = PROJECT_ROOT / "output"
INDEX_PATH = OUTPUT_DIR / "index.json"


def _parse_md(text):
    title = ""
    sections = []
    heading = None
    body = []
    for line in text.splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("## "):
            if heading is not None:
                sections.append({"heading": heading, "text": "\n".join(body).strip()})
            heading = line[3:].strip()
            body = []
        elif heading is not None:
            body.append(line)
    if heading is not None:
        sections.append({"heading": heading, "text": "\n".join(body).strip()})
    return {"title": title, "sections": sections}


def build_index():
    index = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        parsed = _parse_md(path.read_text(encoding="utf-8"))
        index.append({
            "doc": path.stem,
            "title": parsed["title"],
            "sections": parsed["sections"],
        })
    return index


def load_index():
    if INDEX_PATH.exists():
        try:
            value = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            if isinstance(value, list):
                return value
        except (OSError, json.JSONDecodeError):
            pass
    index = build_index()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def _toc(index):
    blocks = []
    for document in index:
        lines = [f"[{document['doc']}] {document['title']}"]
        for section in document.get("sections", []):
            lines.append(str(section.get("heading", "")))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _knowledge(index):
    blocks = []
    for document in index:
        for section in document.get("sections", []):
            blocks.append(f"[doc={document['doc']}][heading={section['heading']}]\n{section['text']}")
    return "\n\n".join(blocks)


def _find_section(index, doc_name, heading):
    for document in index:
        if document.get("doc") != doc_name:
            continue
        for section in document.get("sections", []):
            if section.get("heading") == heading:
                return {
                    "doc": document.get("doc", ""),
                    "heading": section.get("heading", ""),
                    "text": section.get("text", ""),
                }
    return None


def _fallback_section(index, question):
    tokens = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", str(question).lower()))
    best = None
    best_score = 0
    for document in index:
        for section in document.get("sections", []):
            searchable = " ".join([
                str(document.get("title", "")),
                str(section.get("heading", "")),
                str(section.get("text", "")),
            ]).lower()
            score = sum(1 for token in tokens if token in searchable)
            if score > best_score:
                best_score = score
                best = {
                    "doc": document.get("doc", ""),
                    "heading": section.get("heading", ""),
                    "text": section.get("text", ""),
                }
    return best


def answer(question, mode=None):
    started = time.perf_counter()
    index = load_index()
    result = llm.answer_with_source(question, _knowledge(index))
    section = _find_section(index, str(result.get("doc", "")).strip(), str(result.get("heading", "")).strip())
    answer_text = str(result.get("answer", "")).strip()
    if not section or not answer_text or answer_text == NO_KNOWLEDGE_REPLY:
        answer_text = "해당 정보를 찾을 수 없습니다."
        sources = []
    else:
        sources = [f"kb:{section['doc']}#{section['heading']}"] if answer_text else []

    return {
        "answer": answer_text,
        "sources": sources,
        "metrics": {
            "latency_ms": (time.perf_counter() - started) * 1000,
            "cost": 0.0,
        },
    }
