"""Utility modules for Canopy backend."""

from .dedup import generate_dedup_key, normalize_text, is_similar_title

__all__ = ["generate_dedup_key", "normalize_text", "is_similar_title"]
