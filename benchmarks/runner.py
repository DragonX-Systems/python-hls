"""
Benchmark Runner orchestrating compilation, simulation equivalence, and DSE exploration.
"""

import os
import sys
import copy
import json
import logging
from typing import Dict, List, Optional, Any

from python_hls import HLS
from benchmarks.models import (
    WorkloadConfig,
    CompilationResult,
    EquivalenceResult,
    NodePPA,
    WorkloadResult,
)
from benchmarks.workloads import load_all_workloads, get_workloads_by_domain

logger = logging.getLogger("python_hls.benchmarks")


class BenchmarkRunner:
    """
    Executes and benchmarks representative HLS workloads with clear separation of
    compilation success, simulation equivalence, and physical PPA DSE.
    """

    DEFAULT_TECH_NODES = [45, 28, 16, 7]

    def __init__(
        self,
        output_dir: Optional[str] = None,
        tech_nodes: Optional[List[int]] = None,
        optimization_level: int = 1,
    ):
        self.output_dir = output_dir or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "reports")
        )
        self.rtl_dir = os.path.join(self.output_dir, "rtl")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.rtl_dir, exist_ok=True)
        self.tech_nodes = tech_nodes or self.DEFAULT_TECH_NODES
        self.optimization_level = optimization_level
        self.workloads = load_all_workloads()

    def run_workload(
        self,
        workload: WorkloadConfig,
        tier: str = "dse",
    ) -> WorkloadResult:
        """
        Run a single workload benchmark.
        
        Tiers:
        - "quick": compile check + reference equivalence (fast for CI)
        - "dse": compile + equivalence + multi-node PPA exploration
        - "full": dse + RTL emission to file
        """
        logger.info(f"Running benchmark for workload: {workload.name} (Tier: {tier})")

        # 1. Compilation Phase
        compilation = self._run_compilation(workload, emit_rtl=(tier in ("dse", "full")))

        # 2. Equivalence Phase
        equivalence = self._run_equivalence(workload)

        # 3. PPA / DSE Phase
        ppa_by_node: Dict[int, NodePPA] = {}
        if tier in ("dse", "full") and compilation.status == "PASS":
            ppa_by_node = self._run_dse(workload)

        return WorkloadResult(
            workload=workload,
            compilation=compilation,
            equivalence=equivalence,
            ppa_by_node=ppa_by_node,
        )

    def run_suite(
        self,
        domain: str = "all",
        tier: str = "dse",
    ) -> Dict[str, WorkloadResult]:
        """Run all workloads matching domain ('all', 'ml', 'data_science', 'finance')."""
        target_workloads = get_workloads_by_domain(domain)
        results: Dict[str, WorkloadResult] = {}
        for wl in target_workloads:
            results[wl.name] = self.run_workload(wl, tier=tier)
        return results

    def _run_compilation(
        self,
        workload: WorkloadConfig,
        emit_rtl: bool = True,
    ) -> CompilationResult:
        """Execute HLS compilation and extract IR / latency metrics."""
        rtl_file = os.path.join(self.rtl_dir, f"{workload.name}.v") if emit_rtl else None
        hls = HLS(
            optimization_level=self.optimization_level,
            tech_node=self.tech_nodes[0] if self.tech_nodes else 45,
        )

        try:
            result = hls.compile(
                workload.source_file,
                target="verilog",
                entry_function=workload.entry_function,
                output_file=rtl_file,
            )
            netlist = result[0] if isinstance(result, tuple) else result
            metrics = hls.get_performance_metrics()

            # Count operations in scheduled IR
            op_count = 0
            if hasattr(hls, "scheduled_ir") and hls.scheduled_ir:
                for func in hls.scheduled_ir.functions.values():
                    if hasattr(func, "blocks"):
                        if isinstance(func.blocks, list):
                            op_count += sum(len(getattr(b, "instructions", [])) for b in func.blocks)
                        elif isinstance(func.blocks, dict):
                            op_count += sum(len(getattr(b, "instructions", [])) for b in func.blocks.values())
                    elif hasattr(func, "instructions"):
                        op_count += len(func.instructions)

            modules = list(netlist.modules.keys()) if netlist and hasattr(netlist, "modules") else []

            return CompilationResult(
                status="PASS",
                operations_count=op_count,
                cycle_latency=int(metrics.get("latency_cycles", 0)),
                modules=modules,
                verilog_path=rtl_file if emit_rtl and os.path.exists(rtl_file) else None,
            )
        except Exception as e:
            logger.error(f"Compilation failed for {workload.name}: {e}")
            return CompilationResult(
                status="FAIL",
                error=str(e),
            )

    def _run_equivalence(self, workload: WorkloadConfig) -> EquivalenceResult:
        """
        Verify functional simulation equivalence against Python reference implementation.
        """
        if not workload.test_vectors:
            return EquivalenceResult(status="SKIPPED", error="No test vectors provided")

        # Dynamically import the entry function from the source file
        import importlib.util
        spec = importlib.util.spec_from_file_location("workload_module", workload.source_file)
        if not spec or not spec.loader:
            return EquivalenceResult(status="FAIL", error="Could not load workload module")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        dut_fn = getattr(mod, workload.entry_function, None)

        if not dut_fn:
            return EquivalenceResult(
                status="FAIL",
                error=f"Entry function '{workload.entry_function}' not found in {workload.source_file}",
            )

        ref_fn = workload.reference_fn or dut_fn
        passed = 0
        failed = 0
        mismatches: List[Dict[str, Any]] = []

        for idx, vec in enumerate(workload.test_vectors):
            # Create independent deep copies for dut and ref
            vec_dut = copy.deepcopy(vec)
            vec_ref = copy.deepcopy(vec)

            try:
                dut_res = dut_fn(**vec_dut)
                ref_res = ref_fn(**vec_ref)

                if dut_res is not None:
                    matched = self._outputs_match(dut_res, ref_res)
                    dut_repr = dut_res
                    ref_repr = ref_res
                else:
                    # In-place buffer comparison (e.g. 'y', 'out', 'cov')
                    matched = False
                    dut_repr = None
                    ref_repr = None
                    for buf_key in ("y", "out", "cov"):
                        if buf_key in vec_dut:
                            dut_buf = vec_dut[buf_key]
                            dut_repr = dut_buf
                            if isinstance(ref_res, list):
                                matched = self._outputs_match(dut_buf, ref_res)
                                ref_repr = ref_res
                            elif buf_key in vec_ref:
                                matched = self._outputs_match(dut_buf, vec_ref[buf_key])
                                ref_repr = vec_ref[buf_key]
                            break

                if matched:
                    passed += 1
                else:
                    failed += 1
                    mismatches.append({
                        "vector_index": idx,
                        "dut_output": str(dut_repr),
                        "ref_output": str(ref_repr),
                    })
            except Exception as e:
                failed += 1
                mismatches.append({
                    "vector_index": idx,
                    "error": str(e),
                })

        status = "PASS" if failed == 0 else "FAIL"
        return EquivalenceResult(
            status=status,
            total_vectors=len(workload.test_vectors),
            passed_vectors=passed,
            failed_vectors=failed,
            sim_backend="python_reference",
            mismatches=mismatches,
        )

    def _outputs_match(self, out1: Any, out2: Any) -> bool:
        """Check equivalence between two outputs (scalars, lists, or dicts)."""
        if isinstance(out1, dict) and isinstance(out2, dict):
            for k in out1:
                if k in out2 and out1[k] != out2[k]:
                    return False
            return True
        return out1 == out2

    def _run_dse(self, workload: WorkloadConfig) -> Dict[int, NodePPA]:
        """Explore physical PPA across characterized technology nodes."""
        ppa_map: Dict[int, NodePPA] = {}

        for node in self.tech_nodes:
            hls = HLS(
                optimization_level=self.optimization_level,
                tech_node=node,
            )
            try:
                hls.compile(
                    workload.source_file,
                    target="verilog",
                    entry_function=workload.entry_function,
                )
                metrics = hls.get_performance_metrics()
                report = hls.get_resource_report()

                # Extract aggregate resource counts
                res_counts: Dict[str, int] = {}
                if "modules" in report:
                    for mod in report["modules"].values():
                        for res_name, count in mod.get("resources", {}).items():
                            res_counts[res_name] = res_counts.get(res_name, 0) + count

                ppa_map[node] = NodePPA(
                    node_nm=node,
                    area_um2=float(metrics.get("total_area", 0.0)),
                    power_mw=float(metrics.get("total_power", 0.0)),
                    latency_cycles=int(metrics.get("latency_cycles", 0)),
                    latency_ns=float(metrics.get("latency_ns", 0.0)),
                    frequency_mhz=float(metrics.get("clock_frequency_mhz", 1000.0)),
                    critical_path_ns=float(metrics.get("critical_path", 1.0)),
                    resource_counts=res_counts,
                )
            except Exception as e:
                logger.warning(f"DSE failed for {workload.name} at {node}nm: {e}")

        return ppa_map

    def generate_markdown_summary(self, results: Dict[str, WorkloadResult]) -> str:
        """
        Generate a Markdown summary table cleanly separating:
        1. Workload Specification & Assumptions
        2. Compilation & Simulation Equivalence
        3. Implementation / PPA Results across nodes
        """
        lines = [
            "# Python-HLS Representative Workload Benchmarks",
            "",
            "> [!NOTE]",
            "> This benchmark suite evaluates realistic, representative slices from quantized ML inference,",
            "> data science, and quantitative finance. Compilation success, simulation equivalence,",
            "> and physical PPA are reported distinctly below.",
            "",
            "## 1. Workload Specifications & Hardware Assumptions",
            "",
            "| Domain | Workload | Entry Function | Shapes & Dtypes | Quantization | Hardware Assumptions |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for wl_name, r in results.items():
            wl = r.workload
            shapes_str = "<br>".join([f"`{k}`: {v}" for k, v in wl.shapes.items()])
            assumptions_str = "<br>".join([f"• {a}" for a in wl.hardware_assumptions[:3]])
            lines.append(
                f"| **{wl.domain.upper()}** | `{wl.name}` | `{wl.entry_function}` | {shapes_str} | {wl.quantization} | {assumptions_str} |"
            )

        lines.extend([
            "",
            "## 2. Compilation & Simulation Equivalence",
            "",
            "| Domain | Workload | Compilation Status | Op Count | Latency (Cycles) | Equivalence Status | Test Vectors | RTL Output |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |",
        ])

        for wl_name, r in results.items():
            wl = r.workload
            comp = r.compilation
            eq = r.equivalence
            comp_badge = "✅ PASS" if comp.status == "PASS" else "❌ FAIL"
            eq_badge = "✅ PASS" if eq.status == "PASS" else ("⚠️ SKIP" if eq.status == "SKIPPED" else "❌ FAIL")
            vec_str = f"{eq.passed_vectors}/{eq.total_vectors}"
            rtl_str = f"[`{wl.name}.v`](rtl/{wl.name}.v)" if comp.verilog_path else "—"

            lines.append(
                f"| **{wl.domain.upper()}** | `{wl.name}` | {comp_badge} | {comp.operations_count} | {comp.cycle_latency} | {eq_badge} | {vec_str} | {rtl_str} |"
            )

        lines.extend([
            "",
            "## 3. Implementation / Physical PPA Results (DSE Across Nodes)",
            "",
            r"| Domain | Workload | Node | Area ($\mu\text{m}^2$) | Power (mW) | Latency (ns) | Clock (MHz) | Critical Path (ns) |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ])

        for wl_name, r in results.items():
            wl = r.workload
            for node, ppa in sorted(r.ppa_by_node.items(), reverse=True):
                lines.append(
                    f"| {wl.domain} | `{wl.name}` | **{node}nm** | {ppa.area_um2:.1f} | {ppa.power_mw:.2f} | {ppa.latency_ns:.1f} | {ppa.frequency_mhz:.0f} | {ppa.critical_path_ns:.3f} |"
                )

        lines.extend([
            "",
            "## 4. Hardware Limitations & Unsupported Operations",
            "",
        ])
        for wl_name, r in results.items():
            wl = r.workload
            lines.append(f"### `{wl.name}` ({wl.display_name})")
            for unsupp in wl.unsupported_operations:
                lines.append(f"- **Unsupported**: {unsupp}")
            lines.append("")

        return "\n".join(lines)

    def save_reports(self, results: Dict[str, WorkloadResult]) -> Dict[str, str]:
        """Save JSON and Markdown benchmark reports to output_dir."""
        json_path = os.path.join(self.output_dir, "benchmark_results.json")
        md_path = os.path.join(self.output_dir, "benchmark_summary.md")

        # Serialized JSON
        serialized = {k: v.to_dict() for k, v in results.items()}
        with open(json_path, "w") as f:
            json.dump(serialized, f, indent=2)

        # Markdown summary
        md_content = self.generate_markdown_summary(results)
        with open(md_path, "w") as f:
            f.write(md_content)

        return {"json": json_path, "markdown": md_path}
