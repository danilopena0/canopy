"""Routes module."""

from .applications import ApplicationController
from .jobs import JobController
from .profile import ProfileController
from .search import SearchController

__all__ = [
    "JobController",
    "SearchController",
    "ApplicationController",
    "ProfileController",
]
