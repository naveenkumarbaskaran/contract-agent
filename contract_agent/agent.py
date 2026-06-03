"""ContractAgent: AI-powered contract analysis using the Anthropic SDK.

Tools exposed to Claude:
  - read_pdf_text(path)        — extract raw text from a PDF
  - read_file(path)            — read any plain-text file
  - write_file(path, content)  — write text to a file

The agent:
  1. Reads the contract (and optional template) via tools.
  2. Extracts key clauses with ClauseExtractor.
  3. Uses Claude (claude-sonnet-4-6) to flag unusual terms and compare
     against the template.
  4. Returns a structured risk report.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import anthropic

from .clause_extractor import ClauseExtractor, ExtractionResult

# ---------------------------------------------------------------------------
# Tool helpers
# ---------------------------------------------------------------------------

def _read_pdf_text(path: str) -> str:
    """Extract all text from a PDF file using pypdf."""
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is required to read PDF files. "
            "Install it with: pip install pypdf"
        ) from exc

    reader = PdfReader(path)
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        parts.append(text)
    return "\n".join(parts)


def _read_file(path: str) -> str:
    """Read a plain-text file and return its contents."""
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _write_file(path: str, content: str) -> str:
    """Write *content* to *path*, creating parent directories as needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written {len(content)} characters to {path}"


# Map tool name -> callable for dispatch
_TOOL_DISPATCH: dict[str, Any] = {
    "read_pdf_text": lambda args: _read_pdf_text(args["path"]),
    "read_file": lambda args: _read_file(args["path"]),
    "write_file": lambda args: _write_file(args["path"], args["content"]),
}

# ---------------------------------------------------------------------------
# Tool definitions (JSON Schema)
# ---------------------------------------------------------------------------

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "read_pdf_text",
        "description": (
            "Extract and return all text from a PDF file at the given path. "
            "Use this to read contract PDFs before analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative filesystem path to the PDF file.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read the contents of a plain-text file (e.g. .txt, .md). "
            "Use this to read non-PDF contracts or templates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative filesystem path to the text file.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write text content to a file. Use this to save the final risk report "
            "or any intermediate analysis notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Destination file path (will be created if it does not exist).",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write into the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert contract analyst with deep knowledge of commercial, employment,
and software licensing agreements.

Your job:
1. Use the provided tools to read the contract file (and template if supplied).
2. Carefully review the full contract text.
3. Produce a detailed risk report in Markdown covering:
   a. **Executive Summary** — one-paragraph overview of the contract and overall risk level
      (Low / Medium / High / Critical).
   b. **Key Clauses Identified** — for each of: Payment Terms, Termination, Limitation of
      Liability, Intellectual Property, Confidentiality, Indemnification, Governing Law,
      Force Majeure, Warranties, Assignment, Entire Agreement, Amendment — state:
      - Whether the clause is present
      - A concise summary of what it says
      - Any immediate concern or red flag
   c. **Unusual or Risky Terms** — a bulleted list of clauses, phrases, or omissions that
      deviate from standard commercial practice. For each, explain why it is unusual and
      what the risk is.
   d. **Template Comparison** (only if a template was provided) — for each key clause,
      note whether the contract matches, deviates from, or is missing relative to the
      template, and assess the significance of any deviation.
   e. **Missing Standard Clauses** — list any clauses typically expected in this type of
      contract that are absent.
   f. **Recommendations** — prioritised action items for the reviewing party.

Be precise. Quote specific contract language when flagging risks. Do not invent facts.
If a section is missing, say so explicitly.

When you have finished the analysis, use the write_file tool to save the risk report
to the output path provided in the user message, then confirm that you have done so.
"""


# ---------------------------------------------------------------------------
# ContractAgent
# ---------------------------------------------------------------------------

class ContractAgent:
    """Orchestrates contract analysis via Claude and local tools."""

    MODEL = "claude-sonnet-4-6"
    MAX_TOKENS = 8192

    def __init__(self, api_key: str | None = None) -> None:
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self._extractor = ClauseExtractor()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        contract_path: str,
        template_path: str | None = None,
        output_path: str = "risk-report.md",
    ) -> str:
        """Analyse *contract_path* against an optional *template_path*.

        Returns the Markdown risk-report text and writes it to *output_path*.
        """
        # Pre-extract clauses with the rule-based extractor so we can
        # embed structured metadata in the user prompt for Claude.
        contract_text = self._load_text(contract_path)
        extraction: ExtractionResult = self._extractor.extract(contract_text)

        template_info = ""
        if template_path:
            template_text = self._load_text(template_path)
            template_extraction = self._extractor.extract(template_text)
            template_info = (
                f"\n\nA baseline template has been provided at: {template_path}\n"
                f"Template clauses found: {', '.join(template_extraction.names()) or 'none detected'}\n"
                f"Template missing standard clauses: {', '.join(template_extraction.missing_standard) or 'none'}\n"
            )

        user_message = (
            f"Please analyse the contract located at: {contract_path}\n"
            f"Save the risk report to: {output_path}\n"
            f"{template_info}"
            f"\n--- Pre-extracted clause summary (rule-based) ---\n"
            f"Clauses detected: {', '.join(extraction.names()) or 'none'}\n"
            f"Missing standard clauses: {', '.join(extraction.missing_standard) or 'none'}\n"
            f"\nProceed with a full analysis."
        )

        report_text = self._run_agent_loop(user_message)
        return report_text

    def compare(
        self,
        contract1_path: str,
        contract2_path: str,
        output_path: str = "comparison-report.md",
    ) -> str:
        """Compare two contracts side-by-side and write a comparison report."""
        user_message = (
            f"Please compare the following two contracts:\n"
            f"  Contract 1: {contract1_path}\n"
            f"  Contract 2: {contract2_path}\n\n"
            f"For each key clause type (Payment Terms, Termination, Limitation of "
            f"Liability, Intellectual Property, Confidentiality, Indemnification, "
            f"Governing Law, Force Majeure, Warranties, Assignment), compare what "
            f"each contract says, highlight material differences, and assess which "
            f"contract is more favourable to the reviewing party and why.\n\n"
            f"Save the comparison report (in Markdown) to: {output_path}\n"
            f"Then confirm that you have saved it."
        )
        return self._run_agent_loop(user_message)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_text(self, path: str) -> str:
        """Load text from a PDF or plain-text file (local, no API call)."""
        if path.lower().endswith(".pdf"):
            return _read_pdf_text(path)
        return _read_file(path)

    def _run_agent_loop(self, user_message: str) -> str:
        """Run the Claude tool-use agentic loop and return the final text output."""
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_message}
        ]

        final_text = ""

        while True:
            response = self._client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                tools=_TOOLS,  # type: ignore[arg-type]
                messages=messages,
            )

            # Collect any text blocks from this turn
            for block in response.content:
                if block.type == "text":
                    final_text = block.text  # keep last substantive text

            # Stop if Claude is done
            if response.stop_reason == "end_turn":
                break

            if response.stop_reason != "tool_use":
                # Unexpected stop; break to avoid infinite loop
                break

            # Execute all tool calls and collect results
            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tool_result = self._execute_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result,
                    }
                )

            # Append assistant turn + tool results as user turn
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        return final_text

    def _execute_tool(self, name: str, inputs: dict[str, Any]) -> str:
        """Dispatch a tool call and return the result as a string."""
        handler = _TOOL_DISPATCH.get(name)
        if handler is None:
            return f"Error: unknown tool '{name}'"
        try:
            result = handler(inputs)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return f"Error executing {name}: {exc}"
