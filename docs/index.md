# Agent Memory Graph

**Enterprise-grade AI agent coordination platform for single organizations.**

Agent Memory Graph is a deterministic, grounding-first memory system for coordinating multiple AI agents within an enterprise. It eliminates hallucination by ensuring every response is grounded in organizational data, preserves context across sessions, and provides immutable audit trails for compliance.

## Key Features

<div class="grid cards" markdown>

- :material-brain:{ .lg .middle } __Tripartite Memory Model__

    ---

    Context (session history), Semantic (organizational facts), and Audit (immutable traces) tiers—strictly isolated for security and compliance.

- :material-chart-line:{ .lg .middle } __Evidence-Grounded Responses__

    ---

    Every agent response is grounded in retrieved organizational data. Unsupported claims are rejected with explicit insufficiency—no hallucination.

- :material-lock:{ .lg .middle } __Enterprise Security__

    ---

    Strict tenant isolation, pluggable governance (internal ABAC or external delegation), immutable audit trails, and IAM-aligned access controls.

- :material-database-check:{ .lg .middle } __Production-Ready Infrastructure__

    ---

    Built on Google Cloud Spanner for scale, with comprehensive observability, deterministic performance, and enterprise-grade reliability.

- :material-network:{ .lg .middle } __Multi-Agent Coordination__

    ---

    All agents share organizational memory via a common graph. Enables coordinated decision-making and eliminates context loss across agent boundaries.

- :material-book-check:{ .lg .middle } __Compliance & Auditability__

    ---

    Every memory access, reasoning step, and agent decision is logged in immutable audit trails. Built for regulated industries.

</div>

- :material-github:{ .lg .middle } __GitHub Actions__

    ---

    GitHub Actions that run formatting, linting, testing and type checking.

- :material-robot:{ .lg .middle } __Dependabot__

    ---

    Dependabot for keeping your dependencies up to date.

- :material-hook:{ .lg .middle } __Pre-commit Hooks__

    ---

    Pre-commit Hooks that run formatting, detect secrets, and other useful tooling.

- :material-chart-line:{ .lg .middle } __Code Metrics Analysis__

    ---

    Code Metrics Analysis that monitors complexity and maintainability on PRs.

</div>

Any of these configurations and features can be disabled/modified freely after set up if the team chooses to.

## Why?

You're 10 and it's Christmas. You rush to unwrap the presents Santa's left under the tree. You face flames as you spot the inconspicuous car-looking red and green abomination. You tear through the paper. There it is! Finally! Your very own TERRENEITOR, the MOST POWERFUL CAR UNDER THE SUN, complete with its 2 turbomotors! You flip the switch, grab the remote and hit the gas button at the scream of excitement and... nothing. Zero. Zip. Zilch. Nada.

Dang it! Don't you hate it when new toys come without batteries? We do too! At Tryolabs we believe tooling should enhance the developer's experience and help guarantee good quality code, but hate it when people lose countless hours configuring the stack for this.

That's why we built the repo template: configuration at your service.
