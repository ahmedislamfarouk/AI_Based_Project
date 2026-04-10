# Your Script — A Taxonomy of Agentic Systems
## Paper pages 14–18 | Target: 4 minutes | ~520 words spoken

---

> **Pacing guide:** ~130 words/minute. Each timed block adds up to 4 min.
> **Diagrams:** You have 4 images — each one is marked below exactly when to show it.

---

---

## AUDIENCE ENGAGEMENT — Ask This First (30 seconds)

> **[Show nothing on screen yet — make eye contact with the audience]**

> "Before I start — quick question for everyone."

**Ask the audience:**
> **"When you use ChatGPT or any AI assistant — do you think it's just answering from memory, or is it actually going out and searching for something in real time?"**

**[Pause — wait 5–8 seconds, let hands go up or people call out]**

**If they say "searching":**
> "Some of you are right — but only for some tools. And that difference is actually the entire point of this section."

**If they say "memory" / "training data":**
> "Exactly right — and that's the problem. An agent that only knows what it was trained on is blind to the real world. That's where our taxonomy begins."

**If mixed answers:**
> "You're both right — and the fact that it depends on *which* tool you're using is exactly the point. There are five distinct levels of what an AI agent can actually do. Let me show you."

> **[Now move to your slides]**

---

---

## OPENING — 15 seconds

> "The paper gives us a five-level taxonomy — a pyramid. You don't start at the top. You start at the bottom and climb as the task demands it."

---

## ► SHOW DIAGRAM: Level Progression Ladder
### (file: `98d06r` — "Query: What was the score?" L0–L4 table)

**Say while pointing at each row:**
- **L0 row:** "No tools. Just memory. It cannot answer — the game happened after training."
- **L1 row:** "Add a search API. Now it finds the score."
- **L2 row:** "Now it doesn't just search — it plans. Finds score, finds stats, summarizes."
- **L3 row:** "Now it's a team. Coordinator routes to specialists — each one focused."
- **L4 row:** "And here it creates a new tool it didn't have before."

> "Same question — five completely different capabilities. That's the taxonomy."

---

## LEVEL 0 — The Core Reasoning System — 20 seconds

> "At the base: just a language model running alone. No tools, no live data. It knows a lot — but it's completely blind to the real world. Ask it 'what was the Yankees score last night?' — it cannot answer. That game happened after training. This is Level 0."

---

## LEVEL 1 — The Connected Problem-Solver — 30 seconds

> "Level 1 fixes that. Give the model a tool — a search API, a database — and it can now reach outside itself. It thinks: 'this needs real-time data,' calls Google Search, gets 'Yankees won 5-3', answers correctly."

> "The key technology: **RAG — Retrieval-Augmented Generation**. The agent looks it up before it speaks. This kills hallucinations. Most chatbots you use today are roughly here."

---

## ► SHOW DIAGRAM: Think → Act → Observe Loop
### (file: `1ekwq3` — circular loop with THINK / ACT / OBSERVE)

**Say while pointing:**
- **THINK box:** "Every cycle starts here — the agent makes a plan and assembles its context."
- **ACT box:** "Then it acts — calls the tool, hits the API."
- **OBSERVE box:** "Then it reads the result and updates what it knows."
- **Arrow back to THINK:** "And loops. This repeats until the mission is done."

> "This loop is the heartbeat of every agent from Level 1 upward. Keep this in mind — at Level 3, multiple agents are each running their own version of this loop simultaneously."

---

## LEVEL 2 — The Strategic Problem-Solver — 40 seconds

> "Level 2 is where agents start to feel genuinely intelligent. One agent, but now it *plans* multi-step goals. Example from the paper: 'Find a good coffee shop halfway between our two offices.'"

> "A Level 1 agent gets confused. A Level 2 agent thinks: Step one — find the midpoint using Maps. Step two — search for 4-star+ coffee shops there. Step three — present the results."

> "The key skill: **context engineering** — the agent curates exactly the right information to feed itself at each step. It's actively managing its own attention so the model stays accurate."

---

## LEVEL 3 — The Collaborative Multi-Agent System — 35 seconds

> "Level 3 is a complete shift. You stop building one powerful agent and start building a *team*. A coordinator agent gets the mission and delegates to specialists running in parallel."

> "Paper's example: 'Launch the Solaris headphones.' Coordinator spins up a MarketResearchAgent, a MarketingAgent, a WebDevAgent — all working at once. The strength is in division of labor."

---

## ► SHOW DIAGRAM: L2 vs L3 Side-by-Side
### (file: `wrbti1` — "LEVEL 2: Single Agent" vs "LEVEL 3: Multi-Agent")

**Say while pointing:**
- **Left side (L2):** "One agent. Sequential. Step 1 → Step 2 → Step 3. It does everything itself."
- **Right side (L3):** "Coordinator at the top. Three specialist agents below. All running in parallel."
- **Key point:** "Same mission — completely different architecture. L3 is faster and each part is easier to test independently."

---

## LEVEL 4 — The Self-Evolving System — 30 seconds

> "At the frontier: Level 4. This agent doesn't just use tools — it *creates* them. The coordinator notices it needs to track social media sentiment but has no tool for it. So it invokes an AgentCreator, builds a SentimentAgent on the fly, and adds it to the team."

---

## ► SHOW DIAGRAM: Level 4 Self-Expansion
### (file: `up43st` — Before/After with "Gap Identified" arrow and new Sentiment Agent)

**Say while pointing:**
- **Left side (Before):** "Two agents — Research and Writer. Fixed team, fixed capabilities."
- **Arrow in the middle:** "Gap identified. The agent realizes it's missing something."
- **Right side (After):** "New agent created automatically — highlighted in gold. The team expanded itself."

> "This is the key: Level 4 moves from a *fixed* set of capabilities to an *expanding* one. It's not just automation — it's a system that grows."

---

## CLOSING — 15 seconds

> "Most production systems today are Level 1 or 2. Level 3 is emerging. Level 4 is the frontier. This taxonomy is your first design decision before writing a single line of code — scope the agent to the level the task actually needs."

---

**[Hand off]**
> "Now that we know *what kind* of agent we're building, [name] will cover *how* it's actually built — starting with the brain and the hands."

---

---

# DIAGRAM REFERENCE CARD
### What each image is, when to show it, what to say

---

### Diagram A — Level Progression Ladder
**File:** `98d06r` (the table with L0–L4 rows and checkmarks)
**Show:** Right after opening, before Level 0 explanation
**Key lines:**
- "Same question — five different capabilities"
- Point L0: "Can't answer — blind to real world"
- Point L1: "Finds the answer with a tool"
- Point L2: "Plans and summarizes — not just one step"
- Point L3: "Splits the work across a team"
- Point L4: "Builds a new tool it was missing"

---

### Diagram B — Think → Act → Observe Loop
**File:** `1ekwq3` (circular loop with gear / hand / eye icons)
**Show:** After Level 1 explanation
**Key lines:**
- "THINK = plan + assemble context"
- "ACT = call the tool"
- "OBSERVE = read the result, update memory"
- "Loops until mission complete"
- "Every agent from Level 1 up runs this — keep it in mind for what comes next"

---

### Diagram C — L2 vs L3 Side-by-Side
**File:** `wrbti1` (left: single agent steps, right: coordinator + 3 specialists)
**Show:** After Level 3 explanation
**Key lines:**
- "Left: one agent, sequential steps"
- "Right: coordinator delegates, specialists run in parallel"
- "Same result, different architecture — L3 is faster and more modular"

---

### Diagram D — Level 4 Self-Expansion
**File:** `up43st` (before/after org chart with new gold Sentiment Agent)
**Show:** After Level 4 explanation
**Key lines:**
- "Before: fixed team of two"
- "Gap identified: coordinator notices missing capability"
- "After: new agent created automatically — the gold box"
- "The system expanded its own capabilities without a developer doing it"

---

---

# AUDIENCE QUESTIONS — With Full Prepared Answers

---

**Q1 — Most likely**
> "What level do most real-world agents today operate at?"

**Your answer:**
> "Primarily Level 1 and 2. Level 1 is most chatbots and AI assistants that can call an external tool. Level 2 is multi-step planning agents like automated research or workflow tools. Level 3 multi-agent systems exist — the paper covers Google Co-Scientist — but they're much harder to build and debug reliably. Level 4 is almost entirely research right now."

---

**Q2 — Very likely**
> "What's the difference between Level 2 and Level 3? They both plan."

**Your answer:**
> "The distinction is *who* plans and *who* executes. In Level 2, one agent plans and does everything itself — sequentially. In Level 3, a coordinator plans and hands execution to separate specialist agents running in parallel. Level 2 is one person multitasking. Level 3 is a project manager with a team. Each specialist is smaller, faster, and easier to test independently."

---

**Q3 — Possible**
> "Why not just always build Level 4 if it can do everything?"

**Your answer:**
> "Complexity and risk scale with level. A Level 4 agent that creates its own tools can also create *unexpected* tools in unexpected ways. It's much harder to test, audit, and secure. The paper warns against over-engineering — match the level to the task. Customer service questions? Level 1 is fine. Building Level 4 for that is like driving a Formula 1 car to the supermarket."

---

**Q4 — Technical audience**
> "How does context engineering at Level 2 actually work? What goes in the context window?"

**Your answer:**
> "At each step, the agent assembles a fresh context window for the LM. It includes the original goal, the steps already taken, the tool results from each step, and what it plans to do next. The engineering part is that it *selects* what's relevant — overfilling the context degrades performance. It's selective memory. The orchestration layer — covered by the next presenter — manages this assembly."

---

**Q5 — Non-technical audience**
> "Can you give a real example of a Level 3 agent that exists today?"

**Your answer:**
> "Yes — the paper covers two. Google Co-Scientist is a multi-agent research system: a supervisor delegates to agents that generate, review, rank, and evolve scientific hypotheses. AlphaEvolve uses a team of agents to discover new algorithms — it's already improved Google's data center efficiency. Both are Level 3 approaching Level 4. Smaller-scale examples include enterprise automation platforms that route tasks between specialist agents for data retrieval, report writing, and approval."

---

**Q6 — From your engagement question earlier**
> "You asked us if ChatGPT searches in real-time — does that make it Level 1?"

**Your answer:**
> "Exactly right — when ChatGPT uses its search tool, it's operating at Level 1. When it doesn't have search enabled and just answers from training data, that's Level 0. A lot of AI products switch between these levels depending on which tools are turned on. That's why the taxonomy matters — the same underlying model can operate at different levels depending on what you give it access to."
