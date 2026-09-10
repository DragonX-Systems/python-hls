"""
DSE Calibration Engine for Python-HLS.
Compares early architectural resource estimates against physical implementation measurements,
computes calibration discrepancies, and emits calibrated technology library overlays.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .ingestion import ImplementationReport
from .manifest import DSEEstimateSpec


@dataclass
class MetricComparison:
    """Comparison between early DSE estimate and physical implementation measurement."""
    metric_name: str
    unit: str
    dse_estimate: float
    implementation_measurement: float
    absolute_delta: float
    relative_error_pct: float
    ratio: float  # implementation / estimate


@dataclass
class CalibrationReport:
    """Comprehensive comparison and calibration report between DSE and physical implementation."""
    design: str
    pdk: str
    corner: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    dse_estimates: Dict[str, Any] = field(default_factory=dict)
    implementation_measurements: Dict[str, Any] = field(default_factory=dict)
    comparisons: Dict[str, MetricComparison] = field(default_factory=dict)
    area_calibration_factor: float = 1.0
    power_calibration_factor: float = 1.0
    frequency_calibration_factor: float = 1.0
    timing_met: bool = True
    drc_violations: int = 0
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert calibration report to JSON-serializable dictionary."""
        d = asdict(self)
        d["comparisons"] = {k: asdict(v) for k, v in self.comparisons.items()}
        return d

    def to_json(self, indent: int = 2) -> str:
        """Serialize calibration report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, output_path: str) -> str:
        """Write calibration report JSON to disk."""
        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        return str(p)

    def to_markdown(self) -> str:
        """Generate formatted Markdown report with comparisons and calibration guidelines."""
        lines = [
            f"# DSE Calibration Report: `{self.design}`",
            "",
            "> [!NOTE]",
            "> **Signoff Disclaimer**: Implementation measurements are obtained from the automated",
            "> GPU-OpenLane/OpenROAD physical flow to calibrate early Python-HLS architectural models.",
            "> They do not constitute foundry signoff.",
            "",
            "## 1. Provenance & Target Corner",
            "",
            f"- **Design Top**: `{self.design}`",
            f"- **PDK Target**: `{self.pdk}`",
            f"- **PVT Corner**: `{self.corner}`",
            f"- **Timestamp**: `{self.timestamp}`",
            f"- **Timing Status**: `{'✓ MET' if self.timing_met else '✗ VIOLATED'}`",
            f"- **DRC Violations**: `{self.drc_violations}`",
            "",
            "## 2. Comparison Summary: Early DSE vs. Physical Implementation",
            "",
            "| Metric | Unit | Early DSE Estimate | Physical Implementation | Delta (DSE - Impl) | Error (%) | Calibration Factor (Impl/DSE) |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
        ]

        for _, c in self.comparisons.items():
            err_str = f"{c.relative_error_pct:+.1f}%"
            lines.append(
                f"| **{c.metric_name}** | {c.unit} | {c.dse_estimate:.2f} | {c.implementation_measurement:.2f} | {c.absolute_delta:+.2f} | {err_str} | **{c.ratio:.3f}x** |"
            )

        lines.extend([
            "",
            "## 3. Recommended Calibration Factors for DSE Overlays",
            "",
            f"- **Area Correction Factor**: `{self.area_calibration_factor:.3f}x`",
            f"- **Power Correction Factor**: `{self.power_calibration_factor:.3f}x`",
            f"- **Frequency Correction Factor**: `{self.frequency_calibration_factor:.3f}x`",
            "",
            "> [!TIP]",
            "> Apply these factors to your technology library overlay JSON to bring future architectural",
            "> iterations into close alignment with place-and-route QoR.",
            "",
        ])

        return "\n".join(lines)


class DSECalibrator:
    """Calibrates early Python-HLS DSE estimates against physical implementation reports."""

    def compare(
        self,
        dse_estimates: Union[Dict[str, Any], DSEEstimateSpec],
        implementation_report: ImplementationReport,
    ) -> CalibrationReport:
        """
        Compare DSE estimates and implementation report, computing error deltas and ratios.
        """
        if isinstance(dse_estimates, DSEEstimateSpec):
            dse_dict = asdict(dse_estimates)
        else:
            dse_dict = dict(dse_estimates)

        impl_dict = implementation_report.to_dict()
        comparisons: Dict[str, MetricComparison] = {}

        # 1. Area comparison
        dse_area = float(dse_dict.get("total_area", dse_dict.get("total_area_um2", 0.0)))
        impl_area = float(implementation_report.total_area_um2)
        if impl_area > 0:
            area_delta = dse_area - impl_area
            area_err = (area_delta / impl_area) * 100.0
            area_ratio = impl_area / dse_area if dse_area > 0 else 1.0
        else:
            area_delta = 0.0
            area_err = 0.0
            area_ratio = 1.0

        comparisons["area"] = MetricComparison(
            metric_name="Total Area",
            unit="μm²",
            dse_estimate=dse_area,
            implementation_measurement=impl_area,
            absolute_delta=area_delta,
            relative_error_pct=area_err,
            ratio=area_ratio,
        )

        # 2. Power comparison
        dse_power = float(dse_dict.get("total_power", dse_dict.get("total_power_mw", 0.0)))
        impl_power = float(implementation_report.total_power_mw)
        if impl_power > 0:
            power_delta = dse_power - impl_power
            power_err = (power_delta / impl_power) * 100.0
            power_ratio = impl_power / dse_power if dse_power > 0 else 1.0
        else:
            power_delta = 0.0
            power_err = 0.0
            power_ratio = 1.0

        comparisons["power"] = MetricComparison(
            metric_name="Total Power",
            unit="mW",
            dse_estimate=dse_power,
            implementation_measurement=impl_power,
            absolute_delta=power_delta,
            relative_error_pct=power_err,
            ratio=power_ratio,
        )

        # 3. Frequency comparison
        dse_freq = float(dse_dict.get("clock_frequency_mhz", dse_dict.get("clock_frequency", 100.0)))
        impl_freq = float(implementation_report.fmax_mhz)
        if impl_freq > 0:
            freq_delta = dse_freq - impl_freq
            freq_err = (freq_delta / impl_freq) * 100.0
            freq_ratio = impl_freq / dse_freq if dse_freq > 0 else 1.0
        else:
            freq_delta = 0.0
            freq_err = 0.0
            freq_ratio = 1.0

        comparisons["frequency"] = MetricComparison(
            metric_name="Clock Frequency",
            unit="MHz",
            dse_estimate=dse_freq,
            implementation_measurement=impl_freq,
            absolute_delta=freq_delta,
            relative_error_pct=freq_err,
            ratio=freq_ratio,
        )

        # 4. Critical path delay
        dse_period = float(dse_dict.get("clock_period_ns", 10.0))
        impl_crit_ns = float(implementation_report.critical_path_ns)
        crit_delta = dse_period - impl_crit_ns
        crit_err = (crit_delta / impl_crit_ns * 100.0) if impl_crit_ns > 0 else 0.0
        crit_ratio = impl_crit_ns / dse_period if dse_period > 0 else 1.0

        comparisons["critical_path"] = MetricComparison(
            metric_name="Critical Path Delay",
            unit="ns",
            dse_estimate=dse_period,
            implementation_measurement=impl_crit_ns,
            absolute_delta=crit_delta,
            relative_error_pct=crit_err,
            ratio=crit_ratio,
        )

        return CalibrationReport(
            design=implementation_report.design or "top",
            pdk=implementation_report.pdk,
            corner=implementation_report.corner,
            dse_estimates=dse_dict,
            implementation_measurements=impl_dict,
            comparisons=comparisons,
            area_calibration_factor=area_ratio,
            power_calibration_factor=power_ratio,
            frequency_calibration_factor=freq_ratio,
            timing_met=implementation_report.timing_met,
            drc_violations=implementation_report.drc_violations,
            provenance={
                "tool_versions": implementation_report.tool_versions,
                "library_assumptions": implementation_report.library_assumptions,
            },
        )

    def generate_calibrated_tech_library(
        self,
        base_library_path_or_dict: Union[str, Dict[str, Any]],
        calibration_report: CalibrationReport,
        output_path: Optional[str] = None,
        node: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Produce a calibrated TechLibrary overlay JSON scaling resources by the calibration factors.
        """
        if isinstance(base_library_path_or_dict, str):
            with open(base_library_path_or_dict, "r", encoding="utf-8") as f:
                lib_data = json.load(f)
        else:
            lib_data = dict(base_library_path_or_dict)

        tech_node = node or lib_data.get("tech_node", 45)
        area_factor = calibration_report.area_calibration_factor
        power_factor = calibration_report.power_calibration_factor

        calibrated_resources = []
        for res in lib_data.get("resources", []):
            scaled_res = dict(res)
            if "area" in scaled_res:
                scaled_res["area"] = round(float(scaled_res["area"]) * area_factor, 3)
            if "energy_per_op" in scaled_res:
                scaled_res["energy_per_op"] = round(float(scaled_res["energy_per_op"]) * power_factor, 4)
            if "leakage_power" in scaled_res:
                scaled_res["leakage_power"] = round(float(scaled_res["leakage_power"]) * power_factor, 3)
            calibrated_resources.append(scaled_res)

        calibrated_lib = {
            "tech_node": tech_node,
            "calibration_metadata": {
                "calibrated_from_design": calibration_report.design,
                "pdk": calibration_report.pdk,
                "corner": calibration_report.corner,
                "area_scale_applied": round(area_factor, 4),
                "power_scale_applied": round(power_factor, 4),
                "timestamp": calibration_report.timestamp,
            },
            "resources": calibrated_resources,
        }

        if output_path:
            p = Path(output_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(calibrated_lib, f, indent=2)

        return calibrated_lib
