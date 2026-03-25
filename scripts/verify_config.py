"""Configuration verification script.

Loads and validates all configuration sources, then prints a summary.

Usage:
    poetry run python scripts/verify_config.py
"""

import sys
from pathlib import Path

# Make sure src/ is importable when running the script directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    get_confidence_thresholds,
    get_policy,
    get_risk_weights,
    get_scoring_penalties,
    get_settings,
    load_policies,
    load_risk_weights,
)


def section(title: str) -> None:
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


def check(label: str, value: object) -> None:
    print(f"  {'✓':<3} {label}: {value}")


def main() -> None:
    print("AI Release Guardian — Configuration Verification")
    print("=" * 50)

    # ── Settings ─────────────────────────────────────────────────────────────
    section("Settings (src/config/settings.py)")
    s = get_settings()
    check("llm_model", s.llm_model)
    check("llm_temperature", s.llm_temperature)
    check("llm_max_tokens", s.llm_max_tokens)
    check("database_url", s.database_url)
    check("host", s.host)
    check("port", s.port)
    check("dry_run", s.dry_run)
    check("enable_slack_notifications", s.enable_slack_notifications)
    check("enable_github_statuses", s.enable_github_statuses)

    # ── Release Policies ─────────────────────────────────────────────────────
    section("Release Policies (src/config/release_policies.yaml)")
    policies = load_policies()
    for env_name, policy in policies.environments.items():
        can_deploy, reason = policy.can_deploy_now()
        window_str = "open" if can_deploy else f"BLOCKED ({reason})"
        print(
            f"  {'✓':<3} {env_name:<12} "
            f"approve≤{policy.risk_threshold_approve:>3}  "
            f"review≤{policy.risk_threshold_review:>3}  "
            f"block>{policy.risk_threshold_review:>3}  "
            f"human={str(policy.require_human_approval):<5}  "
            f"window={window_str}"
        )

    # Spot-check individual policies
    prod = get_policy("production")
    assert prod.risk_threshold_approve == 25, "production approve threshold mismatch"
    assert prod.risk_threshold_review == 50, "production review threshold mismatch"
    assert prod.require_human_approval is True, "production should require human approval"

    stg = get_policy("staging")
    assert stg.risk_threshold_approve == 50
    assert stg.require_human_approval is False

    # ── Risk Weights ─────────────────────────────────────────────────────────
    section("Risk Weights (src/config/risk_weights.yaml)")
    weights = get_risk_weights()
    for name, value in weights.as_dict().items():
        check(name, f"{value:.2f}")
    total = sum(weights.as_dict().values())
    check("TOTAL (must be 1.0)", f"{total:.4f}")
    assert abs(total - 1.0) <= 0.001, f"Weights sum to {total}, not 1.0!"

    # ── Scoring Penalties ────────────────────────────────────────────────────
    section("Scoring Penalties (src/config/risk_weights.yaml → scoring)")
    p = get_scoring_penalties()
    check("new_bug_penalty", p.new_bug_penalty)
    check("coverage_drop_penalty_per_pct", p.coverage_drop_penalty_per_pct)
    check("regression_penalty", p.regression_penalty)
    check("slo_violation_penalty", p.slo_violation_penalty)
    check("critical_service_penalty", p.critical_service_penalty)
    check("high_rollback_rate_penalty", p.high_rollback_rate_penalty)
    check("large_changeset_penalty", p.large_changeset_penalty)

    # ── Confidence Thresholds ────────────────────────────────────────────────
    section("Confidence Thresholds (src/config/risk_weights.yaml → confidence_thresholds)")
    t = get_confidence_thresholds()
    check("HIGH  upper bound", t.HIGH)
    check("MEDIUM upper bound", t.MEDIUM)
    check("LOW   upper bound", t.LOW)
    check("CRITICAL upper bound", t.CRITICAL)

    test_cases = [
        (15,  "HIGH"),
        (33,  "MEDIUM"),
        (60,  "LOW"),
        (85,  "CRITICAL"),
        (0,   "HIGH"),
        (20,  "HIGH"),
        (21,  "MEDIUM"),
        (50,  "MEDIUM"),
        (51,  "LOW"),
        (75,  "LOW"),
        (76,  "CRITICAL"),
        (100, "CRITICAL"),
    ]
    print()
    all_passed = True
    for score, expected in test_cases:
        actual = t.get_level(score)
        ok = actual == expected
        all_passed = all_passed and ok
        status = "✓" if ok else "✗ FAIL"
        print(f"  {status:<3} get_level({score:>3}) = {actual:<10}  expected {expected}")

    assert all_passed, "One or more confidence threshold checks failed"

    # ── Done ─────────────────────────────────────────────────────────────────
    print(f"\n{'=' * 50}")
    print("  ✅ All configuration verified")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
