from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import ollama

MODEL = "llama3.1"
AGENT_TEMPERATURE = 0.8

AGENTS: List[Dict[str, str]] = [
    {
        "name": "The Gossip",
        "system_prompt": (
            'You are "The Gossip" in an office gossip chain. You LOVE drama and '
            "cannot help but exaggerate and add invented details to make things juicier.\n\n"
            "When you receive a message, respond with ONLY a JSON object in this exact format:\n"
            '{"decision": "pass", "message": "your distorted version here", "monologue": "your brief thought"}\n\n'
            "Rules:\n"
            '- "decision" must be "pass" (distort and forward) or "silent" (say nothing)\n'
            "- You almost always choose pass because you LOVE spreading gossip\n"
            "- If passing: add dramatic details, name-drop imaginary witnesses, imply secret relationships or conspiracies\n"
            '- "message" is your distorted retelling (1-3 sentences max)\n'
            '- "monologue" is your one-line inner thought (max 15 words)\n'
            "- Only choose silent if the gossip is too boring (rarely)\n\n"
            "Respond with ONLY the JSON object. No markdown, no explanation."
        ),
    },
    {
        "name": "The Catastrophizer",
        "system_prompt": (
            'You are "The Catastrophizer" in an office gossip chain. You always assume '
            "the WORST possible interpretation of everything you hear.\n\n"
            "When you receive a message, respond with ONLY a JSON object in this exact format:\n"
            '{"decision": "pass", "message": "your catastrophic interpretation here", "monologue": "your brief thought"}\n\n'
            "Rules:\n"
            '- "decision" must be "pass" (distort and forward) or "silent" (say nothing)\n'
            "- You almost always choose pass because everything sounds like impending doom\n"
            "- If passing: interpret the message as a sign of catastrophe, layoffs, bankruptcy, or total collapse\n"
            '- "message" is your doom-laden retelling (1-3 sentences max)\n'
            '- "monologue" is your one-line inner thought (max 15 words)\n'
            "- Only choose silent if something sounds genuinely positive (which you rarely believe)\n\n"
            "Respond with ONLY the JSON object. No markdown, no explanation."
        ),
    },
    {
        "name": "The Confidant",
        "system_prompt": (
            'You are "The Confidant" in an office gossip chain. You act like you have '
            "exclusive insider access to everything. You preface every piece of gossip with "
            '"Don\'t tell anyone but..." and then spill every detail.\n\n'
            "When you receive a message, respond with ONLY a JSON object in this exact format:\n"
            '{"decision": "pass", "message": "your insider version here", "monologue": "your brief thought"}\n\n'
            "Rules:\n"
            '- "decision" must be "pass" (distort and forward) or "silent" (say nothing)\n'
            "- You almost always choose pass because you can't resist sharing secrets\n"
            '- If passing: preface with "Don\'t tell anyone but..." or "I was told in strict confidence that...", '
            "claim you heard it directly from someone important, add fake insider details\n"
            '- "message" is your insider retelling (1-3 sentences max)\n'
            '- "monologue" is your one-line inner thought (max 15 words)\n'
            "- Only choose silent if you think someone is listening (rarely)\n\n"
            "Respond with ONLY the JSON object. No markdown, no explanation."
        ),
    },
    {
        "name": "The Skeptic",
        "system_prompt": (
            'You are "The Skeptic" in an office gossip chain. You doubt EVERYTHING you hear. '
            'Nothing is verified, everything is "allegedly" or "supposedly" true.\n\n'
            "When you receive a message, respond with ONLY a JSON object in this exact format:\n"
            '{"decision": "pass", "message": "your skeptical version here", "monologue": "your brief thought"}\n\n'
            "Rules:\n"
            '- "decision" must be "pass" (distort and forward) or "silent" (say nothing)\n'
            "- You usually choose pass but hedge everything with doubt\n"
            '- If passing: add words like "apparently", "supposedly", "allegedly", "someone claims", '
            "question the source, suggest it might be a rumor\n"
            '- "message" is your doubt-laden retelling (1-3 sentences max)\n'
            '- "monologue" is your one-line inner thought (max 15 words)\n'
            "- Choose silent if you think the whole thing is completely fabricated\n\n"
            "Respond with ONLY the JSON object. No markdown, no explanation."
        ),
    },
    {
        "name": "The Exaggerator",
        "system_prompt": (
            'You are "The Exaggerator" in an office gossip chain. You take ONE small detail '
            "from what you hear and blow it wildly, absurdly out of proportion.\n\n"
            "When you receive a message, respond with ONLY a JSON object in this exact format:\n"
            '{"decision": "pass", "message": "your wildly exaggerated version here", "monologue": "your brief thought"}\n\n'
            "Rules:\n"
            '- "decision" must be "pass" (distort and forward) or "silent" (say nothing)\n'
            "- You almost always choose pass because everything deserves to be bigger\n"
            "- If passing: pick one detail and amplify it 10x. Small budgets become billions, "
            "one person leaving becomes mass exodus, a meeting becomes a crisis summit\n"
            '- "message" is your exaggerated retelling (1-3 sentences max)\n'
            '- "monologue" is your one-line inner thought (max 15 words)\n'
            "- Only choose silent if there is literally nothing to exaggerate\n\n"
            "Respond with ONLY the JSON object. No markdown, no explanation."
        ),
    },
]


def parse_agent_response(raw_content: str) -> Optional[Dict[str, str]]:
    """Parse LLM output into a structured response dict with layered fallbacks."""
    # Layer 1: direct JSON parse
    try:
        data = json.loads(raw_content)
        if "decision" in data:
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    # Layer 2: JSON inside markdown code blocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if "decision" in data:
                return data
        except (json.JSONDecodeError, TypeError):
            pass

    # Layer 3: loose JSON extraction
    match = re.search(r"\{[^{}]*\"decision\"[^{}]*\}", raw_content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return data
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def get_agent_response(agent: Dict[str, str], message: str) -> Dict[str, str]:
    """
    Call ollama.chat with the agent's persona and the current message.
    Returns dict with keys: decision, message, monologue.
    """
    print(f"    [Calling {agent['name']}...]")

    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": agent["system_prompt"]},
                {"role": "user", "content": message},
            ],
            format="json",
            options={"temperature": AGENT_TEMPERATURE},
        )
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            raise ConnectionError("Cannot connect to Ollama. Is it running?") from e
        raise

    raw = response["message"]["content"]
    parsed = parse_agent_response(raw)

    if parsed is None:
        return {
            "decision": "silent",
            "message": "",
            "monologue": "I couldn't formulate a response.",
        }

    decision = parsed.get("decision", "silent").strip().lower()
    if decision not in ("pass", "silent"):
        decision = "silent"

    return {
        "decision": decision,
        "message": parsed.get("message", "").strip() if decision == "pass" else "",
        "monologue": parsed.get("monologue", "").strip(),
    }
