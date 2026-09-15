"""
OpenLane & GPU-OpenLane handoff runner and bundle exporter.
Automates invocation of the companion GPU-OpenLane flow or exports reproducible execution bundles.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from .manifest import FlowManifest


logger = logging.getLogger(__name__)


@dataclass
class HandoffResult:
    """Outcome of a GPU-OpenLane handoff run or export."""
    success: bool
    output_dir: str
    manifest_path: str
    script_path: str
    results_json_path: Optional[str] = None
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    wall_time_s: float = 0.0


class OpenLaneRunner:
    """Coordinates the handoff between Python-HLS and GPU-OpenLane."""

    def __init__(self, openlane_root: Optional[str] = None):
        self.openlane_root = self._resolve_openlane_root(openlane_root)

    @staticmethod
    def _resolve_openlane_root(explicit_path: Optional[str] = None) -> Optional[str]:
        """Find the GPU-OpenLane repository checkout directory."""
        if explicit_path and os.path.isdir(explicit_path):
            return os.path.abspath(explicit_path)

        env_root = os.environ.get("GPU_OPENLANE_ROOT")
        if env_root and os.path.isdir(env_root):
            return os.path.abspath(env_root)

        # Check sibling directory
        sibling = Path(__file__).resolve().parents[3] / "gpu-openlane"
        if sibling.is_dir() and (sibling / "eda_pipeline.py").exists():
            return str(sibling.resolve())

        return None

    def export_bundle(
        self,
        manifest: FlowManifest,
        output_dir: str,
        copy_rtl: bool = True,
    ) -> Dict[str, str]:
        """
        Export a self-contained, reproducible handoff bundle into output_dir.
        """
        out_path = Path(output_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        # 1. Save manifest
        manifest_file = out_path / "flow_manifest.json"
        manifest.configuration.output_dir = str(out_path)
        manifest.save(str(manifest_file))

        # 2. Optionally copy RTL files into bundle
        bundled_rtl: List[str] = []
        if copy_rtl:
            rtl_dir = out_path / "rtl"
            rtl_dir.mkdir(parents=True, exist_ok=True)
            for src_rtl in manifest.design.rtl_files:
                if os.path.exists(src_rtl):
                    dest = rtl_dir / os.path.basename(src_rtl)
                    shutil.copy2(src_rtl, dest)
                    bundled_rtl.append(str(dest))
                else:
                    bundled_rtl.append(src_rtl)
            manifest.design.rtl_files = bundled_rtl
            manifest.save(str(manifest_file))

        # 3. Generate executable shell script
        script_file = out_path / "run_openlane_handoff.sh"
        manifest.generate_shell_script(str(script_file), openlane_root=self.openlane_root)

        return {
            "output_dir": str(out_path),
            "manifest_file": str(manifest_file),
            "script_file": str(script_file),
            "sdc_file": manifest.design.sdc_file,
        }

    def run(
        self,
        manifest: FlowManifest,
        output_dir: str,
        timeout_s: int = 600,
        mock_mode: bool = False,
    ) -> HandoffResult:
        """
        Execute or export the GPU-OpenLane handoff flow.
        """
        bundle = self.export_bundle(manifest, output_dir)
        out_path = Path(output_dir).resolve()
        manifest_path = bundle["manifest_file"]
        script_path = bundle["script_file"]
        results_json = out_path / "eda_results.json"

        start_time = time.monotonic()

        # Handle Mock Mode for offline validation and CI
        if mock_mode:
            logger.info("Executing handoff in mock mode for reproducible verification")
            mock_data = self._generate_mock_results(manifest)
            with open(results_json, "w", encoding="utf-8") as f:
                json.dump(mock_data, f, indent=2)

            return HandoffResult(
                success=True,
                output_dir=str(out_path),
                manifest_path=manifest_path,
                script_path=script_path,
                results_json_path=str(results_json),
                return_code=0,
                stdout="Mock GPU-OpenLane flow finished successfully",
                stderr="",
                wall_time_s=round(time.monotonic() - start_time, 2),
            )

        # Check if GPU-OpenLane root is configured
        if not self.openlane_root:
            err = (
                "GPU_OPENLANE_ROOT is not set and companion repository not found. "
                f"Generated standalone handoff bundle in {output_dir}. "
                "Execute 'bash run_openlane_handoff.sh' on your EDA runner."
            )
            logger.warning(err)
            return HandoffResult(
                success=False,
                output_dir=str(out_path),
                manifest_path=manifest_path,
                script_path=script_path,
                results_json_path=None,
                return_code=-1,
                stdout="",
                stderr=err,
                wall_time_s=round(time.monotonic() - start_time, 2),
            )

        pipeline_py = Path(self.openlane_root) / "eda_pipeline.py"
        if not pipeline_py.exists():
            err = f"eda_pipeline.py not found at {pipeline_py}"
            logger.error(err)
            return HandoffResult(
                success=False,
                output_dir=str(out_path),
                manifest_path=manifest_path,
                script_path=script_path,
                results_json_path=None,
                return_code=-1,
                stdout="",
                stderr=err,
                wall_time_s=round(time.monotonic() - start_time, 2),
            )

        cmd = [
            sys.executable,
            str(pipeline_py),
            "--rtl", *manifest.design.rtl_files,
            "--top", manifest.design.top_module,
            "--lib", manifest.technology.liberty_file,
            "--sdc", manifest.design.sdc_file,
            "--pdk", manifest.technology.pdk,
            "--stage", manifest.configuration.stage,
            "--threads", str(manifest.configuration.threads),
            "--output", str(out_path),
        ]

        if not manifest.configuration.use_gpu:
            cmd.append("--no-gpu")
        if not manifest.configuration.use_mlx:
            cmd.append("--no-mlx")
        if manifest.configuration.dry_run:
            cmd.append("--dry-run")

        logger.info("Invoking GPU-OpenLane command: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=str(out_path),
            )
            success = (proc.returncode == 0)
            wall_time = round(time.monotonic() - start_time, 2)

            return HandoffResult(
                success=success,
                output_dir=str(out_path),
                manifest_path=manifest_path,
                script_path=script_path,
                results_json_path=str(results_json) if results_json.exists() else None,
                return_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                wall_time_s=wall_time,
            )
        except subprocess.TimeoutExpired:
            wall_time = round(time.monotonic() - start_time, 2)
            return HandoffResult(
                success=False,
                output_dir=str(out_path),
                manifest_path=manifest_path,
                script_path=script_path,
                results_json_path=None,
                return_code=-2,
                stdout="",
                stderr=f"GPU-OpenLane process timed out after {timeout_s} seconds",
                wall_time_s=wall_time,
            )
        except Exception as exc:
            wall_time = round(time.monotonic() - start_time, 2)
            return HandoffResult(
                success=False,
                output_dir=str(out_path),
                manifest_path=manifest_path,
                script_path=script_path,
                results_json_path=None,
                return_code=-3,
                stdout="",
                stderr=str(exc),
                wall_time_s=wall_time,
            )

    @staticmethod
    def _generate_mock_results(manifest: FlowManifest) -> Dict[str, Any]:
        """Generate realistic mock physical implementation results for testing."""
        dse = manifest.dse_estimates
        # Base realistic physical scale: cells slightly larger than pure gate estimates,
        # slight routing wire overhead, realistic dynamic & leakage power
        impl_area = dse.total_area_um2 * 1.12 if dse.total_area_um2 > 0 else 1850.0
        impl_power = dse.total_power_mw * 1.08 if dse.total_power_mw > 0 else 8.5
        crit_ps = (dse.clock_period_ns * 0.85) * 1000.0 if dse.clock_period_ns > 0 else 2200.0

        return {
            "synthesis": {
                "cells": 342,
                "area_um2": round(impl_area, 2),
                "critical_path_ps": round(crit_ps, 1),
                "power_mw": round(impl_power, 3),
                "wall_s": 4.2,
                "status": "ok",
            },
            "pnr": {
                "hpwl_um": 1420.5,
                "core_utilization": 42.5,
                "gds_path": str(Path(manifest.configuration.output_dir) / f"{manifest.design.top_module}.gds"),
                "def_path": str(Path(manifest.configuration.output_dir) / f"{manifest.design.top_module}.def"),
                "wall_s": 12.8,
                "status": "ok",
            },
            "signoff": {
                "drc_violations": 0,
                "wns_ps": 180.0,
                "tns_ps": 0.0,
                "slack_ps": 180.0,
                "wall_s": 3.1,
                "status": "ok",
            },
            "verification": {
                "exit_code": 0,
                "coverage_pct": 100.0,
                "sim_time_s": 0.4,
                "wall_s": 1.2,
                "status": "ok",
            },
            "tool_versions": {
                "synthesis": "Yosys 0.38",
                "pnr": "OpenROAD 2.0 (Metal GPU)",
                "sta": "OpenSTA 2.6.0",
                "drc": "KLayout 0.28",
            },
            "_total_wall_s": 21.3,
        }
