#!/usr/bin/env python3
"""
Command-line executable for running Python-HLS representative workload benchmarks.
"""

import os
import sys
import click

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from benchmarks.runner import BenchmarkRunner
from benchmarks.workloads import load_all_workloads, get_workload


@click.command()
@click.option(
    "--domain", "-d",
    type=click.Choice(["all", "ml", "data_science", "finance"]),
    default="all",
    help="Domain of workloads to benchmark.",
)
@click.option(
    "--workload", "-w",
    type=str,
    default=None,
    help="Specific workload to run (e.g. 'mlp_layer', 'vwap_orderbook').",
)
@click.option(
    "--tier", "-t",
    type=click.Choice(["quick", "dse", "full"]),
    default="dse",
    help="Benchmark execution tier (quick: compilation & ref; dse: multi-node PPA; full: emits RTL).",
)
@click.option(
    "--output-dir", "-o",
    type=click.Path(),
    default=None,
    help="Directory to store reports and emitted RTL.",
)
@click.option(
    "--format", "-f",
    type=click.Choice(["summary", "markdown", "json"]),
    default="summary",
    help="Output format to display to console.",
)
def main(domain, workload, tier, output_dir, format):
    """Run representative ML, Data-Science, and Finance benchmarks for Python-HLS."""
    runner = BenchmarkRunner(output_dir=output_dir)

    if workload:
        wl = get_workload(workload)
        if not wl:
            click.echo(f"Error: Workload '{workload}' not found.", err=True)
            click.echo("Available workloads: " + ", ".join(load_all_workloads().keys()))
            sys.exit(1)
        click.echo(f"Running benchmark for single workload: {workload} (tier={tier})...")
        results = {wl.name: runner.run_workload(wl, tier=tier)}
    else:
        click.echo(f"Running benchmarks for domain '{domain}' (tier={tier})...")
        results = runner.run_suite(domain=domain, tier=tier)

    # Save reports
    saved = runner.save_reports(results)
    click.echo(f"\nSaved benchmark reports:")
    click.echo(f"  • JSON: {saved['json']}")
    click.echo(f"  • Markdown: {saved['markdown']}")

    # Console display
    if format == "json":
        import json
        serialized = {k: v.to_dict() for k, v in results.items()}
        click.echo(json.dumps(serialized, indent=2))
    elif format == "markdown":
        click.echo("\n" + runner.generate_markdown_summary(results))
    else:
        # Standard summary table to console
        click.echo("\n" + "=" * 90)
        click.echo("BENCHMARK EXECUTION SUMMARY")
        click.echo("=" * 90)
        header = f"{'Domain':<14} {'Workload':<24} {'Compile':<10} {'Equiv':<10} {'Latency(cyc)':<14} {'45nm Area':<12}"
        click.echo(header)
        click.echo("-" * 90)

        for name, r in results.items():
            wl = r.workload
            comp = r.compilation.status
            eq = f"{r.equivalence.passed_vectors}/{r.equivalence.total_vectors} {r.equivalence.status}"
            cyc = str(r.compilation.cycle_latency)
            area_45 = f"{r.ppa_by_node[45].area_um2:.1f} um²" if 45 in r.ppa_by_node else "N/A"
            click.echo(f"{wl.domain:<14} {name:<24} {comp:<10} {eq:<10} {cyc:<14} {area_45:<12}")

        click.echo("=" * 90)


if __name__ == "__main__":
    main()
