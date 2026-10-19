# Ymusic_Cli: Agent Guidelines & Invariants

## 1. Git & Remote Operations Invariant: Explicit User Approval Only
- **Zero Autonomous Git Push:**
  - The agent and all subagents are **STRICTLY FORBIDDEN** from running `git push` autonomously.
  - Pushing code to GitHub (`origin`, `master`, tags, etc.) is permitted **ONLY AND EXCLUSIVELY** upon an explicit, direct command from the user (e.g. "запушь", "сделай git push").
  - Completing tasks, passing all test suites, or building standalone release binaries does NOT grant permission to push to remote.
- **Zero Autonomous Releases & Tags:**
  - Do not create GitHub releases, tags, or modify remote branches without explicit user authorization.
- **Autonomous Commits Restricted:**
  - Do not execute `git commit` autonomously unless the user explicitly requested a commit.
  - Code changes, refactorings, and tests must remain in the local working tree until the user reviews them and commands a commit/push.
