# Automatically generate the typing declaration of exposed faldbt functions.
# Usage:
#    $ python tools/generate_typing_context.py


import ast
import copy
import textwrap
import subprocess

TEMPLATE = """
# This file is auto-generated by tools/generate_typing_context.py, please
# don't manually alter the contents.

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd
    from typing import Optional, Dict, List, Protocol, Any
    from faldbt.project import DbtModel, DbtTest, DbtSource, Feature
    from fal.fal_script import Context, CurrentModel

{protocols}

    # Manually introduced annotations, update manually in tools/generate_typing_context.py template.
    class _Write_To_Model(Protocol):
        def __call__(
            self,
            data: pd.DataFrame,
            *,
            dtype: Any = None,
            mode: str = "overwrite",
            target_1: str = ...,
            target_2: Optional[str] = ...,
        ):
            '''
            Write a pandas.DataFrame to a dbt model automagically.
            '''
            ...


context: Context
write_to_model: _Write_To_Model

{annotations}
"""

TYPING_CONTEXT_FILE = "projects/fal/src/fal/typing.py"
FAL_DBT_FILE = "projects/fal/src/faldbt/project.py"
FAL_DBT_CLS = "FalDbt"
MANUAL_ANNOTATIONS = ["write_to_model"]


def collect_methods(file, class_name):
    with open(file) as stream:
        tree = ast.parse(stream.read())

    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            yield from filter(
                lambda node: (
                    isinstance(node, ast.FunctionDef)
                    and not node.name.startswith("_")
                    and not any(
                        isinstance(decorator, ast.Name) and decorator.id == "property"
                        for decorator in node.decorator_list
                    )
                ),
                node.body,
            )


def generate_protocols(file, class_name):
    protocols, annotations = [], []
    for method in collect_methods(file, class_name):
        call_function: ast.FunctionDef = copy.deepcopy(method)  # type: ignore

        if call_function.name in MANUAL_ANNOTATIONS:
            continue

        call_function.name = "__call__"
        call_function.decorator_list.clear()

        if ast.get_docstring(call_function):
            call_function.body = call_function.body[:1]
        else:
            call_function.body = []

        call_function.body.append(ast.Expr(ast.Constant(...)))

        protocols.append(
            ast.ClassDef(
                name="_" + method.name.title(),
                bases=[ast.Name(id="Protocol")],
                body=[call_function],
                decorator_list=[],
                keywords=[],
            )
        )
        annotations.append(
            ast.AnnAssign(
                target=ast.Name(id=method.name),
                annotation=ast.Name(id=protocols[-1].name),
                simple=1,
            )
        )

    return protocols, annotations


def main():
    protocols, annotations = generate_protocols(FAL_DBT_FILE, FAL_DBT_CLS)

    with open(TYPING_CONTEXT_FILE, "w") as stream:
        stream.write(
            TEMPLATE.format(
                protocols=textwrap.indent(
                    "\n".join(map(ast.unparse, protocols)), "    "
                ),
                annotations="\n".join(map(ast.unparse, annotations)),
            )
        )

    subprocess.run(["black", TYPING_CONTEXT_FILE])


if __name__ == "__main__":
    main()
