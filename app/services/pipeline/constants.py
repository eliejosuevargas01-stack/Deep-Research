"""Shared constants to break circular imports between research.py and pipeline modules."""
from typing import Any

from app.models import ResearchPoint

PERSONAS = ("historian", "skeptic", "pragmatist", "futurist")
WORK_LIMIT = None  # set at runtime in research.py