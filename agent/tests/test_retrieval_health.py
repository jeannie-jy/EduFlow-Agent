from __future__ import annotations

import asyncio

from scripts import retrieval_health


def test_retrieval_health_requires_candidates(monkeypatch, capsys):
    async def no_candidates(_query):
        return {"status": "no_evidence", "candidate_count": 0, "selected_count": 0}

    monkeypatch.setattr(retrieval_health, "retrieve_knowledge_context", no_candidates)
    assert asyncio.run(retrieval_health.main()) == 1
    assert '"candidate_count": 0' in capsys.readouterr().out


def test_retrieval_health_accepts_seeded_candidates(monkeypatch, capsys):
    async def seeded(_query):
        return {"status": "ok", "candidate_count": 1, "selected_count": 1}

    monkeypatch.setattr(retrieval_health, "retrieve_knowledge_context", seeded)
    assert asyncio.run(retrieval_health.main()) == 0
    assert '"candidate_count": 1' in capsys.readouterr().out
