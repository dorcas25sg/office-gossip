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

    rounds_data = []

    for round_num in range(1, NUM_ROUNDS + 1):
        print_round_header(round_num, NUM_ROUNDS)

        result = run_round(STARTING_MESSAGE, AGENTS)

        print_round_summary(result["original"], result["final"], result["hops"])

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
