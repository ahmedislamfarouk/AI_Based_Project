# Presentation Script — Introduction to Agents
## Google Whitepaper (Nov 2025) | Starting from Page 14
## 5-Member Team Script

---

> **Format note:** Each member has an opening line, their main talking points as spoken cues, a transition to the next person, and a prep answer for the most likely audience question.

---

---

# MEMBER 1 — A Taxonomy of Agentic Systems

## Opening
> "Before we start building agents, we need to answer one question: *what kind* of agent are we actually building? The paper gives us a clear answer — a 5-level taxonomy that goes from a basic reasoning engine all the way to a system that creates its own tools."

## Main Talking Points (say these in order)

**Point 1 — Why classify at all?**
> "Not every problem needs a Level 3 multi-agent system. Choosing the wrong level means overengineering a simple task — or underbuilding something that needs real autonomy. This taxonomy is your scoping tool."

**Point 2 — Level 0: The Core Reasoning System**
> "At the base is just an LM running alone. It knows a lot — history, rules, concepts — but it's completely blind to the real world. Ask it 'what was the Yankees score last night?' and it simply can't answer. It has no eyes."

**Point 3 — Level 1: The Connected Problem-Solver**
> "Give that same LM a tool — a search API, a database, a calculator — and suddenly it can answer that question. This is the first real agent. It can reach beyond its training data. Most chatbots you use today are roughly here."

**Point 4 — Level 2: The Strategic Problem-Solver**
> "Now the agent doesn't just use one tool — it *plans*. It breaks a complex goal into steps and decides which tool to call at each one. The key skill here is called context engineering: the agent curates exactly what information to feed itself at every step to stay accurate and on track."
>
> *[Show the coffee shop example from the paper if time allows — it's a great concrete illustration.]*

**Point 5 — Level 3: The Collaborative Multi-Agent System**
> "At Level 3 the paradigm shifts completely. Instead of one powerful agent, you have a team of specialists — just like a company. A coordinator agent gets the big mission, breaks it into sub-tasks, and delegates each one to a specialist. A MarketResearchAgent, a MarketingAgent, a WebDevAgent — all running in parallel."

**Point 6 — Level 4: The Self-Evolving System**
> "And at the frontier is an agent that can recognize what it *doesn't* know how to do — and build the tool or agent it needs on the fly. It's not just using capabilities, it's expanding them. This is mostly research territory today, but it's where the field is heading."

**Point 7 — Key takeaway**
> "Most production systems today sit at Level 1 or 2. Level 3 is emerging. Level 4 is the horizon. Knowing this lets you set realistic expectations for what you're building."

## Transition to Member 2
> "So now we know *what kind* of agent we want to build. The next question is: *how is it actually built?* [Member 2's name] will walk us through the first two essential components of any agent — the brain and the hands."

## Likely Audience Question
> **Q: "What level do most real production agents today operate at?"**
>
> A: "Primarily Level 1 and 2. Level 1 is any agent that can call an external tool — search, a database, an API. Level 2 is where you see things like AI assistants that plan multi-step workflows. Level 3 multi-agent systems exist in production but are much harder to build, test and debug reliably. Level 4 is almost exclusively in research labs right now."

---

---

# MEMBER 2 — Core Architecture: The Model (Brain) & Tools (Hands)

## Opening
> "Every agent, no matter how complex, is built on three core components. Think of it like the human body — a brain, hands, and a nervous system. I'm covering the first two: the brain, which is the language model, and the hands, which are the tools."

## Main Talking Points

**Point 1 — The Model is not just a benchmark score**
> "The most common mistake people make is picking the model with the highest benchmark score. That's a path to failure in production. What actually matters is: does this model reason well enough for *your specific multi-step task*, and does it reliably call tools without hallucinating the function call?"

**Point 2 — You might need more than one model**
> "A production agent often uses a *team* of models. A powerful frontier model like Gemini 2.5 Pro handles complex planning and reasoning. A faster, cheaper model like Gemini 2.5 Flash handles simple classification tasks like 'is this message a complaint or a question?' This routing is a key cost-optimization strategy."

**Point 3 — Models evolve fast — build for it**
> "The model you choose today will be superseded in six months. The paper is explicit about this: build a CI/CD pipeline that continuously evaluates new model releases against your business metrics. Your architecture should be model-swappable, not model-locked."

**Point 4 — Tools: the three categories**
> "Now the hands. Tools fall into three buckets. First: *information retrieval* — this is where RAG lives. The agent has a 'library card' to query vector databases, knowledge graphs, or structured data via NL2SQL. This is what kills hallucinations — the agent looks it up before it speaks."

> "Second: *action execution* — this is where agents get powerful and dangerous. The agent can send emails, update CRM records, run Python scripts, call APIs. It's no longer just talking — it's doing."

> "Third: *human-in-the-loop* — the agent can pause and ask a human for confirmation before a high-stakes action. This is your safety valve."

**Point 5 — Function calling and MCP**
> "For the agent to reliably use tools, each tool needs a contract — a clear definition of what it does, what parameters it takes, and what it returns. This uses the OpenAPI standard. A newer, simpler option is MCP — the Model Context Protocol — which is becoming the standard for connecting tools to agents across vendors."

## Transition to Member 3
> "So the brain knows how to reason, and the hands know how to act. But something has to connect them and keep the whole thing running in a loop. That's the nervous system — the Orchestration Layer. [Member 3's name] will take us there."

## Likely Audience Question
> **Q: "How do you stop an agent from hallucinating a tool call — like calling a function that doesn't exist with wrong parameters?"**
>
> A: "The OpenAPI schema acts as a strict contract. The model generates a structured JSON function call, not free text, and that call is validated against the schema before execution. If the parameters are wrong, it errors and the agent can retry. MCP adds further standardization. And for critical actions, HITL tools force human confirmation before execution."

---

---

# MEMBER 3 — Core Architecture: The Orchestration Layer & Deployment

## Opening
> "The Model thinks. The Tools act. But something has to run the loop, manage memory, coordinate multiple agents, and decide when to reason vs. when to act. That's the Orchestration Layer — the nervous system. I'll also cover how you actually deploy all of this into production."

## Main Talking Points

**Point 1 — What the orchestration layer actually does**
> "The orchestration layer runs what the paper calls the Think-Act-Observe loop. At every cycle it asks: what's the goal, what do I know, what's my plan, which tool do I call next, what did that tool return? It then assembles all of that into the context window for the next LM call. The agent *is* this loop."

**Point 2 — The system prompt is the agent's constitution**
> "The most powerful thing you can do as a developer is write a great system prompt. It's not just 'you are a helpful assistant.' It's the agent's identity, its constraints, its tone of voice, explicit rules about when to use which tool, and example scenarios. Get this right and the agent behaves predictably."

**Point 3 — Memory: short-term and long-term**
> "Memory is managed here too. Short-term memory is the running scratchpad of the current conversation — every action and its result. Long-term memory is a RAG system connected to a vector database — the agent can recall what a user asked it three weeks ago. This is what makes an agent feel like a *collaborator* rather than a stateless chatbot."

**Point 4 — Multi-agent design patterns**
> "When tasks get complex, one agent isn't enough. The paper gives us four proven patterns. The **Coordinator** pattern uses a manager agent to route subtasks to specialists. The **Sequential** pattern is a pipeline — output of agent A feeds agent B. The **Iterative Refinement** pattern has a generator and a critic in a quality loop — keep generating until quality threshold is met. And **HITL** creates a mandatory human checkpoint before irreversible actions."

**Point 5 — A good framework must be observable**
> "Whatever framework you use — Google's ADK, LangChain, LlamaIndex — the non-negotiable requirement is observability. When an agent behaves unexpectedly, you can't put a breakpoint in its 'thought.' You need detailed traces: the exact prompt, the reasoning, the tool chosen, the parameters, the raw result. No observability means no debugging."

**Point 6 — Deployment**
> "Once built, the agent needs a home. Options range from fully managed platforms like Vertex AI Agent Engine — which handles runtime, memory, security, and scaling out of the box — to deploying a Docker container on Cloud Run if you want full infrastructure control. Same principles as any production service: session persistence, monitoring, logging, compliance."

## Transition to Member 4
> "So we've built and deployed our agent. Now the hard part begins: keeping it working well in production. [Member 4's name] will cover Agent Ops — how you measure, evaluate, and debug an agent that can never give you a simple pass/fail."

## Likely Audience Question
> **Q: "What happens when the agent gets stuck in an infinite reasoning loop?"**
>
> A: "The orchestration layer enforces a maximum iteration count — a hard stop. A well-designed system prompt also includes explicit instructions like 'if a tool fails three times, stop and escalate to a human.' And because the framework generates traces, you can see exactly which step the agent looped on and diagnose the root cause — whether it was a bad tool response, ambiguous instructions, or a model reasoning error."

---

---

# MEMBER 4 — Agent Ops & Agent Interoperability

## Opening
> "Building a great agent is like building a race car. But Agent Ops is the pit crew — the systems that keep it performing, catch problems before they become failures, and improve it continuously. I'll also cover how agents connect to the outside world: to humans, to other agents, and even to financial transactions."

## Main Talking Points

**Point 1 — Why traditional software testing breaks**
> "If I write a function and test it, I can assert the output equals the expected value. That's binary. But an agent's response is probabilistic — the same question might get a slightly different phrasing each time, and both are correct. You can't do pass/fail. You need to evaluate *quality*."

**Point 2 — LM-as-Judge**
> "The solution is to use a powerful language model as your evaluator. You give it a rubric — did the agent give the right answer, was it factually grounded, did it follow instructions, was the tone appropriate — and it scores the agent's response against a pre-built 'golden dataset' of ideal question-answer pairs. This is your automated quality gate."

**Point 3 — The golden dataset**
> "The golden dataset is your ground truth. Building it is tedious but critical. Start by manually crafting 30-50 representative scenarios. Once in production, every time a user clicks thumbs-down, that's a new test case. The paper says maintaining this dataset is increasingly the responsibility of Product Managers, not just engineers."

**Point 4 — Metrics-driven deployment**
> "Your deployment decision is: does the new version score better than the current production version on the golden dataset? If yes, and latency and cost are acceptable, you ship. Use A/B rollouts to validate in real traffic before full release. This turns agent improvement from guesswork into a scientific process."

**Point 5 — OpenTelemetry traces for debugging**
> "When something goes wrong, traces are your microscope. An OpenTelemetry trace captures every single step: exact prompt sent to the model, the model's internal reasoning, the tool it chose, the exact parameters it generated, the raw response from that tool. You can replay any failure and see exactly where the agent went wrong."

**Point 6 — Agent-to-Human interaction**
> "On the interoperability side — agents talk to humans through interfaces ranging from simple chatbots to real-time voice using the Gemini Live API, where the agent can see through a device's camera and hear through its microphone. Agents can also take control of a UI directly — filling forms, clicking buttons — called computer use."

**Point 7 — Agent-to-Agent: the A2A protocol**
> "As organizations build more agents, they need a standard way for agents to find and talk to each other. The A2A protocol solves this. Each agent publishes an Agent Card — a JSON file that advertises its capabilities, endpoint, and security credentials. Agents then communicate via task-oriented asynchronous messages. This turns a collection of isolated agents into an interoperable ecosystem."

**Point 8 — Agent-to-Money**
> "Finally, agents are starting to transact financially. If an agent clicks 'buy,' who's responsible? Two emerging protocols address this: AP2 uses cryptographically signed digital mandates — a verifiable proof the user authorized the purchase. And x402 enables machine-to-machine micropayments using the standard HTTP 402 status code, so an agent can pay for API access per-use without needing accounts or subscriptions."

## Transition to Member 5
> "So we can build, deploy, measure, and improve agents. But giving an agent power means giving it the ability to cause real harm. [Member 5's name] will cover how to secure agents, scale them across an enterprise, and show us what agents look like at the absolute frontier."

## Likely Audience Question
> **Q: "How do you build a golden evaluation dataset when you're starting from scratch with no production data?"**
>
> A: "You start manually. Sit down with domain experts and write out 30 to 50 representative prompts — covering the normal use cases, the edge cases, and a few adversarial inputs you're worried about. For each one, write the ideal response. It's slow, but this investment pays off immediately. Once the agent is live, every negative user interaction automatically becomes a new test case, and the dataset grows organically. The paper recommends treating this as a Product Manager responsibility with domain expert review."

---

---

# MEMBER 5 — Security, Agent Evolution & Advanced Examples

## Opening
> "Power and risk are two sides of the same coin. The more capable you make an agent, the more damage it can do if it goes wrong. I'll cover how to secure agents at every scale — from a single agent to an enterprise fleet — how agents get smarter over time, and two real-world examples that show where this technology is heading."

## Main Talking Points

**Point 1 — The fundamental security tension**
> "The paper puts it simply: every capability you give an agent introduces a corresponding risk. An agent that can send emails can be tricked into sending the wrong email. An agent with database access can leak sensitive data. You're always balancing the leash — long enough to be useful, short enough to prevent disasters."

**Point 2 — The two main threats**
> "The two biggest threats are rogue actions — the agent does something harmful or unintended — and sensitive data disclosure — the agent leaks private information. Both can be triggered by prompt injection: a malicious instruction hidden in data the agent reads, hijacking its behavior."

**Point 3 — Defense-in-depth: two layers**
> "The paper recommends two layers. The outer layer is deterministic guardrails — hard-coded rules that run *outside* the model's reasoning. Examples: a policy engine that blocks any purchase over $100 without explicit confirmation, or a rule that prevents the agent from calling external APIs without user consent. These are predictable and auditable."
>
> "The inner layer is reasoning-based defenses — using AI to defend AI. Guard models review the agent's *planned* actions before they execute and flag anything risky or policy-violating. Google's Model Armor is a managed version of this."

**Point 4 — Agent identity: the third principal**
> "Traditionally, systems only had two types of actors: users and service accounts. Agents are a third category — they're autonomous actors with delegated authority. Each agent gets a cryptographically verifiable identity using the SPIFFE standard. The SalesAgent gets CRM access. The HRAgent is explicitly denied it. If one agent is compromised, the blast radius is contained."

**Point 5 — Scaling to an enterprise fleet: agent governance**
> "When you have hundreds of agents, you have agent sprawl. The solution is a central gateway — a mandatory chokepoint for all agentic traffic — and a central registry — an enterprise app store where agents are versioned, reviewed, and discoverable. This turns chaos into an auditable, manageable ecosystem."

**Point 6 — How agents learn and evolve**
> "Agents in production degrade over time as the world changes. Policies change, data formats change, regulations change. The paper describes two ways agents adapt. First: refining their own prompts and few-shot examples based on feedback — this is context engineering becoming self-improving. Second: the agent identifies a tool it's missing and creates it — writing a Python script or calling an AgentCreator to spawn a new specialist."

**Point 7 — Advanced Example: Google Co-Scientist**
> "Co-Scientist is a multi-agent research system. A scientist inputs a research goal. A supervisor delegates to specialized agents: a Generation Agent brainstorms hypotheses, a Reflection Agent reviews them, a Ranking Agent runs tournament comparisons, an Evolution Agent refines the best ones. This loop runs for *hours or days*, continuously self-improving. The result: ranked research hypotheses the scientist couldn't have generated alone."

**Point 8 — Advanced Example: AlphaEvolve**
> "AlphaEvolve is an agent that discovers and optimizes algorithms. The loop is: generate code → evaluate it → use the best programs as inspiration for the next generation. It's evolution applied to software. It's already improved Google's data center efficiency, chip design, and AI training pipelines — and discovered faster matrix multiplication algorithms that had been unknown for decades."
>
> "The insight: AlphaEvolve excels when *verifying* a solution is much easier than *finding* it. An evaluator can quickly score code, even when the search space for good code is enormous."

**Point 9 — Conclusion**
> "The paper ends with a clear message: the developer role has fundamentally changed. We used to be bricklayers — defining every line of logic. Now we're directors — setting the scene, selecting the cast, and guiding an autonomous actor to deliver the intended performance. The discipline that makes this work is not prompt engineering. It's the engineering rigor applied to the whole system: tool contracts, context management, evaluation, security, and observability."

## Likely Audience Question
> **Q: "Are Co-Scientist and AlphaEvolve available to use, or are they just research demos?"**
>
> A: "They're real systems, but not general public products. Co-Scientist is being used in partnership with selected scientific institutions — it's shown results in genomics and drug discovery research. AlphaEvolve has been deployed on actual Google infrastructure problems, so it's moved past pure research. The paper uses them as proof points for what Level 3 and Level 4 agents look like in practice — the architecture patterns they use, like iterative refinement and multi-agent specialization, are things any team can build on today."

---

---

## Cheat Sheet: At-a-Glance for All 5 Members

| Member | Topic | Key Term to Know | Their Figure(s) | Their Question |
|--------|-------|-----------------|-----------------|----------------|
| 1 | Taxonomy L0–L4 | Context Engineering | Fig 2 | "What level are most agents today?" |
| 2 | Model + Tools | Function Calling / MCP | — | "How do you stop tool hallucination?" |
| 3 | Orchestration + Deploy | Think-Act-Observe loop | Fig 3, 4 | "What if the agent loops infinitely?" |
| 4 | Agent Ops + Interoperability | LM-as-Judge / A2A | Fig 5 | "How to build a golden dataset from scratch?" |
| 5 | Security + Evolution + Examples | Defense-in-depth / SPIFFE | Fig 6-11, T1 | "Are Co-Scientist/AlphaEvolve public?" |

---

## General Tips for All Members
- **Lead with the concept, then the example** — audience grasps examples faster than definitions
- **Every figure has a caption** — read it aloud before explaining the diagram
- **Use the body-parts analogy** the paper uses: Brain (Model), Hands (Tools), Nervous System (Orchestration) — it's sticky
- **If asked something outside your section**, say: "That's actually covered in [member's name] section — but briefly..."
- **Time target**: ~5–6 minutes per member for a 30-minute presentation
