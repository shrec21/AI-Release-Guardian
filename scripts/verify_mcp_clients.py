"""MCP client verification script.

Exercises all four typed clients against their pre-configured mock data
and prints a human-readable summary of every tool call made.

Usage:
    poetry run python scripts/verify_mcp_clients.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcp_clients import get_mock_clients
from src.mcp_clients.mock_client import MockMCPClient


def section(title: str) -> None:
    print(f"\n{'─' * 56}")
    print(f"  {title}")
    print(f"{'─' * 56}")


async def verify_test_logs(client: MockMCPClient) -> None:
    section("Test Logs Client")

    # ── Test results ──────────────────────────────────────────────────────────
    tests = await client.get_test_results("build-1847")
    by_status = {}
    for t in tests:
        by_status.setdefault(t.status, []).append(t)

    print(f"  Total tests : {len(tests)}")
    print(f"  Passed      : {len(by_status.get('passed', []))}")
    print(f"  Failed      : {len(by_status.get('failed', []))}")
    print(f"  Errored     : {len(by_status.get('error', []))}")
    print(f"  Skipped     : {len(by_status.get('skipped', []))}")

    non_passing = [t for t in tests if t.status in ("failed", "error")]
    if non_passing:
        print()
        print("  Non-passing tests:")
        for t in non_passing:
            msg = (t.error_message or "")[:80]
            print(f"    [{t.status.upper():<6}] {t.test_id}")
            print(f"             {msg}")

    # ── Flaky history for each failure ────────────────────────────────────────
    print()
    print("  Flaky history:")
    for t in non_passing:
        flaky = await client.get_flaky_history(t.test_id)
        rate = flaky.get("flake_rate", 0.0)
        runs = flaky.get("total_runs", 0)
        print(f"    {t.test_id:<35} flake_rate={rate:.0%}  ({runs} runs)")

    # ── Coverage ──────────────────────────────────────────────────────────────
    cov = await client.get_coverage_report("build-1847")
    print()
    print(f"  Coverage    : {cov.get('coverage_percentage', 0):.1f}%  "
          f"(delta {cov.get('delta', 0):+.1f}% vs baseline "
          f"{cov.get('baseline_coverage', 0):.1f}%)")

    # ── Call history check ────────────────────────────────────────────────────
    history = client.call_history
    # get_test_results + 3x get_flaky_history + get_coverage_report = 5
    print(f"  Call history: {len(history)} calls recorded  "
          f"(expect ≥5 — results + flaky×{len(non_passing)} + coverage)")
    assert len(history) >= 5, f"Expected ≥5 calls, got {len(history)}"


async def verify_perf_baselines(client: MockMCPClient) -> None:
    section("Perf Baselines Client")

    # ── Current benchmarks ────────────────────────────────────────────────────
    benchmarks = await client.get_current_benchmarks("build-1847")
    print("  Current benchmarks:")
    for b in benchmarks:
        ep = f" {b.endpoint}" if b.endpoint else ""
        print(f"    {b.service}{ep}")
        print(f"      P50={b.latency_p50_ms:.0f}ms  "
              f"P99={b.latency_p99_ms:.0f}ms  "
              f"throughput={b.throughput_rps:.0f} rps")

    # ── All baselines ─────────────────────────────────────────────────────────
    all_bl = await client.get_all_baselines("checkout-service")
    print()
    print("  Baseline samples:")
    for metric, values in all_bl.items():
        if values:
            mean = sum(values) / len(values)
            print(f"    {metric:<22} {len(values)} samples  mean={mean:.1f}")

    # ── SLO definitions ───────────────────────────────────────────────────────
    slos = await client.get_slo_definitions("checkout-service")
    print()
    print("  SLO definitions:")
    for slo in slos:
        print(f"    {slo['slo_name']:<40} target: {slo['target_description']}")


async def verify_jenkins(client: MockMCPClient) -> None:
    section("Jenkins Client")

    build = await client.get_build_status("build-1847")
    print(f"  Build ID    : {build.build_id}")
    print(f"  Branch      : {build.branch}")
    print(f"  Authors     : {', '.join(build.authors)}")
    print(f"  Files       : {len(build.files_changed)} changed")

    ok = await client.trigger_stage("build-1847", "deploy", "hold")
    print(f"  trigger_stage('hold') -> success={ok}")


async def verify_deploy_history(client: MockMCPClient) -> None:
    section("Deploy History Client")

    history = await client.get_deployment_history("checkout-service")
    rolled_back = [d for d in history if d["status"] == "rolled_back"]
    print(f"  Deployments : {len(history)} total")
    print(f"  Rolled back : {len(rolled_back)}")
    if rolled_back:
        print(f"  Rollback IDs: {', '.join(d['deploy_id'] for d in rolled_back)}")

    rate = await client.get_rollback_rate("checkout-service")
    print(f"  Rollback rate: {rate['rollback_rate']:.0%} "
          f"({rate['rollbacks']}/{rate['total_deploys']} deploys "
          f"over {rate.get('window_days', 90)} days)")


async def main() -> None:
    print("AI Release Guardian — MCP Client Verification")
    print("=" * 56)

    clients = get_mock_clients()

    # Run all four verifications
    await verify_test_logs(clients["test_logs"])
    await verify_perf_baselines(clients["perf_baselines"])
    await verify_jenkins(clients["jenkins"])
    await verify_deploy_history(clients["deploy_history"])

    # ── Summary ───────────────────────────────────────────────────────────────
    section("Summary")
    total_calls = sum(
        len(c.call_history)
        for c in clients.values()
        if hasattr(c, "call_history")
    )
    print(f"  Total MCP tool calls made : {total_calls}")
    for name, client in clients.items():
        if hasattr(client, "call_history"):
            print(f"    {name:<16} {len(client.call_history)} calls")

    print(f"\n{'=' * 56}")
    print("  ✅ All MCP clients verified successfully")
    print(f"{'=' * 56}\n")


if __name__ == "__main__":
    asyncio.run(main())
