"""Configuration module.

Re-exports all public symbols from the three config sub-modules so callers
can import from a single place:

    from src.config import get_settings, get_policy, get_risk_weights
"""

from src.config.policies import (
    DeploymentWindow,
    FreezePeriod,
    ReleasePoliciesConfig,
    ReleasePolicy,
    get_policy,
    load_policies,
)
from src.config.settings import Settings, get_settings
from src.config.weights import (
    ConfidenceThresholds,
    RiskWeightDistribution,
    RiskWeightsConfig,
    ScoringPenalties,
    get_confidence_thresholds,
    get_risk_weights,
    get_scoring_penalties,
    load_risk_weights,
)

__all__ = [
    # settings
    "Settings",
    "get_settings",
    # policies
    "FreezePeriod",
    "DeploymentWindow",
    "ReleasePolicy",
    "ReleasePoliciesConfig",
    "load_policies",
    "get_policy",
    # weights
    "RiskWeightDistribution",
    "ConfidenceThresholds",
    "ScoringPenalties",
    "RiskWeightsConfig",
    "load_risk_weights",
    "get_risk_weights",
    "get_confidence_thresholds",
    "get_scoring_penalties",
]
