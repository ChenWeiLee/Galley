"""
Judge0 status → Verdict mapping test (Plan REV-8: opaque value object).

Imports the adapter's mapping function but NOT through Django settings; we test
the pure function only.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Stub django.conf.settings so importing the adapter doesn't require Django.
sys.modules.setdefault("django", MagicMock())
sys.modules.setdefault("django.conf", MagicMock())

# Path setup
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from domain.entities import Verdict  # noqa: E402
from web.apps.judging.adapters import STATUS_TO_VERDICT, Judge0Client, _b64, _b64d  # noqa: E402


def test_status_3_is_accepted():
    assert STATUS_TO_VERDICT[3] == Verdict.ACCEPTED


def test_status_4_is_wrong_answer():
    assert STATUS_TO_VERDICT[4] == Verdict.WRONG_ANSWER


def test_status_5_is_tle():
    assert STATUS_TO_VERDICT[5] == Verdict.TIME_LIMIT_EXCEEDED


def test_status_6_is_compile_error():
    assert STATUS_TO_VERDICT[6] == Verdict.COMPILE_ERROR


def test_status_14_is_mle():
    assert STATUS_TO_VERDICT[14] == Verdict.MEMORY_LIMIT_EXCEEDED


def test_b64_roundtrip():
    s = "print('hello, 世界')"
    encoded = _b64(s)
    decoded = _b64d(encoded)
    assert decoded == s


def test_b64d_handles_none():
    assert _b64d(None) is None


def test_map_to_result_pulls_status_and_decodes():
    client = Judge0Client.__new__(Judge0Client)  # bypass __init__ (avoid settings)
    item = {
        "token": "abc",
        "status": {"id": 3, "description": "Accepted"},
        "stdout": _b64("1\n"),
        "stderr": None,
        "compile_output": None,
        "time": "0.012",
        "memory": 1024,
    }
    result = client._map_to_result(item)
    assert result.is_accepted()
    assert result.stdout == "1\n"
    assert result.stderr is None
    assert result.time_ms == 12
    assert result.memory_kb == 1024
    # Opaque test: domain doesn't read raw status id
    assert result.is_terminal()


def test_map_to_result_compile_error_uses_compile_output_as_stderr():
    client = Judge0Client.__new__(Judge0Client)
    item = {
        "token": "abc",
        "status": {"id": 6, "description": "Compilation Error"},
        "stdout": None,
        "stderr": None,
        "compile_output": _b64("syntax error: unexpected EOF"),
        "time": None,
        "memory": None,
    }
    result = client._map_to_result(item)
    assert result.is_compile_error()
    assert result.stderr == "syntax error: unexpected EOF"
