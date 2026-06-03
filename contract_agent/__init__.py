"""Contract Agent — extract clauses, flag risks, compare against templates."""

from .agent import ContractAgent
from .clause_extractor import ClauseExtractor

__all__ = ["ContractAgent", "ClauseExtractor"]
__version__ = "0.1.0"
