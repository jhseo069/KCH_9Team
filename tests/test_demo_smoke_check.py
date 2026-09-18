# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.demo_smoke_check import summarize


def test_전부_통과하면_True():
    ok, text = summarize([
        {"name": "판정 API", "ok": True, "detail": "1.2초"},
        {"name": "필지 조회", "ok": True, "detail": "1건"},
    ])
    assert ok is True
    assert "판정 API" in text


def test_하나라도_실패하면_False():
    ok, text = summarize([
        {"name": "판정 API", "ok": True, "detail": "1.2초"},
        {"name": "필지 조회", "ok": False, "detail": "0건"},
    ])
    assert ok is False
    assert "실패" in text


def test_빈_결과는_실패로_본다():
    # 아무것도 확인하지 못한 것을 "이상 없음"으로 보고하면 시연 직전에 위험하다
    ok, _ = summarize([])
    assert ok is False
