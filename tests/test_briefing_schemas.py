import unittest
from datetime import datetime
from uuid import UUID

from pydantic import ValidationError

from app.briefing.domain import BriefingStatus
from app.briefing.schemas import ApprovedBriefingResponse, BriefingResponse, BriefingVersionResponse


class BriefingResponseSchemaTests(unittest.TestCase):
    def response(self, status, points=None):
        return BriefingResponse(
            research_id=UUID(int=1), theme="tema", status=status, points=points or []
        )

    def version_response(self, status, points=None):
        return BriefingVersionResponse(
            version=1, status=status, points=points or [],
            created_at=datetime(2026, 1, 1),
        )

    def approved(self, points):
        return ApprovedBriefingResponse(research_id=UUID(int=1), theme="tema", points=points)

    def valid_points(self, count):
        return [{"title": f"title {n}", "description": f"description {n}"} for n in range(count)]

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.response("banana")

    def test_draft_and_approved_require_three_to_seven_points(self):
        for status in ("draft", "approved"):
            for count in (0, 2, 8):
                with self.subTest(status=status, count=count):
                    with self.assertRaises(ValidationError):
                        self.response(status, self.valid_points(count))
            for count in (3, 4, 5, 6, 7):
                with self.subTest(status=status, count=count):
                    self.assertEqual(len(self.response(status, self.valid_points(count)).points), count)

    def test_approved_response_requires_three_to_seven_points(self):
        for count in (0, 2, 8):
            with self.subTest(count=count), self.assertRaises(ValidationError):
                self.approved(self.valid_points(count))
        for count in (3, 4, 5, 6, 7):
            with self.subTest(count=count):
                self.assertEqual(len(self.approved(self.valid_points(count)).points), count)

    def test_generating_and_failed_allow_empty_points(self):
        for status in ("generating", "failed"):
            with self.subTest(status=status):
                self.assertEqual(self.response(status).points, [])

    def test_states_serialize_and_json_schema_lists_enum(self):
        expected = ["generating", "draft", "failed", "approved"]
        for status in BriefingStatus:
            with self.subTest(status=status):
                points = self.valid_points(3) if status in (BriefingStatus.DRAFT, BriefingStatus.APPROVED) else []
                response = self.response(status, points)
                self.assertEqual(response.model_dump(mode="json")["status"], status.value)
        schema = BriefingResponse.model_json_schema()
        status_schema = schema["properties"]["status"]
        if "$ref" in status_schema:
            ref = status_schema["$ref"].split("/")[-1]
            enum = schema["$defs"][ref]["enum"]
        else:
            enum = status_schema.get("enum")
        self.assertEqual(enum, expected)

    def test_empty_titles_descriptions_and_extra_fields_are_rejected(self):
        for field in ("title", "description"):
            point = {"title": "ok", "description": "ok"}
            point[field] = ""
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.response("draft", [point] * 3)
        with self.assertRaises(ValidationError):
            self.response("draft", [dict(self.valid_points(1)[0], extra="x")] * 3)

    # T035 — BriefingResponse new fields: version, error, approved_at
    def test_briefing_response_version_default_and_serialization(self):
        resp = BriefingResponse(research_id=UUID(int=1), theme="tema", status=BriefingStatus.GENERATING)
        self.assertEqual(resp.version, 1)
        dumped = resp.model_dump(mode="json")
        self.assertEqual(dumped["version"], 1)
        self.assertIn("version", BriefingResponse.model_json_schema()["properties"])

    def test_briefing_response_version_invalid_zero_negative_rejected(self):
        for bad in (0, -1):
            with self.subTest(version=bad), self.assertRaises(ValidationError):
                BriefingResponse(research_id=UUID(int=1), theme="tema", status=BriefingStatus.GENERATING, version=bad)

    def test_briefing_response_error_default_none_and_optional(self):
        resp = BriefingResponse(research_id=UUID(int=1), theme="tema", status=BriefingStatus.GENERATING)
        self.assertIsNone(resp.error)
        resp2 = BriefingResponse(research_id=UUID(int=1), theme="tema", status=BriefingStatus.FAILED, error="falha")
        self.assertEqual(resp2.error, "falha")

    def test_briefing_response_approved_at_default_none_and_optional(self):
        resp = BriefingResponse(research_id=UUID(int=1), theme="tema", status=BriefingStatus.GENERATING)
        self.assertIsNone(resp.approved_at)
        dt = datetime(2026, 1, 1, 12, 0, 0)
        resp2 = BriefingResponse(research_id=UUID(int=1), theme="tema", status=BriefingStatus.APPROVED, approved_at=dt, points=self.valid_points(3))
        self.assertEqual(resp2.approved_at, dt)

    # T035 — BriefingVersionResponse schema
    def test_briefing_version_response_required_fields(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        resp = BriefingVersionResponse(
            version=2,
            status=BriefingStatus.DRAFT,
            points=self.valid_points(3),
            error=None,
            approved_at=None,
            created_at=dt,
        )
        self.assertEqual(resp.version, 2)
        self.assertEqual(resp.status, BriefingStatus.DRAFT)
        self.assertEqual(len(resp.points), 3)
        self.assertIsNone(resp.error)
        self.assertIsNone(resp.approved_at)
        self.assertEqual(resp.created_at, dt)

    def test_briefing_version_response_version_missing_rejected(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        with self.assertRaises(ValidationError):
            BriefingVersionResponse(status=BriefingStatus.DRAFT, points=self.valid_points(3), created_at=dt)

    def test_briefing_version_response_created_at_missing_rejected(self):
        with self.assertRaises(ValidationError):
            BriefingVersionResponse(version=1, status=BriefingStatus.DRAFT, points=self.valid_points(3))

    def test_briefing_version_response_version_zero_negative_rejected(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        for bad in (0, -1):
            with self.subTest(version=bad), self.assertRaises(ValidationError):
                BriefingVersionResponse(version=bad, status=BriefingStatus.DRAFT, points=self.valid_points(3), created_at=dt)

    def test_briefing_version_response_unknown_status_rejected(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        with self.assertRaises(ValidationError):
            BriefingVersionResponse(version=1, status="banana", points=self.valid_points(3), created_at=dt)

    def test_briefing_version_response_draft_approved_accept_valid_cardinality(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        for status in (BriefingStatus.DRAFT, BriefingStatus.APPROVED):
            for count in (3, 7):
                with self.subTest(status=status, count=count):
                    resp = BriefingVersionResponse(version=1, status=status, points=self.valid_points(count), created_at=dt)
                    self.assertEqual(len(resp.points), count)

    def test_briefing_version_response_draft_approved_reject_invalid_cardinality(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        for status in (BriefingStatus.DRAFT, BriefingStatus.APPROVED):
            for count in (0, 2, 8):
                with self.subTest(status=status, count=count), self.assertRaises(ValidationError):
                    BriefingVersionResponse(version=1, status=status, points=self.valid_points(count), created_at=dt)

    def test_briefing_version_response_failed_generating_allow_empty_points(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        for status in (BriefingStatus.FAILED, BriefingStatus.GENERATING):
            with self.subTest(status=status):
                resp = BriefingVersionResponse(version=1, status=status, points=[], created_at=dt)
                self.assertEqual(resp.points, [])

    def test_briefing_version_response_extra_fields_rejected(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        with self.assertRaises(ValidationError):
            BriefingVersionResponse(version=1, status=BriefingStatus.DRAFT, points=self.valid_points(3), created_at=dt, extra="x")

    def test_briefing_version_response_no_id_theme_briefing_id_prompt_search_updated_at(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        schema = BriefingVersionResponse.model_json_schema()
        props = schema.get("properties", {})
        forbidden = {"id", "theme", "briefing_id", "prompt", "search", "updated_at"}
        for f in forbidden:
            self.assertNotIn(f, props, f"BriefingVersionResponse should not have field {f}")

    # T035 — Backward compatibility: existing BriefingResponse construction preserved
    def test_briefing_response_backward_construction_no_new_required(self):
        # Old code constructing without version/error/approved_at must still work
        resp = BriefingResponse(research_id=UUID(int=1), theme="tema", status=BriefingStatus.DRAFT, points=self.valid_points(3))
        self.assertEqual(resp.version, 1)
        self.assertIsNone(resp.error)
        self.assertIsNone(resp.approved_at)

    # T035 — Mutable default points not aliased
    def test_briefing_response_points_default_mutable_isolation(self):
        r1 = BriefingResponse(research_id=UUID(int=1), theme="tema", status=BriefingStatus.GENERATING)
        r2 = BriefingResponse(research_id=UUID(int=2), theme="tema", status=BriefingStatus.GENERATING)
        r1.points.append({"title": "t", "description": "d"})
        self.assertEqual(r2.points, [])

    def test_briefing_version_response_points_default_mutable_isolation(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        r1 = BriefingVersionResponse(version=1, status=BriefingStatus.GENERATING, created_at=dt)
        r2 = BriefingVersionResponse(version=1, status=BriefingStatus.GENERATING, created_at=dt)
        r1.points.append({"title": "t", "description": "d"})
        self.assertEqual(r2.points, [])

    def test_briefing_response_json_dump_exact_payload_and_utc_datetime(self):
        from datetime import timezone

        approved_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        resp = BriefingResponse(
            research_id=UUID(int=1), theme="tema", status=BriefingStatus.DRAFT,
            points=self.valid_points(3), version=2, error=None, approved_at=approved_at,
        )
        self.assertEqual(resp.model_dump(mode="json"), {
            "research_id": "00000000-0000-0000-0000-000000000001",
            "theme": "tema", "status": "draft",
            "points": self.valid_points(3), "version": 2, "error": None,
            "approved_at": "2026-01-01T12:00:00Z",
        })

    def test_briefing_version_response_json_dump_exact_fields_defaults_and_schema(self):
        from datetime import timezone

        created_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        resp = BriefingVersionResponse(
            version=2, status=BriefingStatus.DRAFT,
            points=self.valid_points(3), created_at=created_at,
            error=None, approved_at=dt,
        )
        self.assertEqual(resp.model_dump(mode="json"), {
            "version": 2, "status": "draft", "points": self.valid_points(3),
            "error": None, "approved_at": "2026-01-01T12:00:00Z",
            "created_at": "2026-01-01T12:00:00Z",
        })
        defaulted = BriefingVersionResponse(
            version=1, status=BriefingStatus.GENERATING, created_at=created_at,
        ).model_dump(mode="json")
        self.assertEqual(defaulted, {
            "version": 1, "status": "generating", "points": [], "error": None,
            "approved_at": None, "created_at": "2026-01-01T12:00:00Z",
        })
        schema = BriefingVersionResponse.model_json_schema()
        self.assertEqual(set(schema["required"]), {"version", "status", "created_at"})
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(set(schema["properties"]), {
            "version", "status", "points", "error", "approved_at", "created_at",
        })
        status_schema = schema["properties"]["status"]
        if "$ref" in status_schema:
            enum = schema["$defs"][status_schema["$ref"].split("/")[-1]]["enum"]
        else:
            enum = status_schema["enum"]
        self.assertEqual(enum, ["generating", "draft", "failed", "approved"])
        self.assertEqual(schema["properties"]["points"]["type"], "array")
        self.assertEqual(schema["properties"]["points"]["items"], {"$ref": "#/$defs/BriefingPoint"})
        self.assertNotIn("default", schema["properties"]["points"])

    def test_title_description_invalid_values_rejected_independent_of_cardinality(self):
        invalid_values = ("", "   ", 7)
        for schema_name, build in (
            ("BriefingResponse", self.response),
            ("BriefingVersionResponse", self.version_response),
        ):
            for status in (BriefingStatus.DRAFT, BriefingStatus.APPROVED):
                for field in ("title", "description"):
                    for value in invalid_values:
                        for count in (3, 7):
                            points = self.valid_points(count)
                            points[0][field] = value
                            with self.subTest(schema=schema_name, status=status, field=field, value=value, count=count):
                                with self.assertRaises(ValidationError) as caught:
                                    build(status, points)
                                self.assertTrue(
                                    any(error["loc"][-1] == field for error in caught.exception.errors()),
                                    caught.exception.errors(),
                                )
                                self.assertFalse(
                                    any(error["loc"] == ("points",) for error in caught.exception.errors()),
                                    caught.exception.errors(),
                                )

    def test_briefing_version_response_json_schema_fields_enum_and_required_contract(self):
        schema = BriefingVersionResponse.model_json_schema()
        props = schema["properties"]
        self.assertEqual(set(props), {
            "version", "status", "points", "error", "approved_at", "created_at",
        })
        self.assertEqual(set(schema["required"]), {"version", "status", "created_at"})
        self.assertIs(schema["additionalProperties"], False)
        for forbidden in ("id", "theme", "briefing_id", "prompt", "search", "updated_at"):
            self.assertNotIn(forbidden, props)
        status_schema = props["status"]
        if "$ref" in status_schema:
            enum = schema["$defs"][status_schema["$ref"].split("/")[-1]]["enum"]
        else:
            enum = status_schema["enum"]
        self.assertEqual(enum, ["generating", "draft", "failed", "approved"])
        self.assertEqual(props["points"]["type"], "array")
        self.assertEqual(props["points"]["items"], {"$ref": "#/$defs/BriefingPoint"})
        self.assertNotIn("default", props["points"])
        point_schema = schema["$defs"]["BriefingPoint"]
        self.assertIs(point_schema["additionalProperties"], False)
        self.assertEqual(set(point_schema["properties"]), {"title", "description"})
        self.assertEqual(set(point_schema["required"]), {"title", "description"})
        self.assertIs(point_schema["properties"]["title"]["type"], "string")
        self.assertIs(point_schema["properties"]["description"]["type"], "string")
        self.assertEqual(point_schema["properties"]["title"]["minLength"], 1)
        self.assertEqual(point_schema["properties"]["description"]["minLength"], 1)


if __name__ == "__main__":
    unittest.main()
