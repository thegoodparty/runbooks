"""Product and policy configuration for runbook QA."""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


CLAIM_TYPE_DEFAULTS: Dict[str, Dict[str, str]] = {
    "budget_number": {
        "claim_weight": "high",
        "route_if_unsupported": "block_release",
        "normalized_claim_type": "factual",
        "risk": "high",
    },
    "date_or_deadline": {
        "claim_weight": "high",
        "route_if_unsupported": "block_release",
        "normalized_claim_type": "factual",
        "risk": "high",
    },
    "legal_identifier": {
        "claim_weight": "high",
        "route_if_unsupported": "block_release",
        "normalized_claim_type": "factual",
        "risk": "high",
    },
    "named_person_or_role": {
        "claim_weight": "high",
        "route_if_unsupported": "human_review",
        "normalized_claim_type": "factual",
        "risk": "high",
    },
    "vote_or_decision_fact": {
        "claim_weight": "high",
        "route_if_unsupported": "block_release",
        "normalized_claim_type": "factual",
        "risk": "high",
    },
    "jurisdictional_authority": {
        "claim_weight": "high",
        "route_if_unsupported": "block_release",
        "normalized_claim_type": "factual",
        "risk": "high",
    },
    "campaign_commitment": {
        "claim_weight": "medium",
        "route_if_unsupported": "human_review",
        "normalized_claim_type": "factual",
        "risk": "medium",
    },
    "constituent_priority": {
        "claim_weight": "medium",
        "route_if_unsupported": "human_review",
        "normalized_claim_type": "modeled",
        "risk": "medium",
    },
    "background_context": {
        "claim_weight": "medium",
        "route_if_unsupported": "regenerate",
        "normalized_claim_type": "factual",
        "risk": "medium",
    },
    "news_or_narrative_context": {
        "claim_weight": "medium",
        "route_if_unsupported": "human_review",
        "normalized_claim_type": "factual",
        "risk": "medium",
    },
    "modeled_estimate": {
        "claim_weight": "medium",
        "route_if_unsupported": "human_review",
        "normalized_claim_type": "modeled",
        "risk": "medium",
    },
    "advice": {
        "claim_weight": "low",
        "route_if_unsupported": "human_review",
        "normalized_claim_type": "recommendation",
        "risk": "low",
    },
    "calculation": {
        "claim_weight": "medium",
        "route_if_unsupported": "human_review",
        "normalized_claim_type": "calculation",
        "risk": "medium",
    },
}


DEFAULT_SOURCE_POLICIES: Dict[str, Dict[str, Any]] = {
    "budget_number": {
        "allowed_source_types": [
            "official_budget",
            "audited_financial_report",
            "official_state_finance_page",
            "official_city_budget",
            "official_city_finance_page",
        ],
        "citation_required": True,
        "route_if_unsupported": "block_release",
    },
    "date_or_deadline": {
        "allowed_source_types": [
            "state_statute",
            "government_record",
            "official_state_page",
            "official_transition_page",
        ],
        "citation_required": True,
        "route_if_unsupported": "block_release",
    },
    "legal_identifier": {
        "allowed_source_types": ["state_statute", "government_record", "official_state_page"],
        "citation_required": True,
        "route_if_unsupported": "block_release",
    },
    "jurisdictional_authority": {
        "allowed_source_types": ["state_statute", "government_record", "official_state_page"],
        "citation_required": True,
        "route_if_unsupported": "block_release",
    },
    "named_person_or_role": {
        "allowed_source_types": ["government_record", "official_state_page", "campaign"],
        "citation_required": True,
        "route_if_unsupported": "human_review",
    },
    "vote_or_decision_fact": {
        "allowed_source_types": ["government_record", "staff_report", "news"],
        "citation_required": True,
        "route_if_unsupported": "block_release",
    },
    "campaign_commitment": {
        "allowed_source_types": ["campaign", "news", "government_record"],
        "citation_required": True,
        "route_if_unsupported": "human_review",
    },
    "news_or_narrative_context": {
        "allowed_source_types": ["news", "government_record"],
        "citation_required": True,
        "route_if_unsupported": "human_review",
    },
    "constituent_priority": {
        "allowed_source_types": ["modeled", "database_query"],
        "citation_required": True,
        "route_if_unsupported": "human_review",
    },
    "modeled_estimate": {
        "allowed_source_types": ["modeled", "database_query"],
        "citation_required": True,
        "route_if_unsupported": "human_review",
    },
    "background_context": {
        "allowed_source_types": [
            "government_record",
            "staff_report",
            "news",
            "academic",
            "official_state_page",
        ],
        "citation_required": True,
        "route_if_unsupported": "regenerate",
    },
    "advice": {
        "allowed_source_types": ["synthesis"],
        "citation_required": False,
        "route_if_unsupported": "human_review",
    },
    "calculation": {
        "allowed_source_types": [
            "official_budget",
            "audited_financial_report",
            "government_record",
            "database_query",
        ],
        "citation_required": True,
        "route_if_unsupported": "human_review",
    },
}


@dataclass
class ProductConfig:
    briefing_type: str = "default"
    required_sections: List[str] = field(default_factory=list)
    required_data_points: List[Dict[str, Any]] = field(default_factory=list)
    source_policies: Dict[str, Dict[str, Any]] = field(default_factory=lambda: dict(DEFAULT_SOURCE_POLICIES))
    requires_explicit_product_spec: bool = False

    def policy_for_claim(self, claim: Dict[str, Any]) -> Dict[str, Any]:
        claim_type = claim.get("claim_type", "")
        policy = dict(self.source_policies.get(claim_type, {}))
        required_source_type = claim.get("required_source_type")
        if required_source_type:
            policy.setdefault("allowed_source_types", [required_source_type])
            if required_source_type not in policy["allowed_source_types"]:
                policy["allowed_source_types"] = list(policy["allowed_source_types"]) + [required_source_type]
        policy.setdefault("citation_required", claim_type != "advice")
        policy.setdefault("route_if_unsupported", claim.get("route_if_unsupported", "human_review"))
        return policy


def default_config() -> ProductConfig:
    return ProductConfig()


def governor_orientation_config() -> ProductConfig:
    return ProductConfig(
        briefing_type="governor_orientation",
        required_sections=[
            "executive_summary",
            "role_and_legal_authority",
            "transition_calendar",
            "budget_and_fiscal_snapshot",
            "agency_and_cabinet_map",
            "legislative_landscape",
            "public_commitments_and_constraints",
            "first_100_days_recommendations",
            "source_limitations",
        ],
    )


BUILTIN_CONFIGS = {
    "default": default_config,
    "governor_orientation": governor_orientation_config,
}


def apply_product_spec(base: ProductConfig, product_spec: Optional[Dict[str, Any]]) -> ProductConfig:
    if not product_spec:
        return base
    config = ProductConfig(
        briefing_type=product_spec.get("briefing_type", base.briefing_type),
        required_sections=list(product_spec.get("required_sections", base.required_sections)),
        required_data_points=list(product_spec.get("required_data_points", base.required_data_points)),
        source_policies=dict(base.source_policies),
        requires_explicit_product_spec=bool(
            product_spec.get("requires_explicit_product_spec", base.requires_explicit_product_spec)
        ),
    )
    for point in config.required_data_points:
        claim_type = point.get("claim_type")
        if not claim_type:
            continue
        allowed = point.get("allowed_source_types") or point.get("allowed_sources")
        if allowed:
            config.source_policies[claim_type] = {
                "allowed_source_types": list(allowed),
                "citation_required": bool(point.get("citation_required", True)),
                "route_if_unsupported": point.get("route_if_unsupported", "human_review"),
            }
    return config


def load_config(
    name: Optional[str],
    product_spec: Optional[Dict[str, Any]] = None,
    audit_bundle: Optional[Dict[str, Any]] = None,
) -> ProductConfig:
    briefing_type = name or (audit_bundle or {}).get("briefing_type") or "default"
    factory = BUILTIN_CONFIGS.get(briefing_type, BUILTIN_CONFIGS["default"])
    config = factory()
    if config.briefing_type == "default" and briefing_type != "default":
        config.briefing_type = briefing_type
    if audit_bundle and audit_bundle.get("requires_explicit_product_spec"):
        config.requires_explicit_product_spec = True
    return apply_product_spec(config, product_spec)


def enrich_claim(claim: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(claim)
    defaults = CLAIM_TYPE_DEFAULTS.get(enriched.get("claim_type", ""), {})
    enriched.setdefault("claim_weight", defaults.get("claim_weight", "medium"))
    enriched.setdefault("route_if_unsupported", defaults.get("route_if_unsupported", "human_review"))
    enriched.setdefault("normalized_claim_type", defaults.get("normalized_claim_type", "factual"))
    enriched.setdefault("risk", defaults.get("risk", enriched.get("claim_weight", "medium")))
    enriched.setdefault("verification_category", "unverified")
    return enriched


def max_weight(weights: Iterable[str]) -> str:
    priority = {"low": 0, "medium": 1, "high": 2}
    current = "low"
    for weight in weights:
        if priority.get(weight, 1) > priority[current]:
            current = weight
    return current

