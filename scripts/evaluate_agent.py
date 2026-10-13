"""Read-only synthetic benchmark. Optional Ollama calls never reach a wallet or RPC."""

import argparse
import sys
from pathlib import Path


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
    from app.agent.portfolio import AITradingAgent
    from app.evaluation import evaluate_scenarios
    from app.policies.ollama import OllamaProvider

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ollama-model", help="Installed local model; omit for deterministic baseline"
    )
    parser.add_argument("--limit", type=int, choices=range(1, 17), default=16)
    args = parser.parse_args()
    if args.ollama_model and ("cloud" in args.ollama_model.lower() or "/" in args.ollama_model):
        parser.error("Use an installed local Ollama model; cloud models are unsupported")
    report = evaluate_scenarios(
        AITradingAgent(OllamaProvider(args.ollama_model)) if args.ollama_model else None,
        "ollama_trades" if args.ollama_model else "deterministic",
        args.ollama_model,
        args.limit,
    )
    folder = Path("local/evaluation")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ("ollama_trades.json" if args.ollama_model else "deterministic.json")
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(
        f"{report.decision_matches}/{report.decision_cases} intent agreements; "
        f"{report.sizing_matches}/{report.sizing_cases} proposal matches with reference; "
        f"{report.invalid_outputs} invalid outputs"
    )
    print(f"Report: {path}. No blockchain transactions were submitted.")


if __name__ == "__main__":
    main()
