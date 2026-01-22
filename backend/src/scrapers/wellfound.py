"""Wellfound (formerly AngelList) jobs scraper."""

import asyncio
import hashlib
import json
import logging
import re
from typing import AsyncIterator

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from bs4 import BeautifulSoup

from ..config import get_settings
from ..models import JobCreate
from .base import BaseScraper

logger = logging.getLogger(__name__)


class WellfoundScraper(BaseScraper):
    """Scraper for Wellfound (AngelList) job listings.

    Wellfound uses Next.js with Apollo GraphQL. Data is embedded in
    __NEXT_DATA__ script tag as JSON.
    """

    BASE_URL = "https://wellfound.com"

    # Role slugs for common data science/ML titles
    ROLE_SLUGS = [
        "data-scientist",
        "machine-learning-engineer",
        "data-engineer",
        "ai-engineer",
        "ml-engineer",
    ]

    def __init__(
        self,
        role: str = "data-scientist",
        location: str | None = None,
        max_pages: int = 3,
    ):
        """Initialize the Wellfound scraper.

        Args:
            role: Role slug to search for (e.g., 'data-scientist')
            location: Optional location slug (e.g., 'san-antonio')
            max_pages: Maximum number of result pages to scrape
        """
        self.role = role
        self.location = location
        self.max_pages = max_pages
        self.settings = get_settings()

    @property
    def source_name(self) -> str:
        return "wellfound"

    def _generate_job_id(self, url: str) -> str:
        """Generate a stable job ID from the URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def _build_search_url(self, page: int = 1) -> str:
        """Build the Wellfound search URL.

        Args:
            page: Page number (1-indexed)
        """
        if self.location:
            url = f"{self.BASE_URL}/role/l/{self.role}/{self.location}"
        else:
            url = f"{self.BASE_URL}/role/{self.role}"

        if page > 1:
            url += f"?page={page}"

        return url

    def _extract_next_data(self, html: str) -> dict | None:
        """Extract __NEXT_DATA__ JSON from the page."""
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script:
            logger.warning("Could not find __NEXT_DATA__ script tag")
            return None

        try:
            return json.loads(script.string)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse __NEXT_DATA__: {e}")
            return None

    def _extract_jobs_from_apollo_state(self, next_data: dict) -> list[dict]:
        """Extract job listings from Apollo state cache.

        The Apollo state contains nodes like:
        - JobListingSearchResult:<id>
        - Startup:<id>
        - JobListing:<id>

        Jobs are linked: SearchResult -> JobListing -> Startup
        """
        jobs = []

        try:
            # Navigate to Apollo state
            apollo_state = (
                next_data.get("props", {})
                .get("pageProps", {})
                .get("apolloState", {})
            )

            if not apollo_state:
                # Try alternate path
                apollo_state = (
                    next_data.get("props", {})
                    .get("pageProps", {})
                    .get("__APOLLO_STATE__", {})
                )

            if not apollo_state:
                logger.warning("Could not find Apollo state in page data")
                return jobs

            # Find all job listing entries
            job_listings = {}
            startups = {}

            for key, value in apollo_state.items():
                if key.startswith("JobListing:"):
                    job_listings[key] = value
                elif key.startswith("Startup:"):
                    startups[key] = value

            # Process each job listing
            for listing_key, listing in job_listings.items():
                try:
                    job_data = self._parse_job_listing(listing, startups, apollo_state)
                    if job_data:
                        jobs.append(job_data)
                except Exception as e:
                    logger.warning(f"Error parsing job listing {listing_key}: {e}")

        except Exception as e:
            logger.error(f"Error extracting jobs from Apollo state: {e}")

        return jobs

    def _parse_job_listing(
        self,
        listing: dict,
        startups: dict,
        apollo_state: dict,
    ) -> dict | None:
        """Parse a single job listing from Apollo state."""
        # Get basic fields
        title = listing.get("title") or listing.get("jobTitle")
        if not title:
            return None

        slug = listing.get("slug", "")
        listing_id = listing.get("id", "")

        # Build job URL
        if slug:
            job_url = f"{self.BASE_URL}/jobs/{slug}"
        elif listing_id:
            job_url = f"{self.BASE_URL}/jobs/{listing_id}"
        else:
            return None

        # Get company info from linked startup
        company_name = "Unknown Startup"
        company_location = None

        startup_ref = listing.get("startup")
        if startup_ref and isinstance(startup_ref, dict):
            startup_key = startup_ref.get("__ref")
            if startup_key and startup_key in startups:
                startup = startups[startup_key]
                company_name = startup.get("name", company_name)
                company_location = startup.get("locationTagline")
            elif startup_key and startup_key in apollo_state:
                startup = apollo_state[startup_key]
                company_name = startup.get("name", company_name)
                company_location = startup.get("locationTagline")

        # Get location
        location = None
        if listing.get("remote"):
            location = "Remote"
        elif listing.get("locationNames"):
            locations = listing.get("locationNames", [])
            if locations:
                location = ", ".join(locations[:3])  # Limit to first 3
        elif company_location:
            location = company_location

        # Get salary info
        salary_min = None
        salary_max = None
        compensation = listing.get("compensation")
        if compensation:
            salary_min = compensation.get("min")
            salary_max = compensation.get("max")
        else:
            # Try direct fields
            salary_min = listing.get("salaryMin") or listing.get("compensationMin")
            salary_max = listing.get("salaryMax") or listing.get("compensationMax")

        # Get work type
        work_type = None
        if listing.get("remote"):
            work_type = "remote"
        elif listing.get("hybrid"):
            work_type = "hybrid"
        elif listing.get("onsite") or listing.get("onsiteOrRemote") == "onsite":
            work_type = "onsite"

        # Get description snippet
        description = listing.get("description") or listing.get("descriptionSnippet")

        return {
            "url": job_url,
            "title": title,
            "company": company_name,
            "location": location or "Not specified",
            "description": description,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "work_type": work_type,
        }

    async def scrape(self) -> AsyncIterator[JobCreate]:
        """Scrape Wellfound jobs for the configured role."""
        logger.info(f"Starting Wellfound scrape for role: {self.role}")

        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        crawl_config = CrawlerRunConfig(
            delay_before_return_html=4.0,  # Wait for Next.js hydration
        )

        seen_urls = set()
        total_jobs = 0

        async with AsyncWebCrawler(config=browser_config) as crawler:
            for page in range(1, self.max_pages + 1):
                search_url = self._build_search_url(page)

                logger.info(f"Scraping Wellfound page {page}: {search_url}")

                # Rate limit between pages
                if page > 1:
                    await asyncio.sleep(self.settings.scrape_delay_seconds * 2)

                result = await crawler.arun(
                    url=search_url,
                    config=crawl_config,
                )

                if not result.success:
                    logger.error(
                        f"Failed to crawl Wellfound page {page}: {result.error_message}"
                    )
                    break

                # Extract __NEXT_DATA__
                next_data = self._extract_next_data(result.html)
                if not next_data:
                    logger.warning(f"No data found on page {page}, trying HTML parse")
                    # Fallback to HTML parsing
                    jobs_on_page = self._extract_jobs_from_html(result.html)
                else:
                    jobs_on_page = self._extract_jobs_from_apollo_state(next_data)

                if not jobs_on_page:
                    logger.info(f"No more jobs found on page {page}")
                    break

                page_count = 0
                for job_data in jobs_on_page:
                    if job_data["url"] in seen_urls:
                        continue

                    seen_urls.add(job_data["url"])

                    job = JobCreate(
                        id=self._generate_job_id(job_data["url"]),
                        url=job_data["url"],
                        source=self.source_name,
                        title=job_data["title"],
                        company=job_data["company"],
                        location=job_data["location"],
                        description=job_data.get("description", "")[:10000]
                        if job_data.get("description")
                        else None,
                        salary_min=job_data.get("salary_min"),
                        salary_max=job_data.get("salary_max"),
                        work_type=job_data.get("work_type"),
                    )

                    total_jobs += 1
                    page_count += 1
                    logger.info(f"Job {total_jobs}: {job.title} at {job.company}")
                    yield job

                logger.info(f"Found {page_count} jobs on page {page}")

                # Stop if we got fewer jobs than expected (likely last page)
                if page_count < 10:
                    break

        logger.info(f"Finished Wellfound scrape. Total jobs found: {total_jobs}")

    def _extract_jobs_from_html(self, html: str) -> list[dict]:
        """Fallback HTML parsing if Apollo state extraction fails."""
        jobs = []
        soup = BeautifulSoup(html, "html.parser")

        # Try to find job cards - Wellfound uses various class patterns
        job_cards = soup.find_all(
            "div",
            class_=re.compile(r"styles_jobListingCard|JobListing|job-listing", re.I),
        )

        if not job_cards:
            # Try finding job links
            job_links = soup.find_all("a", href=re.compile(r"/jobs/[a-z0-9-]+"))
            for link in job_links:
                href = link.get("href", "")
                if not href.startswith("http"):
                    href = f"{self.BASE_URL}{href}"

                title = link.get_text(strip=True)
                if title and len(title) > 5:
                    jobs.append(
                        {
                            "url": href,
                            "title": title,
                            "company": "Unknown Startup",
                            "location": "Not specified",
                        }
                    )

        for card in job_cards:
            try:
                # Find job link
                link = card.find("a", href=re.compile(r"/jobs/"))
                if not link:
                    continue

                href = link.get("href", "")
                if not href.startswith("http"):
                    href = f"{self.BASE_URL}{href}"

                # Find title
                title_elem = card.find(class_=re.compile(r"title|jobTitle", re.I))
                title = (
                    title_elem.get_text(strip=True)
                    if title_elem
                    else link.get_text(strip=True)
                )

                # Find company
                company_elem = card.find(class_=re.compile(r"company|startup", re.I))
                company = (
                    company_elem.get_text(strip=True)
                    if company_elem
                    else "Unknown Startup"
                )

                # Find location
                loc_elem = card.find(class_=re.compile(r"location", re.I))
                location = (
                    loc_elem.get_text(strip=True) if loc_elem else "Not specified"
                )

                jobs.append(
                    {
                        "url": href,
                        "title": title,
                        "company": company,
                        "location": location,
                    }
                )

            except Exception as e:
                logger.warning(f"Error parsing job card: {e}")

        return jobs
