import pytest

torch = pytest.importorskip("torch")

from python_hls.frontend.torch_fx import trace_torch_model


def test_traces_linear_relu_model_with_shapes():
    model = torch.nn.Sequential(torch.nn.Linear(4, 2), torch.nn.ReLU())
    graph = trace_torch_model(model, [torch.zeros(1, 4)])

    assert graph.inputs == ("input_1",)
    assert graph.outputs
    assert any("linear" in node.operation.lower() for node in graph.nodes)
    assert any("relu" in node.operation.lower() for node in graph.nodes)
    assert graph.to_dict()["nodes"]
