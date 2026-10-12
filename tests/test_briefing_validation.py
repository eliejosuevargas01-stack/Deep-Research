"""Contratos locais de validação; rejeição antes de I/O pertence a T010."""
import unittest
from typing import Any, cast
from uuid import UUID

from pydantic import ValidationError

from app.briefing import domain
from app.briefing.schemas import BriefingCreateRequest


class BriefingValidationTests(unittest.TestCase):
    def test_theme_boundaries_and_normalization(self):
        for size in (2, 3, 300, 301):
            value = " " + "x" * size + "\n"
            with self.subTest(size=size):
                if size in (3, 300):
                    self.assertEqual(domain.validate_theme(value), "x" * size)
                    self.assertEqual(BriefingCreateRequest(theme=value).theme, "x" * size)
                else:
                    with self.assertRaises(domain.InvalidContent):
                        domain.validate_theme(value)
                    with self.assertRaises(ValidationError):
                        BriefingCreateRequest(theme=value)

    def test_theme_rejects_invalid_types_and_whitespace(self):
        for value in (None, 0, True, [], {}, " \t\n"):
            with self.subTest(value=value):
                with self.assertRaises(domain.InvalidContent):
                    domain.validate_theme(cast(Any, value))
                with self.assertRaises(ValidationError):
                    BriefingCreateRequest(theme=cast(Any, value))

    def test_new_briefing_starts_generating_with_normalized_theme(self):
        self.assertTrue(callable(getattr(domain, "new_briefing", None)), "missing domain.new_briefing")
        briefing = domain.new_briefing("  Climate research  ")
        self.assertIsInstance(briefing.id, UUID)
        self.assertEqual(briefing.theme, "Climate research")
        self.assertEqual(briefing.status, domain.BriefingStatus.GENERATING)
        self.assertEqual(briefing.version, 1)
        self.assertEqual(briefing.points, ())
        self.assertIsNone(briefing.approved_at)
        self.assertIsNone(briefing.error)

    def test_new_briefing_rejects_invalid_theme_boundary(self):
        self.assertTrue(callable(getattr(domain, "new_briefing", None)), "missing domain.new_briefing")
        for value in (None, 0, True, [], {}, "  \t\n"):
            with self.subTest(value=value):
                with self.assertRaises(domain.InvalidContent):
                    domain.new_briefing(cast(Any, value))
        for size in (2, 301):
            value = " " + "x" * size + "\n"
            with self.subTest(size=size):
                with self.assertRaises(domain.InvalidContent):
                    domain.new_briefing(value)
        for size in (3, 300):
            value = " " + "x" * size + "\n"
            with self.subTest(size=size):
                briefing = domain.new_briefing(value)
                self.assertEqual(briefing.theme, "x" * size)
                self.assertEqual(briefing.status, domain.BriefingStatus.GENERATING)


if __name__ == "__main__":
    unittest.main()
