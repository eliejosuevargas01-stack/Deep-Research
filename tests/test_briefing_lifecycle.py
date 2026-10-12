"""Ciclo de vida local do briefing; persistência durável pertence a T011."""
import dataclasses
import unittest
from collections import UserDict
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from app.briefing import domain

APPROVED_AT = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)


def require_op(name: str) -> Any:
    op = getattr(domain, name, None)
    assert callable(op), f"missing domain.{name}"
    return op


def points(count: int, prefix: str = "focus") -> list:
    return [{"title": f"{prefix} title {i}", "description": f"{prefix} description {i}"} for i in range(count)]


def fresh_draft(count: int = 3) -> Any:
    return require_op("complete_briefing")(require_op("new_briefing")("Climate research"), points(count))


def fresh_approved(count: int = 3) -> Any:
    return require_op("approve_briefing")(fresh_draft(count), APPROVED_AT)


class BriefingLifecycleTests(unittest.TestCase):
    def test_full_cycle_create_complete_edit_approve_reopen_and_read(self):
        created = require_op("new_briefing")("Climate research")
        draft = require_op("complete_briefing")(created, points(3))
        self.assertEqual(draft.status, domain.BriefingStatus.DRAFT)
        edited = require_op("edit_briefing")(draft, points(4, "edited"))
        approved = require_op("approve_briefing")(edited, APPROVED_AT)
        self.assertEqual(approved.status, domain.BriefingStatus.APPROVED)
        self.assertEqual(approved.approved_at, APPROVED_AT)
        with self.assertRaises(domain.InvalidTransition):
            require_op("edit_briefing")(approved, points(3))
        reopened = require_op("reopen_briefing")(approved)
        self.assertEqual(reopened.status, domain.BriefingStatus.DRAFT)
        self.assertIsNone(reopened.approved_at)
        reedited = require_op("edit_briefing")(reopened, points(5, "reopened"))
        self.assertEqual(len(reedited.points), 5)
        reread = require_op("read_approved")(require_op("approve_briefing")(reedited, APPROVED_AT))
        self.assertEqual(len(reread.points), 5)
        for snapshot in (created, draft, edited, approved, reopened, reedited):
            self.assertEqual(snapshot.id, created.id)

    def test_generation_accepts_counts_three_to_seven(self):
        for count in (3, 4, 5, 6, 7):
            with self.subTest(count=count):
                draft = require_op("complete_briefing")(
                    require_op("new_briefing")("Climate research"), points(count)
                )
                self.assertEqual(draft.status, domain.BriefingStatus.DRAFT)
                self.assertEqual(len(draft.points), count)
                self.assertEqual(draft.version, 2)

    def test_generation_rejects_counts_zero_two_eight(self):
        for count in (0, 2, 8):
            with self.subTest(count=count):
                created = require_op("new_briefing")("Climate research")
                with self.assertRaises(domain.InvalidContent):
                    require_op("complete_briefing")(created, points(count))
                self.assertEqual(created.status, domain.BriefingStatus.GENERATING)
                self.assertEqual(created.version, 1)
                self.assertEqual(created.points, ())

    def test_edit_rejects_counts_outside_range_and_preserves_snapshot(self):
        for count in (0, 2, 8):
            with self.subTest(count=count):
                draft = fresh_draft(3)
                with self.assertRaises(domain.InvalidContent):
                    require_op("edit_briefing")(draft, points(count))
                self.assertEqual(len(draft.points), 3)
                self.assertEqual(draft.version, 2)

    def test_approve_rejects_invalid_content_and_preserves_snapshot(self):
        draft = fresh_draft(3)
        for count in (0, 2, 8):
            with self.subTest(count=count):
                invalid = dataclasses.replace(draft, points=tuple(points(count)))
                with self.assertRaises(domain.InvalidContent):
                    require_op("approve_briefing")(invalid, APPROVED_AT)
        for field in ("title", "description"):
            for value in ("", "  \t\n", None, 0, True, [], {}):
                with self.subTest(field=field, value=value):
                    bad = points(3)
                    bad[0][field] = value
                    invalid = dataclasses.replace(draft, points=tuple(bad))
                    with self.assertRaises(domain.InvalidContent):
                        require_op("approve_briefing")(invalid, APPROVED_AT)
        self.assertEqual(draft.status, domain.BriefingStatus.DRAFT)
        self.assertEqual(len(draft.points), 3)
        self.assertEqual(draft.version, 2)

    def test_titles_and_descriptions_must_be_non_empty_strings(self):
        cases: list[Any] = ["", "  \t\n", None, 0, True, [], {}]
        for field in ("title", "description"):
            for value in cases:
                with self.subTest(field=field, value=value):
                    bad = points(3)
                    bad[0][field] = value
                    with self.assertRaises(domain.InvalidContent):
                        require_op("complete_briefing")(require_op("new_briefing")("Climate research"), bad)
            with self.subTest(missing=field):
                incomplete = [{k: "ok" for k in ("title", "description") if k != field} for _ in range(3)]
                with self.assertRaises(domain.InvalidContent):
                    require_op("edit_briefing")(fresh_draft(3), incomplete)

    def test_inputs_accept_list_tuple_and_non_dict_mappings(self):
        point_cls = require_op("BriefingPoint")
        raw = points(3)
        proxy = MappingProxyType({"title": "proxy title", "description": "proxy description"})
        user = UserDict({"title": "userdict title", "description": "userdict description"})
        mixed = [point_cls(title="kept title", description="kept description"), proxy, user]
        expected = {
            "list": ["focus title 0", "focus title 1", "focus title 2"],
            "tuple": ["focus title 0", "focus title 1", "focus title 2"],
            "mixed": ["kept title", "proxy title", "userdict title"],
        }
        for label, value in (("list", [dict(p) for p in raw]), ("tuple", tuple(dict(p) for p in raw)), ("mixed", mixed)):
            with self.subTest(kind=label):
                draft = require_op("complete_briefing")(require_op("new_briefing")("Climate research"), value)
                self.assertEqual([p.title for p in draft.points], expected[label])
                self.assertEqual(draft.points[0].description, "focus description 0" if label != "mixed" else "kept description")
        ordered = tuple(dict(p) for p in points(3, "order"))
        edited = require_op("edit_briefing")(fresh_draft(3), ordered)
        self.assertEqual([p.title for p in edited.points], [p["title"] for p in ordered])
        for bad in ("points", b"points", 0, None, {}):
            with self.subTest(rejected=repr(bad)):
                with self.assertRaises(domain.InvalidContent):
                    require_op("complete_briefing")(require_op("new_briefing")("Climate research"), bad)
        for bad_item in (None, 0, "point", {}):
            with self.subTest(item=repr(bad_item)):
                with self.assertRaises(domain.InvalidContent):
                    require_op("complete_briefing")(require_op("new_briefing")("Climate research"), [bad_item] * 3)

    def test_mutating_inputs_and_snapshots_does_not_contaminate(self):
        raw = points(3)
        draft = require_op("complete_briefing")(require_op("new_briefing")("Climate research"), raw)
        raw.append({"title": "late", "description": "late"})
        raw[0]["title"] = "mutated"
        self.assertEqual(len(draft.points), 3)
        self.assertEqual(draft.points[0].title, "focus title 0")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            draft.points[0].title = "mutated"  # type: ignore[misc]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            draft.version = 99  # type: ignore[misc]

    def test_generate_and_fail_only_from_generating_and_failed_is_terminal(self):
        created = require_op("new_briefing")("Climate research")
        failed = require_op("fail_briefing")(created, "search unavailable")
        self.assertEqual(failed.status, domain.BriefingStatus.FAILED)
        self.assertEqual(failed.points, ())
        self.assertEqual(failed.error, "search unavailable")
        self.assertEqual(failed.version, 2)
        for name in ("complete_briefing", "fail_briefing", "edit_briefing", "approve_briefing", "reopen_briefing"):
            op = require_op(name)
            with self.subTest(op=name):
                if name == "reopen_briefing":
                    with self.assertRaises(domain.InvalidTransition):
                        op(failed)
                else:
                    arg: Any = points(3) if name in ("complete_briefing", "edit_briefing") else ("boom" if name == "fail_briefing" else APPROVED_AT)
                    with self.assertRaises(domain.InvalidTransition):
                        op(failed, arg)
        with self.assertRaises(domain.InvalidTransition):
            require_op("complete_briefing")(fresh_draft(3), points(3))
        with self.assertRaises(domain.InvalidTransition):
            require_op("fail_briefing")(fresh_draft(3), "late failure")
        with self.assertRaises(domain.InvalidTransition):
            require_op("read_approved")(failed)

    def test_edit_and_approve_only_from_draft_reopen_only_from_approved(self):
        draft = fresh_draft(3)
        approved = require_op("approve_briefing")(draft, APPROVED_AT)
        with self.assertRaises(domain.InvalidTransition):
            require_op("edit_briefing")(approved, points(3))
        with self.assertRaises(domain.InvalidTransition):
            require_op("approve_briefing")(approved, APPROVED_AT)
        with self.assertRaises(domain.InvalidTransition):
            require_op("reopen_briefing")(draft)
        with self.assertRaises(domain.InvalidTransition):
            require_op("reopen_briefing")(require_op("new_briefing")("Climate research"))
        self.assertEqual(approved.status, domain.BriefingStatus.APPROVED)
        self.assertEqual(draft.version, 2)

    def test_success_keeps_id_increments_once_and_allows_many_edits(self):
        created = require_op("new_briefing")("Climate research")
        current = require_op("complete_briefing")(created, points(3))
        for _ in range(11):
            current = require_op("edit_briefing")(current, points(4, "repeat"))
        self.assertEqual(current.id, created.id)
        self.assertEqual(current.version, 2 + 11)
        before = current.version
        with self.assertRaises(domain.InvalidContent):
            require_op("edit_briefing")(current, points(8))
        self.assertEqual(current.version, before)

    def test_read_approved_returns_isolated_equivalent_without_version_bump(self):
        approved = fresh_approved(4)
        first = require_op("read_approved")(approved)
        second = require_op("read_approved")(approved)
        self.assertEqual(first, second)
        self.assertEqual(first.approved_at, APPROVED_AT)
        self.assertEqual(first.version, approved.version)
        self.assertEqual(first.points, approved.points)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            first.version = 99  # type: ignore[misc]
        for snapshot in (require_op("new_briefing")("fresh theme"), fresh_draft(3)):
            with self.subTest(status=snapshot.status):
                with self.assertRaises(domain.InvalidTransition):
                    require_op("read_approved")(snapshot)


if __name__ == "__main__":
    unittest.main()
