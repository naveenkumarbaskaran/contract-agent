# contract-agent-ai

An AI-powered contract analysis agent built with the [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) and `claude-sonnet-4-6`. It extracts key clauses, flags unusual or risky terms, and compares contracts against a baseline template.

## Features

- **Clause extraction** — rule-based `ClauseExtractor` identifies Payment Terms, Termination, Limitation of Liability, Intellectual Property, Confidentiality, Indemnification, Governing Law, Force Majeure, Warranties, Assignment, Entire Agreement, and Amendment clauses.
- **AI risk analysis** — Claude reads the full contract via tool use and produces a structured Markdown risk report with executive summary, clause-by-clause review, unusual terms, and prioritised recommendations.
- **Template comparison** — supply a baseline template PDF or text file; the agent highlights deviations and assesses their significance.
- **Side-by-side comparison** — compare two contracts directly to understand material differences.
- **CLI** — ergonomic `contract-agent` command with Rich-formatted terminal output and Markdown preview.
- **PDF and plain-text support** — contracts can be `.pdf`, `.txt`, or `.md`.

## Installation

```bash
pip install contract-agent-ai
```

Or install from source:

```bash
git clone https://github.com/example/contract-agent-ai
cd contract-agent-ai
pip install -e .
```

## Quick Start

### Set your API key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Analyse a contract

```bash
contract-agent analyze contract.pdf
```

The risk report is saved to `risk-report.md` by default and printed to the terminal.

### Analyse with a baseline template

```bash
contract-agent analyze contract.pdf --template template.pdf --output risk-report.md
```

### Compare two contracts

```bash
contract-agent compare contract1.pdf contract2.pdf
contract-agent compare contract1.pdf contract2.pdf --output comparison.md
```

### Suppress terminal preview

```bash
contract-agent analyze contract.pdf --no-preview
```

## CLI Reference

```
Usage: contract-agent [OPTIONS] COMMAND [ARGS]...

  Contract Agent — AI-powered contract analysis and risk assessment.

Commands:
  analyze  Analyse CONTRACT_FILE and produce a risk report.
  compare  Compare CONTRACT_1 and CONTRACT_2 side-by-side.
```

### `analyze`

```
Usage: contract-agent analyze [OPTIONS] CONTRACT_FILE

  Analyse CONTRACT_FILE and produce a risk report.

Options:
  -t, --template TEMPLATE_FILE  Baseline template to compare against.
  -o, --output OUTPUT_FILE      Output path for the Markdown report.  [default: risk-report.md]
  --api-key TEXT                Anthropic API key.  [env var: ANTHROPIC_API_KEY]
  --no-preview                  Do not print the report to the terminal.
  --help                        Show this message and exit.
```

### `compare`

```
Usage: contract-agent compare [OPTIONS] CONTRACT_1 CONTRACT_2

  Compare CONTRACT_1 and CONTRACT_2 side-by-side.

Options:
  -o, --output OUTPUT_FILE      Output path for the Markdown report.  [default: comparison-report.md]
  --api-key TEXT                Anthropic API key.  [env var: ANTHROPIC_API_KEY]
  --no-preview                  Do not print the report to the terminal.
  --help                        Show this message and exit.
```

## Python API

```python
from contract_agent import ContractAgent

agent = ContractAgent()  # reads ANTHROPIC_API_KEY from environment

# Analyse a single contract
report = agent.analyze(
    contract_path="contract.pdf",
    template_path="template.pdf",   # optional
    output_path="risk-report.md",
)
print(report)

# Compare two contracts
comparison = agent.compare(
    contract1_path="contract1.pdf",
    contract2_path="contract2.pdf",
    output_path="comparison.md",
)
print(comparison)
```

### Using `ClauseExtractor` directly

If you only need the rule-based clause extractor (no API calls):

```python
from contract_agent import ClauseExtractor

extractor = ClauseExtractor()
result = extractor.extract(open("contract.txt").read())

for clause in result.clauses:
    print(f"[{clause.name}] {clause.summary()}")

if result.missing_standard:
    print("Missing standard clauses:", ", ".join(result.missing_standard))
```

## Architecture

```
contract_agent/
  __init__.py         — public exports
  agent.py            — ContractAgent: Claude tool-use agentic loop
  clause_extractor.py — ClauseExtractor: regex-based clause detector
  cli.py              — Click CLI with Rich output
```

### Agent tool loop

`ContractAgent` uses the Anthropic SDK's standard tool-use pattern:

1. The user message tells Claude the contract path and output path.
2. Claude calls `read_pdf_text` or `read_file` to get the contract text.
3. If a template was supplied, Claude reads that too.
4. Claude reasons over the full text and writes the report with `write_file`.
5. The loop ends when `stop_reason == "end_turn"`.

Three tools are available to Claude:

| Tool | Description |
|------|-------------|
| `read_pdf_text(path)` | Extract text from a PDF using pypdf |
| `read_file(path)` | Read a plain-text file |
| `write_file(path, content)` | Write text to a file |

## Risk Report Structure

The generated Markdown report contains:

1. **Executive Summary** — overall risk level (Low / Medium / High / Critical)
2. **Key Clauses Identified** — presence, summary, and red flags for each standard clause
3. **Unusual or Risky Terms** — deviations from standard commercial practice with quoted language
4. **Template Comparison** — clause-level diff against the baseline (when template provided)
5. **Missing Standard Clauses** — clauses expected but absent
6. **Recommendations** — prioritised action items

## Requirements

- Python 3.10+
- `anthropic >= 0.40.0`
- `click >= 8.1`
- `rich >= 13.0`
- `pypdf >= 4.0`

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (required) |

## License

MIT
