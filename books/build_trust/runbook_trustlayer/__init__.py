"""QA layer for runbook-generated governance briefings."""

from .pipeline import RunbookQAPipeline, validate_output_folder

__all__ = ["RunbookQAPipeline", "validate_output_folder"]

