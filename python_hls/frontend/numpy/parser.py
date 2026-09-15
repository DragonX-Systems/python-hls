"""
Frontend parser and coordinator for bounded NumPy kernels.

Integrates AST extraction, specification resolution, and lowering
into synthesizable Python constructs for the Python-HLS compilation pipeline.
"""

import ast
import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .diagnostics import (
    NumPyFrontendError,
    NumPyShapeError,
    NumPyDTypeError,
    NumPyUnsupportedOperationError,
)
from .spec import (
    ArraySpec,
    KernelSpec,
    numpy_kernel,
    resolve_kernel_specs,
    infer_spec_from_value,
)
from .lowering import NumPyLowering


def _extract_decorator_specs(dec_node: ast.AST) -> Optional[Tuple[Dict[str, Tuple[int, ...]], Dict[str, str], str]]:
    """
    Extract shapes, dtypes, and layout from a @numpy_kernel AST decorator node.
    """
    is_numpy_dec = False
    if isinstance(dec_node, ast.Call):
        if isinstance(dec_node.func, ast.Name) and dec_node.func.id == "numpy_kernel":
            is_numpy_dec = True
        elif isinstance(dec_node.func, ast.Attribute) and dec_node.func.attr == "numpy_kernel":
            is_numpy_dec = True
    elif isinstance(dec_node, ast.Name) and dec_node.id == "numpy_kernel":
        is_numpy_dec = True

    if not is_numpy_dec:
        return None

    shapes: Dict[str, Tuple[int, ...]] = {}
    dtypes: Dict[str, str] = {}
    layout: str = "C"

    if isinstance(dec_node, ast.Call):
        for kw in dec_node.keywords:
            if kw.arg == "shapes":
                try:
                    shapes = ast.literal_eval(kw.value)
                except Exception as e:
                    raise NumPyShapeError(f"Could not statically evaluate @numpy_kernel shapes argument: {e}")
            elif kw.arg == "dtypes":
                try:
                    dtypes = ast.literal_eval(kw.value)
                except Exception as e:
                    raise NumPyDTypeError(f"Could not statically evaluate @numpy_kernel dtypes argument: {e}")
            elif kw.arg == "layout":
                try:
                    layout = ast.literal_eval(kw.value)
                except Exception as e:
                    raise NumPyShapeError(f"Could not statically evaluate @numpy_kernel layout argument: {e}")

    return shapes, dtypes, layout


class NumPyFrontend:
    """
    Coordinator frontend for bounded NumPy kernels.
    """

    def __init__(self):
        pass

    @staticmethod
    def is_numpy_source(source: str) -> bool:
        """Check if source code imports or uses NumPy / numpy_kernel."""
        keywords = ["import numpy", "from numpy", "np.", "numpy.", "numpy_kernel"]
        return any(kw in source for kw in keywords)

    @staticmethod
    def is_numpy_function(func: Callable) -> bool:
        """Check if a callable is decorated with @numpy_kernel or references numpy."""
        if hasattr(func, "__numpy_kernel_spec__"):
            return True
        try:
            source = inspect.getsource(func)
            return NumPyFrontend.is_numpy_source(source)
        except Exception:
            return False

    def lower_callable(
        self,
        func: Callable,
        array_specs: Optional[Dict[str, ArraySpec]] = None,
        shapes: Optional[Dict[str, Tuple[int, ...]]] = None,
        dtypes: Optional[Dict[str, str]] = None,
        example_inputs: Optional[Tuple[Any, ...]] = None,
    ) -> ast.FunctionDef:
        """
        Lower a Python callable decorated with @numpy_kernel or specified with specs into an AST FunctionDef.
        """
        resolved_specs = resolve_kernel_specs(
            func,
            shapes=shapes,
            dtypes=dtypes,
            example_inputs=example_inputs,
        )
        if array_specs:
            resolved_specs.update(array_specs)

        # Parse AST from function source
        source = inspect.getsource(func)
        # Handle indented functions (e.g. methods or test inner functions)
        source = inspect.cleandoc(source)
        module_ast = ast.parse(source)

        func_node = None
        for node in module_ast.body:
            if isinstance(node, ast.FunctionDef):
                func_node = node
                break

        if func_node is None:
            raise NumPyFrontendError(f"Could not find function definition in source of {func.__name__}")

        lowering = NumPyLowering(resolved_specs)
        return lowering.lower_function(func_node)

    def parse_and_lower_ast(
        self,
        tree: ast.Module,
        array_specs: Optional[Dict[str, ArraySpec]] = None,
        entry_function: Optional[str] = None,
    ) -> ast.Module:
        """
        Lower all NumPy kernels and operations in an ast.Module.
        Strips NumPy import statements and @numpy_kernel decorators.
        """
        new_body: List[ast.stmt] = []

        for node in tree.body:
            # Strip numpy and python_hls imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                    if any(name in ("numpy", "python_hls") or name.startswith(("numpy.", "python_hls.")) for name in names):
                        continue
                elif isinstance(node, ast.ImportFrom):
                    if node.module in ("numpy", "python_hls") or (node.module and node.module.startswith(("numpy.", "python_hls."))):
                        continue
                new_body.append(node)
                continue

            # Process function definitions
            if isinstance(node, ast.FunctionDef):
                func_specs: Dict[str, ArraySpec] = {}
                if array_specs:
                    func_specs.update(array_specs)

                # Check decorators for @numpy_kernel
                has_numpy_kernel_dec = False
                for dec in node.decorator_list:
                    extracted = _extract_decorator_specs(dec)
                    if extracted is not None:
                        has_numpy_kernel_dec = True
                        dec_shapes, dec_dtypes, dec_layout = extracted
                        for p_name, shp in dec_shapes.items():
                            dt = dec_dtypes.get(p_name, "int32")
                            func_specs[p_name] = ArraySpec(shape=shp, dtype=dt, layout=dec_layout)

                # Lower the function if it has specs or uses numpy
                has_np_calls = any(
                    isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name) and child.value.id in ("np", "numpy")
                    for child in ast.walk(node)
                )

                if has_numpy_kernel_dec or has_np_calls or (entry_function and node.name == entry_function and func_specs):
                    lowering = NumPyLowering(func_specs)
                    lowered_func = lowering.lower_function(node)
                    new_body.append(lowered_func)
                else:
                    new_body.append(node)
            else:
                new_body.append(node)

        lowered_module = ast.Module(body=new_body, type_ignores=getattr(tree, "type_ignores", []))
        ast.fix_missing_locations(lowered_module)
        return lowered_module

    def parse_and_lower_source(
        self,
        source_code: str,
        array_specs: Optional[Dict[str, ArraySpec]] = None,
        entry_function: Optional[str] = None,
    ) -> str:
        """
        Parse source code, lower NumPy operations into synthesizable loops,
        and return the lowered Python source code.
        """
        tree = ast.parse(source_code)
        lowered_tree = self.parse_and_lower_ast(
            tree,
            array_specs=array_specs,
            entry_function=entry_function,
        )
        return ast.unparse(lowered_tree)

    def compile_to_callable(
        self,
        func: Callable,
        array_specs: Optional[Dict[str, ArraySpec]] = None,
        shapes: Optional[Dict[str, Tuple[int, ...]]] = None,
        dtypes: Optional[Dict[str, str]] = None,
        example_inputs: Optional[Tuple[Any, ...]] = None,
    ) -> Callable:
        """
        Lower a NumPy function and compile it back into a pure Python executable callable.
        Useful for software emulation and functional bit-accurate validation.
        """
        lowered_ast = self.lower_callable(
            func,
            array_specs=array_specs,
            shapes=shapes,
            dtypes=dtypes,
            example_inputs=example_inputs,
        )
        module = ast.Module(body=[lowered_ast], type_ignores=[])
        ast.fix_missing_locations(module)
        code_obj = compile(module, filename=f"<lowered_{func.__name__}>", mode="exec")

        exec_env: Dict[str, Any] = {}
        exec(code_obj, exec_env)
        return exec_env[func.__name__]
