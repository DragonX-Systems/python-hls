"""
Flow Manifest generation and serialization for GPU-OpenLane handoff.
Defines the complete contract between Python-HLS and downstream physical design.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DesignSpec:
    """Specification of the synthesized hardware design."""
    top_module: str
    rtl_files: List[str] = field(default_factory=list)
    sdc_file: str = ""
    source_file: Optional[str] = None
    target_clock_period_ns: float = 10.0
    target_clock_frequency_mhz: float = 100.0


@dataclass
class TechnologySpec:
    """Foundry and library technology specifications."""
    pdk: str = "sky130A"
    liberty_file: str = ""
    corner: str = "tt_025C_1v80"
    process: str = "typical"
    voltage: float = 1.8
    temperature: float = 25.0


@dataclass
class FlowConfig:
    """EDA pipeline execution parameters."""
    stage: str = "all"  # synthesis, pnr, verification, signoff, all
    use_gpu: bool = True
    use_mlx: bool = True
    threads: int = 8
    dry_run: bool = False
    output_dir: str = "eda_output"


@dataclass
class DSEEstimateSpec:
    """Early architectural DSE estimates from Python-HLS to be calibrated."""
    total_area_um2: float = 0.0
    total_power_mw: float = 0.0
    dynamic_power_mw: float = 0.0
    leakage_power_mw: float = 0.0
    latency_cycles: int = 0
    clock_period_ns: float = 10.0
    clock_frequency_mhz: float = 100.0
    tech_node: int = 45


@dataclass
class ProvenanceSpec:
    """Provenance tracking for repeatable implementation and DSE calibration."""
    generator: str = "python-hls"
    generator_version: str = "0.1.0"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    git_branch: Optional[str] = None


@dataclass
class FlowManifest:
    """
    Top-level flow manifest packaging RTL, SDC, Liberty library, configuration,
    and early DSE estimates for GPU-OpenLane handoff.
    """
    manifest_version: str = "1.0"
    design: DesignSpec = field(default_factory=lambda: DesignSpec(top_module=""))
    technology: TechnologySpec = field(default_factory=TechnologySpec)
    configuration: FlowConfig = field(default_factory=FlowConfig)
    dse_estimates: DSEEstimateSpec = field(default_factory=DSEEstimateSpec)
    provenance: ProvenanceSpec = field(default_factory=ProvenanceSpec)

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to JSON-serializable dictionary."""
        return asdict(self)

    def save(self, path: str) -> str:
        """Write manifest JSON to disk."""
        target_path = Path(path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return str(target_path)

    @classmethod
    def load(cls, path: str) -> FlowManifest:
        """Load manifest from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(
            manifest_version=data.get("manifest_version", "1.0"),
            design=DesignSpec(**data.get("design", {})),
            technology=TechnologySpec(**data.get("technology", {})),
            configuration=FlowConfig(**data.get("configuration", {})),
            dse_estimates=DSEEstimateSpec(**data.get("dse_estimates", {})),
            provenance=ProvenanceSpec(**data.get("provenance", {})),
        )

    def validate(self) -> List[str]:
        """Validate manifest parameters and return list of warning/error messages."""
        errors = []
        if not self.design.top_module:
            errors.append("design.top_module is required")
        if not self.design.rtl_files:
            errors.append("design.rtl_files cannot be empty")
        if not self.technology.liberty_file:
            errors.append("technology.liberty_file is required")
        if not self.design.sdc_file:
            errors.append("design.sdc_file is required")
        return errors

    def generate_shell_script(
        self,
        output_script_path: str,
        openlane_root: Optional[str] = None,
    ) -> str:
        """
        Generate standalone executable bash script to invoke GPU-OpenLane.
        """
        script_path = Path(output_script_path).resolve()
        script_path.parent.mkdir(parents=True, exist_ok=True)

        rtl_args = " ".join(f'"{f}"' for f in self.design.rtl_files)
        openlane_env = openlane_root or "${GPU_OPENLANE_ROOT:-/path/to/gpu-openlane}"

        lines = [
            "#!/usr/bin/env bash",
            "# Standalone GPU-OpenLane Handoff Script",
            "# Generated automatically by Python-HLS",
            f"# Design: {self.design.top_module}",
            f"# Timestamp: {self.provenance.timestamp}",
            "set -euo pipefail",
            "",
            f'GPU_OPENLANE_ROOT="{openlane_env}"',
            "",
            'if [[ ! -f "$GPU_OPENLANE_ROOT/eda_pipeline.py" ]]; then',
            '    echo "Error: eda_pipeline.py not found at $GPU_OPENLANE_ROOT" >&2',
            '    echo "Please set GPU_OPENLANE_ROOT to the companion gpu-openlane checkout directory." >&2',
            "    exit 1",
            "fi",
            "",
            f'echo "Starting GPU-OpenLane implementation for {self.design.top_module}..."',
            "",
            'python3 "$GPU_OPENLANE_ROOT/eda_pipeline.py" \\',
            f"  --rtl {rtl_args} \\",
            f'  --top "{self.design.top_module}" \\',
            f'  --lib "{self.technology.liberty_file}" \\',
            f'  --sdc "{self.design.sdc_file}" \\',
            f'  --pdk "{self.technology.pdk}" \\',
            f'  --stage "{self.configuration.stage}" \\',
            f"  --threads {self.configuration.threads} \\",
            f'  --output "{self.configuration.output_dir}" \\',
        ]

        if not self.configuration.use_gpu:
            lines.append("  --no-gpu \\")
        if not self.configuration.use_mlx:
            lines.append("  --no-mlx \\")
        if self.configuration.dry_run:
            lines.append("  --dry-run \\")

        # Strip trailing backslash from last line
        lines[-1] = lines[-1].rstrip(" \\")
        lines.append("")
        lines.append('echo "GPU-OpenLane handoff completed successfully."')
        lines.append("")

        content = "\n".join(lines)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(script_path, 0o755)

        return str(script_path)
