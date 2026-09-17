"""TIES Content SOP header-block parsing and document splitting."""
from __future__ import annotations

from app.scoring import sop_header

FULL = """WRITING FOR: TIES Website
HEADING: India's export surge
SUB-HEADING: What the FY24 numbers hide
AUTHOR'S NAME: A Writer
AUTHOR'S INSTAGRAM ID: @awriter
EDITOR'S NAME: An Editor
DATE OF ASSIGNMENT: 01/09/2026
DATE OF SUBMISSION: 02/09/2026
DATE OF EDITING: 03/09/2026

(YOUR CONTENT STARTS HERE)

India's merchandise exports rose 12.7% in FY24, according to Ministry data.
The gain was led by electronics.

FOOTNOTES / LINKS TO ALL YOUR REFERENCES
https://commerce.gov.in/report
https://rbi.org.in/data
"""


# --- happy path -------------------------------------------------------------

def test_parses_all_nine_fields():
    h = sop_header.parse(FULL)
    assert h.present
    assert h.get("writing_for") == "TIES Website"
    assert h.get("heading") == "India's export surge"
    assert h.get("sub_heading") == "What the FY24 numbers hide"
    assert h.get("author_name") == "A Writer"
    assert h.get("author_instagram") == "@awriter"
    assert h.get("editor_name") == "An Editor"
    assert h.get("date_of_assignment") == "01/09/2026"
    assert h.get("date_of_submission") == "02/09/2026"
    assert h.get("date_of_editing") == "03/09/2026"
    assert h.missing == [] and h.complete


def test_body_excludes_header_and_references():
    h = sop_header.parse(FULL)
    assert h.body.startswith("India's merchandise exports")
    assert "WRITING FOR" not in h.body
    assert "AUTHOR'S NAME" not in h.body
    assert "FOOTNOTES" not in h.body
    assert "commerce.gov.in" not in h.body


def test_references_captured_with_urls():
    h = sop_header.parse(FULL)
    assert h.has_references
    assert h.reference_urls == [
        "https://commerce.gov.in/report",
        "https://rbi.org.in/data",
    ]


def test_content_marker_detected():
    assert sop_header.parse(FULL).has_content_marker


# --- the correctness fix ----------------------------------------------------

def test_scoring_text_strips_metadata():
    """Header words must not count toward the article, or the 300-350 SOP
    window is measured against the wrong text."""
    scored = sop_header.scoring_text(FULL)
    assert "India's merchandise exports" in scored
    assert "AUTHOR'S INSTAGRAM ID" not in scored
    assert len(scored.split()) < len(FULL.split())


def test_non_sop_document_is_untouched():
    """Documents without a header must grade exactly as before."""
    plain = "Just an ordinary article with no SOP header at all. It has prose."
    assert sop_header.scoring_text(plain) == plain
    assert sop_header.parse(plain).present is False


# --- real-world messiness ---------------------------------------------------

def test_tolerates_case_curly_apostrophes_and_bold_markers():
    messy = (
        "**Writing For:** Substack\n"
        "**Heading:** A title\n"
        "Author’s Name: Someone\n"
        "AUTHOR’S INSTAGRAM ID: @someone\n"
        "(your content starts here)\n\n"
        "Body text here."
    )
    h = sop_header.parse(messy)
    assert h.present and h.has_content_marker
    assert h.get("writing_for") == "Substack"
    assert h.get("author_name") == "Someone"
    assert h.body == "Body text here."


def test_unfilled_placeholder_counts_as_missing():
    """A pasted-but-unfilled '[TIES Website / Substack / ...]' is not an answer."""
    doc = (
        "WRITING FOR: [TIES Website / Substack / LinkedIn / Main Page]\n"
        "HEADING: Real title\n"
        "SUB-HEADING: Real sub\n"
        "AUTHOR'S NAME: Writer\n"
        "(YOUR CONTENT STARTS HERE)\n\nBody."
    )
    h = sop_header.parse(doc)
    assert "WRITING FOR" in h.missing
    assert not h.complete


def test_blank_field_is_missing_not_empty_string():
    doc = (
        "WRITING FOR: TIES Website\nHEADING: T\nSUB-HEADING: S\n"
        "AUTHOR'S NAME: W\nAUTHOR'S INSTAGRAM ID:\n"
        "(YOUR CONTENT STARTS HERE)\n\nBody."
    )
    h = sop_header.parse(doc)
    assert "AUTHOR'S INSTAGRAM ID" in h.missing


def test_editor_fields_tracked_separately():
    """An author cannot fill the editor's fields at drafting time."""
    doc = (
        "WRITING FOR: TIES Website\nHEADING: T\nSUB-HEADING: S\n"
        "AUTHOR'S NAME: W\nAUTHOR'S INSTAGRAM ID: @w\n"
        "DATE OF ASSIGNMENT: 01/09/2026\nDATE OF SUBMISSION: 02/09/2026\n"
        "(YOUR CONTENT STARTS HERE)\n\nBody."
    )
    h = sop_header.parse(doc)
    assert h.missing == []                       # author did their part
    assert "EDITOR'S NAME" in h.missing_editor
    assert "DATE OF EDITING" in h.missing_editor
    assert h.complete                            # not blocked on the editor


def test_heading_word_inside_article_is_not_a_header():
    """A 'heading:' line mid-article must not be mistaken for the SOP block."""
    doc = "An article discussing layout.\n\nheading: and this is prose about it.\n"
    assert sop_header.parse(doc).present is False


def test_accepts_plain_references_heading():
    doc = (
        "WRITING FOR: TIES Website\nHEADING: T\nSUB-HEADING: S\n"
        "(YOUR CONTENT STARTS HERE)\n\nBody text.\n\nReferences\nhttps://x.gov.in/a\n"
    )
    h = sop_header.parse(doc)
    assert h.has_references and h.reference_urls == ["https://x.gov.in/a"]
    assert h.body == "Body text."


def test_header_without_content_marker_still_splits():
    doc = (
        "WRITING FOR: TIES Website\nHEADING: T\nSUB-HEADING: S\n"
        "AUTHOR'S NAME: W\n\nThe article begins here without a marker.\n"
    )
    h = sop_header.parse(doc)
    assert h.present and not h.has_content_marker
    assert h.body.startswith("The article begins here")


def test_empty_input_is_safe():
    h = sop_header.parse("")
    assert not h.present and h.body == ""
    assert sop_header.scoring_text("") == ""


# --- end-to-end: the header must not change the score -----------------------

def test_header_does_not_change_the_score_or_word_count():
    """The correctness fix. Before this, a compliant header added 64 words and
    6 points: sourcing fell (bare URLs diluted the signal) while headline rose
    (the 'HEADING:' line satisfied the headline check)."""
    import asyncio

    from app.pipeline.hybrid_evaluator import HybridEvaluator
    from app.schemas.evaluation import ContentType, EvaluationRequest

    body = (
        "India's merchandise exports rose 12.7% in FY24, according to Ministry of "
        "Commerce data. The gain was led by electronics, a sector that barely "
        "registered a decade ago. Analysts at the RBI note the strategic shift was "
        "supported by the PLI scheme. Economists caution that global demand remains "
        "uncertain going into the next cycle. "
    ) * 6
    refs = (
        "\n\nFOOTNOTES / LINKS TO ALL YOUR REFERENCES\n"
        "https://commerce.gov.in/r\nhttps://rbi.org.in/d\n"
    )
    header = FULL.split("(YOUR CONTENT STARTS HERE)")[0] + "(YOUR CONTENT STARTS HERE)\n\n"

    ev = HybridEvaluator(client=None, provider="mock", model="")

    def run(text: str):
        return asyncio.run(
            ev.evaluate(
                EvaluationRequest(
                    text=text,
                    content_type=ContentType.analysis,
                    title="India's export surge",
                )
            )
        )

    plain = run(body)
    with_header = run(header + body + refs)

    assert with_header.overall_score == plain.overall_score
    assert with_header.meta.word_count == plain.meta.word_count


# --- WRITING FOR validation -------------------------------------------------

def test_writing_for_choices():
    for good in ("TIES Website", "substack", "LinkedIn", "Main Page"):
        assert sop_header.writing_for_is_valid(good), good
    for bad in ("Medium", "my blog", ""):
        assert not sop_header.writing_for_is_valid(bad), bad
