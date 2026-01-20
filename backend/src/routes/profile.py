"""Profile routes for user preferences and skills."""

import json
from pathlib import Path
from typing import Any

from litestar import Controller, get, put

from ..config import get_settings


# Default user profile schema
DEFAULT_PROFILE: dict[str, Any] = {
    "name": "",
    "target_titles": [
        "Data Scientist",
        "ML Engineer",
        "AI Engineer",
        "Data Engineer",
    ],
    "skills": {
        "languages": [],
        "ml_tools": [],
        "platforms": [],
        "other": [],
    },
    "experience_years": 0,
    "locations": ["San Antonio, TX", "Austin, TX", "Remote"],
    "work_types": ["remote", "hybrid"],
    "industries": [],
    "min_salary": None,
    "dealbreakers": [],
}


class ProfileController(Controller):
    """Controller for user profile endpoints."""

    path = "/api/profile"

    def _get_profile_path(self) -> Path:
        """Get the path to the profile JSON file."""
        settings = get_settings()
        # Profile is stored alongside the database
        db_path = Path(settings.database_path)
        return db_path.parent / "profile.json"

    def _load_profile(self) -> dict[str, Any]:
        """Load user profile from file."""
        profile_path = self._get_profile_path()
        if profile_path.exists():
            with open(profile_path) as f:
                return json.load(f)
        return DEFAULT_PROFILE.copy()

    def _save_profile(self, profile: dict[str, Any]) -> None:
        """Save user profile to file."""
        profile_path = self._get_profile_path()
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        with open(profile_path, "w") as f:
            json.dump(profile, f, indent=2)

    @get("/")
    async def get_profile(self) -> dict[str, Any]:
        """Get the user profile."""
        return self._load_profile()

    @put("/")
    async def update_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        """Update the user profile."""
        # Merge with existing profile to preserve unspecified fields
        current = self._load_profile()
        current.update(data)
        self._save_profile(current)
        return current
