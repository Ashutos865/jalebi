"""Dependency-free heuristic grammar checker.

Not Grammarly-class — it catches common mechanical errors (typos, repeated words,
spacing, capitalization, a/an) with correct offsets, so /api/check works with zero
infrastructure. Set JALEBI_LANGUAGETOOL_URL to swap in the LanguageTool engine for
thousands of professional rules.
"""
from __future__ import annotations

import re
from typing import List

from app.schemas.grammar import GrammarIssue

TYPOS = {
    "teh": "the", "recieve": "receive", "seperate": "separate",
    "definately": "definitely", "occured": "occurred", "wich": "which",
    "thier": "their", "becuase": "because", "untill": "until",
    "tommorow": "tomorrow", "adress": "address", "arguement": "argument",
    "calender": "calendar", "enviroment": "environment", "existance": "existence",
    "goverment": "government", "independant": "independent", "occassion": "occasion",
    "priviledge": "privilege", "recomend": "recommend", "refered": "referred",
    "succesful": "successful", "wierd": "weird", "accomodate": "accommodate",
    "publically": "publicly", "neccessary": "necessary", "gaurd": "guard",
}

# Wordy phrase → concise rewrite (clarity / conciseness).
WORDY = {
    "in order to": "to", "due to the fact that": "because",
    "for the purpose of": "to", "in the event that": "if",
    "in spite of the fact that": "although", "with regard to": "about",
    "with reference to": "about", "in the near future": "soon",
    "at this point in time": "now", "at the present time": "now",
    "a large number of": "many", "the majority of": "most",
    "a majority of": "most", "a number of": "several",
    "has the ability to": "can", "have the ability to": "can",
    "is able to": "can", "are able to": "can", "prior to": "before",
    "subsequent to": "after", "in the process of": "",
    "each and every": "every", "on a daily basis": "daily",
    "in a timely manner": "promptly", "take into consideration": "consider",
    "make a decision": "decide", "give consideration to": "consider",
    "in the course of": "during", "for the reason that": "because",
}

# Redundant phrase → trimmed form.
REDUNDANT = {
    "very unique": "unique", "most unique": "unique",
    "absolutely essential": "essential", "absolutely certain": "certain",
    "past history": "history", "past experience": "experience",
    "end result": "result", "final outcome": "outcome",
    "free gift": "gift", "advance planning": "planning",
    "close proximity": "proximity", "unexpected surprise": "surprise",
    "basic fundamentals": "fundamentals", "future plans": "plans",
    "added bonus": "bonus", "join together": "join",
    "completely eliminate": "eliminate", "brief summary": "summary",
}

# Filler / weakener words worth cutting for a crisper tone.
FILLERS = {"very", "really", "just", "quite", "actually", "basically",
           "literally", "simply", "totally", "definitely", "certainly"}


# Regions where punctuation rules must not fire: URLs, emails, and file-ish
# tokens. Inside these, a period with no following space is correct.
_PROTECTED = re.compile(
    r"https?://\S+|www\.\S+|\b[\w.+-]+@[\w-]+\.[\w.-]+\b|\b\w+\.(?:com|org|net|gov|edu|io|in|co)\b\S*",
    re.IGNORECASE,
)


def _protected_spans(text: str):
    return [(m.start(), m.end()) for m in _PROTECTED.finditer(text)]


# --- a/an: English picks the article by sound, not by letter ----------------

# Vowel-letter words that begin with a consonant sound: "a university", "a one-off".
_CONSONANT_SOUND_PREFIXES = (
    # "yoo-" sounds: university, unique, useful, usual, utility, ubiquitous,
    # unanimous, union, unit, uranium, urine, usage, utensil, euro, eulogy...
    "uni", "una", "use", "usa", "usu", "uti", "ute", "ubi", "ura", "uri",
    "eul", "eur", "ewe", "ufo",
    # "w-" sound: one, once
    "one", "once",
)
# Consonant-letter words that begin with a vowel sound: "an hour", "an heir".
_VOWEL_SOUND_PREFIXES = ("hour", "honest", "honour", "honor", "heir", "herb")
# Letters pronounced with a leading vowel, so an initialism takes "an":
# an FBI agent, an MP, an NGO, an X-ray.
_VOWEL_SOUND_LETTERS = set("AEFHILMNORSX")


def _starts_with_consonant_sound(word: str) -> bool:
    """True for vowel-spelled words that sound consonantal ("university")."""
    low = word.lower()
    return any(low.startswith(p) for p in _CONSONANT_SOUND_PREFIXES)


def _is_initialism(word: str) -> bool:
    """FBI, MP, NGO — read letter by letter, so the first letter's *name*
    decides the article. Excludes ordinary capitalised words like 'Ministry'."""
    stripped = word.rstrip(".,;:!?)")
    letters = [c for c in stripped if c.isalpha()]
    return len(letters) >= 2 and all(c.isupper() for c in letters)


def _starts_with_vowel_sound(word: str) -> bool:
    """True for consonant-spelled words that sound vocalic ("hour", "FBI")."""
    low = word.lower()
    if any(low.startswith(p) for p in _VOWEL_SOUND_PREFIXES):
        return True
    if _is_initialism(word) and word[0].upper() in _VOWEL_SOUND_LETTERS:
        return True
    return False


def _match_case(original: str, suggestion: str) -> str:
    if original[:1].isupper():
        return suggestion[:1].upper() + suggestion[1:]
    return suggestion


def _ctx(text: str, offset: int, length: int, pad: int = 24) -> str:
    a = max(0, offset - pad)
    b = min(len(text), offset + length + pad)
    return ("…" if a > 0 else "") + text[a:b] + ("…" if b < len(text) else "")


def check(text: str) -> List[GrammarIssue]:
    issues: List[GrammarIssue] = []

    def add(offset, length, message, repl, severity, short="", rule=""):
        issues.append(GrammarIssue(
            offset=offset, length=length, message=message, short=short,
            replacements=repl, severity=severity, rule=rule,
            category=severity.capitalize(), context=_ctx(text, offset, length),
        ))

    # Common misspellings.
    for m in re.finditer(r"\b\w+\b", text):
        low = m.group(0).lower()
        if low in TYPOS:
            add(m.start(), len(m.group(0)), f"Possible spelling mistake: “{m.group(0)}”.",
                [_match_case(m.group(0), TYPOS[low])], "spelling", "Spelling", "TYPO")

    # Repeated words ("the the").
    for m in re.finditer(r"\b(\w+)(\s+)(\1)\b", text, re.I):
        add(m.start(), len(m.group(0)),
            f"Repeated word: “{m.group(1)}”.", [m.group(1)], "grammar",
            "Repetition", "REPEATED_WORD")

    # Double+ spaces.
    for m in re.finditer(r"  +", text):
        add(m.start(), len(m.group(0)), "Multiple consecutive spaces.", [" "],
            "punctuation", "Whitespace", "DOUBLE_SPACE")

    # Space before punctuation. [ \t]+ not \s+: \s matches newlines, so applying
    # the fix across a line break replaced the break with the punctuation mark
    # and silently deleted the writer's paragraph structure.
    for m in re.finditer(r"[ \t]+([,.!?;:])", text):
        add(m.start(), len(m.group(0)), "Remove the space before the punctuation.",
            [m.group(1)], "punctuation", "Whitespace", "SPACE_BEFORE_PUNCT")

    # Missing space after sentence punctuation. Skipped inside URLs, emails and
    # decimals, where the absence of a space is correct: "commerce.gov.in" and
    # "12.7%" were both reported as errors, and applying the fix broke the link.
    url_spans = _protected_spans(text)
    for m in re.finditer(r"(?<!\d)([,.!?;:])([A-Za-z])", text):
        if any(start <= m.start() < end for start, end in url_spans):
            continue
        add(m.start(), len(m.group(0)), "Add a space after the punctuation.",
            [f"{m.group(1)} {m.group(2)}"], "punctuation", "Whitespace",
            "MISSING_SPACE_AFTER_PUNCT")

    # Standalone lowercase "i".
    for m in re.finditer(r"(?<![\w'])i(?![\w'])", text):
        add(m.start(), 1, "The pronoun “I” should be capitalized.", ["I"],
            "grammar", "Capitalization", "LOWERCASE_I")

    # Sentence not starting with a capital (after . ! ?).
    for m in re.finditer(r"([.!?])(\s+)([a-z])", text):
        letter = m.group(3)
        pos = m.start(3)
        add(pos, 1, "Sentences should start with a capital letter.",
            [letter.upper()], "grammar", "Capitalization", "SENT_START_CAP")

    # a/an agreement. English selects the article by *sound*, not spelling, so a
    # letter test alone flags correct English: "a university", "a European",
    # "an hour", "an FBI agent" were all reported as errors.
    for m in re.finditer(r"\b(a)\s+([aeiouAEIOU]\w+)", text):
        if _starts_with_consonant_sound(m.group(2)):
            continue                      # "a university", "a one-off", "a European"
        add(m.start(1), 1, "Use “an” before a word starting with a vowel sound.",
            [_match_case(m.group(1), "an")], "grammar", "Agreement", "A_AN")
    for m in re.finditer(r"\b(an)\s+([b-df-hj-np-tv-zB-DF-HJ-NP-TV-Z]\w+)", text):
        if _starts_with_vowel_sound(m.group(2)):
            continue                      # "an hour", "an FBI agent", "an MP"
        add(m.start(1), 2, "Use “a” before a word starting with a consonant sound.",
            [_match_case(m.group(1), "a")], "grammar", "Agreement", "A_AN")

    # ── tone / clarity / conciseness ────────────────────────────────────────
    # Wordy phrases → concise rewrite.
    for phrase, concise in WORDY.items():
        for m in re.finditer(rf"\b{re.escape(phrase)}\b", text, re.I):
            add(m.start(), len(m.group(0)),
                f"Wordy — try “{concise}”." if concise else "Wordy — this phrase can be cut.",
                [_match_case(m.group(0), concise)], "style", "Conciseness", "WORDY")

    # Redundant phrases → trimmed form.
    for phrase, trimmed in REDUNDANT.items():
        for m in re.finditer(rf"\b{re.escape(phrase)}\b", text, re.I):
            add(m.start(), len(m.group(0)),
                f"Redundant — “{trimmed}” already says it.",
                [_match_case(m.group(0), trimmed)], "style", "Clarity", "REDUNDANT")

    # Filler words that weaken the sentence.
    for m in re.finditer(r"\b(" + "|".join(FILLERS) + r")\b", text, re.I):
        add(m.start(), len(m.group(0)),
            f"Filler — “{m.group(0)}” usually adds little. Consider removing it.",
            [""], "style", "Tone", "FILLER")

    # Passive voice (conservative: be-verb + past participle). No auto-fix — a
    # rewrite depends on the actor, so we flag rather than guess.
    for m in re.finditer(
        r"\b(?:is|are|was|were|be|been|being)\s+(\w+ed)\b", text, re.I
    ):
        add(m.start(), len(m.group(0)),
            "Passive voice — consider an active construction for a stronger tone.",
            [], "style", "Tone", "PASSIVE")

    # Drop duplicate/overlapping identical suggestions (e.g. two rules both
    # capitalizing the same "i").
    seen = set()
    unique: List[GrammarIssue] = []
    for i in sorted(issues, key=lambda x: (x.offset, x.length)):
        key = (i.offset, i.length, tuple(i.replacements))
        if key not in seen:
            seen.add(key)
            unique.append(i)

    # Suppress an issue fully contained within a longer actionable fix, so a phrase
    # like "very unique" shows one "→ unique" suggestion, not that plus a "very" cut.
    def contained(a: GrammarIssue) -> bool:
        a_end = a.offset + a.length
        for b in unique:
            if b is a or not b.replacements:
                continue
            b_end = b.offset + b.length
            if b.offset <= a.offset and b_end >= a_end and b.length > a.length:
                return True
        return False

    return [i for i in unique if not contained(i)]
