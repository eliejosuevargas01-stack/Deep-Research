"""RED tests for round-based storage contract (T008/T011).

Contract source: data-delta.md §§2-3 and actions T008/T011.

These tests target the *proposed* storage contract that does NOT yet exist
in app/investigation/storage.py. They are expected to fail at import/collection
time (missing symbols) — true RED.
"""
import pytest
from uuid import uuid4

from app.investigation.prompts import PERSONA_NAMES
from app.models.domain_models import Research, ResearchPoint


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def seeded_research(db_session):
    """Seed a research + 1 point in SCRAPER_PENDING."""
    rid = uuid4()
    pid = uuid4()
    research = Research(id=rid, theme="test theme", status="SCRAPER")
    db_session.add(research)
    point = ResearchPoint(
        id=pid, research_id=rid, position=1, title="t", description="d",
        status="SCRAPER_PENDING", attempt_count=0,
    )
    db_session.add(point)
    await db_session.commit()
    return rid, pid


# ---------------------------------------------------------------------------
# T008 ACCEPTANCE 1: round is mandatory for new save_step_result
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_save_step_result_rejects_round_none(db_session, seeded_research):
    rid, pid = seeded_research
    from app.investigation.storage import save_step_result
    with pytest.raises((ValueError, TypeError, AssertionError)):
        await save_step_result(
            db_session, rid, pid, "title", "historian",
            "result", [], [], True, round=None,
        )


@pytest.mark.anyio
async def test_save_step_result_rejects_round_zero(db_session, seeded_research):
    rid, pid = seeded_research
    from app.investigation.storage import save_step_result
    with pytest.raises((ValueError, TypeError, AssertionError)):
        await save_step_result(
            db_session, rid, pid, "title", "historian",
            "result", [], [], True, round=0,
        )


@pytest.mark.anyio
async def test_save_step_result_rejects_round_negative(db_session, seeded_research):
    rid, pid = seeded_research
    from app.investigation.storage import save_step_result
    with pytest.raises((ValueError, TypeError, AssertionError)):
        await save_step_result(
            db_session, rid, pid, "title", "historian",
            "result", [], [], True, round=-1,
        )


@pytest.mark.anyio
async def test_save_step_result_rejects_round_bool(db_session, seeded_research):
    rid, pid = seeded_research
    from app.investigation.storage import save_step_result
    with pytest.raises((ValueError, TypeError, AssertionError)):
        await save_step_result(
            db_session, rid, pid, "title", "historian",
            "result", [], [], True, round=True,
        )


@pytest.mark.anyio
async def test_save_step_result_accepts_round_one(db_session, seeded_research):
    """Positive round=1 succeeds and persists round."""
    rid, pid = seeded_research
    from app.investigation.storage import save_step_result
    res = await save_step_result(
        db_session, rid, pid, "title", "historian",
        "result", [], [], True, round=1,
    )
    assert res.round == 1


# ---------------------------------------------------------------------------
# T008 ACCEPTANCE 1b: research/point association validation
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_save_step_result_rejects_mismatched_research_id(db_session):
    """step_id must belong to research_id; divergent research -> reject."""
    from app.investigation.storage import save_step_result
    rid = uuid4()
    other_rid = uuid4()
    point = ResearchPoint(
        id=uuid4(), research_id=rid, position=1, title="t", description="d",
        status="SCRAPER_PENDING", attempt_count=0,
    )
    db_session.add(point)
    await db_session.commit()

    from app.models.domain_models import Research as ResearchModel
    db_session.add(ResearchModel(id=other_rid, theme="other", status="SCRAPER"))
    await db_session.commit()

    with pytest.raises((ValueError, AssertionError)):
        await save_step_result(
            db_session, other_rid, point.id, "title", "historian",
            "result", [], [], True, round=1,
        )


# ---------------------------------------------------------------------------
# T008 ACCEPTANCE 3: historical round=None records are readable but
#   ineligible for the active-round 4-persona barrier.
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_historical_null_round_readable_but_not_in_barrier(db_session, seeded_research):
    """get_step_results returns historical round=None; merge barrier skips them."""
    rid, pid = seeded_research
    from app.investigation.storage import save_step_result, get_step_results
    # Seed a historical legacy row directly (simulate NULL round).
    from app.models.domain_models import ResearchStepResult
    legacy = ResearchStepResult(
        research_id=rid, step_id=pid, step_title="old", result="old",
        used_urls=[], read_urls=[], worker="historian",
        status="AUDIT_PENDING",
    )
    db_session.add(legacy)
    await db_session.commit()

    rows = await get_step_results(db_session, rid)
    legacy_rows = [r for r in rows if r.round is None]
    assert len(legacy_rows) >= 1

    from app.investigation.storage import check_merge_barrier
    barrier = await check_merge_barrier(db_session, rid, pid, round=1)
    assert barrier is False  # historical NULL excluded from active barrier


# ---------------------------------------------------------------------------
# T008 ACCEPTANCE 4: merge barrier requires 4 valid same-round personas
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_barrier_requires_four_personas_same_round(db_session, seeded_research):
    rid, pid = seeded_research
    from app.investigation.storage import save_step_result, check_merge_barrier
    for persona in PERSONA_NAMES:
        await save_step_result(
            db_session, rid, pid, "title", persona, "result", [], [], True, round=1,
        )
    barrier = await check_merge_barrier(db_session, rid, pid, round=1)
    assert barrier is True


@pytest.mark.anyio
async def test_barrier_rejects_three_of_four(db_session, seeded_research):
    rid, pid = seeded_research
    from app.investigation.storage import save_step_result, check_merge_barrier
    for persona in PERSONA_NAMES[:3]:
        await save_step_result(
            db_session, rid, pid, "title", persona, "result", [], [], True, round=1,
        )
    barrier = await check_merge_barrier(db_session, rid, pid, round=1)
    assert barrier is False


@pytest.mark.anyio
async def test_barrier_rejects_different_rounds(db_session, seeded_research):
    rid, pid = seeded_research
    from app.investigation.storage import save_step_result, check_merge_barrier
    for persona in PERSONA_NAMES[:3]:
        await save_step_result(
            db_session, rid, pid, "title", persona, "result", [], [], True, round=1,
        )
    await save_step_result(
        db_session, rid, pid, "title", "futurist", "result", [], [], True, round=2,
    )
    barrier = await check_merge_barrier(db_session, rid, pid, round=1)
    assert barrier is False


# ---------------------------------------------------------------------------
# T008 ACCEPTANCE 5: save_investigation_merge writes investigation_merges
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_save_investigation_merge_writes_and_unique(db_session, seeded_research):
    rid, pid = seeded_research
    from app.investigation.storage import save_step_result, save_investigation_merge, check_merge_barrier
    for persona in PERSONA_NAMES:
        await save_step_result(
            db_session, rid, pid, "title", persona, "result", [], [], True, round=1,
        )
    assert await check_merge_barrier(db_session, rid, pid, round=1)

    content = {"historian": {"analysis": "a"}, "skeptic": {"analysis": "b"},
               "pragmatist": {"analysis": "c"}, "futurist": {"analysis": "d"}}
    m1 = await save_investigation_merge(db_session, rid, pid, round=1, content=content)
    assert m1 is not None

    # Second identical merge -> unique violation / conflict
    with pytest.raises(Exception):
        await save_investigation_merge(db_session, rid, pid, round=1, content=content)
