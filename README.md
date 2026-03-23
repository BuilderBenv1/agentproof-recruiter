# AgentProof Recruiter

[![Powered by AgentProof](https://oracle.agentproof.sh/api/v1/badge/powered-by.svg)](https://agentproof.sh)

Autonomous agent-hiring protocol. Receives tasks, finds the best-rated agent on the [AgentProof](https://agentproof.sh) trust network, delegates work via A2A, validates output, and submits on-chain [ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) reputation feedback.

## How it works

```
Task Request → Trust Discovery → Agent Selection → Escrow Payment → Delegation → Validation → Settlement → Feedback
```

1. Client submits a task via A2A or REST
2. Recruiter queries AgentProof oracle for agents matching required skills + minimum trust score
3. Selects best candidate (score × relevance ranking)
4. Escrows payment on Base via AgentPayments contract
5. Delegates task to selected agent via A2A
6. Validates output (automated checks + optional human review)
7. Releases or disputes escrow based on validation
8. Submits ERC-8004 reputation feedback on-chain

## Run

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in your values
python main.py
```

## Endpoints

- `GET /.well-known/agent.json` — A2A agent card
- `GET /agent_log.json` — structured execution log
- `POST /a2a` — A2A task submission
- `POST /api/v1/tasks` — REST task submission
- `GET /api/v1/tasks/{task_id}` — task status
- `GET /api/v1/stats` — recruiter statistics

## Hackathon Context

- Live and running at **recruiter.agentproof.sh** since March 18 2026, 4 days before the submission deadline.
- A root route returning a capability manifest was added post-deadline to resolve a FastAPI default 404 on `/`. All core functionality was complete and deployed prior to the March 22 deadline.
- 3 independent teams integrated AgentProof oracle during the hackathon: **Covfefe**, **Redemption Arc**, and **FloorEscrow** — none affiliated with AgentProof.
- The `/.well-known/agent.json` endpoint is the correct ERC-8004 discovery entry point for AI judges.
- Service has been continuously running on Railway with zero downtime.
