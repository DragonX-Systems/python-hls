"""
Command-line interface for the Python HLS tool.
"""

import os
import sys
import click
import json
from typing import Dict, Any

from .hls import HLS
from .tech import TechLibrary
from .constraints import (
    EquivalenceChecker,
    EquivalenceMode,
    check_refactor_equivalence,
)


@click.group()
def main():
    """Python-HLS: High-Level Synthesis from Python to Hardware."""
    pass


@main.command()
@click.argument('source_file', type=click.Path(exists=True))
@click.option('--target', '-t', type=click.Choice(['verilog', 'vhdl']), default='verilog',
              help='Target hardware description language.')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='Output file path.')
@click.option('--opt-level', '-O', type=click.IntRange(0, 3), default=1,
              help='Optimization level (0-3).')
@click.option('--tech-node', '-n', type=int, default=45,
              help='Technology node in nm (e.g., 45, 28, 16, 7).')
@click.option('--tech-library', type=click.Path(exists=True, dir_okay=False), default=None,
              help='JSON resource models used for scheduling and early PPA estimates.')
@click.option('--schedule', '-s', type=click.Choice(['asap', 'alap', 'list']), default='asap',
              help='Scheduling algorithm.')
@click.option('--visualize/--no-visualize', default=True,
              help='Generate visualizations.')
def compile(source_file, target, output, opt_level, tech_node, tech_library, schedule, visualize):
    """Compile a Python file to a hardware netlist."""
    # Create HLS compiler
    library = TechLibrary.from_json(tech_library, tech_node) if tech_library else None
    hls = HLS(optimization_level=opt_level, tech_node=tech_node, tech_library=library)
    
    try:
        # Determine output file if not specified
        if output is None:
            base, _ = os.path.splitext(source_file)
            if target == 'verilog':
                output = f"{base}.v"
            else:
                output = f"{base}.vhd"
        
        # Compile (pass output path for RTL file)
        result = hls.compile(source_file, target=target, output_file=output)
        netlist = result[0] if isinstance(result, tuple) else result
        
        # Generate reports and visualizations
        report = hls.get_resource_report()
        metrics = hls.get_performance_metrics()
        opt_report = hls.get_optimization_report()
        
        # Get optimization summary
        opt_summary = hls.get_optimization_summary()
        
        # Print summary
        click.echo(f"Compiled {source_file} to {output}")
        click.echo(f"Technology node: {tech_node} nm")
        click.echo(f"Optimization level: {opt_level}")
        click.echo(f"Scheduling algorithm: {schedule}")
        
        # Print optimization summary
        click.echo("\nOptimization Summary:")
        click.echo("===============================")
        
        # Print a condensed version of the optimization summary
        for line in opt_summary.split('\n'):
            if line.startswith('OPTIMIZATION SUMMARY') or line.startswith('=========='):
                continue
            if not line.strip():  # Skip empty lines for more condensed output
                continue
            click.echo(line)
        
        # Print resource usage
        click.echo("\nResource usage:")
        for module_name, module_report in report['modules'].items():
            click.echo(f"  Module: {module_name}")
            click.echo(f"    Latency: {module_report['latency']} cycles")
            click.echo(f"    Area: {module_report['area']:.2f} μm²")
            click.echo(f"    Power: {module_report['power']:.2f} mW")
            
            click.echo("    Resources:")
            for res_type, count in module_report['resources'].items():
                click.echo(f"      {res_type}: {count}")
        
        # Generate visualizations if requested
        if visualize:
            datapath_file = hls.visualize_datapath()
            click.echo(f"\nDatapath visualization: {datapath_file}")
            
            scheduled_file = hls.visualize_scheduled_datapath()
            click.echo(f"Scheduled datapath visualization: {scheduled_file}")
            
            control_file = hls.visualize_control_flow()
            click.echo(f"Control flow visualization: {control_file}")
            
            netlist_file = hls.visualize_netlist()
            click.echo(f"Netlist visualization: {netlist_file}")
        
        # Save report to JSON file
        report_file = f"{os.path.splitext(output)[0]}_report.json"
        with open(report_file, 'w') as f:
            json.dump({
                'resource_report': report,
                'performance_metrics': metrics,
                'optimization_report': opt_report
            }, f, indent=2)
        
        # Save optimization summary to a text file
        summary_file = f"{os.path.splitext(output)[0]}_optimization_summary.txt"
        with open(summary_file, 'w') as f:
            f.write(opt_summary)
        
        click.echo(f"\nDetailed report saved to: {report_file}")
        click.echo(f"Optimization summary saved to: {summary_file}")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@main.command()
@click.argument('source_file', type=click.Path(exists=True))
@click.option('--tech-nodes', '-n', type=str, default='45,28,16,7',
              help='Comma-separated list of technology nodes to analyze.')
@click.option('--opt-level', '-O', type=click.IntRange(0, 3), default=1,
              help='Optimization level (0-3).')
@click.option('--tech-library', type=click.Path(exists=True, dir_okay=False), default=None,
              help='JSON resource models used for scheduling and early PPA estimates.')
def analyze(source_file, tech_nodes, opt_level, tech_library):
    """Analyze a Python file for different technology nodes."""
    # Parse technology nodes
    nodes = [int(node.strip()) for node in tech_nodes.split(',')]
    
    # Collect results for each technology node
    results = {}
    optimization_reports = {}
    optimization_summaries = {}
    
    for node in nodes:
        click.echo(f"Analyzing for {node} nm technology node...")
        
        # Create HLS compiler with this technology node
        library = TechLibrary.from_json(tech_library, node) if tech_library else None
        hls = HLS(optimization_level=opt_level, tech_node=node, tech_library=library)
        
        try:
            # Compile
            netlist = hls.compile(source_file, target='verilog')
            
            # Get metrics and optimization report
            metrics = hls.get_performance_metrics()
            opt_report = hls.get_optimization_report()
            opt_summary = hls.get_optimization_summary()
            
            # Store results
            results[node] = metrics
            optimization_reports[node] = opt_report
            optimization_summaries[node] = opt_summary
            
        except Exception as e:
            click.echo(f"Error analyzing for {node} nm: {str(e)}", err=True)
    
    # Print comparison
    click.echo("\nTechnology comparison:")
    click.echo("===============================")
    click.echo(f"{'Node (nm)':<10} {'Area (μm²)':<15} {'Power (mW)':<15} {'Latency (cycles)':<15}")
    click.echo("-------------------------------")
    
    for node in sorted(results.keys()):
        metrics = results[node]
        area = metrics['total_area']
        power = metrics['total_power']
        latency = metrics['latency_cycles']
        
        click.echo(f"{node:<10} {area:<15.2f} {power:<15.2f} {latency:<15}")
    
    # Print optimization summary for the first node
    if optimization_summaries:
        first_node = sorted(optimization_summaries.keys())[0]
        opt_summary = optimization_summaries[first_node]
        
        click.echo("\nOptimization Summary:")
        click.echo("===============================")
        
        # Print a condensed version (skip the header and empty lines)
        for line in opt_summary.split('\n'):
            if line.startswith('OPTIMIZATION SUMMARY') or line.startswith('=========='):
                continue
            if not line.strip():  # Skip empty lines
                continue
            click.echo(line)
    
    # Save report to JSON file
    report_file = f"{os.path.splitext(source_file)[0]}_tech_analysis.json"
    with open(report_file, 'w') as f:
        json.dump({
            'tech_comparison': results,
            'optimization_reports': optimization_reports
        }, f, indent=2)
    
    # Save optimization summaries to a text file
    summary_file = f"{os.path.splitext(source_file)[0]}_optimization_summaries.txt"
    with open(summary_file, 'w') as f:
        for node in sorted(optimization_summaries.keys()):
            f.write(f"===== {node} nm Technology Node =====\n\n")
            f.write(optimization_summaries[node])
            f.write("\n\n")
    
    click.echo(f"\nDetailed analysis saved to: {report_file}")
    click.echo(f"Optimization summaries saved to: {summary_file}")


@main.command()
@click.argument('source_file', type=click.Path(exists=True))
@click.option('--opt-level', '-O', type=click.IntRange(0, 3), default=1,
              help='Optimization level (0-3).')
@click.option('--tech-node', '-n', type=int, default=45,
              help='Technology node in nm (e.g., 45, 28, 16, 7).')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='Output file path for the optimization summary.')
def optimize(source_file, opt_level, tech_node, output):
    """Generate and display optimization report for a Python file."""
    # Create HLS compiler
    hls = HLS(optimization_level=opt_level, tech_node=tech_node)
    
    try:
        # Compile (using Verilog as default target)
        netlist = hls.compile(source_file, target='verilog')
        
        # Get optimization summary
        opt_summary = hls.get_optimization_summary()
        
        # Print the full optimization summary
        click.echo(opt_summary)
        
        # Save to file if requested
        if output:
            summary_file = output
        else:
            summary_file = f"{os.path.splitext(source_file)[0]}_optimization_summary.txt"
        
        with open(summary_file, 'w') as f:
            f.write(opt_summary)
        
        click.echo(f"\nOptimization summary saved to: {summary_file}")
        
        # Also save the detailed report in JSON format
        opt_report = hls.get_optimization_report()
        metrics = hls.get_performance_metrics()
        report_file = f"{os.path.splitext(source_file)[0]}_optimization_report.json"
        
        with open(report_file, 'w') as f:
            json.dump({
                'optimization_report': opt_report,
                'performance_metrics': metrics
            }, f, indent=2)
        
        click.echo(f"Detailed report saved to: {report_file}")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@main.command()
@click.argument('source_file', type=click.Path(exists=True))
@click.option('--schedule', '-s', 
              type=click.Choice(['asap', 'alap', 'list']), 
              default='asap',
              help='Scheduling algorithm.')
@click.option('--opt-level', '-O', type=click.IntRange(0, 3), default=1,
              help='Optimization level (0-3).')
def visualize(source_file, schedule, opt_level):
    """Visualize the datapath and control flow of a Python file."""
    # Create HLS compiler
    hls = HLS(optimization_level=opt_level)
    
    try:
        # Parse and generate IR
        hls.ast = hls.parser.parse_file(source_file)
        hls.ir = hls.ir_generator.generate(hls.ast)
        hls.optimized_ir = hls.optimizer.optimize(hls.ir)
        
        # Schedule based on selected algorithm
        if schedule == 'asap':
            hls.schedule_asap()
        elif schedule == 'alap':
            hls.schedule_alap()
        elif schedule == 'list':
            # Default resource constraints for list scheduling
            resource_constraints = {
                'ALU_32bit': 2,
                'Multiplier_32bit': 1,
                'Divider_32bit': 1
            }
            hls.schedule_list(resource_constraints)
        
        # Set source file for output path generation
        hls.source_file = source_file
        
        # Generate visualizations
        datapath_file = hls.visualize_datapath()
        click.echo(f"Datapath visualization: {datapath_file}")
        
        scheduled_file = hls.visualize_scheduled_datapath()
        click.echo(f"Scheduled datapath visualization: {scheduled_file}")
        
        control_file = hls.visualize_control_flow()
        click.echo(f"Control flow visualization: {control_file}")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@main.command('verify-equivalence')
@click.argument('original_file', type=click.Path(exists=True))
@click.argument('refactored_file', type=click.Path(exists=True))
@click.option('--mode', '-m',
              type=click.Choice(['functional', 'bit_exact', 'cycle_accurate']),
              default='functional',
              help='Equivalence mode: functional (outputs match), bit_exact (RTL identical), cycle_accurate (same latency).')
@click.option('--strict/--no-strict', default=False,
              help='Exit with error code 1 if not equivalent (for CI/CD).')
def verify_equivalence(original_file, refactored_file, mode, strict):
    """
    Verify that a refactored Python file produces equivalent hardware to the original.
    
    This is the "refactor safety" check: prove that code changes preserve behavior.
    
    Example:
        python -m python_hls.cli verify-equivalence examples/gcd.py examples/gcd_refactored.py
        python -m python_hls.cli verify-equivalence old.py new.py --mode cycle_accurate --strict
    """
    try:
        with open(original_file, 'r') as f:
            original_source = f.read()
        with open(refactored_file, 'r') as f:
            refactored_source = f.read()
        
        mode_enum = {
            'functional': EquivalenceMode.FUNCTIONAL,
            'bit_exact': EquivalenceMode.BIT_EXACT,
            'cycle_accurate': EquivalenceMode.CYCLE_ACCURATE,
        }[mode]
        
        click.echo(f"Checking equivalence: {original_file} vs {refactored_file}")
        click.echo(f"Mode: {mode}")
        
        result = check_refactor_equivalence(
            original_source, 
            refactored_source,
            mode=mode_enum
        )
        
        click.echo(f"\n{result.summary()}")
        
        if result.mismatches:
            click.echo("\nMismatches:")
            for i, m in enumerate(result.mismatches[:5], 1):
                click.echo(f"  {i}. {m.get('type', 'unknown')}: {m}")
            if len(result.mismatches) > 5:
                click.echo(f"  ... and {len(result.mismatches) - 5} more")
        
        if not result.equivalent and strict:
            sys.exit(1)
        elif result.equivalent:
            click.echo("\nRefactor is safe - behavior preserved.")
            
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@main.command()
@click.argument('source_file', type=click.Path(exists=True))
@click.option('--strict/--no-strict', default=False,
              help='Exit with error code 1 if any violations found (for CI/CD).')
def validate(source_file, strict):
    """
    Validate a Python file against HLS semantic rules without full compilation.
    
    Checks for: global mutable state, non-determinism, side effects, dynamic allocation, recursion.
    """
    from .constraints import validate_semantics, SemanticViolationError
    
    try:
        with open(source_file, 'r') as f:
            source = f.read()
        
        click.echo(f"Validating: {source_file}")
        
        violations = validate_semantics(source)
        
        if not violations:
            click.echo("PASS: No semantic violations found.")
            return
        
        click.echo(f"FAIL: {len(violations)} violation(s) found:\n")
        for v in violations:
            loc = f" (line {v.line})" if v.line else ""
            click.echo(f"  [{v.violation_type.name}]{loc}: {v.message}")
        
        if strict:
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@main.command()
@click.option('--domain', '-d', type=click.Choice(['all', 'ml', 'data_science', 'finance']), default='all',
              help='Domain of workloads to benchmark.')
@click.option('--workload', '-w', type=str, default=None,
              help='Specific workload name to benchmark.')
@click.option('--tier', '-t', type=click.Choice(['quick', 'dse', 'full']), default='quick',
              help='Benchmark execution tier: quick (compile+equiv), dse (multi-node PPA), full (emits RTL).')
@click.option('--output-dir', '-o', type=click.Path(), default=None,
              help='Output directory to save reports and generated RTL.')
@click.option('--format', '-f', type=click.Choice(['summary', 'markdown', 'json']), default='summary',
              help='Console display format.')
def benchmark(domain, workload, tier, output_dir, format):
    """
    Run representative ML, data-science, and finance workload benchmarks.
    
    Examples:
        python -m python_hls.cli benchmark --domain ml --tier quick
        python -m python_hls.cli benchmark --domain all --tier dse
        python -m python_hls.cli benchmark --workload vwap_orderbook --format markdown
    """
    from benchmarks.runner import BenchmarkRunner
    from benchmarks.workloads import load_all_workloads, get_workload

    runner = BenchmarkRunner(output_dir=output_dir)

    if workload:
        wl = get_workload(workload)
        if not wl:
            click.echo(f"Error: Workload '{workload}' not found.", err=True)
            click.echo("Available workloads: " + ", ".join(load_all_workloads().keys()))
            sys.exit(1)
        click.echo(f"Running benchmark for {workload} (tier={tier})...")
        results = {wl.name: runner.run_workload(wl, tier=tier)}
    else:
        click.echo(f"Running benchmarks for domain '{domain}' (tier={tier})...")
        results = runner.run_suite(domain=domain, tier=tier)

    saved = runner.save_reports(results)
    click.echo(f"\nSaved benchmark reports:")
    click.echo(f"  • JSON: {saved['json']}")
    click.echo(f"  • Markdown: {saved['markdown']}")

    if format == 'json':
        serialized = {k: v.to_dict() for k, v in results.items()}
        click.echo(json.dumps(serialized, indent=2))
    elif format == 'markdown':
        click.echo("\n" + runner.generate_markdown_summary(results))
    else:
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
@main.command('compile-torch')
@click.argument('source_file', type=click.Path(exists=True))
@click.option('--model-var', '-m', type=str, default='model',
              help='Name of model variable or factory function in source file.')
@click.option('--input-shapes', '-s', type=str, required=True,
              help='Semicolon-separated input tensor shapes, e.g. "1,4" or "4;4".')
@click.option('--target', '-t', type=click.Choice(['verilog', 'vhdl']), default='verilog',
              help='Target HDL.')
@click.option('--output', '-o', type=click.Path(), default=None,
              help='Output file path for generated RTL.')
@click.option('--opt-level', '-O', type=click.IntRange(0, 3), default=1,
              help='Optimization level (0-3).')
@click.option('--tech-node', '-n', type=int, default=45,
              help='Technology node in nm.')
@click.option('--embed-weights/--no-embed-weights', default=False,
              help='Embed weights as constants (ROM) or interface ports.')
def compile_torch_cli(source_file, model_var, input_shapes, target, output, opt_level, tech_node, embed_weights):
    """
    Compile a PyTorch model to hardware using FX qualified lowering.
    
    Example:
        python -m python_hls.cli compile-torch examples/pytorch_linear_relu.py --input-shapes "1,4" -o model.v
    """
    import importlib.util
    import torch
    from .frontend.torch_fx import compile_torch_model

    try:
        spec = importlib.util.spec_from_file_location("user_model_module", source_file)
        if not spec or not spec.loader:
            click.echo(f"Error: Could not load module from {source_file}", err=True)
            sys.exit(1)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        if not hasattr(mod, model_var):
            click.echo(f"Error: '{model_var}' not found in {source_file}", err=True)
            sys.exit(1)

        model_obj = getattr(mod, model_var)
        model = model_obj() if callable(model_obj) and not isinstance(model_obj, torch.nn.Module) else model_obj

        example_inputs = []
        for shape_str in input_shapes.split(";"):
            shape = tuple(int(x.strip()) for x in shape_str.split(",") if x.strip())
            example_inputs.append(torch.zeros(shape))

        click.echo(f"Tracing and lowering PyTorch model '{type(model).__name__}' with shapes {[tuple(t.shape) for t in example_inputs]}...")
        result = compile_torch_model(
            model=model,
            example_inputs=example_inputs,
            target=target,
            output_file=output,
            opt_level=opt_level,
            tech_node=tech_node,
            embed_weights=embed_weights,
        )
        click.echo(f"Compilation succeeded! Target: {target}, Tech Node: {tech_node}nm")
        if output:
            click.echo(f"RTL generated at: {output}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
@main.command('compile-pipeline')
@click.argument('source_file', type=click.Path(exists=True))
@click.option('--entry-function', '-e', default=None, help='Entry function name.')
@click.option('--ii', type=int, default=1, help='Initiation interval target (cycles).')
@click.option('--depth', '-d', type=int, default=2, help='Pipeline depth / latency in cycles.')
@click.option('--interface', '-i', type=click.Choice(['axis', 'ready_valid', 'memory']), default='axis',
              help='Standard hardware interface.')
@click.option('--data-width', '-w', type=int, default=32, help='Data width in bits.')
@click.option('--output', '-o', type=click.Path(), default=None, help='Output Verilog file.')
def compile_pipeline_cmd(source_file, entry_function, ii, depth, interface, data_width, output):
    """Compile Python function to a cycle-accounted hardware pipeline with standard interfaces."""
    hls = HLS()
    try:
        verilog = hls.compile_pipeline(
            source=source_file,
            entry_function=entry_function,
            ii=ii,
            depth=depth,
            interface=interface,
            data_width=data_width,
            output_file=output,
        )
        if output:
            click.echo(f"Compiled pipeline to {output}")
        else:
            click.echo(verilog)
    except Exception as e:
        click.echo(f"Error compiling pipeline: {str(e)}", err=True)
        sys.exit(1)


@main.command('verify-pipeline')
@click.argument('source_file', type=click.Path(exists=True))
@click.option('--entry-function', '-e', default=None, help='Entry function name.')
@click.option('--ii', type=int, default=1, help='Initiation interval target (cycles).')
@click.option('--depth', '-d', type=int, default=2, help='Pipeline depth / latency in cycles.')
@click.option('--interface', '-i', type=click.Choice(['axis', 'ready_valid', 'memory']), default='axis',
              help='Standard hardware interface.')
@click.option('--test-stalls/--no-stalls', default=True, help='Test backpressure stall behavior.')
@click.option('--test-bubbles/--no-bubbles', default=True, help='Test bubble propagation.')
def verify_pipeline_cmd(source_file, entry_function, ii, depth, interface, test_stalls, test_bubbles):
    """Co-simulate and verify a pipeline implementation with Verilator."""
    hls = HLS()
    try:
        res = hls.verify_pipeline(
            source=source_file,
            entry_function=entry_function,
            ii=ii,
            depth=depth,
            interface=interface,
            test_stalls=test_stalls,
            test_bubbles=test_bubbles,
        )
        click.echo(f"Pipeline verification for {res.module_name}:")
        click.echo(f"  Passed: {res.passed}")
        click.echo(f"  Interface: {res.interface.upper()}")
        click.echo(f"  Target II: {res.target_ii}, Measured II: {res.measured_ii:.2f}")
        click.echo(f"  Transactions: {res.total_transactions_received}/{res.total_transactions_sent}")
        click.echo(f"  Mismatches: {res.mismatches}")
        click.echo(f"  Stalls tested: {res.stalls_tested}")
        click.echo(f"  Bubbles tested: {res.bubbles_tested}")
        click.echo(f"  Drained cleanly: {res.drained_cleanly}")
        if not res.passed:
            click.echo(f"Error: {res.error_message}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"Verification error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

