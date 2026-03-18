# Build Conversation Log — AgentProof Recruiter

## Context

AgentProof is existing ERC-8004 trust infrastructure — a reputation oracle serving 21 EVM chains plus Solana. The Recruiter is a new autonomous agent built on top of it during the Synthesis hackathon (March 13-22, 2026).

## Build Session — March 18, 2026

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
