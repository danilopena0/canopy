"""Required keyword tests — assert that critical instructions exist in prompt templates.

These are static assertions on the template strings themselves (no LLM call, no
rendering). A keyword missing from a prompt means the model was never told about
it, regardless of how plausible the output looks.
"""

from src.services.scorer import SCORING_SYSTEM_PROMPT, SCORING_USER_PROMPT
from src.services.cover import COVER_SYSTEM_PROMPT, COVER_USER_PROMPT
from src.services.resume import TAILOR_SYSTEM_PROMPT, TAILOR_USER_PROMPT
from src.services.project_matcher import SYSTEM_PROMPT as PM_SYSTEM_PROMPT
from src.services.project_matcher import USER_PROMPT as PM_USER_PROMPT


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

def test_scorer_user_prompt_has_point_total():
    """Rubric must state the 100-point ceiling so the model calibrates scores."""
    assert "100" in SCORING_USER_PROMPT


def test_scorer_user_prompt_has_dealbreaker_instruction():
    """Dealbreaker logic must be explicit — it's a hard business rule."""
    assert "dealbreaker" in SCORING_USER_PROMPT.lower()


def test_scorer_user_prompt_has_zero_on_dealbreaker():
    """Score must explicitly be set to 0 when a dealbreaker fires."""
    assert "0" in SCORING_USER_PROMPT
    assert "dealbreaker" in SCORING_USER_PROMPT.lower()


def test_scorer_user_prompt_has_all_rubric_categories():
    required = ["Title", "Skills", "Location", "Salary", "Experience"]
    for category in required:
        assert category in SCORING_USER_PROMPT, f"Rubric category '{category}' missing from scorer prompt"


def test_scorer_user_prompt_requires_json_keys():
    """All expected output keys must be named in the prompt."""
    required_keys = ["score", "rationale", "matching_skills", "missing_skills", "dealbreaker_triggered"]
    for key in required_keys:
        assert f'"{key}"' in SCORING_USER_PROMPT, f"JSON key '{key}' not documented in scorer prompt"


def test_scorer_system_prompt_discourages_inflation():
    """System prompt must tell the model not to inflate scores."""
    text = SCORING_SYSTEM_PROMPT.lower()
    assert "inflate" in text or "honest" in text or "precise" in text


# ---------------------------------------------------------------------------
# Cover letter
# ---------------------------------------------------------------------------

def test_cover_user_prompt_has_word_count_guidance():
    """Without word count guidance the model produces wildly varying lengths."""
    assert "300" in COVER_USER_PROMPT or "400" in COVER_USER_PROMPT


def test_cover_user_prompt_requires_opening_hook():
    assert "hook" in COVER_USER_PROMPT.lower() or "open" in COVER_USER_PROMPT.lower()


def test_cover_user_prompt_requires_call_to_action():
    assert "call to action" in COVER_USER_PROMPT.lower() or "closing" in COVER_USER_PROMPT.lower()


def test_cover_user_prompt_requires_json_keys():
    assert '"cover_letter"' in COVER_USER_PROMPT
    assert '"tone_used"' in COVER_USER_PROMPT


def test_cover_system_prompt_stresses_personalization():
    text = COVER_SYSTEM_PROMPT.lower()
    assert "personalized" in text or "tailored" in text


def test_cover_system_prompt_requires_professional_output():
    assert "professional" in COVER_SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# Resume tailor
# ---------------------------------------------------------------------------

def test_tailor_user_prompt_mentions_keyword_optimization():
    """Keyword instruction is what gets resumes past ATS filters."""
    assert "keyword" in TAILOR_USER_PROMPT.lower()


def test_tailor_user_prompt_requires_json_keys():
    assert '"tailored_resume"' in TAILOR_USER_PROMPT
    assert '"highlights"' in TAILOR_USER_PROMPT


def test_tailor_system_prompt_prohibits_fabrication():
    text = TAILOR_SYSTEM_PROMPT.lower()
    assert "fabricat" in text or "truthful" in text or "never" in text


def test_tailor_system_prompt_specifies_markdown_output():
    assert "markdown" in TAILOR_SYSTEM_PROMPT.lower()


def test_tailor_user_prompt_asks_for_highlights():
    """The 3-5 highlights are what agents surface for interview prep."""
    assert "highlight" in TAILOR_USER_PROMPT.lower()


# ---------------------------------------------------------------------------
# Project matcher
# ---------------------------------------------------------------------------

def test_project_matcher_user_prompt_requires_star_format():
    assert "STAR" in PM_USER_PROMPT


def test_project_matcher_user_prompt_requires_lead_project():
    """Lead project is the single most important output for interview openers."""
    assert "lead" in PM_USER_PROMPT.lower()


def test_project_matcher_user_prompt_requires_skill_gaps():
    assert "skill gap" in PM_USER_PROMPT.lower() or "skill_gaps" in PM_USER_PROMPT


def test_project_matcher_user_prompt_requires_json_keys():
    required = ['"lead_project"', '"projects"', '"skill_gaps"']
    for key in required:
        assert key in PM_USER_PROMPT, f"JSON key {key} missing from project matcher prompt"


def test_project_matcher_user_prompt_requires_reframe():
    """Reframe guidance is what makes gaps actionable in interviews."""
    assert "reframe" in PM_USER_PROMPT.lower()


def test_project_matcher_system_prompt_names_the_role():
    """System prompt should name a concrete persona, not be generic."""
    text = PM_SYSTEM_PROMPT.lower()
    assert "career" in text or "coach" in text or "data scientist" in text
