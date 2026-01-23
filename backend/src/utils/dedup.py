"""Job deduplication utilities.

This module provides functions to detect duplicate job postings across
different sources by normalizing job data and computing similarity scores.
"""

import hashlib
import re
import unicodedata


# Common title variations to normalize
TITLE_SUBSTITUTIONS = [
    (r"\bsr\.?\b", "senior"),
    (r"\bjr\.?\b", "junior"),
    (r"\bmid-?level\b", "mid"),
    (r"\blead\b", "senior"),
    (r"\bprincipal\b", "senior"),
    (r"\bstaff\b", "senior"),
    (r"\bii+\b", ""),  # Remove Roman numerals like II, III
    (r"\b[ivx]+\b", ""),  # Remove I, II, III, IV, V, etc.
    (r"\b[123]\b", ""),  # Remove level numbers
    (r"\bml\b", "machine learning"),
    (r"\bai\b", "artificial intelligence"),
    (r"\bds\b", "data science"),
    (r"\bde\b", "data engineer"),
    (r"\bswe\b", "software engineer"),
    (r"\bengr\.?\b", "engineer"),
    (r"\bdev\.?\b", "developer"),
    (r"\bops\b", "operations"),
    (r"\bdevops\b", "devops"),
    (r"\bfull-?stack\b", "fullstack"),
    (r"\bfront-?end\b", "frontend"),
    (r"\bback-?end\b", "backend"),
]

# Company name variations to normalize
COMPANY_SUBSTITUTIONS = [
    (r"\binc\.?\b", ""),
    (r"\bincorporated\b", ""),
    (r"\bllc\.?\b", ""),
    (r"\bltd\.?\b", ""),
    (r"\blimited\b", ""),
    (r"\bcorp\.?\b", ""),
    (r"\bcorporation\b", ""),
    (r"\bco\.?\b", ""),
    (r"\bcompany\b", ""),
    (r"\bgroup\b", ""),
    (r"\bholdings\b", ""),
    (r"\binternational\b", ""),
    (r"\bglobal\b", ""),
    (r"\bthe\b", ""),
    (r"\b&\b", "and"),
    (r"\binsurance\b", ""),
    (r"\btechnologies?\b", ""),
    (r"\bsolutions?\b", ""),
    (r"\bservices?\b", ""),
    (r"\bsystems?\b", ""),
    (r"\bconsulting\b", ""),
    # Remove dashes/hyphens for companies like H-E-B
    (r"-", ""),
]

# Location normalization
LOCATION_SUBSTITUTIONS = [
    (r"\btx\b", "texas"),
    (r"\bca\b", "california"),
    (r"\bny\b", "new york"),
    (r",\s*usa?\b", ""),
    (r",\s*united states\b", ""),
    (r"\bremote\b.*", "remote"),  # Normalize all remote variations
    (r"\bhybrid\b.*", "hybrid"),
]


def normalize_text(text: str | None, substitutions: list[tuple[str, str]] | None = None) -> str:
    """Normalize text for comparison.

    - Convert to lowercase
    - Remove accents/diacritics
    - Remove special characters
    - Apply substitutions
    - Collapse whitespace

    Args:
        text: The text to normalize
        substitutions: Optional list of (pattern, replacement) tuples

    Returns:
        Normalized text string
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove accents/diacritics (e.g., café → cafe)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))

    # Apply substitutions
    if substitutions:
        for pattern, replacement in substitutions:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Remove special characters (keep alphanumeric and spaces)
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Collapse whitespace
    text = " ".join(text.split())

    return text.strip()


def normalize_title(title: str | None) -> str:
    """Normalize a job title for comparison."""
    return normalize_text(title, TITLE_SUBSTITUTIONS)


def normalize_company(company: str | None) -> str:
    """Normalize a company name for comparison."""
    result = normalize_text(company, COMPANY_SUBSTITUTIONS)
    # Remove all spaces for final comparison (handles H-E-B vs HEB)
    return result.replace(" ", "")


def normalize_location(location: str | None) -> str:
    """Normalize a location for comparison."""
    return normalize_text(location, LOCATION_SUBSTITUTIONS)


def generate_dedup_key(title: str | None, company: str | None, location: str | None = None) -> str:
    """Generate a deduplication key from job attributes.

    Creates a stable hash from normalized title + company (+ optional location).
    Same logical job from different sources should produce the same key.

    Args:
        title: Job title
        company: Company name
        location: Optional location (included if provided)

    Returns:
        16-character hex hash
    """
    norm_title = normalize_title(title)
    norm_company = normalize_company(company)

    # Create base key from title + company
    key_parts = [norm_title, norm_company]

    # Include location if it's meaningful (not empty, not just "remote")
    if location:
        norm_loc = normalize_location(location)
        # Only include specific locations, not generic ones
        if norm_loc and norm_loc not in ("remote", "hybrid", ""):
            # Extract just the city for comparison
            city = norm_loc.split()[0] if norm_loc else ""
            if city:
                key_parts.append(city)

    key_string = "|".join(key_parts)
    return hashlib.sha256(key_string.encode()).hexdigest()[:16]


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein (edit) distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def is_similar_title(title1: str | None, title2: str | None, threshold: float = 0.85) -> bool:
    """Check if two job titles are similar enough to be considered duplicates.

    Uses normalized Levenshtein similarity.

    Args:
        title1: First title
        title2: Second title
        threshold: Similarity threshold (0-1), default 0.85

    Returns:
        True if titles are similar enough
    """
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)

    if not norm1 or not norm2:
        return False

    # Exact match after normalization
    if norm1 == norm2:
        return True

    # Calculate similarity
    distance = levenshtein_distance(norm1, norm2)
    max_len = max(len(norm1), len(norm2))
    similarity = 1 - (distance / max_len)

    return similarity >= threshold


def find_duplicate_candidates(
    title: str | None,
    company: str | None,
    existing_jobs: list[dict],
    title_threshold: float = 0.85,
) -> list[dict]:
    """Find potential duplicate jobs from a list of existing jobs.

    Args:
        title: New job title
        company: New job company
        existing_jobs: List of existing job dicts with 'id', 'title', 'company' keys
        title_threshold: Similarity threshold for title matching

    Returns:
        List of potential duplicate job dicts
    """
    norm_company = normalize_company(company)
    candidates = []

    for job in existing_jobs:
        # Must be same company (after normalization)
        if normalize_company(job.get("company")) != norm_company:
            continue

        # Check title similarity
        if is_similar_title(title, job.get("title"), title_threshold):
            candidates.append(job)

    return candidates
