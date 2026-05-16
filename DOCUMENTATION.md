# Office Gossip Simulator - Documentation

A Python CLI app that simulates office gossip spreading through a chain of AI-powered persona agents. Each agent distorts a message according to their personality, orchestrated by a separate LLM-based coordinator. Built on Ollama running locally with the `llama3.1` (8B) model.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Version 1: Linear Gossip Chain](#version-1-linear-gossip-chain)
- [Version 2: Multi-Pass Parallel Fan-Out](#version-2-multi-pass-parallel-fan-out)
- [Agent Personas](#agent-personas)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Python 3.9+**
- **Ollama** installed and running locally ([ollama.com/download](https://ollama.com/download))
- **llama3.1** model pulled: `ollama pull llama3.1`
- **ollama Python package**: `pip3 install ollama`

## Quick Start

```bash
# 1. Make sure Ollama is running
ollama serve

# 2. Pull the model (one-time, ~4.7GB download)
ollama pull llama3.1

# 3. Install the Python package
pip3 install ollama

# 4. Run the simulator
cd /path/to/Gossip
python3 -m gossip_simulator.main              # Defaults to v2 (parallel fan-out)
python3 -m gossip_simulator.main --mode v1    # Linear chain (1 agent at a time)
python3 -m gossip_simulator.main --mode v2    # Multi-pass parallel fan-out
```

## Running Each Version

### Version 1 - Linear Chain
```bash
python3 -m gossip_simulator.main --mode v1
```
Each agent speaks once per round. A simple telephone-game chain with up to 5 hops per round.

### Version 2 - Multi-Pass Parallel Fan-Out (Default)
```bash
python3 -m gossip_simulator.main --mode v2
```
Agents can be called multiple times. The orchestrator can send the message to multiple agents simultaneously, and their outputs are merged. Up to 10 passes per round.

## Project Structure

```
gossip_simulator/
  __init__.py          - Package marker (empty)
  agents.py            - 5 persona definitions + LLM call wrapper (shared)
  display.py           - Terminal output formatting with ANSI colors (shared)
  orchestrator_v1.py   - v1 routing logic (pick one agent from shrinking pool)
  orchestrator_v2.py   - v2 routing logic (pick 1+ agents, merger)
  runner_v1.py         - v1 round loop (linear, agents used once)
  runner_v2.py         - v2 round loop (multi-pass, parallel fan-out, merge)
  drift.py             - Semantic drift analysis, scoring, HR report templates (v2)
  visualize.py         - Graphviz flow diagram + matplotlib drift chart (v2)
  main.py              - Entry point with --mode flag, runs N rounds
```

---

## Version 1: Linear Gossip Chain

```bash
python3 -m gossip_simulator.main --mode v1
```

The original design. A simple telephone-game chain where each agent speaks once per round.

### How It Works

1. A starting message is provided (default: *"Did you hear? The CEO is thinking of leaving."*)
2. The **orchestrator** (a separate LLM call) picks which agent should hear the gossip first
3. That agent receives the message and either:
   - **Passes**: distorts the message through their personality and forwards it
   - **Stays silent**: declines to participate
4. The agent is **removed from the pool** (each agent can only speak once per round)
5. The orchestrator picks the next agent from the remaining pool
6. This repeats until the orchestrator ends the chain or all 5 agents have gone
7. The process runs for 3 rounds total, each starting fresh

### Architecture

```
main.py  ->  run_round()  ->  [ orchestrator picks ] -> [ agent distorts ] -> repeat
                                       |                        |
                              orchestrator_v1.py           agents.py
                            (pick_next_agent)         (get_agent_response)
```

**Key design principle**: Each agent call is fully isolated. An agent only receives its own system prompt and the current version of the message. No agent sees previous agents' reasoning, the audit trail, or the original message.

### Orchestrator (v1)

- Makes a separate `ollama.chat()` call with `temperature=0.3` (low creativity for coherent routing)
- Returns JSON: `{"next_agent": "name"}` or `{"next_agent": null}` to end the chain
- Receives the list of agents who haven't spoken yet and a summary of what's happened
- Prompted to be unpredictable: sometimes skipping agents, sometimes ending early

### Agent Calls (v1)

- Each agent gets a separate `ollama.chat()` call with `temperature=0.8` (higher creativity for varied distortion)
- All calls use `format="json"` to force valid JSON output from the model
- Returns JSON: `{"decision": "pass"|"silent", "message": "...", "monologue": "..."}`

### Output Format (v1)

Per hop:
```
[Pass 1]
[The Gossip] -> pass
Internal monologue: "This is too juicy not to share"
Message: "I heard from three different people that the CEO..."
```

End of round:
```
=== FINAL MESSAGE ===
Original: "Did you hear? The CEO is thinking of leaving."
Final:    "The entire board is being replaced after the CEO's secret meeting..."
Hops: 4
```

After all rounds: a comparison table showing each round's agent sequence and final message.

### Limitations (v1)

- **Linear only**: one agent at a time, no parallel processing
- **Single use**: each agent can only speak once per round (max 5 hops)
- **Predictable decay**: the message always passes through a subset of agents in sequence

---

## Version 2: Multi-Pass Parallel Fan-Out

```bash
python3 -m gossip_simulator.main --mode v2    # or just: python3 -m gossip_simulator.main
```

The default version. Agents can be called multiple times, the orchestrator can send the message to multiple agents simultaneously, and parallel outputs are merged into one chaotic blended message.

### What Changed from v1

| Feature | v1 | v2 |
|---------|----|----|
| Agent reuse | Once per round | Unlimited (up to 10 passes total) |
| Routing | One agent at a time | Single or parallel fan-out (2-3 agents) |
| Agent pool | Shrinks as agents speak | Never shrinks, stays full |
| Self-loops | N/A (agents removed) | Prevented: agent can't immediately follow itself |
| Max hops | 5 (one per agent) | 10 passes per round |
| Merge step | N/A | Blends parallel outputs via separate LLM call |
| Orchestrator format | `{"next_agent": "name"}` | `{"next_agents": ["name1", "name2"]}` |

### How It Works (v2)

1. Starting message is the same
2. The orchestrator picks **one or more agents** from the full pool
3. **If one agent is picked** (single pass): same as v1, agent distorts and the chain continues
4. **If multiple agents are picked** (parallel fan-out):
   - All selected agents receive the **same current message** independently
   - Each agent produces their own distorted version (or stays silent)
   - A **merger LLM call** blends all outputs into one chaotic combined message
   - The merged message becomes the new current message
5. After each pass, the agents who just spoke are **excluded from the next pass only** (no self-loops), but can be picked again after that
6. The loop continues for up to **10 passes** per round, or until the orchestrator ends the chain
7. Still runs 3 rounds total

### Architecture (v2)

```
main.py -> run_round() -> [ orchestrator picks 1+ agents ]
                                    |
                          +---------+---------+
                          |         |         |
                       agent A   agent B   agent C    (parallel fan-out)
                          |         |         |
                          +---------+---------+
                                    |
                            [ merger blends ]          (if 2+ agents passed)
                                    |
                            merged message
                                    |
                          [ orchestrator picks next ]
                                    |
                                  ...repeat (up to 10 passes)
```

### Orchestrator (v2)

- Same model and temperature as v1 (`llama3.1`, `temperature=0.3`)
- New JSON format: `{"next_agents": ["name1", "name2"]}` or `{"next_agents": null}`
- Receives all agent names + which ones are **excluded** (spoke in the previous pass)
- Prompted to vary between single picks and parallel fan-outs
- Backward compatible: still handles `{"next_agent": "name"}` from v1 format

### Merger

- A separate LLM call (`temperature=0.7`) that only activates when 2+ agents produce output in parallel
- Receives each agent's distorted version and blends them into one message
- Prompted to keep the most dramatic details from each version and create a "confused amalgamation"
- Returns JSON: `{"merged_message": "..."}`
- Fallback: if parsing fails, uses the longest agent message

### Self-Loop Prevention

- After each pass, all agents who participated (whether they passed or stayed silent) are added to `last_speakers`
- The orchestrator is told to exclude these agents on the next pick
- The parser also filters them out as a safety net
- After one pass of exclusion, agents become available again

### Output Format (v2)

Single pass (same as v1 but with pass number):
```
[Pass 1]
[The Gossip] -> pass
Internal monologue: "This is too juicy not to share"
Message: "I heard from three different people that the CEO..."
```

Parallel fan-out:
```
[Pass 3 - PARALLEL FAN-OUT]
........................................
[The Catastrophizer] -> pass
  Internal monologue: "This is the end of everything"
  Message: "The company is on the verge of total collapse..."
[The Exaggerator] -> pass
  Internal monologue: "This needs to be bigger"
  Message: "Over 500 executives are reportedly fleeing..."
........................................

[MERGE]
Blended message: "The company is collapsing as hundreds of executives flee..."
```

End of round:
```
=== FINAL MESSAGE ===
Original: "Did you hear? The CEO is thinking of leaving."
Final:    "Thousands of employees are being evacuated as the company..."
Passes: 7 (2 parallel)
```

Comparison table shows parallel groups in bracket notation:
```
Round 1
Agents: The Gossip -> [The Catastrophizer + The Exaggerator] -> The Confidant -> ...
Final:  "..."
```

---

## Agent Personas

| Agent | Color | Behavior |
|-------|-------|----------|
| **The Gossip** | Magenta | Exaggerates everything, adds drama, invents details, name-drops imaginary witnesses |
| **The Catastrophizer** | Red | Assumes the worst interpretation: layoffs, bankruptcy, total collapse |
| **The Confidant** | Blue | Prefaces with "Don't tell anyone but...", claims insider sources, adds fake secrecy |
| **The Skeptic** | Yellow | Doubts everything, hedges with "apparently", "supposedly", "allegedly" |
| **The Exaggerator** | Green | Picks one detail and amplifies it 10x (one person leaving becomes mass exodus) |

Each agent's system prompt instructs them to:
1. Receive the current message
2. Decide to "pass" (distort and forward) or stay "silent"
3. If passing: produce a distorted 1-3 sentence version + a one-line internal monologue
4. Return a JSON object: `{"decision": "pass", "message": "...", "monologue": "..."}`

Agents almost always choose "pass" — silence is rare by design.

---

## Semantic Drift Analysis (v2 Only)

v2 includes an HR investigation mode that measures how much each agent distorts the message from the original, identifies the worst offenders, and produces a witty HR report.

### How Drift is Measured

After each round completes, the drift module:
1. Converts the original message into an embedding vector using `nomic-embed-text` (via Ollama)
2. Converts each hop's output message into an embedding
3. Calculates **cosine similarity** between each output and the original (1.0 = identical, 0.0 = completely different)
4. The **drift delta** per hop = previous similarity - current similarity (how much that hop moved away from the original)

### Culpable Score

Each agent's culpable score is the **sum** of all their drift deltas across every pass they participated in during a round.

- **Single pass**: the full drift delta is attributed to the agent
- **Parallel fan-out**: the drift delta from the merged output is split equally among participating agents

An agent who causes small damage repeatedly accumulates a higher score than one who causes a single large spike. This measures total organizational damage.

### Worst Offender Categories

After scoring, the system identifies three categories:

| Category | Criteria | HR Report Style |
|----------|----------|-----------------|
| **Worst single agent** | Highest individual culpable score | Probation notice, disciplinary review |
| **Toxic duo** | Pair in consecutive or parallel passes with highest combined drift | Mandatory separation protocol |
| **Misinformation team** | 3+ agents in a parallel fan-out with the largest single drift spike | Staggered lunch breaks, communications watch |

The HR report picks whichever category caused the most damage and produces a randomly selected corporate memo template.

### Visualizations

Two PNG files are generated per round:

- **`gossip_flow_round_N.png`** — Graphviz directed graph showing message flow. Nodes are agent passes, edges show drift scores, color-coded green (low drift) to red (high drift). Parallel fan-outs display as branching/converging paths.
- **`drift_chart_round_N.png`** — Matplotlib line chart. X-axis = pass number, Y-axis = cosine similarity to original (starts at 1.0, decays). Each point is labeled with the agent name.

### Dependencies

```bash
ollama pull nomic-embed-text    # embedding model
pip3 install numpy matplotlib graphviz
```

System graphviz is also required for flow diagrams:
- macOS: `brew install graphviz`
- Ubuntu: `sudo apt install graphviz`

### Disabling Drift Analysis

```bash
python3 -m gossip_simulator.main --no-drift
```

### Files

- `gossip_simulator/drift.py` — embedding calls, cosine similarity, scoring, HR report templates
- `gossip_simulator/visualize.py` — graphviz flow diagram, matplotlib drift chart

---

## Configuration

Constants you can change in the source files:

| Constant | File | Default | Purpose |
|----------|------|---------|---------|
| `STARTING_MESSAGE` | main.py | "Did you hear? The CEO is thinking of leaving." | The initial gossip |
| `NUM_ROUNDS` | main.py | 3 | How many rounds to run |
| `MAX_PASSES` | runner_v2.py | 10 | Max passes per round (v2 only) |
| `MODEL` | agents.py | "llama3.1" | Ollama model name |
| `AGENT_TEMPERATURE` | agents.py | 0.8 | Creativity for persona agents |
| `ORCHESTRATOR_TEMPERATURE` | orchestrator_v1.py / orchestrator_v2.py | 0.3 | Creativity for routing decisions |
| `MERGER_TEMPERATURE` | orchestrator_v2.py | 0.7 | Creativity for merging parallel outputs (v2 only) |
| `EMBED_MODEL` | drift.py | "nomic-embed-text" | Ollama embedding model for drift analysis |

---

## Troubleshooting

**"Cannot connect to Ollama"**
- Make sure Ollama is running: `ollama serve`
- If you see "address already in use", Ollama is already running (this is fine)

**"Model not found"**
- Pull the model: `ollama pull llama3.1`

**Slow responses**
- Each LLM call takes a few seconds on the 8B model. A full 3-round run with parallel fan-outs can take several minutes.
- Status messages (`[Calling The Gossip...]`, `[Asking orchestrator...]`) show progress in real-time.

**JSON parsing errors**
- All LLM calls use `format="json"` which constrains the model to produce valid JSON.
- A layered fallback parser handles edge cases: direct parse, code-block extraction, regex extraction.
- If all parsing fails, agents default to "silent" and the orchestrator falls back to random picks. The app never crashes from malformed LLM output.

**"ModuleNotFoundError: No module named 'ollama'"**
- Install the package: `pip3 install ollama`

**Drift analysis says "nomic-embed-text not available"**
- Pull the embedding model: `ollama pull nomic-embed-text`

**Flow diagram fails to render**
- Install system graphviz: `brew install graphviz` (macOS) or `sudo apt install graphviz` (Ubuntu)
- Also install the Python package: `pip3 install graphviz`
