# -*- coding: utf-8 -*-
"""앞 실습에서 완성한 QA와 가드레일을 하나로 연결한 기능입니다."""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import qa

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "output" / "guardrail.jsonl"
MAX_INPUT_LENGTH = 500
MAX_ATTEMPTS = 3
NO_KNOWLEDGE_REPLY = "해당 정보를 찾을 수 없습니다."
HITL_REPLY = "담당자 확인이 필요합니다. 잠시만 기다려 주세요."
EMPTY_REPLY = "질문을 입력해 주세요."
TOO_LONG_REPLY = "질문은 500자 이내로 입력해 주세요."


def _result(answer_text, sources=None, latency_ms=0.0, cost=0.0):
    return {
        "answer": str(answer_text),
        "sources": list(sources or []),
        "metrics": {"latency_ms": float(latency_ms), "cost": float(cost)},
    }


def _validate_input(question):
    if not isinstance(question, str) or not question.strip():
        return "empty"
    text = question.strip()
    if len(text) > MAX_INPUT_LENGTH:
        return "too_long"
    compact = re.sub(r"\s+", "", text.lower())
    patterns = [
        "이전지시를무시", "기존지시를무시", "시스템프롬프트를보여",
        "시스템프롬프트공개", "개발자메시지공개", "관리자권한을부여",
        "접근허용이라고답",
    ]
    if any(pattern in compact for pattern in patterns):
        return "prompt_injection"
    return None


def _call_with_retry(question):
    for _ in range(MAX_ATTEMPTS):
        try:
            return qa.answer(question)
        except Exception:
            continue
    return None


def _validate_output(result):
    if not isinstance(result, dict):
        return None
    answer_text = result.get("answer")
    sources = result.get("sources")
    metrics = result.get("metrics")
    if not isinstance(answer_text, str) or not answer_text.strip():
        return None
    if not isinstance(sources, list) or not isinstance(metrics, dict):
        return None
    if not sources:
        return _result(NO_KNOWLEDGE_REPLY, [], metrics.get("latency_ms", 0.0), metrics.get("cost", 0.0))
    dangerous = ["openai_api_key", "시스템 프롬프트 원문", "관리자 권한 승인됨", "접근 허용됨"]
    lower = answer_text.lower()
    if any(token in lower for token in dangerous) or re.search(r"\bsk-[A-Za-z0-9_-]{8,}", answer_text):
        return None
    return _result(answer_text.strip(), sources, metrics.get("latency_ms", 0.0), metrics.get("cost", 0.0))


def _log(question, status, reason, source_count):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reason": reason,
        "question_length": len(question) if isinstance(question, str) else 0,
        "source_count": int(source_count),
    }
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")


def answer(question, mode=None):
    started = time.perf_counter()
    reason = _validate_input(question)
    if reason == "empty":
        result = _result(EMPTY_REPLY)
        _log(question, "blocked", reason, 0)
    elif reason == "too_long":
        result = _result(TOO_LONG_REPLY)
        _log(question, "blocked", reason, 0)
    elif reason:
        result = _result(HITL_REPLY)
        _log(question, "review_required", reason, 0)
    else:
        raw = _call_with_retry(question.strip())
        if raw is None:
            result = _result(HITL_REPLY)
            _log(question, "review_required", "call_failed", 0)
        else:
            checked = _validate_output(raw)
            if checked is None:
                result = _result(HITL_REPLY)
                _log(question, "review_required", "unsafe_output", 0)
            else:
                result = checked
                status = "passed" if checked["sources"] else "blocked"
                reason_text = "ok" if checked["sources"] else "no_knowledge"
                _log(question, status, reason_text, len(checked["sources"]))
    result["metrics"]["latency_ms"] = (time.perf_counter() - started) * 1000
    return result
