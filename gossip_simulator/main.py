from __future__ import annotations

import argparse
import sys

import ollama

from gossip_simulator.agents import AGENTS, MODEL
from gossip_simulator.display import (
    print_banner,
    print_round_header,
    print_round_summary,
    print_comparison_table,
    print_drift_leaderboard,
    print_hr_report,
    print_status,
)

STARTING_MESSAGE = "Did you hear? The CEO is thinking of leaving."
NUM_ROUNDS = 3

MODE_DESCRIPTIONS = {
    "v1": "Linear chain (one agent at a time, each agent speaks once)",
    "v2": "Multi-pass parallel fan-out with merge (agents can repeat, up to 10 passes)",
}


def check_ollama_connection() -> bool:
    try:
        ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": "hi"}],
            options={"num_predict": 1},
        )
        return True
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Office Gossip Simulator")
    parser.add_argument(
        "--mode",
        choices=["v1", "v2"],
        default="v2",
        help="v1 = linear chain (1 agent at a time), v2 = multi-pass parallel fan-out (default: v2)",
    )
    parser.add_argument(
        "--no-drift",
        action="store_true",
        help="Disable semantic drift analysis (v2 only)",
    )
    args = parser.parse_args()

    if args.mode == "v1":
        from gossip_simulator.runner_v1 import run_round
    else:
        from gossip_simulator.runner_v2 import run_round

    print_banner()
    print_status(f"Mode: {args.mode} — {MODE_DESCRIPTIONS[args.mode]}")
    print()

    print_status("Checking Ollama connection...")
    if not check_ollama_connection():
        print("\n[ERROR] Cannot connect to Ollama or model not available.")
        print("Make sure Ollama is running:  ollama serve")
        print(f"And the model is pulled:      ollama pull {MODEL}")
        sys.exit(1)
    print_status("Connected to Ollama.\n")

    drift_enabled = False
    if args.mode == "v2" and not args.no_drift:
        from gossip_simulator.drift import check_embed_model_available
        print_status("Checking embedding model for drift analysis...")
        if check_embed_model_available():
            drift_enabled = True
            print_status("Drift analysis enabled (nomic-embed-text).\n")
        else:
            print_status("WARNING: nomic-embed-text not available. Drift analysis disabled.")
            print_status("Pull it with: ollama pull nomic-embed-text\n")

    rounds_data = []

    for round_num in range(1, NUM_ROUNDS + 1):
        print_round_header(round_num, NUM_ROUNDS)

        result = run_round(STARTING_MESSAGE, AGENTS)

        print_round_summary(result["original"], result["final"], result["hops"])

        if drift_enabled:
            from gossip_simulator.drift import analyze_round, generate_hr_report
            from gossip_simulator.visualize import generate_flow_diagram, generate_drift_chart

            print_status("    Running drift analysis...")
            drift_report = analyze_round(result)

            if drift_report is not None:
                print_drift_leaderboard(drift_report)

                hr_text = generate_hr_report(drift_report)
                print_hr_report(hr_text)

                flow_path = generate_flow_diagram(round_num, result, drift_report)
                if flow_path:
                    print_status(f"    Flow diagram saved: {flow_path}")

                chart_path = generate_drift_chart(round_num, drift_report)
                if chart_path:
                    print_status(f"    Drift chart saved: {chart_path}")

        rounds_data.append(
            {
                "round_num": round_num,
                "agent_sequence": result["agent_sequence"],
                "final_message": result["final"],
            }
        )

    print_comparison_table(rounds_data)


if __name__ == "__main__":
    main()
