import ast
from pathlib import Path


def test_decision_layers_do_not_import_execution_or_llm() -> None:
    root = Path(__file__).parents[1] / "app"
    boundaries = {
        "agent/portfolio.py": {"app.schemas", "app.agent.sizing"},
        "agent/sizing.py": {"app.schemas", "app.policies.rebalance"},
        "policies/rules.py": {"app.schemas"},
        "risk/engine.py": {"app.schemas"},
        "policies/interpreter.py": {"app.schemas"},
    }
    for file, allowed in boundaries.items():
        tree = ast.parse((root / file).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app."):
                assert any(node.module.startswith(prefix) for prefix in allowed), file
