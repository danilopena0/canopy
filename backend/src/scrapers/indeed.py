"""Indeed jobs scraper."""

import asyncio
import hashlib
import logging
import re
from typing import AsyncIterator
from urllib.parse import quote_plus

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from bs4 import BeautifulSoup

from ..config import get_settings
from ..models import JobCreate
from .base import BaseScraper

logger = logging.getLogger(__name__)


class IndeedScraper(BaseScraper):
    """Scraper for Indeed job listings."""

    BASE_URL = "https://www.indeed.com"

    # Salary patterns - Indeed shows various formats
    SALARY_PATTERN = re.compile(
        r"\$([0-9,]+(?:\.\d{2})?)\s*(?:-|to|–)\s*\$([0-9,]+(?:\.\d{2})?)\s*(?:a |per )?(year|hour|month)",
        re.IGNORECASE
    )
    SINGLE_SALARY_PATTERN = re.compile(
        r"\$([0-9,]+(?:\.\d{2})?)\s*(?:a |per )?(year|hour|month)",
        re.IGNORECASE
    )

    def __init__(
        self,
        query: str = "data scientist",
        location: str = "San Antonio, TX",
        radius: int = 50,
        days_ago: int = 7,
        max_pages: int = 3,
    ):
        """Initialize the Indeed scraper.

        Args:
            query: Job search keywords
            location: Location to search
            radius: Search radius in miles
            days_ago: Only show jobs posted within this many days
            max_pages: Maximum number of result pages to scrape
        """
        self.query = query
        self.location = location
        self.radius = radius
        self.days_ago = days_ago
        self.max_pages = max_pages
        self.settings = get_settings()

    @property
    def source_name(self) -> str:
        return "indeed"

    def _generate_job_id(self, url: str) -> str:
        """Generate a stable job ID from the URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def _extract_salary(self, text: str) -> tuple[int | None, int | None]:
        """Extract salary range from text. Returns (min, max) as integers or None."""
        if not text:
            return None, None

        # Try range pattern first
        match = self.SALARY_PATTERN.search(text)
        if match:
            min_val = match.group(1).replace(",", "").split(".")[0]
            max_val = match.group(2).replace(",", "").split(".")[0]
            period = match.group(3).lower()

            try:
                min_salary = int(min_val)
                max_salary = int(max_val)

                # Convert to annual if needed
                if period == "hour":
                    min_salary *= 2080  # 40 hrs/week * 52 weeks
                    max_salary *= 2080
                elif period == "month":
                    min_salary *= 12
                    max_salary *= 12

                return min_salary, max_salary
            except ValueError:
                pass

        # Try single salary pattern
        match = self.SINGLE_SALARY_PATTERN.search(text)
        if match:
            salary_val = match.group(1).replace(",", "").split(".")[0]
            period = match.group(2).lower() if match.group(2) else "year"

            try:
                salary = int(salary_val)
                if period == "hour":
                    salary *= 2080
                elif period == "month":
                    salary *= 12
                return salary, salary
            except ValueError:
                pass

        return None, None

    def _build_search_url(self, start: int = 0) -> str:
        """Build the Indeed search URL.

        Args:
            start: Starting result index for pagination (0, 10, 20, etc.)
        """
        query_encoded = quote_plus(self.query)
        location_encoded = quote_plus(self.location)

        url = (
            f"{self.BASE_URL}/jobs"
            f"?q={query_encoded}"
            f"&l={location_encoded}"
            f"&radius={self.radius}"
            f"&fromage={self.days_ago}"
            f"&start={start}"
        )
        return url

    def _extract_job_key(self, element) -> str | None:
        """Extract the Indeed job key from a job card element."""
        # Indeed uses data-jk attribute for job keys
        job_key = element.get("data-jk")
        if job_key:
            return job_key

        # Try finding in nested link
        link = element.find("a", href=re.compile(r"jk=([a-f0-9]+)", re.I))
        if link:
            match = re.search(r"jk=([a-f0-9]+)", link.get("href", ""))
            if match:
                return match.group(1)

        return None

    async def scrape(self) -> AsyncIterator[JobCreate]:
        """Scrape Indeed jobs for the configured search parameters."""
        logger.info(f"Starting Indeed scrape: '{self.query}' in {self.location}")

        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            # Use a realistic user agent
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        crawl_config = CrawlerRunConfig(
            delay_before_return_html=3.0,  # Wait for JS to render
        )

        seen_job_keys = set()
        total_jobs = 0

        async with AsyncWebCrawler(config=browser_config) as crawler:
            for page in range(self.max_pages):
                start_index = page * 10  # Indeed uses 10 results per page
                search_url = self._build_search_url(start_index)

                logger.info(f"Scraping Indeed page {page + 1}: {search_url}")

                # Rate limit between pages
                if page > 0:
                    await asyncio.sleep(self.settings.scrape_delay_seconds * 2)

                result = await crawler.arun(
                    url=search_url,
                    config=crawl_config,
                )

                if not result.success:
                    logger.error(f"Failed to crawl Indeed page {page + 1}: {result.error_message}")
                    break

                soup = BeautifulSoup(result.html, "html.parser")

                # Find job cards - Indeed uses various container classes
                job_cards = soup.find_all("div", class_=re.compile(r"job_seen_beacon|jobsearch-ResultsList|result"))

                if not job_cards:
                    # Try alternative selectors
                    job_cards = soup.find_all("a", {"data-jk": True})

                if not job_cards:
                    logger.warning(f"No job cards found on page {page + 1}. Selector may need updating.")
                    # Save HTML for debugging
                    logger.debug(f"Page HTML length: {len(result.html)}")
                    break

                page_jobs = 0
                for card in job_cards:
                    job_key = self._extract_job_key(card)
                    if not job_key or job_key in seen_job_keys:
                        continue

                    seen_job_keys.add(job_key)

                    # Extract basic info from card
                    job_data = self._parse_job_card(card, job_key)
                    if not job_data:
                        continue

                    # Rate limit between job detail fetches
                    if total_jobs > 0:
                        await asyncio.sleep(self.settings.scrape_delay_seconds)

                    # Fetch full job details
                    job = await self._scrape_job_detail(
                        crawler,
                        job_data["url"],
                        crawl_config,
                        job_data,
                    )

                    if job:
                        total_jobs += 1
                        page_jobs += 1
                        logger.info(f"Scraped job: {job.title} at {job.company}")
                        yield job

                logger.info(f"Found {page_jobs} jobs on page {page + 1}")

                # Stop if no jobs found on this page
                if page_jobs == 0:
                    break

        logger.info(f"Finished Indeed scrape. Total jobs found: {total_jobs}")

    def _parse_job_card(self, card, job_key: str) -> dict | None:
        """Parse basic job info from a job card element."""
        try:
            # Build job URL from key
            job_url = f"{self.BASE_URL}/viewjob?jk={job_key}"

            # Extract title
            title = None
            title_elem = card.find(class_=re.compile(r"jobTitle|title", re.I))
            if title_elem:
                # Get text from span or direct text
                title_span = title_elem.find("span")
                title = (title_span or title_elem).get_text(strip=True)

            if not title:
                # Try finding title in link
                title_link = card.find("a", class_=re.compile(r"title|jobTitle", re.I))
                if title_link:
                    title = title_link.get_text(strip=True)

            if not title:
                return None

            # Extract company
            company = None
            company_elem = card.find(class_=re.compile(r"company|companyName", re.I))
            if company_elem:
                company = company_elem.get_text(strip=True)

            # Extract location
            location = self.location
            loc_elem = card.find(class_=re.compile(r"companyLocation|location", re.I))
            if loc_elem:
                location = loc_elem.get_text(strip=True)

            # Extract salary snippet if present
            salary_min, salary_max = None, None
            salary_elem = card.find(class_=re.compile(r"salary|metadata", re.I))
            if salary_elem:
                salary_min, salary_max = self._extract_salary(salary_elem.get_text())

            # Extract snippet/description preview
            snippet = None
            snippet_elem = card.find(class_=re.compile(r"snippet|summary|description", re.I))
            if snippet_elem:
                snippet = snippet_elem.get_text(strip=True)

            return {
                "job_key": job_key,
                "url": job_url,
                "title": title,
                "company": company or "Unknown Company",
                "location": location,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "snippet": snippet,
            }

        except Exception as e:
            logger.warning(f"Error parsing job card: {e}")
            return None

    async def _scrape_job_detail(
        self,
        crawler: AsyncWebCrawler,
        url: str,
        config: CrawlerRunConfig,
        card_data: dict,
    ) -> JobCreate | None:
        """Scrape full details from a job posting page."""
        try:
            result = await crawler.arun(url=url, config=config)

            if not result.success:
                logger.warning(f"Failed to fetch job detail: {url}")
                # Return basic info from card
                return JobCreate(
                    id=self._generate_job_id(url),
                    url=url,
                    source=self.source_name,
                    title=card_data["title"],
                    company=card_data["company"],
                    location=card_data["location"],
                    description=card_data.get("snippet"),
                    salary_min=card_data.get("salary_min"),
                    salary_max=card_data.get("salary_max"),
                )

            soup = BeautifulSoup(result.html, "html.parser")

            # Extract full description
            description = card_data.get("snippet", "")
            desc_elem = soup.find(id="jobDescriptionText")
            if not desc_elem:
                desc_elem = soup.find(class_=re.compile(r"jobDescription|job-description", re.I))
            if desc_elem:
                description = desc_elem.get_text(separator="\n", strip=True)

            # Try to get better salary info from detail page
            salary_min = card_data.get("salary_min")
            salary_max = card_data.get("salary_max")

            if not salary_min:
                page_text = soup.get_text()
                salary_min, salary_max = self._extract_salary(page_text)

            # Extract work type if available
            work_type = None
            page_text_lower = soup.get_text().lower()
            if "remote" in page_text_lower:
                work_type = "remote"
            elif "hybrid" in page_text_lower:
                work_type = "hybrid"
            elif "on-site" in page_text_lower or "onsite" in page_text_lower:
                work_type = "onsite"

            return JobCreate(
                id=self._generate_job_id(url),
                url=url,
                source=self.source_name,
                title=card_data["title"],
                company=card_data["company"],
                location=card_data["location"],
                description=description[:10000] if description else None,
                salary_min=salary_min,
                salary_max=salary_max,
                work_type=work_type,
            )

        except Exception as e:
            logger.error(f"Error scraping job detail {url}: {e}")
            # Return basic info on error
            return JobCreate(
                id=self._generate_job_id(url),
                url=url,
                source=self.source_name,
                title=card_data["title"],
                company=card_data["company"],
                location=card_data["location"],
            )
