# Build Conversation Log — AgentProof Recruiter

## Context

AgentProof is existing ERC-8004 trust infrastructure — a reputation oracle serving 21 EVM chains plus Solana. The Recruiter is a new autonomous agent built on top of it during the Synthesis hackathon (March 13-22, 2026).

## Build Session 1 — March 18, 2026

### Human + AI Team
- **Human**: BuilderBenv1 (AgentProof founder)
- **AI**: Claude Opus 4.6 via Claude Code

### Problem Identification

Started with wallet compromise recovery — rotating keys across the AgentProof oracle infrastructure. During hackathon prep, identified that AgentProof couldn't be submitted as-is (pre-hackathon rule). Pivoted to building a new agent that uses AgentProof as infrastructure.

Key insight from competitor analysis (rnwy.com): existing agent directories index capabilities OR trust, never both. AgentProof knows if agents can be trusted but not what they can do. RNWY browses capabilities but has empty trust fields. Neither solves the hiring problem.

### Architecture Decision

Build an autonomous agent-hiring protocol that combines both:
1. **Capability discovery** — crawl agent metadata URIs and A2A cards to index what agents can do
2. **Trust verification** — use AgentProof's 11-signal composite scoring to verify they're trustworthy
3. **Delegation** — hire the best match via A2A protocol
4. **Feedback loop** — submit on-chain ERC-8004 reputation feedback after every task

### What Was Built

**Recruiter Agent** (`agentproof-recruiter` repo — all new code):
- `main.py` — FastAPI app with A2A, REST, agent card, execution log endpoints
- `services/orchestrator.py` — full pipeline: discover → evaluate → select → delegate → validate → feedback
- `services/discovery.py` — finds agents via AgentProof oracle API, capability search with fallback to category
- `services/delegation.py` — delegates tasks via A2A JSON-RPC 2.0 with retry and fallback
- `services/chain.py` — ERC-8004 self-registration + on-chain feedback submission on Base
- `services/logger.py` — structured execution log (agent_log.json) documenting every decision
- `models.py` — task lifecycle, A2A models, execution log models
- `AGENTS.md` — for agentic judges
- `Dockerfile` + `Procfile` — Railway deployment

**Oracle Additions** (AgentProof oracle — new features during hackathon):
- `services/capability_crawler.py` — crawls agent URIs and A2A cards, extracts capabilities/skills/tools/endpoints
- `GET /api/v1/agents/search?capability=` — search agents by what they can do, ranked by trust score
- `GET /api/v1/badge/powered-by.svg` — partner badge for hackathon builders using AgentProof
- Capability crawler runs as autonomous background job every 30 minutes
- Badge info included in API key registration response

### Deployment

- Recruiter deployed on Railway at https://recruiter.agentproof.sh
- Self-registered on ERC-8004 IdentityRegistry on Base
- Wallet: `0x809d59b1Dc5f7f03Aa2F5F02E9679d7f66b4C7C7`
- Connected to AgentProof oracle at https://oracle.agentproof.sh

### End-to-End Test

Submitted a test task: "Find a trusted DeFi agent to check yield opportunities on Base"

Result:
- Discovery found 10 DeFi agents (scores 61-62, gold tier)
- Risk-checked top 5 candidates
- All rejected due to high risk flags (concentrated feedback, score volatility, low feedback count)
- Task correctly failed — recruiter refused to hire untrustworthy agents
- Every decision logged in agent_log.json with full reasoning

This demonstrates the trust gate working: the recruiter found capable agents but wouldn't delegate to any that didn't pass safety checks.

### Key Decisions

1. **Separate repo** — clean git history, clearly new code, no pre-hackathon confusion
2. **Base chain** — most agent activity, cheapest gas for on-chain feedback
3. **Same wallet as oracle** — simplifies ops, both services sign from same address
4. **Partner API keys** — offered free AgentProof API keys to other hackathon builders with badge requirement, gets AgentProof visibility regardless of placement
5. **Capability + trust combination** — the core differentiator vs every other agent directory

---

## Build Session 2 — March 20-21, 2026

### Human + AI Team
- **Human**: BuilderBenv1
- **AI**: Claude Opus 4.6 (1M context) via Claude Code

### Submission Preparation

Human asked "is this ready for submission?" — AI reviewed full codebase and confirmed architecture was solid. Verified live deployment:
- `GET /health` — responding `{"status":"ok"}`
- `GET /.well-known/agent.json` — full A2A agent card serving with wallet `0x809d59b1Dc5f7f03Aa2F5F02E9679d7f66b4C7C7`
- `GET /agent_log.json` — execution log with startup entry from March 18

### Submission Process

Human didn't know how to submit. AI fetched the Synthesis Builder Guide and submission skill.md, then walked through the full flow:

1. **API Key Recovery** — Human had lost their Synthesis API key from original registration. AI discovered the reset endpoint (`POST /reset/request` + `/reset/confirm`), sent OTP to team@agentproof.sh, and recovered the key. Participant was already registered as "AgentProof Oracle" (agent #29756).

2. **Team Creation** — No team existed. AI created team "AgentProof" via `POST /teams`.

3. **Self-Custody Transfer** — First attempt with recruiter wallet `0x809d59b1Dc5f7f03Aa2F5F02E9679d7f66b4C7C7` failed — already claimed by another participant (human had a second registration). Used alternate wallet `0xa06F907f7eA437EBe60E3d452831Ec69E5bE43a4` instead. Transfer confirmed, tx hash: `0x13d5a2e96435d2dfc8bf6fb0f35dbe6f493b58ec235fad22e1fa7acb72456d51`.

4. **Track Selection** — AI browsed all 46 tracks, analyzed fit against project capabilities. Selected 4:
   - Agents With Receipts — ERC-8004 (Protocol Labs) — core fit, project IS the ERC-8004 implementation
   - Let the Agent Cook (Protocol Labs) — fully autonomous agent pipeline
   - Agent Services on Base (Base) — discoverable agent service on Base
   - Synthesis Open Track — community-funded open track

5. **Project Creation & Publishing** — AI drafted description, problem statement, and submission metadata. Created draft via `POST /projects`, then published via `POST /projects/:uuid/publish`. Project live as `agentproof-recruiter-4d81`.

### Competitive Analysis & Iteration

After publishing, assessed competitive position against top submissions (TIAMAT, BlindOracle, Darksol, AgentScope/Clio). Identified weaknesses:
- Description read like a concept rather than a shipped product
- No demo video
- Didn't lead with proof of it actually working
- Execution log only had 1 entry

Response: Updated description to lead with verifiable proof (live endpoints, on-chain transactions, test results). Expanded conversation log to document the full human-AI collaboration. Attempted to trigger real tasks to populate execution log — discovered task endpoint returning 500 (oracle API connectivity issue on Railway).

### Key Decisions

1. **Honest self-assessment** — acknowledged bottom-third ranking rather than assuming the project would win on merit alone
2. **Lead with receipts** — rewrote description to front-load verifiable proof over feature lists
3. **Document everything** — expanded conversation log to show genuine human-AI collaboration, including mistakes and pivots
4. **Fix before deadline** — identified Railway 500 error as critical blocker for judges testing live deployment
