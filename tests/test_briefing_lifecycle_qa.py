"""QA complementar T007: domínio real, sem persistência ou mocks."""
import unittest
from collections import UserDict
from dataclasses import asdict
from datetime import datetime, timezone
from types import MappingProxyType
from uuid import UUID

from app.briefing import domain as d


STAMP = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


def points(count):
    return [{"title": f" title {i} ", "description": f" description {i} "}
            for i in range(count)]


class BriefingLifecycleQATests(unittest.TestCase):
    def test_edit_approve_all_counts_keep_full_history_and_exact_versions(self):
        for count in range(3, 8):
            with self.subTest(count=count):
                created = d.new_briefing("  Tema QA  ")
                self.assertIsInstance(created.id, UUID)
                self.assertEqual(created.id.version, 4)
                self.assertEqual(asdict(created), dict(
                    id=created.id, theme="Tema QA", status=d.BriefingStatus.GENERATING,
                    points=(), version=1, approved_at=None, error=None))
                history = [created]
                saved = [asdict(created)]
                draft = d.complete_briefing(created, points(3))
                history.append(draft)
                saved.append(asdict(draft))
                raw = list(reversed(points(count)))
                edited = d.edit_briefing(draft, raw)
                history.append(edited)
                saved.append(asdict(edited))
                approved = d.approve_briefing(edited, STAMP)
                history.append(approved)
                saved.append(asdict(approved))
                read = d.read_approved(approved)
                with self.assertRaisesRegex(d.InvalidTransition, "^Briefing aprovado não pode ser reaberto$"):
                    d.reopen_briefing(approved)
                history.append(read)
                self.assertEqual([s.version for s in history], [1, 2, 3, 4, 4])
                expected_points = tuple(dict(p) for p in raw)
                for snapshot, state, version, stamp in (
                    (edited, d.BriefingStatus.DRAFT, 3, None),
                    (approved, d.BriefingStatus.APPROVED, 4, STAMP),
                    (read, d.BriefingStatus.APPROVED, 4, STAMP),
                ):
                    self.assertEqual(asdict(snapshot), dict(
                        id=created.id, theme="Tema QA", status=state,
                        points=expected_points, version=version, approved_at=stamp, error=None))
                self.assertIsNot(read, approved)
                self.assertEqual([asdict(s) for s in history[:4]], saved)
                failed = d.fail_briefing(created, " safe failure ")
                self.assertEqual(asdict(failed), dict(
                    id=created.id, theme="Tema QA", status=d.BriefingStatus.FAILED,
                    points=(), version=2, approved_at=None, error=" safe failure "))
                self.assertEqual(asdict(created), saved[0])

    def test_invalid_timestamp_and_failure_message_preserve_entire_snapshot(self):
        created = d.new_briefing("Tema QA")
        draft = d.complete_briefing(created, points(3))
        cases = (
            (d.approve_briefing, draft, (None, 0, True, [], {}, "", " \t\n"),
             "Instante de aprovação inválido"),
            (d.fail_briefing, created, (None, 0, True, [], {}, "", " \t\n"),
             "Mensagem de falha inválida"),
        )
        for operation, snapshot, values, message in cases:
            original = asdict(snapshot)
            for value in values:
                with self.subTest(operation=operation.__name__, value=value):
                    with self.assertRaises(d.InvalidContent) as caught:
                        operation(snapshot, value)
                    self.assertEqual(str(caught.exception), message)
                    self.assertEqual(asdict(snapshot), original)
        # Caller supplies datetime; no timezone policy added by this gate.
        naive = datetime(2026, 10, 11)
        self.assertEqual(d.approve_briefing(draft, naive).approved_at, naive)
        self.assertEqual(d.approve_briefing(draft, STAMP).approved_at, STAMP)

    def test_point_boundary_rejections_and_mixed_mapping_copy_on_both_operations(self):
        created = d.new_briefing("Tema QA")
        draft = d.complete_briefing(created, points(3))
        for operation, snapshot in ((d.complete_briefing, created), (d.edit_briefing, draft)):
            original = asdict(snapshot)
            for value in ("points", b"points", bytearray(b"points"), None, 0,
                          {}, iter(points(3)), set()):
                with self.subTest(operation=operation.__name__, input=repr(value)):
                    with self.assertRaises(d.InvalidContent) as caught:
                        operation(snapshot, value)
                    self.assertEqual(str(caught.exception), "Lista de pontos inválida")
                    self.assertEqual(asdict(snapshot), original)
            for value in (None, 0, True, "point", [], object()):
                with self.subTest(operation=operation.__name__, item=repr(value)):
                    raw = points(3)
                    raw[1] = value
                    with self.assertRaises(d.InvalidContent) as caught:
                        operation(snapshot, raw)
                    self.assertEqual(str(caught.exception), "Ponto inválido")
                    self.assertEqual(asdict(snapshot), original)
            raw = points(3)
            user = UserDict(raw[1])
            backing = dict(raw[2])
            point = d.BriefingPoint(**raw[0])
            mixed = (point, user, MappingProxyType(backing))
            result = operation(snapshot, mixed)
            expected = tuple(dict(p) for p in raw)
            self.assertEqual(asdict(result)["points"], expected)
            self.assertIsNot(result.points[0], point)
            user["title"] = "mutated"
            backing["description"] = "mutated"
            raw.clear()
            self.assertEqual(asdict(result)["points"], expected)
            self.assertEqual(asdict(snapshot), original)


if __name__ == "__main__":
    unittest.main()
