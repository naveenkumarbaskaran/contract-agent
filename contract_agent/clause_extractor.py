"""ClauseExtractor: identify and extract standard contract sections from text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Clause:
    """A single extracted contract clause."""
    name: str
    raw_text: str
    start_pos: int
    end_pos: int
    confidence: str = "high"  # high | medium | low

    def summary(self, max_chars: int = 300) -> str:
        text = self.raw_text.strip()
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + " ..."


@dataclass
class ExtractionResult:
    """All clauses found in a contract document."""
    clauses: list[Clause] = field(default_factory=list)
    missing_standard: list[str] = field(default_factory=list)
    full_text: str = ""

    def get(self, clause_name: str) -> Optional[Clause]:
        name_lower = clause_name.lower()
        for c in self.clauses:
            if c.name.lower() == name_lower:
                return c
        return None

    def names(self) -> list[str]:
        return [c.name for c in self.clauses]


# ---------------------------------------------------------------------------
# Patterns for each standard clause type
# ---------------------------------------------------------------------------

# Each entry: (canonical_name, list_of_heading_patterns)
_CLAUSE_PATTERNS: list[tuple[str, list[str]]] = [
    (
        "Payment Terms",
        [
            r"payment\s+terms?",
            r"fees?\s+and\s+payment",
            r"compensation",
            r"invoic(?:e|ing)",
            r"billing",
        ],
    ),
    (
        "Termination",
        [
            r"termination",
            r"term\s+and\s+termination",
            r"cancellation",
            r"expiration\s+and\s+termination",
        ],
    ),
    (
        "Limitation of Liability",
        [
            r"limitation\s+of\s+liabilit(?:y|ies)",
            r"liability\s+limit(?:ation)?",
            r"exclusion\s+of\s+liabilit(?:y|ies)",
            r"cap\s+on\s+liabilit(?:y|ies)",
        ],
    ),
    (
        "Intellectual Property",
        [
            r"intellectual\s+property",
            r"ip\s+ownership",
            r"ownership\s+of\s+(?:work|ip|deliverables)",
            r"work\s+product",
            r"copyright",
            r"proprietary\s+rights",
        ],
    ),
    (
        "Confidentiality",
        [
            r"confidentialit(?:y|ies)",
            r"non-disclosure",
            r"nda",
            r"confidential\s+information",
        ],
    ),
    (
        "Indemnification",
        [
            r"indemnif(?:ication|y|ied|ies)",
            r"indemnit(?:y|ies)",
            r"hold\s+harmless",
        ],
    ),
    (
        "Governing Law",
        [
            r"governing\s+law",
            r"jurisdiction",
            r"applicable\s+law",
            r"choice\s+of\s+law",
            r"dispute\s+resolution",
        ],
    ),
    (
        "Force Majeure",
        [
            r"force\s+majeure",
            r"acts?\s+of\s+god",
            r"unforeseeable\s+circumstances",
        ],
    ),
    (
        "Warranties",
        [
            r"warranties?",
            r"representations?\s+and\s+warranties?",
            r"disclaimer\s+of\s+warranties?",
        ],
    ),
    (
        "Assignment",
        [
            r"assignment",
            r"transfer\s+of\s+rights",
            r"no\s+assignment",
        ],
    ),
    (
        "Entire Agreement",
        [
            r"entire\s+agreement",
            r"integration\s+clause",
            r"merger\s+clause",
        ],
    ),
    (
        "Amendment",
        [
            r"amendment(?:s|ment)?",
            r"modification(?:s)?",
            r"changes\s+to\s+(?:this\s+)?agreement",
        ],
    ),
]

# Clauses that are considered essential in a commercial contract
STANDARD_CLAUSES = {
    "Payment Terms",
    "Termination",
    "Limitation of Liability",
    "Intellectual Property",
    "Confidentiality",
    "Governing Law",
}


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class ClauseExtractor:
    """Rule-based extractor for standard contract clauses.

    Uses heading patterns to locate clause boundaries, then captures the
    body text until the next heading or end of document.
    """

    # A line is treated as a section heading if it is short (<= 120 chars),
    # contains no period (not a prose sentence), and matches a known pattern.
    _MAX_HEADING_LEN = 120

    def __init__(self) -> None:
        # Precompile a combined pattern per canonical clause name.
        self._compiled: list[tuple[str, re.Pattern[str]]] = []
        for name, patterns in _CLAUSE_PATTERNS:
            combined = "|".join(f"(?:{p})" for p in patterns)
            self._compiled.append(
                (name, re.compile(combined, re.IGNORECASE))
            )

        # Pattern to detect any heading-like line (numbered or uppercase)
        self._heading_detector = re.compile(
            r"^(?:\d+[\.)\s]+|[A-Z]{2,}|[A-Z][a-z]+(?:\s+[A-Z][a-z]*){0,4})\s*$"
            r"|^(?:\d+\.?\s+)[A-Z]",
            re.MULTILINE,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, text: str) -> ExtractionResult:
        """Extract all known clauses from *text* and report missing ones."""
        clauses: list[Clause] = []
        found_names: set[str] = set()

        # Split into lines, track character offsets
        lines = text.splitlines(keepends=True)
        line_starts = self._compute_line_starts(lines)

        # Find all candidate heading positions
        headings = self._find_headings(lines, line_starts)

        # For each heading, check if it matches a known clause
        for i, (heading_text, heading_start, heading_end) in enumerate(headings):
            for canonical_name, pattern in self._compiled:
                if canonical_name in found_names:
                    continue
                if pattern.search(heading_text):
                    # Body spans from end of this heading to start of next
                    if i + 1 < len(headings):
                        body_end = headings[i + 1][1]
                    else:
                        body_end = len(text)
                    body = text[heading_end:body_end].strip()
                    full_clause_text = heading_text.strip() + "\n" + body
                    clauses.append(
                        Clause(
                            name=canonical_name,
                            raw_text=full_clause_text,
                            start_pos=heading_start,
                            end_pos=body_end,
                        )
                    )
                    found_names.add(canonical_name)
                    break  # move to next heading

        missing = sorted(STANDARD_CLAUSES - found_names)
        return ExtractionResult(
            clauses=clauses,
            missing_standard=missing,
            full_text=text,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_line_starts(lines: list[str]) -> list[int]:
        starts = []
        pos = 0
        for line in lines:
            starts.append(pos)
            pos += len(line)
        return starts

    def _find_headings(
        self,
        lines: list[str],
        line_starts: list[int],
    ) -> list[tuple[str, int, int]]:
        """Return list of (heading_text, start_char, end_char) for candidate headings."""
        results = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            # Length guard
            if len(stripped) > self._MAX_HEADING_LEN:
                continue
            # Check if any known pattern matches the line
            is_heading = False
            for _, pattern in self._compiled:
                if pattern.search(stripped):
                    is_heading = True
                    break
            if not is_heading:
                continue
            start = line_starts[idx]
            end = start + len(line)
            results.append((stripped, start, end))
        return results
