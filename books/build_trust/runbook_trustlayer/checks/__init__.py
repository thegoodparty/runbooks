"""Independent QA checks used by the runbook QA pipeline."""

from .claim_support import ClaimSupportCheck
from .copy_checks import NumericDateNameCopyCheck
from .modeled_data import ModeledDataLabelingCheck
from .referential_integrity import ReferentialIntegrityCheck
from .required_data import RequiredDataCompletenessCheck
from .schema import SchemaValidationCheck
from .source_integrity import SourceIntegrityCheck
from .source_policy import SourcePolicyCheck

DEFAULT_CHECKS = (
    SchemaValidationCheck(),
    ReferentialIntegrityCheck(),
    SourceIntegrityCheck(),
    SourcePolicyCheck(),
    ClaimSupportCheck(),
    NumericDateNameCopyCheck(),
    ModeledDataLabelingCheck(),
    RequiredDataCompletenessCheck(),
)

__all__ = [
    "ClaimSupportCheck",
    "DEFAULT_CHECKS",
    "ModeledDataLabelingCheck",
    "NumericDateNameCopyCheck",
    "ReferentialIntegrityCheck",
    "RequiredDataCompletenessCheck",
    "SchemaValidationCheck",
    "SourceIntegrityCheck",
    "SourcePolicyCheck",
]

