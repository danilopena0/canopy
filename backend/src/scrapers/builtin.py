"""Built In (builtin.com) job board scraper."""

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


class BuiltInScraper(BaseScraper):
    """Scraper for Built In job listings (builtin.com).

    Built In uses server-side rendered HTML with schema.org JSON-LD
    embedded in each page. Job listings include title, URL, and description
    snippet. Detail pages contain full description, salary, and work type
    via structured JobPosting JSON-LD.
    """

    BASE_URL = "https://builtin.com"

    STATE_ABBREVS = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming",
    }

    def __init__(
        self,
        keywords: str = "data scientist",
        location: str | None = None,
        work_type: str = "hybrid",
        max_pages: int = 3,
    ):
        """Initialize the Built In scraper.

        Args:
            keywords: Search query (e.g., 'data scientist')
            location: Optional city/state filter (e.g., 'Austin, TX')
            work_type: 'hybrid', 'onsite', or 'remote'
            max_pages: Maximum number of result pages to scrape
        """
        self.keywords = keywords
        self.location = location
        self.work_type = work_type
        self.max_pages = max_pages
        self.settings = get_settings()

    @property
    def source_name(self) -> str:
        return "builtin"

    def _generate_job_id(self, url: str) -> str:
        """Generate a stable job ID from the URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def _parse_location(self) -> tuple[str | None, str | None]:
        """Parse 'City, ST' into (city, full_state_name)."""
        if not self.location:
            return None, None
        parts = [p.strip() for p in self.location.split(",")]
        if len(parts) == 2:
            city = parts[0]
            state = self.STATE_ABBREVS.get(parts[1].upper(), parts[1])
            return city, state
        return self.location, None

    def _build_search_url(self, page: int = 1) -> str:
        """Build the Built In search URL using the correct path/param structure."""
        # Path: /jobs/remote, /jobs/hybrid/office, /jobs/office
        if self.work_type == "remote":
            path = "/jobs/remote"
        elif self.work_type == "hybrid":
            path = "/jobs/hybrid/office"
        else:  # onsite
            path = "/jobs/office"

        params = f"search={self.keywords.replace(' ', '+')}"

        city, state = self._parse_location()
        if city:
            params += f"&city={city.replace(' ', '+')}"
        if state:
            params += f"&state={state.replace(' ', '+')}"
        if city or state:
            params += "&country=USA&allLocations=true"

        if page > 1:
            params += f"&page={page}"

        return f"{self.BASE_URL}{path}?{params}"

    def _extract_listings_from_jsonld(self, html: str) -> list[dict]:
        """Extract job listings from schema.org JSON-LD ItemList."""
        soup = BeautifulSoup(html, "html.parser")
        jobs = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if data.get("@type") == "CollectionPage":
                    item_list = data.get("mainEntity", {})
                    if item_list.get("@type") == "ItemList":
                        for item in item_list.get("itemListElement", []):
                            url = item.get("url")
                            title = item.get("name")
                            description = item.get("description", "")
                            if url and title:
                                jobs.append({
                                    "url": url,
                                    "title": title,
                                    "description": description,
                                })
            except (json.JSONDecodeError, AttributeError):
                continue

        return jobs

    def _extract_detail_from_jsonld(self, html: str) -> dict:
        """Extract structured job data from a detail page's JSON-LD JobPosting."""
        soup = BeautifulSoup(html, "html.parser")
        result = {}

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if data.get("@type") == "JobPosting":
                    # Full description
                    result["description"] = data.get("description", "")

                    # Company
                    hiring_org = data.get("hiringOrganization", {})
                    result["company"] = hiring_org.get("name", "")

                    # Location
                    job_location = data.get("jobLocation", {})
                    address = job_location.get("address", {})
                    city = address.get("addressLocality", "")
                    state = address.get("addressRegion", "")
                    if city and state:
                        result["location"] = f"{city}, {state}"
                    elif city:
                        result["location"] = city

                    # Work type from jobLocationType
                    loc_type = data.get("jobLocationType", "")
                    if loc_type == "TELECOMMUTE":
                        result["work_type"] = "remote"

                    # Employment type hint
                    employment_type = data.get("employmentType", "")
                    if not result.get("work_type") and "remote" in employment_type.lower():
                        result["work_type"] = "remote"

                    # Salary
                    salary = data.get("baseSalary", {})
                    value = salary.get("value", {})
                    if isinstance(value, dict):
                        result["salary_min"] = value.get("minValue")
                        result["salary_max"] = value.get("maxValue")
                    elif isinstance(value, (int, float)):
                        result["salary_min"] = value
                        result["salary_max"] = value

                    break
            except (json.JSONDecodeError, AttributeError):
                continue

        return result

    def _extract_work_type_from_html(self, html: str) -> str | None:
        """Infer work type from page text when JSON-LD doesn't specify."""
        lower = html.lower()
        if "remote" in lower:
            return "remote"
        if "hybrid" in lower:
            return "hybrid"
        return None

    def _extract_company_from_html(self, html: str) -> str | None:
        """Fallback: extract company name from HTML if not in JSON-LD."""
        soup = BeautifulSoup(html, "html.parser")
        # Built In company links follow /company/<slug> pattern
        company_link = soup.find("a", href=re.compile(r"/company/[a-z0-9-]+"))
        if company_link:
            return company_link.get_text(strip=True)
        return None

    async def _fetch_job_detail(
        self, crawler: AsyncWebCrawler, url: str, crawl_config: CrawlerRunConfig
    ) -> dict:
        """Fetch and parse a job detail page."""
        try:
            result = await crawler.arun(url=url, config=crawl_config)
            if not result.success:
                logger.warning(f"Failed to fetch detail page: {url}")
                return {}

            detail = self._extract_detail_from_jsonld(result.html)

            # Fill gaps with HTML fallbacks
            if not detail.get("company"):
                detail["company"] = self._extract_company_from_html(result.html) or ""
            if not detail.get("work_type"):
                detail["work_type"] = self._extract_work_type_from_html(result.html)

            return detail

        except Exception as e:
            logger.warning(f"Error fetching detail for {url}: {e}")
            return {}

    async def scrape(self) -> AsyncIterator[JobCreate]:
        """Scrape Built In jobs for the configured query."""
        logger.info(
            f"Starting Built In scrape: keywords={self.keywords!r}, "
            f"location={self.location!r}, work_type={self.work_type!r}"
        )

        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # Built In is SSR — no JS hydration wait needed, but a small delay
        # helps ensure full page render on first load.
        listing_config = CrawlerRunConfig(delay_before_return_html=2.0)
        detail_config = CrawlerRunConfig(delay_before_return_html=1.5)

        seen_urls: set[str] = set()
        total_jobs = 0

        async with AsyncWebCrawler(config=browser_config) as crawler:
            for page in range(1, self.max_pages + 1):
                search_url = self._build_search_url(page)
                logger.info(f"Scraping Built In page {page}: {search_url}")

                if page > 1:
                    await asyncio.sleep(self.settings.scrape_delay_seconds * 2)

                result = await crawler.arun(url=search_url, config=listing_config)

                if not result.success:
                    logger.error(
                        f"Failed to crawl Built In page {page}: {result.error_message}"
                    )
                    break

                listings = self._extract_listings_from_jsonld(result.html)

                if not listings:
                    logger.info(f"No listings found on page {page}, stopping")
                    break

                logger.info(f"Found {len(listings)} listings on page {page}")
                page_new = 0

                for listing in listings:
                    url = listing["url"]
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    await asyncio.sleep(self.settings.scrape_delay_seconds)

                    detail = await self._fetch_job_detail(crawler, url, detail_config)

                    title = listing["title"]
                    company = detail.get("company") or "Unknown"
                    location = detail.get("location") or self.location or "Not specified"
                    description = detail.get("description") or listing.get("description", "")
                    salary_min = detail.get("salary_min")
                    salary_max = detail.get("salary_max")
                    work_type = detail.get("work_type")

                    # Infer work type from location string if still missing
                    if not work_type:
                        loc_lower = location.lower()
                        if "remote" in loc_lower:
                            work_type = "remote"
                        elif "hybrid" in loc_lower:
                            work_type = "hybrid"

                    job = JobCreate(
                        id=self._generate_job_id(url),
                        url=url,
                        source=self.source_name,
                        title=title,
                        company=company,
                        location=location,
                        description=description[:10000] if description else None,
                        salary_min=int(salary_min) if salary_min else None,
                        salary_max=int(salary_max) if salary_max else None,
                        work_type=work_type,
                    )

                    total_jobs += 1
                    page_new += 1
                    logger.info(f"Job {total_jobs}: {job.title} at {job.company}")
                    yield job

                logger.info(f"Yielded {page_new} new jobs from page {page}")

                # Built In shows ~25 per page; fewer means last page
                if len(listings) < 10:
                    break

        logger.info(f"Finished Built In scrape. Total jobs: {total_jobs}")
