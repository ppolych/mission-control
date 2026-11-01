# Research and operational limits

Primary sources reviewed for the redesign:

- [Effective harnesses for long-running agents](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents): durable progress and incremental verification. Applied through persisted evidence and resume revalidation.
- [Demystifying evals for AI agents](https://www.anthropic.com/research/demystifying-evals-for-ai-agents): measure outcomes, not claims. Applied through command results and explicit manual judgments.
- [Agent Skills specification](https://agentskills.io/specification): concise discovery metadata and progressively loaded details. Applied through a short entrypoint and linked references.

Confirmed original defects: empty verifier groups passed; extra file arguments
were ignored; failed pipeline stages could pass; argument boundaries were lost
in repeat hashes. Original instructions and templates also used incompatible
contract shapes and proposed unavailable p95-derived defaults.

The CLI is a local cooperative guardrail, not a tamper-proof audit service.
An agent that can edit state can falsify it. Manual judgments require human or
agent review. Commands are trusted code and inherit caller permissions.
Filesystem checks do not establish semantic correctness. Verification should be
safe to rerun. Locks protect lifecycle operations, not arbitrary external editors.

Behavioral review scenarios: simple questions should avoid mission overhead;
existing authorization should not trigger step-count approvals; failed commands
must prevent completion despite positive manual judgments; interrupted external
actions require inspection before retrying. These are review scenarios rather
than claims of independently measured agent performance.

The 0.1 agentic enhancement adds workspace-first complete drafts, post-finish
goal assessment, and episodic lessons. See [workflow details](agentic-workflow.md).
The new CLI records goal-review verdicts; it cannot automatically prove that
the original user goal has been met. Metrics and lessons are agent-authored,
not automatically collected evaluation data. The skill-level register begins
without invented mission histories or claims of measured autonomy gains.
