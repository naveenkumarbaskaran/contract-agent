"""Command-line interface for contract-agent.

Usage examples:

  # Analyse a contract and write risk-report.md
  contract-agent analyze contract.pdf

  # Analyse with a baseline template
  contract-agent analyze contract.pdf --template template.pdf --output risk-report.md

  # Compare two contracts
  contract-agent compare contract1.pdf contract2.pdf
  contract-agent compare contract1.pdf contract2.pdf --output comparison.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule

from .agent import ContractAgent

console = Console()


def _check_file(path: str, label: str = "File") -> None:
    """Exit with an error message if *path* does not exist."""
    if not Path(path).exists():
        console.print(f"[bold red]Error:[/] {label} not found: {path}")
        sys.exit(1)


def _build_agent(api_key: str | None) -> ContractAgent:
    """Create a ContractAgent, printing a helpful error if the key is missing."""
    import os

    effective_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not effective_key:
        console.print(
            "[bold red]Error:[/] ANTHROPIC_API_KEY is not set.\n"
            "Either export it as an environment variable or pass --api-key."
        )
        sys.exit(1)
    return ContractAgent(api_key=effective_key)


@click.group()
@click.version_option(package_name="contract-agent-ai")
def main() -> None:
    """Contract Agent — AI-powered contract analysis and risk assessment."""


# ---------------------------------------------------------------------------
# analyze command
# ---------------------------------------------------------------------------

@main.command("analyze")
@click.argument("contract", metavar="CONTRACT_FILE")
@click.option(
    "--template",
    "-t",
    metavar="TEMPLATE_FILE",
    default=None,
    help="Baseline template contract to compare against (PDF or text).",
)
@click.option(
    "--output",
    "-o",
    metavar="OUTPUT_FILE",
    default="risk-report.md",
    show_default=True,
    help="Output path for the Markdown risk report.",
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default=None,
    help="Anthropic API key (defaults to ANTHROPIC_API_KEY env var).",
    show_envvar=True,
)
@click.option(
    "--no-preview",
    is_flag=True,
    default=False,
    help="Do not print the report to the terminal after generation.",
)
def analyze_cmd(
    contract: str,
    template: str | None,
    output: str,
    api_key: str | None,
    no_preview: bool,
) -> None:
    """Analyse CONTRACT_FILE and produce a risk report.

    CONTRACT_FILE can be a PDF (.pdf) or plain-text (.txt / .md) file.
    """
    _check_file(contract, "Contract file")
    if template:
        _check_file(template, "Template file")

    agent = _build_agent(api_key)

    console.print(Rule("[bold cyan]Contract Agent[/]"))
    console.print(f"[cyan]Contract :[/] {contract}")
    if template:
        console.print(f"[cyan]Template  :[/] {template}")
    console.print(f"[cyan]Output    :[/] {output}")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Analysing contract with Claude...", total=None)
        report = agent.analyze(
            contract_path=contract,
            template_path=template,
            output_path=output,
        )

    console.print(
        Panel(
            f"[bold green]Analysis complete.[/] Report saved to [cyan]{output}[/]",
            expand=False,
        )
    )

    if not no_preview:
        console.print()
        console.print(Rule("Risk Report Preview"))
        try:
            report_text = Path(output).read_text(encoding="utf-8")
        except FileNotFoundError:
            # Claude may have returned the report text without writing it;
            # fall back to what was returned.
            report_text = report
        console.print(Markdown(report_text))


# ---------------------------------------------------------------------------
# compare command
# ---------------------------------------------------------------------------

@main.command("compare")
@click.argument("contract1", metavar="CONTRACT_1")
@click.argument("contract2", metavar="CONTRACT_2")
@click.option(
    "--output",
    "-o",
    metavar="OUTPUT_FILE",
    default="comparison-report.md",
    show_default=True,
    help="Output path for the Markdown comparison report.",
)
@click.option(
    "--api-key",
    envvar="ANTHROPIC_API_KEY",
    default=None,
    help="Anthropic API key (defaults to ANTHROPIC_API_KEY env var).",
    show_envvar=True,
)
@click.option(
    "--no-preview",
    is_flag=True,
    default=False,
    help="Do not print the report to the terminal after generation.",
)
def compare_cmd(
    contract1: str,
    contract2: str,
    output: str,
    api_key: str | None,
    no_preview: bool,
) -> None:
    """Compare CONTRACT_1 and CONTRACT_2 side-by-side.

    Both files can be PDF (.pdf) or plain-text (.txt / .md).
    """
    _check_file(contract1, "Contract 1")
    _check_file(contract2, "Contract 2")

    agent = _build_agent(api_key)

    console.print(Rule("[bold cyan]Contract Agent — Comparison[/]"))
    console.print(f"[cyan]Contract 1:[/] {contract1}")
    console.print(f"[cyan]Contract 2:[/] {contract2}")
    console.print(f"[cyan]Output    :[/] {output}")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Comparing contracts with Claude...", total=None)
        report = agent.compare(
            contract1_path=contract1,
            contract2_path=contract2,
            output_path=output,
        )

    console.print(
        Panel(
            f"[bold green]Comparison complete.[/] Report saved to [cyan]{output}[/]",
            expand=False,
        )
    )

    if not no_preview:
        console.print()
        console.print(Rule("Comparison Report Preview"))
        try:
            report_text = Path(output).read_text(encoding="utf-8")
        except FileNotFoundError:
            report_text = report
        console.print(Markdown(report_text))


if __name__ == "__main__":
    main()
