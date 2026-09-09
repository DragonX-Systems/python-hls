import json

from python_hls.tech import TechLibrary


def test_json_library_overrides_a_resource_model(tmp_path):
    library_file = tmp_path / "library.json"
    library_file.write_text(json.dumps({
        "tech_node": 45,
        "resources": [{
            "name": "Adder_32bit", "area": 321.0, "latency": 2,
            "energy_per_op": 1.5, "leakage_power": 9.0,
            "tech_node": 45, "frequency": 750.0,
        }],
    }))

    library = TechLibrary.from_json(str(library_file))

    assert library.get_resource("Adder_32bit").area == 321.0
    assert library.get_resource("Adder_32bit").latency == 2
    assert library.get_resource("Register_32bit").area == 32.0
