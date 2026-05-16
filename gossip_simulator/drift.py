from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import ollama

EMBED_MODEL = "nomic-embed-text"


@dataclass
class HopDrift:
    pass_number: int
    hop_type: str
    agent_names: List[str]
    input_similarity: float
    output_similarity: float
    drift_delta: float


@dataclass
class AgentScore:
    name: str
    culpable_score: float
    hop_count: int


@dataclass
class DriftReport:
    hop_drifts: List[HopDrift]
    agent_scores: List[AgentScore]
    worst_single: Optional[AgentScore]
    worst_duo: Optional[Tuple[str, str, float]]
    worst_team: Optional[Tuple[List[str], float]]
    total_drift: float


def get_embedding(text: str) -> Optional[List[float]]:
    try:
        response = ollama.embed(model=EMBED_MODEL, input=text)
        return response["embeddings"][0]
    except Exception:
        return None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    norm_product = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if norm_product == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / norm_product)


def check_embed_model_available() -> bool:
    try:
        ollama.embed(model=EMBED_MODEL, input="test")
        return True
    except Exception:
        return False


def analyze_round(round_result: Dict) -> Optional[DriftReport]:
    original = round_result["original"]
    hops = round_result["hops"]

    original_emb = get_embedding(original)
    if original_emb is None:
        return None

    hop_drifts = _compute_hop_drifts(original_emb, hops)
    agent_scores = _compute_agent_scores(hop_drifts)
    worst_duo = _find_worst_duo(hop_drifts, agent_scores)
    worst_team = _find_worst_team(hop_drifts)

    worst_single = agent_scores[0] if agent_scores else None

    final_sim = hop_drifts[-1].output_similarity if hop_drifts else 1.0
    total_drift = 1.0 - final_sim

    return DriftReport(
        hop_drifts=hop_drifts,
        agent_scores=agent_scores,
        worst_single=worst_single,
        worst_duo=worst_duo,
        worst_team=worst_team,
        total_drift=total_drift,
    )


def _compute_hop_drifts(
    original_emb: List[float],
    hops: List[Dict],
) -> List[HopDrift]:
    results = []
    prev_similarity = 1.0
    prev_emb = original_emb

    for hop in hops:
        pass_number = hop["pass_number"]

        if hop["type"] == "single":
            agent_names = [hop["agent_name"]]
            if hop["decision"] == "pass" and hop["message"]:
                output_text = hop["message"]
            else:
                results.append(HopDrift(
                    pass_number=pass_number,
                    hop_type="single",
                    agent_names=agent_names,
                    input_similarity=prev_similarity,
                    output_similarity=prev_similarity,
                    drift_delta=0.0,
                ))
                continue
        else:
            agent_names = [a["agent_name"] for a in hop.get("agents", [])]
            merged = hop.get("merged_message", "")
            if merged:
                output_text = merged
            else:
                results.append(HopDrift(
                    pass_number=pass_number,
                    hop_type="parallel",
                    agent_names=agent_names,
                    input_similarity=prev_similarity,
                    output_similarity=prev_similarity,
                    drift_delta=0.0,
                ))
                continue

        output_emb = get_embedding(output_text)
        if output_emb is None:
            results.append(HopDrift(
                pass_number=pass_number,
                hop_type=hop["type"],
                agent_names=agent_names,
                input_similarity=prev_similarity,
                output_similarity=prev_similarity,
                drift_delta=0.0,
            ))
            continue

        output_similarity = cosine_similarity(original_emb, output_emb)
        drift_delta = prev_similarity - output_similarity
        if drift_delta < 0:
            drift_delta = 0.0

        results.append(HopDrift(
            pass_number=pass_number,
            hop_type=hop["type"],
            agent_names=agent_names,
            input_similarity=prev_similarity,
            output_similarity=output_similarity,
            drift_delta=drift_delta,
        ))

        prev_similarity = output_similarity
        prev_emb = output_emb

    return results


def _compute_agent_scores(hop_drifts: List[HopDrift]) -> List[AgentScore]:
    scores = defaultdict(lambda: {"score": 0.0, "count": 0})

    for hd in hop_drifts:
        if hd.drift_delta <= 0:
            continue
        share = hd.drift_delta / len(hd.agent_names)
        for name in hd.agent_names:
            scores[name]["score"] += share
            scores[name]["count"] += 1

    result = [
        AgentScore(name=name, culpable_score=data["score"], hop_count=data["count"])
        for name, data in scores.items()
    ]
    result.sort(key=lambda s: s.culpable_score, reverse=True)
    return result


def _find_worst_duo(
    hop_drifts: List[HopDrift],
    agent_scores: List[AgentScore],
) -> Optional[Tuple[str, str, float]]:
    best_duo = None
    best_score = 0.0

    # Check consecutive passes
    for i in range(len(hop_drifts) - 1):
        h1 = hop_drifts[i]
        h2 = hop_drifts[i + 1]
        if len(h1.agent_names) == 1 and len(h2.agent_names) == 1:
            combined = h1.drift_delta + h2.drift_delta
            if combined > best_score:
                best_score = combined
                best_duo = (h1.agent_names[0], h2.agent_names[0], combined)

    # Check pairs within parallel groups
    for hd in hop_drifts:
        if hd.hop_type == "parallel" and len(hd.agent_names) == 2 and hd.drift_delta > best_score:
            best_score = hd.drift_delta
            best_duo = (hd.agent_names[0], hd.agent_names[1], hd.drift_delta)

    return best_duo


def _find_worst_team(
    hop_drifts: List[HopDrift],
) -> Optional[Tuple[List[str], float]]:
    best_team = None
    best_score = 0.0

    for hd in hop_drifts:
        if hd.hop_type == "parallel" and len(hd.agent_names) >= 3:
            if hd.drift_delta > best_score:
                best_score = hd.drift_delta
                best_team = (list(hd.agent_names), hd.drift_delta)

    return best_team


SINGLE_TEMPLATES = [
    (
        "HR NOTICE: {name} is hereby placed on probation for single-handedly\n"
        "derailing office communications.\n"
        "Culpable drift score: {score:.3f}\n"
        "Recommended action: Mandatory active listening workshop (3 days)."
    ),
    (
        "INTERNAL MEMO — RE: Communication Integrity Violation\n"
        "Employee: {name}\n"
        "Infraction: Willful distortion of corporate messaging ({score:.3f} drift units)\n"
        "Status: Under review by the Office of Information Accuracy."
    ),
    (
        "DISCIPLINARY NOTICE: {name} has been identified as the primary vector\n"
        "of informational entropy in this communication chain.\n"
        "Drift contribution: {score:.3f}\n"
        "Please report to HR Conference Room B at your earliest convenience."
    ),
]

DUO_TEMPLATES = [
    (
        "HR ALERT: The partnership of {name1} and {name2} has been flagged as\n"
        "a toxic communication dyad.\n"
        "Combined drift damage: {score:.3f}\n"
        "Recommendation: These employees must not be assigned to the same\n"
        "floor, breakroom rotation, or Slack channel."
    ),
    (
        "MEMO — RE: Coordinated Misinformation Event\n"
        "Parties involved: {name1}, {name2}\n"
        "Assessment: When these two are in proximity, message fidelity drops\n"
        "by {score:.3f} units. This is not a coincidence.\n"
        "Action: Mandatory separation protocol effective immediately."
    ),
    (
        "NOTICE OF INVESTIGATION: {name1} and {name2} have been referred\n"
        "to the Internal Communications Review Board.\n"
        "Joint drift impact: {score:.3f}\n"
        "Pending investigation, both parties are restricted to email-only\n"
        "communication. No hallway conversations until further notice."
    ),
]

TEAM_TEMPLATES = [
    (
        "URGENT — ALL-HANDS NOTICE\n"
        "A {count}-person misinformation task force has been identified:\n"
        "{names_list}\n"
        "Single-pass drift spike: {score:.3f}\n"
        "This group, when operating simultaneously, constitutes an existential\n"
        "threat to factual office communication.\n"
        "Recommended action: Staggered lunch breaks. Permanently."
    ),
    (
        "INCIDENT REPORT — Category: Mass Communication Failure\n"
        "Responsible parties: {names_list}\n"
        "When these {count} individuals received the same message simultaneously,\n"
        "the resulting merged output deviated {score:.3f} units from source material.\n"
        "HR assessment: This is not collaboration. This is coordinated chaos."
    ),
    (
        "EMERGENCY MEMO — RE: Group Misinformation Event\n"
        "The following {count} employees have been placed on immediate\n"
        "communications watch: {names_list}\n"
        "Combined drift spike: {score:.3f}\n"
        "Until further notice, this group may not occupy the same meeting room,\n"
        "group chat, or water cooler vicinity."
    ),
]


def generate_hr_report(report: DriftReport) -> str:
    candidates = []

    if report.worst_single:
        candidates.append(("single", report.worst_single.culpable_score))
    if report.worst_duo:
        candidates.append(("duo", report.worst_duo[2]))
    if report.worst_team:
        candidates.append(("team", report.worst_team[1]))

    if not candidates:
        return "HR NOTE: No significant communication drift detected. Carry on."

    candidates.sort(key=lambda c: c[1], reverse=True)
    winner = candidates[0][0]

    if winner == "single":
        agent = report.worst_single
        template = random.choice(SINGLE_TEMPLATES)
        return template.format(name=agent.name, score=agent.culpable_score)

    if winner == "duo":
        name1, name2, score = report.worst_duo
        template = random.choice(DUO_TEMPLATES)
        return template.format(name1=name1, name2=name2, score=score)

    names, score = report.worst_team
    names_list = ", ".join(names)
    template = random.choice(TEAM_TEMPLATES)
    return template.format(count=len(names), names_list=names_list, score=score)
