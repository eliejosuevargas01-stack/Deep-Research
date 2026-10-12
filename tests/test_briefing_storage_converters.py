"""T020: conversores domain<->storage puros + mapeamento ORM."""

import unittest
from datetime import datetime, timezone
from uuid import UUID

from app.briefing.domain import (
    BriefingPoint,
    BriefingStatus,
    approve_briefing,
    complete_briefing,
    fail_briefing,
    new_briefing,
)
from app.briefing.storage import (
    briefing_to_record,
    briefing_to_version_dict,
    json_to_points,
    points_to_json,
    record_to_briefing,
)
from app.models.domain_models import BriefingRecord, BriefingVersion


def _pts(n=3):
    return tuple(BriefingPoint(f"t{i}", f"d{i}") for i in range(n))


class TestPointsConverters(unittest.TestCase):
    def test_round_trip(self):
        pts = _pts(5)
        self.assertEqual(json_to_points(points_to_json(pts)), pts)

    def test_tuple_isolation(self):
        pts = _pts(3)
        blob = points_to_json(pts)
        blob.append({"title": "x", "description": "y"})
        blob[0]["title"] = "mut"
        self.assertEqual(len(json_to_points(blob[:-1])), 3)
        self.assertEqual(pts[0].title, "t0")
        out = json_to_points(points_to_json(pts))
        self.assertIsInstance(out, tuple)
        self.assertTrue(all(isinstance(p, BriefingPoint) for p in out))


class TestBriefingConverters(unittest.TestCase):
    def test_round_trip_all_states(self):
        now = datetime.now(timezone.utc)
        cases = [
            new_briefing("tema valido aqui"),
            complete_briefing(new_briefing("tema valido aqui"), _pts(3)),
            fail_briefing(new_briefing("tema valido aqui"), "boom"),
            approve_briefing(complete_briefing(new_briefing("tema valido aqui"), _pts(4)), now),
        ]
        for b in cases:
            with self.subTest(status=b.status):
                rec = briefing_to_record(b)
                self.assertIsInstance(rec.id, UUID)
                self.assertEqual(rec.id, b.id)
                back = record_to_briefing(rec)
                self.assertEqual(back, b)
                self.assertIsInstance(back.points, tuple)
                self.assertIsInstance(back.status, BriefingStatus)

    def test_timestamps(self):
        now = datetime.now(timezone.utc)
        b = approve_briefing(complete_briefing(new_briefing("tema valido aqui"), _pts(3)), now)
        rec = briefing_to_record(b)
        self.assertEqual(rec.approved_at, now)
        gen = new_briefing("outro tema valido")
        self.assertIsNone(briefing_to_record(gen).approved_at)
        self.assertIsNone(record_to_briefing(briefing_to_record(gen)).approved_at)

    def test_version_dict(self):
        b = complete_briefing(new_briefing("tema valido aqui"), _pts(3))
        d = briefing_to_version_dict(b)
        self.assertEqual(
            (d["briefing_id"], d["version"], d["status"]), (b.id, b.version, b.status.value)
        )
        self.assertEqual(d["points_json"], points_to_json(b.points))
        self.assertEqual((d["error"], d["approved_at"]), (b.error, b.approved_at))


class TestOrmMapping(unittest.TestCase):
    def test_tables_and_columns(self):
        self.assertEqual(BriefingRecord.__tablename__, "briefings")
        self.assertEqual(BriefingVersion.__tablename__, "briefing_versions")
        cols = BriefingRecord.__table__.c
        self.assertEqual(cols["theme"].type.length, 300)
        self.assertEqual(cols["status"].type.length, 20)
        for c in ("id", "theme", "status", "version", "points_json", "error",
                  "approved_at", "created_at", "updated_at"):
            self.assertIn(c, cols)
        self.assertFalse(cols["theme"].nullable)
        self.assertFalse(cols["status"].nullable)

    def test_version_constraints_and_isolation(self):
        names = [c.name for c in BriefingVersion.__table__.constraints]
        self.assertIn("uq_briefing_version", names)
        idx = [i.name for i in BriefingVersion.__table__.indexes]
        self.assertTrue(any("briefing_id" in (i or "") and "version" in (i or "") for i in idx))
        fk = list(BriefingVersion.__table__.c["briefing_id"].foreign_keys)[0]
        self.assertEqual(fk.column.table.name, "briefings")
        self.assertEqual(fk.ondelete, "CASCADE")
        for tbl in (BriefingRecord.__table__, BriefingVersion.__table__):
            for col in tbl.c:
                for f in col.foreign_keys:
                    self.assertNotIn(f.column.table.name, ("research", "research_points"))


if __name__ == "__main__":
    unittest.main()
