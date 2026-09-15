"""
Unit and integration tests for characterized foundry technology library ingestion.

Covers:
- Synopsys Liberty (.lib) parsing and units conversion
- Standard cell discovery and unsupported construct tracking
- Cell-to-resource mapping and model selection
- Normalized characterization schema validation and roundtrip export/import
- DSE report traceability (provenance, PVT corners, assumptions)
- Backwards compatibility with legacy JSON overlays
"""

import os
import json
import pytest
import tempfile
from pathlib import Path

from python_hls import HLS
from python_hls.tech import (
    TechLibrary,
    ResourceModel,
    LibertyParser,
    LibertyLibrary,
    CellToResourceMapper,
    CharacterizationMetadata,
    NormalizedProvenance,
    validate_normalized_schema,
)

REPO_ROOT = Path(__file__).parent.parent
REF_LIB_PATH = REPO_ROOT / "examples" / "technology_libraries" / "reference_45nm.lib"
REF_JSON_PATH = REPO_ROOT / "examples" / "technology_libraries" / "reference_45nm_characterized.json"
LEGACY_JSON_PATH = REPO_ROOT / "examples" / "technology_libraries" / "example_45nm.json"


def test_liberty_parser_reads_reference_library():
    """Verify that LibertyParser accurately extracts headers, PVT corners, and cells."""
    assert REF_LIB_PATH.exists(), f"Missing reference lib file at {REF_LIB_PATH}"
    lib = LibertyParser.parse_file(str(REF_LIB_PATH))

    assert lib.name == "reference_45nm"
    assert lib.technology == "cmos"
    assert lib.time_unit_ns == 1.0  # 1ns
    assert lib.power_unit_uw == 1e-3  # 1nW converted to μW
    assert lib.voltage_unit_v == 1.0  # 1V
    assert lib.capacitive_load_unit_ff == 1.0  # 1fF

    # Verify operating conditions / PVT corners
    assert "typical" in lib.operating_conditions
    assert "slow" in lib.operating_conditions

    typical = lib.get_operating_condition("typical")
    assert typical.voltage == 1.10
    assert typical.temperature == 25.0
    assert typical.process == 1.0

    slow = lib.get_operating_condition("slow")
    assert slow.voltage == 0.95
    assert slow.temperature == 125.0
    assert slow.process == 1.1

    # Verify standard cells
    assert "FA_X1" in lib.cells
    fa = lib.cells["FA_X1"]
    assert fa.area == 3.724
    assert pytest.approx(fa.cell_leakage_power, 1e-6) == 15.4 * 1e-3  # 15.4 nW in μW
    assert "A" in fa.pins
    assert "S" in fa.pins
    assert fa.pins["S"].function == "A ^ B ^ CI"
    assert fa.get_max_delay() > 0.0

    assert "DFF_X1" in lib.cells
    dff = lib.cells["DFF_X1"]
    assert dff.area == 4.256
    assert "CK" in dff.pins
    assert "Q" in dff.pins


def test_liberty_parser_syntax_errors():
    """Verify that LibertyParser handles empty or malformed inputs gracefully."""
    with pytest.raises(ValueError, match="Empty Liberty content"):
        LibertyParser("   ").parse()

    with pytest.raises(ValueError, match="must start with 'library'"):
        LibertyParser("cell (INV) { area: 1.0; }").parse()


def test_cell_mapper_discovers_primitives_and_unsupported_constructs():
    """Verify primitive pattern matching and logging of unsupported constructs."""
    lib = LibertyParser.parse_file(str(REF_LIB_PATH))
    mapper = CellToResourceMapper(tech_node=45)

    matched, unsupported = mapper.discover_cells(lib)

    # Required standard primitives matched
    assert "FA" in matched and matched["FA"].name == "FA_X1"
    assert "HA" in matched and matched["HA"].name == "HA_X1"
    assert "DFF" in matched and matched["DFF"].name == "DFF_X1"
    assert "MUX2" in matched and matched["MUX2"].name == "MUX2_X1"
    assert "XOR2" in matched and matched["XOR2"].name == "XOR2_X1"

    # Unsupported constructs tracked
    assert len(unsupported) == 1
    assert "LEVEL_SHIFTER_X1" in unsupported[0]
    assert "Level shifter" in unsupported[0]


def test_cell_mapper_builds_valid_resources():
    """Verify generated ResourceModels have expected structural and timing attributes."""
    lib = LibertyParser.parse_file(str(REF_LIB_PATH))
    mapper = CellToResourceMapper(tech_node=45, target_frequency_mhz=1000.0)

    resources, metadata = mapper.build_resource_models(lib)

    res_map = {r["name"]: r for r in resources}
    assert "Adder_32bit" in res_map
    assert "Register_32bit" in res_map
    assert "MUX_32bit" in res_map
    assert "Multiplier_32bit" in res_map

    # Combinational vs sequential latencies
    assert res_map["MUX_32bit"]["latency"] == 0
    assert res_map["Adder_32bit"]["latency"] == 1
    assert res_map["Register_32bit"]["latency"] == 1
    assert res_map["Multiplier_32bit"]["latency"] == 2

    # Verify area relationships
    assert res_map["Register_64bit"]["area"] > res_map["Register_32bit"]["area"]
    assert res_map["Multiplier_32bit"]["area"] > res_map["Adder_32bit"]["area"]

    # Metadata check
    assert metadata.library_name == "reference_45nm"
    assert metadata.operating_condition.corner == "typical"
    assert metadata.operating_condition.voltage == 1.10
    assert "LEVEL_SHIFTER_X1" in metadata.unsupported_cells[0]


def test_normalized_schema_validation():
    """Verify schema validator enforces types and required fields."""
    valid_payload = {
        "schema_version": "1.0",
        "library_name": "test_lib",
        "tech_node": 45,
        "resources": [{
            "name": "Adder_32bit",
            "area": 100.0,
            "latency": 1,
            "energy_per_op": 0.5,
            "leakage_power": 5.0,
            "tech_node": 45,
            "frequency": 1000.0,
        }]
    }
    validate_normalized_schema(valid_payload)

    # Missing resources
    with pytest.raises(ValueError, match="'resources' list"):
        validate_normalized_schema({"schema_version": "1.0", "resources": []})

    # Missing required field in resource
    invalid_res = {
        "schema_version": "1.0",
        "resources": [{
            "name": "Adder_32bit",
            "area": 100.0,
            # missing latency
            "energy_per_op": 0.5,
            "leakage_power": 5.0,
            "tech_node": 45,
            "frequency": 1000.0,
        }]
    }
    with pytest.raises(ValueError, match="missing fields.*latency"):
        validate_normalized_schema(invalid_res)


def test_liberty_ingestion_and_roundtrip_json(tmp_path):
    """Verify ingesting Liberty, exporting to normalized JSON, and reloading."""
    # Ingest from Liberty
    lib_from_lib = TechLibrary.from_liberty(
        str(REF_LIB_PATH),
        tech_node=45,
        operating_condition="typical",
    )

    assert lib_from_lib.metadata is not None
    assert lib_from_lib.metadata.library_name == "reference_45nm"
    assert lib_from_lib.metadata.provenance is not None
    assert lib_from_lib.metadata.provenance.sha256 != ""

    adder = lib_from_lib.get_resource("Adder_32bit", 45)
    reg32 = lib_from_lib.get_resource("Register_32bit", 45)
    assert adder.area > 0
    assert reg32.area > 0

    # Export to normalized JSON
    json_path = tmp_path / "exported.json"
    exported_dict = lib_from_lib.to_normalized_json(str(json_path))

    assert json_path.exists()
    assert exported_dict["schema_version"] == "1.0"
    assert exported_dict["provenance"]["sha256"] == lib_from_lib.metadata.provenance.sha256

    # Reload from JSON
    reloaded_lib = TechLibrary.from_json(str(json_path), tech_node=45)
    assert reloaded_lib.metadata is not None
    assert reloaded_lib.metadata.library_name == "reference_45nm"
    assert reloaded_lib.metadata.operating_condition.voltage == 1.10

    reloaded_adder = reloaded_lib.get_resource("Adder_32bit", 45)
    assert reloaded_adder.area == adder.area
    assert reloaded_adder.latency == adder.latency


def test_backwards_compatibility_with_legacy_json():
    """Verify legacy JSON overlays load cleanly without breaking."""
    assert LEGACY_JSON_PATH.exists()
    lib = TechLibrary.from_json(str(LEGACY_JSON_PATH), tech_node=45)

    adder = lib.get_resource("Adder_32bit", 45)
    assert adder.area == 180.0
    assert lib.metadata is not None
    assert lib.metadata.library_name == "custom_json_overlay"


def test_dse_report_provenance_traceability(tmp_path):
    """Verify that performance metrics and resource reports include complete provenance."""
    test_src = tmp_path / "kernel.py"
    test_src.write_text("""
def add_kernel(a, b):
    return a + b
""")

    lib = TechLibrary.from_file(str(REF_LIB_PATH), tech_node=45)
    hls = HLS(optimization_level=1, tech_node=45, tech_library=lib)
    hls.compile(str(test_src), target="verilog")

    # Metrics
    metrics = hls.get_performance_metrics()
    assert "technology_metadata" in metrics
    tech_meta = metrics["technology_metadata"]
    assert tech_meta["library_name"] == "reference_45nm"
    assert tech_meta["corner"] == "typical"
    assert tech_meta["operating_voltage_v"] == 1.10
    assert tech_meta["temperature_c"] == 25.0
    assert tech_meta["drive_strength"] == "X1"
    assert tech_meta["is_signoff"] is False
    assert "reference_45nm.lib" in tech_meta["source_file"]
    assert "sha256_short" in tech_meta

    # Resource report
    report = hls.get_resource_report()
    assert "technology_metadata" in report
    assert report["technology_metadata"]["corner"] == "typical"


def test_tech_library_scaling_across_nodes():
    """Verify characterized library scales correctly across process nodes."""
    lib = TechLibrary.from_file(str(REF_LIB_PATH), tech_node=45)

    adder_45 = lib.get_resource("Adder_32bit", 45)
    adder_28 = lib.get_resource("Adder_32bit", 28)
    adder_7 = lib.get_resource("Adder_32bit", 7)

    assert adder_45.area > adder_28.area > adder_7.area
    assert adder_7.frequency > adder_45.frequency

    # Scaling provenance recorded
    assert adder_28.provenance is not None
    assert adder_28.provenance.get("scaled_from_node") == 45
    assert adder_28.provenance.get("target_node") == 28
