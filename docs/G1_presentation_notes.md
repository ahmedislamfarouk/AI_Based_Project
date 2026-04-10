# Introduction to Agents — Presentation Notes
## Starting from Paper Page 14: A Taxonomy of Agentic Systems

> Paper: "Introduction to Agents" — Google (Nov 2025)
> Coverage: Pages 14–51
> Team: 5 members

---

## MEMBER 1 — A Taxonomy of Agentic Systems (pp. 14–18)

### Core Idea
Not all agents are equal. Before building, you must decide *what kind* of agent fits the problem. The paper classifies agents into 5 levels, each building on the last.

### Key Points

**Figure 2 — The Taxonomy Pyramid (use this slide)**
```
Level 4: Self-Evolving System
  Level 3: Collaborative Multi-Agent
    Level 2: Strategic Problem-Solver
      Level 1: Connected Problem-Solver
        Level 0: Core Reasoning System
```

**Level 0 — Core Reasoning System**
- Just an LM running in isolation
- No tools, no memory, no real-time data
- Strong at explaining concepts, useless for live queries
- Example: "What was the Yankees score last night?" → cannot answer

**Level 1 — The Connected Problem-Solver**
- LM + external tools (search APIs, databases, RAG)
- Can now answer real-time questions
- Example: calls Google Search API → gets "Yankees won 5-3" → answers correctly
- Core capability: **Retrieval-Augmented Generation (RAG)**

**Level 2 — The Strategic Problem-Solver**
- Adds **context engineering**: agent actively selects and packages the right info for each step
- Plans multi-step goals autonomously
- Example: "Find a coffee shop halfway between our offices" → agent thinks: find midpoint → search for 4-star+ coffee shops there → synthesize
- Key skill: curating the model's attention window at each reasoning step

**Level 3 — Collaborative Multi-Agent System**
- Moves from one "super-agent" to a **team of specialists**
- A coordinator/manager agent delegates subtasks to specialist agents
- Example: "Launch new headphones" → Manager delegates to MarketResearchAgent, MarketingAgent, WebDevAgent simultaneously
- Mirrors how real human organizations work

**Level 4 — The Self-Evolving System**
- Agent can identify gaps in its own capabilities and **create new tools or agents** to fill them
- Example: Manager agent notices it needs social media monitoring → invokes AgentCreator → a new SentimentAnalysisAgent is born and joins the team
- Frontier territory — most production systems today are Level 1–2

### Diagram to Create
- Side-by-side comparison: same query handled at L0, L1, L2, L3 to show capability jump

### Likely Audience Question
> "What level do most production agents today operate at?"
- **Answer**: Most real-world production agents are Level 1–2. Level 3 multi-agent systems are emerging but still complex to maintain. Level 4 is mostly research.

---

## MEMBER 2 — Core Architecture: Model & Tools (pp. 19–22)

### Core Idea
An agent has 3 essential parts. Member 2 covers the first two: the **Model (Brain)** and **Tools (Hands)**.

### Key Points

**The Model — The Brain**
- The LM is the reasoning core. Model choice dictates capability, cost, and speed
- Picking the highest benchmark score ≠ best agent. Real-world success requires:
  - Superior **reasoning** for multi-step problems
  - Reliable **tool use** to interact with the world
- Best practice: define business problem first, then test models against *your specific metrics*
- Cost/speed routing: use a frontier model (Gemini 2.5 Pro) for complex planning, a fast model (Gemini 2.5 Flash) for simple classification tasks
- Models evolve fast — build a CI/CD pipeline to continuously evaluate new models (Agent Ops)

**Tools — The Hands**
Three categories:

| Category | What it does | Examples |
|----------|-------------|---------|
| **Retrieve Information** | Ground the agent in facts | RAG, Vector DBs, Knowledge Graphs, NL2SQL |
| **Execute Actions** | Change the world | Send email, update CRM, run Python code, call APIs |
| **Human in the Loop (HITL)** | Pause for human approval | `ask_for_confirmation()`, `ask_for_date_input()` |

- **RAG** = "library card" for the agent. Dramatically reduces hallucinations
- **NL2SQL** = query structured databases in plain English ("What were our top products last quarter?")
- **Code execution** = agent writes and runs Python/SQL on the fly in a secure sandbox
- **Function Calling** uses the **OpenAPI spec** as a contract: defines what a tool does, its parameters, and expected response
- **MCP (Model Context Protocol)** — new open standard for simpler tool discovery and connection

### Diagram to Create
- Visual: agent architecture showing Model + Tools connected, with the 3 tool categories labeled

### Likely Audience Question
> "How do you prevent the agent from calling the wrong tool or hallucinating a tool call?"
- **Answer**: The OpenAPI schema acts as a strict contract. The model generates a structured function call (not free text), which is validated before execution. MCP adds further standardization. HITL tools add a human checkpoint for high-stakes actions.

---

## MEMBER 3 — Core Architecture: Orchestration Layer + Deployment (pp. 22–26)

### Core Idea
If the Model is the brain and Tools are the hands, the **Orchestration Layer is the nervous system** — it runs the Think→Act→Observe loop, manages memory, and governs how agents collaborate.

### Key Points

**The Orchestration Layer**
- Runs the core agent loop: plan → pick tool → execute → observe result → repeat
- Decides: *when to think vs. when to act*, which tool to use, what goes into context next
- Uses reasoning strategies: **Chain-of-Thought** (break problem into steps), **ReAct** (reason + act interleaved)

**Core Design Choices**
- **Deterministic vs. Autonomous**: spectrum from hard-coded workflow (predictable) to fully LM-driven (flexible but unpredictable)
- **No-code vs. Code-first**: no-code builders for simple tasks; Google's **ADK (Agent Development Kit)** for production-grade systems
- A good framework must be: **open** (no vendor lock-in), **observable** (full traces/logs), and **controllable** (hybrid hard-rules + LM)

**Instruct with Domain Knowledge and Persona**
- System prompt = the agent's "constitution": who it is, what it can do, tone of voice, when to use which tools
- Example: `You are a helpful customer support agent for Acme Corp...`
- Few-shot examples in the prompt dramatically improve reliability

**Memory (Augment with Context)**
- **Short-term**: running scratchpad of the current conversation (Action → Observation pairs)
- **Long-term**: RAG system connected to vector DB — agent can "remember" user preferences from weeks ago

**Multi-Agent Design Patterns**

| Pattern | When to use | How it works |
|---------|-------------|-------------|
| **Coordinator** | Dynamic/non-linear tasks | Manager routes sub-tasks to specialists, aggregates responses |
| **Sequential** | Linear pipelines | Output of Agent A feeds directly into Agent B |
| **Iterative Refinement** | Quality-critical content | Generator agent creates, Critic agent evaluates, loop until quality threshold met (Figure 3) |
| **HITL** | High-stakes decisions | Workflow pauses for human approval before irreversible action |

**Agent Deployment and Services**
- Agent needs: runtime, session history, memory persistence, logging, security
- Options: **Vertex AI Agent Engine** (fully managed), or Docker container on Cloud Run/GKE
- Figure 4 (Vertex AI stack) shows the full deployment ecosystem: Agent Engine + ADK + LangGraph/LangChain + Tools + Models

### Diagram to Create
- Context window composition: show what fills the LM's input (system prompt + user query + tool results + memory + examples)

### Likely Audience Question
> "What happens when the agent gets stuck in an infinite loop or keeps failing at a task?"
- **Answer**: The orchestration layer sets a max iteration count. A well-designed agent also has error-handling in its system prompt ("if tool fails 3 times, escalate to human"). Observability traces let developers diagnose exactly where it looped.

---

## MEMBER 4 — Agent Ops & Interoperability (pp. 27–34)

### Core Idea
Building the agent is only half the job. **Agent Ops** is the discipline of measuring, evaluating, debugging, and continuously improving agents in production. Interoperability covers how agents connect to humans, other agents, and the financial world.

### Key Points

**Why Agent Ops is Different from Normal Software Testing**
- Traditional: `output == expected` — deterministic, binary pass/fail
- Agents: responses are probabilistic. You need a **Language Model as Judge** to evaluate quality
- Figure 5: Agent Ops is a sub-domain of GenAIOps, which inherits from MLOps → DevOps

**The Agent Ops Toolkit**

1. **Measure What Matters** — define KPIs before testing:
   - Goal completion rate, user satisfaction, task latency, cost per interaction, business impact (revenue, retention)

2. **LM-as-Judge** — automated quality evaluation:
   - A powerful model grades agent responses against a rubric: correctness, grounding, instruction-following
   - Run against a "golden dataset" of curated prompt→ideal-response pairs
   - Golden dataset maintenance is increasingly a Product Manager responsibility

3. **Metrics-Driven Deployment** — Go/No-Go gate:
   - Run new version against full eval dataset, compare scores to current production version
   - Use A/B deployments for safe rollout

4. **OpenTelemetry Traces** — for debugging:
   - Step-by-step recording of the agent's full execution: exact prompt sent → model reasoning → tool chosen → parameters → raw result
   - Trace ≠ metric. Traces are for root-cause analysis, not dashboards

5. **Human Feedback Loop**:
   - Thumbs-down = a new test case
   - Capture → replicate → add to evaluation dataset → prevent recurrence

**Agent Interoperability**

| Relationship | Protocol | Key Concept |
|---|---|---|
| **Agent ↔ Human** | UI / Gemini Live API | Chatbot, HITL, computer use, real-time voice/video |
| **Agent ↔ Agent** | **A2A protocol** | Agent Card (JSON business card) → task-oriented async communication |
| **Agent ↔ Money** | **AP2 + x402** | Cryptographically signed mandates; machine-to-machine micropayments via HTTP 402 |

- **A2A** solves discovery + communication between agents across teams/orgs
- **x402** allows an agent to pay for API access on a pay-per-use basis without accounts

### Likely Audience Question
> "How do you build a golden evaluation dataset if you have no production data yet?"
- **Answer**: Start by manually crafting 30–50 representative scenarios covering the full range of expected use cases, plus a few adversarial edge cases. As the agent goes to production, real interactions (especially negative feedback) continuously expand it.

---

## MEMBER 5 — Security, Evolution & Advanced Examples (pp. 34–51)

### Core Idea
Agents are powerful but dangerous if unsecured. This section covers the trust model for single agents and enterprise fleets, how agents improve over time, and two cutting-edge real-world examples.

### Key Points

**Securing a Single Agent — The Trust Trade-Off**
- More capability = more risk. Two primary threats:
  - **Rogue actions**: unintended harmful behaviors
  - **Sensitive data disclosure**: leaking private information
- Defense-in-depth (two layers):
  1. **Deterministic guardrails**: hard-coded rules outside the LM (e.g., policy engine blocks purchases >$100 without confirmation)
  2. **Reasoning-based defenses**: guard models that review the agent's proposed plan *before execution*, flag risky steps

**Agent Identity — A New Class of Principal**
- Agents are a 3rd category alongside users (OAuth/SSO) and service accounts (IAM)
- Each agent gets a cryptographically verifiable identity via **SPIFFE**
- Least-privilege principle: SalesAgent gets CRM read/write; HRAgent is explicitly denied
- Table 1: Users / Agents / Service accounts — authentication and scope

**Enterprise Fleet: Governance at Scale**
- "Agent sprawl" = same problem as API sprawl — chaotic, unauditable
- Solution: **Central Gateway** (control plane) + **Central Registry** (enterprise app store for agents)
  - Gateway enforces auth/authz, creates audit logs for every interaction
  - Registry provides versioning, security reviews, and discovery
- Figure 6: Security architecture layers (Application → Agent → Orchestration → Model)

**How Agents Evolve and Learn**
- Agents "age" and degrade as the world changes — must adapt autonomously
- Two learning inputs: **Runtime experience** (logs, traces, HITL feedback) + **External signals** (new policies, regulations)
- Two adaptation techniques:
  - **Enhanced Context Engineering**: continuously refine prompts, few-shot examples, memory retrieval
  - **Tool Optimization/Creation**: agent identifies missing capability → creates a new tool or Python script on the fly
- Figure 7: Multi-agent compliance workflow (Orchestrator → Query Decomposer → Reporting → Critiquing → Learning Agent)

**Advanced Example 1 — Google Co-Scientist**
- Multi-agent system for scientific research
- Supervisor agent delegates to: Generation, Reflection, Ranking (tournament), Evolution, Proximity Check, Meta-Review agents
- Continuously runs for hours/days, self-improving hypotheses in a loop
- Figures 8 & 9

**Advanced Example 2 — AlphaEvolve**
- AI agent that discovers and optimizes algorithms via evolutionary search
- Loop: LM generates code → Evaluator scores it → best programs seed next generation
- Already achieved: faster matrix multiplication, improved Google data center efficiency, new solutions to open math problems
- Excels when: *verifying a solution is easier than finding it*
- Figure 10 & 11

**Conclusion**
- Agent = Model (Brain) + Tools (Hands) + Orchestration (Nervous System) in a Think→Act→Observe loop
- Success is not in the initial prompt but in engineering rigor: robust tool contracts, context management, evaluation
- Paradigm shift: developer goes from "bricklayer" (explicit logic) to "director" (guiding an autonomous actor)

### Diagram to Create
- Security layers as concentric rings: deterministic guardrails (outer) → AI guard models (middle) → LM reasoning (inner)

### Likely Audience Question
> "AlphaEvolve and Co-Scientist sound impressive — are these available for use, or just research demos?"
- **Answer**: Co-Scientist is a research system currently used in partnership with select scientific institutions. AlphaEvolve has been applied to real Google infrastructure problems (chip design, data centers) — it's not a general public product but demonstrates what Level 4 agents can do. The paper positions these as the near-future trajectory for all agentic systems.

---

## Quick Reference: Section → Member → Pages → Figures

| Member | Section | Pages | Figures |
|--------|---------|-------|---------|
| 1 | Taxonomy (Levels 0–4) | 14–18 | Fig 2 |
| 2 | Model + Tools | 19–22 | — (create new) |
| 3 | Orchestration + Deployment | 22–26 | Fig 3, Fig 4 |
| 4 | Agent Ops + Interoperability | 27–34 | Fig 5 |
| 5 | Security + Evolution + Examples + Conclusion | 34–51 | Fig 6, 7, 8, 9, 10, 11, Table 1 |

---

## New Diagrams Each Member Should Create

| Member | Diagram to make |
|--------|----------------|
| 1 | Same query at L0 → L1 → L2 → L3 comparison table/visual |
| 2 | Agent architecture: Model + Tool categories + how they connect |
| 3 | Context window composition (what fills the LM's input at each step) |
| 4 | Agent Ops feedback loop (deploy → measure → evaluate → human feedback → improve) + A2A flow |
| 5 | Security concentric rings (guardrails → guard models → LM) |
