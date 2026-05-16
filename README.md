# Office Gossip Simulator

Ever played the telephone game? Now imagine it with AI agents who each have their own dramatic personality. One exaggerates, one catastrophizes, one adds fake "insider sources" — and by the end, a simple rumor about the CEO becomes an apocalyptic company-wide meltdown.

This is a multi-agent orchestration demo built on Ollama. A central orchestrator LLM decides who hears the gossip next, and each persona agent distorts the message before passing it on. No agent sees what the others said — just like real office gossip.

## Sample Output

```
[Pass 1]
[The Gossip] -> pass
Internal monologue: "This is too juicy not to share"
Message: "I heard from three different people that the CEO was seen leaving
         a secret meeting with the board, and apparently his office is already
         being cleared out."

[Pass 2]
[The Catastrophizer] -> pass
Internal monologue: "This is the beginning of the end"
Message: "The company is on the verge of total collapse — the CEO has been
         forced out by the board and mass layoffs are expected by Friday."

[Pass 3]
[The Exaggerator] -> pass
Internal monologue: "This needs to be way bigger"
Message: "Over 500 employees are being let go as the entire executive team
         flees the sinking ship. The building might be shut down by Monday."

=== FINAL MESSAGE ===
Original: "Did you hear? The CEO is thinking of leaving."
Final:    "Over 500 employees are being let go as the entire executive team..."
Passes: 3
```

## Two Modes

| Mode | Command | Description |
|------|---------|-------------|
| **v1 - Linear** | `python3 -m gossip_simulator.main --mode v1` | One agent at a time, each speaks once. Classic telephone game. |
| **v2 - Parallel** | `python3 -m gossip_simulator.main --mode v2` | Agents can repeat, multiple agents hear the message at once, outputs get merged. More chaos. Default. |

## Quick Start

```bash
# 1. Make sure Ollama is running
ollama serve

# 2. Pull the model (one-time, ~4.7GB download)
ollama pull llama3.1

# 3. Install the Python package
pip3 install ollama

# 4. Run it
cd /path/to/Gossip
python3 -m gossip_simulator.main              # v2 parallel (default)
python3 -m gossip_simulator.main --mode v1    # v1 linear
```

## The Agents

| Agent | Personality |
|-------|-------------|
| **The Gossip** | Adds drama, invents details, name-drops imaginary witnesses |
| **The Catastrophizer** | Assumes the worst: layoffs, bankruptcy, total collapse |
| **The Confidant** | "Don't tell anyone but..." — claims insider sources, adds fake secrecy |
| **The Skeptic** | Doubts everything, hedges with "apparently" and "supposedly" |
| **The Exaggerator** | Picks one detail and amplifies it 10x |

## How It Works

- An **orchestrator agent** (separate LLM call) decides who hears the gossip next
- Each **persona agent** (separate LLM call) distorts the message through their personality
- No agent sees what the others said — only their own persona and the current message
- In v2, multiple agents can hear the message at once, and a **merger** blends their outputs
- Runs 3 rounds to show how the same starting message drifts differently each time

## HR Investigation Mode (v2)

v2 includes semantic drift analysis — it measures how much each agent distorts the message using text embeddings, then produces:

- **Culpable Score Leaderboard** — ranks agents by total drift contribution
- **HR "Name and Shame" Report** — a witty corporate memo naming the worst offender, toxic duo, or misinformation team
- **Drift Chart** — a line graph showing similarity decay over passes (saved as PNG)
- **Flow Diagram** — a directed graph showing message flow between agents with color-coded drift (saved as PNG)

```
=== CULPABLE SCORE LEADERBOARD ===

1. The Catastrophizer      [##########..........] 0.185  (2 passes)
2. The Exaggerator         [########............] 0.142  (1 pass)
3. The Gossip              [######..............] 0.098  (2 passes)

**************************************************
OFFICE OF HUMAN RESOURCES
CONFIDENTIAL — INTERNAL INVESTIGATION
**************************************************

HR ALERT: The partnership of The Catastrophizer and The Exaggerator has been
flagged as a toxic communication dyad.
Combined drift damage: 0.250
Recommendation: These employees must not be assigned to the same
floor, breakroom rotation, or Slack channel.

**************************************************
```

Requires the `nomic-embed-text` embedding model:
```bash
ollama pull nomic-embed-text
pip3 install numpy matplotlib graphviz
```

Disable drift analysis with `--no-drift`:
```bash
python3 -m gossip_simulator.main --no-drift
```

## Prerequisites

- Python 3.9+
- [Ollama](https://ollama.com/download) running locally
- `llama3.1` model: `ollama pull llama3.1`
- `pip3 install ollama`
- For drift analysis (v2): `ollama pull nomic-embed-text` and `pip3 install numpy matplotlib graphviz`

## Full Documentation

See [DOCUMENTATION.md](DOCUMENTATION.md) for the complete technical reference — architecture diagrams, JSON formats, configuration options, and troubleshooting.
