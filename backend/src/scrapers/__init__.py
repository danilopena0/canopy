"""Scrapers module for job boards and company career pages."""

from .base import BaseScraper
from .heb import HEBScraper

__all__ = ["BaseScraper", "HEBScraper"]
