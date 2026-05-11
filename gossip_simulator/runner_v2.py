from __future__ import annotations

from typing import Dict, List

from gossip_simulator.agents import get_agent_response
from gossip_simulator.orchestrator import pick_next_agents, merge_parallel_outputs
from gossip_simulator.display import (
    print_hop,
    print_parallel_hop,
    print_merge,
    print_status,
)

MAX_PASSES = 10


def run_round(starting_message: str, agents: List[Dict[str, str]]) -> Dict:
    """
    Execute one round of the gossip chain with multi-pass parallel support.
    Agents can be called more than once. Max 10 passes per round.
    """
    current_message = starting_message
    hops = []
    agent_sequence = []
    last_speakers = []
    round_context = 'Starting message: "' + starting_message + '"'

    for pass_number in range(1, MAX_PASSES + 1):
        next_names = pick_next_agents(agents, last_speakers, round_context)

        if next_names is None:
            print_status("    Orchestrator ended the chain.")
            break

        # Look up agent dicts
        agent_map = {a["name"]: a for a in agents}
        selected = [agent_map[n] for n in next_names if n in agent_map]
        if not selected:
            print_status("    No valid agents selected, ending chain.")
            break

        if len(selected) == 1:
            # Single pass
            agent = selected[0]
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

            last_speakers = [agent["name"]]

        else:
            # Parallel fan-out
            agent_responses = []
            for agent in selected:
                response = get_agent_response(agent, current_message)
                agent_responses.append({
                    "agent_name": agent["name"],
                    "decision": response["decision"],
                    "message": response["message"],
                    "monologue": response["monologue"],
                })

            hop = {
                "pass_number": pass_number,
                "type": "parallel",
                "agents": agent_responses,
                "input_message": current_message,
                "merged_message": "",
            }

            print_parallel_hop(hop)

            passing = [r for r in agent_responses if r["decision"] == "pass" and r["message"]]

            if len(passing) == 0:
                round_context += "\n- Parallel pass: all agents stayed silent"
            elif len(passing) == 1:
                current_message = passing[0]["message"]
                hop["merged_message"] = current_message
                agent_sequence.append([passing[0]["agent_name"]])
                round_context += '\n- Parallel pass, only ' + passing[0]["agent_name"] + ' spoke: "' + current_message[:80] + '..."'
            else:
                merged = merge_parallel_outputs(passing)
                current_message = merged
                hop["merged_message"] = merged
                agent_sequence.append([r["agent_name"] for r in passing])
                print_merge(merged)
                round_context += '\n- Parallel merge from ' + ", ".join(r["agent_name"] for r in passing) + ': "' + merged[:80] + '..."'

            hops.append(hop)
            last_speakers = [r["agent_name"] for r in agent_responses]

    return {
        "original": starting_message,
        "final": current_message,
        "hops": hops,
        "agent_sequence": agent_sequence,
    }
