from __future__ import annotations

import json
import random
import re
from typing import Dict, List, Optional

import ollama

MODEL = "llama3.1"
ORCHESTRATOR_TEMPERATURE = 0.3
MERGER_TEMPERATURE = 0.7

ORCHESTRATOR_SYSTEM_PROMPT = (
    "You are the orchestrator of an office gossip chain simulation. "
    "Your job is to decide which agent(s) should receive the gossip next, or end the chain.\n\n"
    "You can pick ONE agent for a single pass, or MULTIPLE agents for a parallel fan-out "
    "(they all hear the same message simultaneously, then their outputs get merged into one).\n\n"
    "Respond with ONLY a JSON object in this exact format:\n"
    '{"next_agents": ["Agent Name"]}\n\n'
    "For parallel fan-out (2-3 agents simultaneously):\n"
    '{"next_agents": ["Agent A", "Agent B"]}\n\n'
    "To end the chain:\n"
    '{"next_agents": null}\n\n'
    "Rules:\n"
    "- Only pick from the available agents listed\n"
    "- NEVER include an agent marked as excluded (they spoke last pass)\n"
    "- No agent can appear twice in the same fan-out group\n"
    "- Parallel fan-out creates chaos — use it sometimes for fun\n"
    "- Pick agents that would create interesting or funny interactions\n"
    "- Be unpredictable — vary between single picks and parallel fan-outs\n"
    "- End the chain (null) when the gossip feels sufficiently distorted\n\n"
    "Respond with ONLY the JSON object. No markdown, no explanation."
)

MERGER_SYSTEM_PROMPT = (
    "You are the gossip merger in an office gossip chain simulation. "
    "Multiple people heard the same gossip simultaneously and each retold it differently. "
    "Your job is to BLEND their versions into ONE single message that continues the chain.\n\n"
    "Rules:\n"
    "- Combine elements from ALL versions into one coherent but chaotic message\n"
    "- Keep the most dramatic, exaggerated, or interesting details from each version\n"
    "- The result should feel like a confused amalgamation — as if someone "
    "overheard multiple conversations and mixed them together\n"
    "- Keep it to 1-3 sentences\n"
    "- Do NOT mention that multiple people told you\n\n"
    "Respond with ONLY a JSON object:\n"
    '{"merged_message": "the blended gossip here"}\n\n'
    "Respond with ONLY the JSON object. No markdown, no explanation."
)


def _fuzzy_match(name: str, valid_names: List[str]) -> Optional[str]:
    for valid in valid_names:
        if valid.lower() == name.lower():
            return valid
    return None


def parse_orchestrator_response(
    raw_content: str, valid_names: List[str], last_speakers: List[str]
) -> Optional[List[str]]:
    """
    Parse orchestrator output.
    Returns list of agent names for fan-out, or None to end chain.
    """
    data = None

    # Layer 1: direct JSON parse
    try:
        data = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        # Layer 2: regex fallback
        match = re.search(r"\{[^{}]*\"next_agents?\"[^{}]*\}", raw_content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except (json.JSONDecodeError, TypeError):
                pass

    if data is None:
        return None

    # Handle both "next_agents" (new) and "next_agent" (backward compat)
    raw_agents = data.get("next_agents", data.get("next_agent"))

    if raw_agents is None:
        return None

    # Normalize to list
    if isinstance(raw_agents, str):
        raw_agents = [raw_agents]

    if not isinstance(raw_agents, list):
        return None

    # Validate and filter
    result = []
    seen = set()
    for name in raw_agents:
        if not isinstance(name, str):
            continue
        matched = _fuzzy_match(name, valid_names)
        if matched and matched not in seen and matched not in last_speakers:
            result.append(matched)
            seen.add(matched)

    return result if result else None


def pick_next_agents(
    all_agents: List[Dict[str, str]],
    last_speakers: List[str],
    round_context: str,
) -> Optional[List[str]]:
    """
    Ask the orchestrator to pick the next agent(s) or end the chain.
    Returns list of agent name strings, or None to end.
    """
    all_names = [a["name"] for a in all_agents]
    excluded = [n for n in last_speakers if n in all_names]
    available = [n for n in all_names if n not in excluded]

    if not available:
        available = all_names

    agent_list = ", ".join(available)
    excluded_str = ", ".join(excluded) if excluded else "none"

    user_message = (
        f"Available agents: [{agent_list}]\n"
        f"Excluded (spoke last pass): [{excluded_str}]\n\n"
        f"Context so far:\n{round_context}\n\n"
        "Who should receive the gossip next? Pick one or more agents, or end the chain."
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
        result = parse_orchestrator_response(raw, all_names, last_speakers)

        if result is not None:
            return result

        if "null" in raw.lower():
            return None

        if attempt == 0:
            print("    [Orchestrator gave unclear response, retrying...]")

    # Fallback: random pick of 1-2 agents from available pool
    print("    [Orchestrator fallback: picking randomly]")
    count = random.choice([1, 1, 2])
    return random.sample(available, min(count, len(available)))


def merge_parallel_outputs(outputs: List[Dict[str, str]]) -> str:
    """
    Blend multiple agent messages into one chaotic merged message.
    Returns merged message string.
    """
    versions = "\n".join(
        f'- {o["agent_name"]} said: "{o["message"]}"' for o in outputs
    )
    user_message = (
        f"Here are the different versions of the gossip:\n{versions}\n\n"
        "Blend these into ONE single gossip message."
    )

    print("    [Merging parallel outputs...]")

    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": MERGER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            format="json",
            options={"temperature": MERGER_TEMPERATURE},
        )
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            raise ConnectionError("Cannot connect to Ollama. Is it running?") from e
        raise

    raw = response["message"]["content"]

    try:
        data = json.loads(raw)
        merged = data.get("merged_message", "")
        if merged:
            return merged.strip()
    except (json.JSONDecodeError, TypeError):
        pass

    match = re.search(r'"merged_message"\s*:\s*"([^"]*)"', raw)
    if match:
        return match.group(1).strip()

    # Fallback: pick the longest message
    return max(outputs, key=lambda o: len(o["message"]))["message"]
