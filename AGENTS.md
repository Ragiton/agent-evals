# Agent Evals — Codex instructions

Codex is the primary assistant for this project. Use this repository as a benchmark workbench, not as a general agent orchestration service.

- Read README.md and the relevant eval spec before changing the harness.
- Keep existing eval specs, research, run results, and grading history unless the user explicitly requests a change.
- New runs default to the native Codex CLI with GPT-6 Luna in an isolated results/runs workspace. Select Claude Code or Cursor only for an explicitly scoped benchmark comparison.
- Do not use Hermes, Telegram, external Kanban, MiniMax watchers, Hermes provider routing, or Hermes snapshot paths. Those systems were retired.
- Treat existing pricing, quota, and model assignments as dated experiment records. Verify current official documentation before adding live model or CLI behavior.
- Keep credentials, tokens, cookies, authentication files, and raw provider payloads out of Git and result artifacts.
- Review .gitignore and stage exact intended paths. Do not add broad ignore rules that hide durable project data.
- Do not invoke the nightly dispatcher or usage snapshot without first confirming their inputs and dependencies still exist after the 2026 reimage.
