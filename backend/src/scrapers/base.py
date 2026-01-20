"""Abstract base class for job scrapers."""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from ..models import JobCreate


class BaseScraper(ABC):
    """Abstract base class for job scrapers."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the source identifier for this scraper."""
        pass

    @abstractmethod
    async def scrape(self) -> AsyncIterator[JobCreate]:
        """Scrape jobs and yield them one by one.

        Yields:
            JobCreate instances for each discovered job.
        """
        pass
