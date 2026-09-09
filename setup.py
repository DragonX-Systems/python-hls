from setuptools import setup, find_packages
from pathlib import Path

readme = (Path(__file__).parent / "README.md").read_text(encoding="utf-8", errors="replace")

setup(
    name="python_hls",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "astroid>=2.15.0",
        "networkx>=3.1",
        "graphviz>=0.20.1",
        "pyverilog>=1.3.0",
        "pygraphviz>=1.10",
        "matplotlib>=3.7.1",
        "click>=8.1.3",
    ],
    extras_require={
        "ml": ["torch>=2.0"],
    },
    entry_points={
        "console_scripts": [
            "python-hls=python_hls.cli:main",
        ],
    },
    author="Python-HLS Contributors",
    description="High-Level Synthesis tool that compiles Python to hardware netlists. Built for trading firms.",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/missionfission/hls-python",
    project_urls={
        "Documentation": "https://github.com/missionfission/hls-python#readme",
        "Source": "https://github.com/missionfission/hls-python",
    },
    keywords="hls, hardware, synthesis, fpga, verilog, vhdl, trading",
    python_requires=">=3.9",
    license="PolyForm Noncommercial 1.0.0",
)
