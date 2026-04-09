"""Shared fixtures for prompt engineering tests."""

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


def pytest_addoption(parser):
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Overwrite snapshot files with current output.",
    )

from src.services.llm import LLMProvider

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class MockLLMProvider(LLMProvider):
    """LLM provider that captures prompts and returns preset responses.

    Set `json_response` before calling complete_json to control what the
    service receives. Captured prompts are stored in `captured_prompts` and
    `captured_systems`.
    """

    def __init__(self, json_response: dict[str, Any] | None = None, text_response: str = ""):
        self.json_response: dict[str, Any] = json_response or {}
        self.text_response: str = text_response
        self.captured_prompts: list[str] = []
        self.captured_systems: list[str | None] = []

    async def complete(self, prompt: str, system: str | None = None) -> str:
        self.captured_prompts.append(prompt)
        self.captured_systems.append(system)
        return self.text_response

    async def complete_json(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        self.captured_prompts.append(prompt)
        self.captured_systems.append(system)
        return self.json_response

    async def close(self) -> None:
        pass

    @property
    def last_prompt(self) -> str:
        """The most recently captured user prompt."""
        return self.captured_prompts[-1] if self.captured_prompts else ""

    @property
    def last_system(self) -> str | None:
        """The most recently captured system prompt."""
        return self.captured_systems[-1] if self.captured_systems else None


@pytest.fixture
def sample_job() -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / "sample_job.json").read_text())


@pytest.fixture
def sample_profile() -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / "sample_profile.json").read_text())


@pytest.fixture
def sample_resume() -> str:
    return (FIXTURES_DIR / "sample_resume.md").read_text()


@pytest.fixture
def dealbreaker_job(sample_job) -> dict[str, Any]:
    """Job that triggers a dealbreaker (requires clearance)."""
    return {
        **sample_job,
        "title": "Data Scientist — Cleared",
        "description": sample_job["description"] + " Active security clearance required.",
        "requirements": sample_job["requirements"] + " Active TS/SCI clearance required.",
    }


@pytest.fixture
def snapshot(request):
    """Compare a string value against a golden file in tests/prompts/snapshots/.

    Usage::

        def test_my_prompt(snapshot):
            snapshot(rendered_prompt)          # uses test name as filename
            snapshot(rendered_prompt, "cover") # explicit name

    First run (or --update-snapshots): writes the file and passes.
    Subsequent runs: compares and fails on mismatch.
    """
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    update = request.config.getoption("--update-snapshots")

    def assert_matches(value: str, name: str | None = None) -> None:
        filename = (name or request.node.name) + ".txt"
        snap_file = SNAPSHOTS_DIR / filename
        if update or not snap_file.exists():
            snap_file.write_text(value, encoding="utf-8")
            return
        expected = snap_file.read_text(encoding="utf-8")
        assert value == expected, (
            f"Snapshot mismatch for '{filename}'.\n"
            "Run with --update-snapshots to accept the new output."
        )

    return assert_matches


@pytest.fixture
def minimal_job() -> dict[str, Any]:
    """Job with only required fields, all optionals missing."""
    return {
        "id": "minimal000000001",
        "title": "Data Scientist",
        "company": "Acme Corp",
        "location": None,
        "work_type": None,
        "salary_min": None,
        "salary_max": None,
        "description": "Build ML models.",
        "requirements": None,
    }
