from __future__ import annotations

from typing import Dict, List, Optional

from gossip_simulator.drift import DriftReport, HopDrift


def _drift_to_color(drift_delta: float) -> str:
    """Map drift delta to hex color: green (low) -> yellow -> red (high)."""
    clamped = min(max(drift_delta / 0.3, 0.0), 1.0)
    if clamped < 0.5:
        r = int(255 * (clamped * 2))
        g = 200
    else:
        r = 255
        g = int(200 * (1 - (clamped - 0.5) * 2))
    return f"#{r:02x}{g:02x}44"


def generate_flow_diagram(
    round_num: int,
    round_result: Dict,
    report: DriftReport,
    output_dir: str = ".",
) -> Optional[str]:
    try:
        import graphviz
    except ImportError:
        print("    [graphviz not installed, skipping flow diagram]")
        return None

    dot = graphviz.Digraph(
        format="png",
        graph_attr={"rankdir": "TB", "bgcolor": "#1a1a2e", "pad": "0.5"},
        node_attr={
            "style": "filled",
            "fontname": "Helvetica",
            "fontsize": "11",
            "fontcolor": "white",
            "shape": "box",
            "margin": "0.15,0.1",
        },
        edge_attr={
            "fontname": "Helvetica",
            "fontsize": "9",
            "fontcolor": "#cccccc",
            "color": "#555555",
        },
    )

    dot.node("original", f"Original Message\n(similarity: 1.000)", fillcolor="#16213e")

    prev_node = "original"

    for i, hd in enumerate(report.hop_drifts):
        color = _drift_to_color(hd.drift_delta)
        node_id = f"hop_{i}"

        if hd.hop_type == "single":
            label = f"Pass {hd.pass_number}: {hd.agent_names[0]}\nsim: {hd.output_similarity:.3f}"
            dot.node(node_id, label, fillcolor=color)
            dot.edge(prev_node, node_id, label=f" drift: {hd.drift_delta:.3f}")
            prev_node = node_id
        else:
            fan_out_id = f"fanout_{i}"
            merge_id = f"merge_{i}"

            dot.node(fan_out_id, f"Pass {hd.pass_number}: Fan-Out", fillcolor="#0f3460", shape="diamond")
            dot.edge(prev_node, fan_out_id)

            for j, name in enumerate(hd.agent_names):
                agent_id = f"hop_{i}_agent_{j}"
                dot.node(agent_id, name, fillcolor=color)
                dot.edge(fan_out_id, agent_id)
                dot.edge(agent_id, merge_id)

            dot.node(merge_id, f"Merge\nsim: {hd.output_similarity:.3f}", fillcolor=color, shape="diamond")
            dot.edge(fan_out_id, merge_id, style="invis")
            prev_node = merge_id

    final_sim = report.hop_drifts[-1].output_similarity if report.hop_drifts else 1.0
    dot.node("final", f"Final Message\n(similarity: {final_sim:.3f})", fillcolor="#e94560")
    dot.edge(prev_node, "final")

    path = f"{output_dir}/gossip_flow_round_{round_num}"
    try:
        dot.render(path, cleanup=True)
        return f"{path}.png"
    except Exception as e:
        print(f"    [Failed to render flow diagram: {e}]")
        return None


def generate_drift_chart(
    round_num: int,
    report: DriftReport,
    output_dir: str = ".",
) -> Optional[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("    [matplotlib not installed, skipping drift chart]")
        return None

    passes = [0]
    similarities = [1.0]
    labels = ["Original"]

    for hd in report.hop_drifts:
        passes.append(hd.pass_number)
        similarities.append(hd.output_similarity)
        if len(hd.agent_names) == 1:
            labels.append(hd.agent_names[0])
        else:
            labels.append(" + ".join(hd.agent_names))

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    ax.plot(passes, similarities, "o-", color="#e94560", linewidth=2, markersize=8, zorder=3)
    ax.fill_between(passes, similarities, alpha=0.15, color="#e94560")

    for x, y, label in zip(passes, similarities, labels):
        short = label.replace("The ", "")
        ax.annotate(
            short,
            (x, y),
            textcoords="offset points",
            xytext=(0, 12),
            ha="center",
            fontsize=8,
            color="white",
            fontweight="bold",
        )

    ax.set_xlabel("Pass Number", color="white", fontsize=11)
    ax.set_ylabel("Cosine Similarity to Original", color="white", fontsize=11)
    ax.set_title(f"Semantic Drift — Round {round_num}", color="white", fontsize=13, fontweight="bold")
    ax.set_ylim(0, 1.05)
    ax.tick_params(colors="white")
    ax.spines["bottom"].set_color("#555555")
    ax.spines["left"].set_color("#555555")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.2, color="white")

    path = f"{output_dir}/drift_chart_round_{round_num}.png"
    try:
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        return path
    except Exception as e:
        print(f"    [Failed to save drift chart: {e}]")
        plt.close(fig)
        return None
