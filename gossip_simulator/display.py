from __future__ import annotations

from typing import Dict, List, Union

COLORS = {
    "The Gossip": "\033[95m",
    "The Catastrophizer": "\033[91m",
    "The Confidant": "\033[94m",
    "The Skeptic": "\033[93m",
    "The Exaggerator": "\033[92m",
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
MERGE_COLOR = "\033[96m"


def print_status(message: str) -> None:
    print(f"{DIM}{message}{RESET}")


def print_hop(hop: Dict) -> None:
    name = hop["agent_name"]
    color = COLORS.get(name, "")
    decision = hop["decision"]
    pass_num = hop.get("pass_number", "?")

    print()
    print(f"  {DIM}[Pass {pass_num}]{RESET}")
    print(f"  {color}{BOLD}[{name}]{RESET} {color}-> {decision}{RESET}")

    if hop.get("monologue"):
        print(f"  {DIM}Internal monologue: \"{hop['monologue']}\"{RESET}")

    if decision == "pass" and hop.get("message"):
        print(f"  Message: \"{hop['message']}\"")
    print()


def print_parallel_hop(hop: Dict) -> None:
    pass_num = hop.get("pass_number", "?")
    agents = hop.get("agents", [])

    print()
    print(f"  {DIM}[Pass {pass_num} — PARALLEL FAN-OUT]{RESET}")
    print(f"  {DIM}{'.' * 40}{RESET}")

    for agent_resp in agents:
        name = agent_resp["agent_name"]
        color = COLORS.get(name, "")
        decision = agent_resp["decision"]

        print(f"  {color}{BOLD}[{name}]{RESET} {color}-> {decision}{RESET}")
        if agent_resp.get("monologue"):
            print(f"    {DIM}Internal monologue: \"{agent_resp['monologue']}\"{RESET}")
        if decision == "pass" and agent_resp.get("message"):
            print(f"    Message: \"{agent_resp['message']}\"")

    print(f"  {DIM}{'.' * 40}{RESET}")
    print()


def print_merge(merged_message: str) -> None:
    print(f"  {MERGE_COLOR}{BOLD}[MERGE]{RESET}")
    print(f"  {MERGE_COLOR}Blended message: \"{merged_message}\"{RESET}")
    print()


def format_sequence(agent_sequence: List[Union[str, List[str]]]) -> str:
    parts = []
    for item in agent_sequence:
        if isinstance(item, list):
            parts.append("[" + " + ".join(item) + "]")
        else:
            parts.append(item)
    return " -> ".join(parts) if parts else "(no agents spoke)"


def print_round_summary(
    original: str, final: str, hops: List[Dict]
) -> None:
    pass_count = len(hops)
    parallel_count = sum(1 for h in hops if h.get("type") == "parallel")
    print()
    print(f"  {BOLD}=== FINAL MESSAGE ==={RESET}")
    print(f"  Original: \"{original}\"")
    print(f"  Final:    \"{final}\"")
    print(f"  Passes: {pass_count} ({parallel_count} parallel)")
    print()


def print_comparison_table(rounds_data: List[Dict]) -> None:
    print()
    print(f"{BOLD}{'=' * 80}")
    print("COMPARISON ACROSS ALL ROUNDS")
    print(f"{'=' * 80}{RESET}")
    print()

    for rd in rounds_data:
        round_num = rd["round_num"]
        sequence = format_sequence(rd["agent_sequence"])
        final = rd["final_message"]

        print(f"  {BOLD}Round {round_num}{RESET}")
        print(f"  Agents: {sequence}")
        print(f"  Final:  \"{final}\"")
        print()

    print(f"{BOLD}{'=' * 80}{RESET}")


def print_banner() -> None:
    print()
    print(f"{BOLD}{'=' * 60}")
    print("           OFFICE GOSSIP SIMULATOR")
    print(f"{'=' * 60}{RESET}")
    print()


def print_round_header(round_num: int, total: int) -> None:
    print()
    print(f"{BOLD}{'-' * 60}")
    print(f"  ROUND {round_num} of {total}")
    print(f"{'-' * 60}{RESET}")
    print()
