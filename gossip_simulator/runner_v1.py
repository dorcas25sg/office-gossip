from __future__ import annotations

from typing import Dict, List

from gossip_simulator.agents import get_agent_response
from gossip_simulator.orchestrator_v1 import pick_next_agent
from gossip_simulator.display import print_hop, print_status


def run_round(starting_message: str, agents: List[Dict[str, str]]) -> Dict:
    """
    Execute one round of the gossip chain (linear, one agent at a time).
    Each agent can only speak once per round.
    """
    remaining = list(agents)
    current_message = starting_message
    hops = []
    agent_sequence = []
    pass_number = 0

    round_context = 'Starting message: "' + starting_message + '"'

    while remaining:
        pass_number += 1
        next_name = pick_next_agent(remaining, round_context)

        if next_name is None:
            print_status("    Orchestrator ended the chain.")
            break

        agent = next((a for a in remaining if a["name"] == next_name), None)
        if agent is None:
            print_status(f"    Agent '{next_name}' not found in pool, ending chain.")
            break

        response = get_agent_response(agent, current_message)

        hop = {
            "pass_number": pass_number,
            "type": "single",
            "agent_name": agent["name"],
            "decision": response["decision"],
            "message": response["message"],
            "monologue": response["monologue"],
            "input_message": current_message,
        }
        hops.append(hop)
        print_hop(hop)

        if response["decision"] == "pass" and response["message"]:
            current_message = response["message"]
            agent_sequence.append(agent["name"])
            round_context += '\n- ' + agent["name"] + ' passed: "' + response["message"][:80] + '..."'
        else:
            round_context += "\n- " + agent["name"] + " stayed silent"

        remaining = [a for a in remaining if a["name"] != agent["name"]]

    return {
        "original": starting_message,
        "final": current_message,
        "hops": hops,
        "agent_sequence": agent_sequence,
    }
