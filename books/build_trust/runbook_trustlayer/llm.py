"""Replaceable LLM verification interface.

The MVP does not wire in a provider. Future integrations can subclass
``LLMVerifier`` or pass any object with a compatible ``classify`` method.
"""

from typing import Dict, List, Optional


class LLMVerifier:
    def classify(self, claim: Dict[str, object], evidence_texts: List[str]) -> Optional[str]:
        """Return a support category or ``None`` when no adjudication is available."""
        return None

