from __future__ import annotations

import json
import random
import re
from typing import Dict, List, Optional

import ollama

MODEL = "llama3.1"
ORCHESTRATOR_TEMPERATURE = 0.3

ORCHESTRATOR_SYSTEM_PROMPT = (
    "You are the orchestrator of an office gossip chain simulation. "
    "Your job is to decide which agent should receive the gossip next, or end the chain.\n\n"
    "You will be given a list of available agents and context about what has happened so far.\n\n"
    "Respond with ONLY a JSON object in this exact format:\n"
    '{"next_agent": "Agent Name Here"}\n\n'
    "Or to end the chain:\n"
    '{"next_agent": null}\n\n'
    "Rules:\n"
    "- Only pick from the available agents listed\n"
    "- Pick agents that would create interesting or funny interactions with the current message\n"
    "- Be unpredictable — sometimes skip agents, sometimes end early after just 2-3 agents\n"
    "- End the chain (null) when the gossip feels sufficiently distorted or when remaining agents wouldn't add much\n"
    "- You do NOT always have to use all agents\n\n"
    "Respond with ONLY the JSON object. No markdown, no explanation."
)


def parse_orchestrator_response(
    raw_content: str, valid_names: List[str]
) -> Optional[str]:
    """Parse orchestrator output. Returns agent name or None (end chain)."""
    try:
        data = json.loads(raw_content)
        next_agent = data.get("next_agent")
        if next_agent is None:
            return None
        if isinstance(next_agent, str) and next_agent in valid_names:
            return next_agent
        for name in valid_names:
            if name.lower() == str(next_agent).lower():
                return name
        return None
    except (json.JSONDecodeError, TypeError):
        pass

    match = re.search(r"\{[^{}]*\"next_agent\"[^{}]*\}", raw_content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            next_agent = data.get("next_agent")
            if next_agent is None:
                return None
            for name in valid_names:
                if name.lower() == str(next_agent).lower():
                    return name
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def pick_next_agent(
    remaining_agents: List[Dict[str, str]], round_context: str
) -> Optional[str]:
    """
    Ask the orchestrator to pick the next agent or end the chain.
    Returns agent name string or None to end.
    """
    valid_names = [a["name"] for a in remaining_agents]
    agent_list = ", ".join(valid_names)

    user_message = (
        f"Available agents: [{agent_list}]\n\n"
        f"Context so far:\n{round_context}\n\n"
        "Who should receive the gossip next? Pick one agent or end the chain."
    )

    print("    [Asking orchestrator...]")

    for attempt in range(2):
        try:
            response = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                format="json",
                options={"temperature": ORCHESTRATOR_TEMPERATURE},
            )
        except Exception as e:
            if "connect" in str(e).lower() or "refused" in str(e).lower():
                raise ConnectionError(
                    "Cannot connect to Ollama. Is it running?"
                ) from e
            raise

        raw = response["message"]["content"]
        result = parse_orchestrator_response(raw, valid_names)

        if result is not None:
            return result

        if "null" in raw.lower():
            return None

        if attempt == 0:
            print("    [Orchestrator gave unclear response, retrying...]")

    print("    [Orchestrator fallback: picking randomly]")
    return random.choice(valid_names)
