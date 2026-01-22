"""H-E-B careers page scraper."""

import asyncio
import hashlib
import logging
import re
from typing import AsyncIterator

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from bs4 import BeautifulSoup

from ..config import get_settings
from ..models import JobCreate
from .base import BaseScraper

logger = logging.getLogger(__name__)


class HEBScraper(BaseScraper):
    """Scraper for H-E-B careers page."""

    BASE_URL = "https://careers.heb.com"
    # Pattern to match salary like "USD $72,200.00/Yr" or "$141,500.00/Yr"
    SALARY_PATTERN = re.compile(r"(?:USD\s*)?\$([0-9,]+(?:\.\d{2})?)/Yr", re.IGNORECASE)

    def __init__(
        self,
        location: str = "San Antonio, TX",
        keywords: str = "data",
    ):
        self.location = location
        self.keywords = keywords
        self.settings = get_settings()

    @property
    def source_name(self) -> str:
        return "heb"

    def _generate_job_id(self, url: str) -> str:
        """Generate a stable job ID from the URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def _extract_salary(self, text: str) -> int | None:
        """Extract annual salary from text. Returns salary as integer or None."""
        if not text:
            return None
        match = self.SALARY_PATTERN.search(text)
        if match:
            # Remove commas and convert to int
            salary_str = match.group(1).replace(",", "").split(".")[0]
            try:
                return int(salary_str)
            except ValueError:
                return None
        return None

    def _build_search_url(self) -> str:
        """Build the search URL with location and keywords."""
        location_encoded = self.location.replace(" ", "%20").replace(",", "%2C")
        url = f"{self.BASE_URL}/jobs?location={location_encoded}"
        if self.keywords:
            url += f"&keywords={self.keywords.replace(' ', '%20')}"
        return url

    async def scrape(self) -> AsyncIterator[JobCreate]:
        """Scrape H-E-B jobs for the configured location and keywords."""
        search_url = self._build_search_url()
        logger.info(f"Scraping H-E-B jobs from: {search_url}")

        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
        )

        crawl_config = CrawlerRunConfig(
            delay_before_return_html=5.0,  # Wait for Angular to render
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            # Get the job listing page
            result = await crawler.arun(
                url=search_url,
                config=crawl_config,
            )

            if not result.success:
                logger.error(f"Failed to crawl H-E-B careers page: {result.error_message}")
                return

            # Parse job listings from the page
            soup = BeautifulSoup(result.html, "html.parser")

            # Find all job cards - filter to only internal job links (not "Apply Now" links)
            job_links = soup.find_all("a", href=re.compile(r"^/jobs/\d+"))

            seen_urls = set()
            jobs_found = 0

            for link in job_links:
                href = link.get("href", "")
                if not href or href in seen_urls:
                    continue

                # Skip "Apply Now" links (they go to icims)
                link_text = link.get_text(strip=True)
                if link_text.lower() in ["apply now", "apply"]:
                    continue

                seen_urls.add(href)

                # Clean up the URL - remove query params for cleaner ID
                clean_href = href.split("?")[0]
                job_url = f"{self.BASE_URL}{clean_href}"

                # Extract title from the link
                title = link_text or "Unknown Position"

                # Try to find location from parent card
                location = self.location
                parent = link.find_parent(class_=re.compile(r"card|result|item", re.I))
                if parent:
                    # Look for location element
                    loc_elem = parent.find(string=re.compile(r"San Antonio|Austin|Texas", re.I))
                    if loc_elem:
                        # Get the parent's text for full location
                        loc_parent = loc_elem.find_parent()
                        if loc_parent:
                            loc_text = loc_parent.get_text(strip=True)
                            # Clean up "Location" prefix
                            loc_text = re.sub(r"^Location", "", loc_text).strip()
                            if loc_text:
                                location = loc_text[:200]  # Limit length

                # Rate limit between job detail fetches
                if jobs_found > 0:
                    await asyncio.sleep(self.settings.scrape_delay_seconds)

                # Fetch job details
                job = await self._scrape_job_detail(crawler, job_url, crawl_config, title, location)
                if job:
                    jobs_found += 1
                    logger.info(f"Scraped job: {job.title} at {job.company}")
                    yield job

            logger.info(f"Finished scraping H-E-B. Found {jobs_found} jobs.")

    async def _scrape_job_detail(
        self,
        crawler: AsyncWebCrawler,
        url: str,
        config: CrawlerRunConfig,
        fallback_title: str,
        fallback_location: str,
    ) -> JobCreate | None:
        """Scrape details from a single job posting page."""
        try:
            result = await crawler.arun(url=url, config=config)

            if not result.success:
                logger.warning(f"Failed to scrape job detail: {url}")
                # Return basic info we have from listing page
                return JobCreate(
                    id=self._generate_job_id(url),
                    url=url,
                    source=self.source_name,
                    title=fallback_title,
                    company="H-E-B",
                    location=fallback_location,
                )

            soup = BeautifulSoup(result.html, "html.parser")

            # Extract job title - try multiple selectors
            title = fallback_title
            for selector in ["h1", ".job-title", "[class*='title']"]:
                title_elem = soup.select_one(selector)
                if title_elem:
                    text = title_elem.get_text(strip=True)
                    # Clean up title
                    if text and len(text) > 5 and "H-E-B" not in text:
                        title = text
                        break

            # Extract location
            location = fallback_location
            loc_elem = soup.find(class_=re.compile(r"location", re.I))
            if loc_elem:
                loc_text = loc_elem.get_text(strip=True)
                if loc_text:
                    location = loc_text[:200]

            # Extract description - look for main content area
            description = ""
            for selector in [".job-description", "[class*='description']", "main", "[role='main']"]:
                desc_elem = soup.select_one(selector)
                if desc_elem:
                    text = desc_elem.get_text(separator="\n", strip=True)
                    if len(text) > len(description):
                        description = text

            # Extract salary from page content
            page_text = soup.get_text()
            salary = self._extract_salary(page_text)

            return JobCreate(
                id=self._generate_job_id(url),
                url=url,
                source=self.source_name,
                title=title,
                company="H-E-B",
                location=location,
                description=description[:10000] if description else None,
                salary_min=salary,
                salary_max=salary,  # H-E-B posts single salary, not range
            )

        except Exception as e:
            logger.error(f"Error scraping job detail {url}: {e}")
            # Return basic info on error
            return JobCreate(
                id=self._generate_job_id(url),
                url=url,
                source=self.source_name,
                title=fallback_title,
                company="H-E-B",
                location=fallback_location,
            )
