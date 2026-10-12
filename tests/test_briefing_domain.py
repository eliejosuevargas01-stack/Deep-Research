"""QA das regras puras existentes; não comprova service ou persistência."""
import unittest
from types import SimpleNamespace

from app.briefing.domain import (
    BriefingStatus, InvalidContent, InvalidTransition, assert_can_edit,
    transition, validate_points, validate_theme,
)


class BriefingDomainTests(unittest.TestCase):
    def test_theme_normalized_boundaries(self):
        for count in (2, 3, 300, 301):
            with self.subTest(count=count):
                value = " \t" + "á" * count + "\n "
                if count in (3, 300):
                    self.assertEqual(validate_theme(value), "á" * count)
                else:
                    with self.assertRaises(InvalidContent):
                        validate_theme(value)

    def test_theme_empty_whitespace_and_types(self):
        for value in ("", " \t\n", None, 0, True, [], {}):
            with self.subTest(value=value), self.assertRaises(InvalidContent):
                validate_theme(value)

    def test_point_count_boundaries_and_order_preserved(self):
        for count in (0, 2, 3, 4, 5, 6, 7, 8):
            points = [{"title": f" t {i} ", "description": " d "} for i in range(count)]
            with self.subTest(count=count):
                if 3 <= count <= 7:
                    self.assertIs(validate_points(points), points)
                    self.assertEqual(points[0]["title"], " t 0 ")
                else:
                    with self.assertRaises(InvalidContent):
                        validate_points(points)

    def test_points_require_list(self):
        for value in (None, 0, "points", {}, (), tuple([{}] * 3)):
            with self.subTest(value=value), self.assertRaises(InvalidContent):
                validate_points(value)

    def test_point_fields_empty_whitespace_types_and_missing(self):
        for field in ("title", "description"):
            for value in ("", " \t\n", None, 0, True, [], {}):
                point = {"title": "ok", "description": "ok", field: value}
                with self.subTest(field=field, value=value), self.assertRaises(InvalidContent):
                    validate_points([point] * 3)
            point = {key: "ok" for key in ("title", "description") if key != field}
            with self.subTest(missing=field), self.assertRaises(InvalidContent):
                validate_points([point] * 3)
        for value in (None, 0, "point", {}):
            with self.subTest(point=value), self.assertRaises(InvalidContent):
                validate_points([value] * 3)

    def test_attribute_points_supported(self):
        points = [SimpleNamespace(title=" t ", description=" d ")] * 3
        self.assertIs(validate_points(points), points)
        self.assertEqual(points[0].description, " d ")

    def test_all_sixteen_transitions_enum_and_string(self):
        allowed = {("generating", "draft"), ("generating", "failed"),
                   ("draft", "approved"), ("approved", "draft")}
        for source in BriefingStatus:
            for target in BriefingStatus:
                for current, next_status in ((source, target), (source.value, target.value)):
                    with self.subTest(source=current, target=next_status):
                        if (source.value, target.value) in allowed:
                            self.assertIs(transition(current, next_status), target)
                        else:
                            with self.assertRaises(InvalidTransition):
                                transition(current, next_status)

    def test_unknown_transition_states_rejected(self):
        for source, target in (("banana", "draft"), ("draft", "banana"), (None, "draft")):
            with self.subTest(source=source, target=target), self.assertRaises(InvalidTransition):
                transition(source, target)

    def test_only_draft_editable(self):
        for status in (*BriefingStatus, "draft", "approved", "banana", None):
            with self.subTest(status=status):
                if status == BriefingStatus.DRAFT:
                    self.assertIsNone(assert_can_edit(status))
                else:
                    with self.assertRaises(InvalidTransition):
                        assert_can_edit(status)

    def test_reopen_and_repeat_edit_without_research_guard_or_limit(self):
        status = BriefingStatus.APPROVED
        for _ in range(20):
            status = transition(status, BriefingStatus.DRAFT)
            for _ in range(20):
                self.assertIsNone(assert_can_edit(status))
            status = transition(status, BriefingStatus.APPROVED)


if __name__ == "__main__":
    unittest.main()
