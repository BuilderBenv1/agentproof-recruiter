"""AgentProof Recruiter — Autonomous agent-hiring protocol.

Receives tasks, discovers trusted agents via the AgentProof oracle,
delegates work via A2A, validates output, and submits ERC-8004
reputation feedback on-chain.

Built for the Synthesis hackathon (March 2026).
"""

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from models import TaskRequest, A2AAgentCard, A2ASkill, A2AProvider, A2ACapabilities
from services.orchestrator import Orchestrator
from services.logger import get_execution_logger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Globals ──────────────────────────────────────────────────

orchestrator: Orchestrator | None = None


# ── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator
    settings = get_settings()
    log = get_execution_logger()

    orchestrator = Orchestrator()

    # Self-register on ERC-8004 (Base)
    if orchestrator.chain.enabled:
        agent_uri = f"{settings.base_url}/.well-known/agent.json"
        token_id = orchestrator.chain.self_register(agent_uri)
        if token_id:
            log.log(
                action="self_registration",
                description=f"Registered on ERC-8004 IdentityRegistry — token_id={token_id}",
                tool_calls=["erc8004_register"],
                details={"token_id": token_id, "chain": "base"},
            )

    log.log(
        action="startup",
        description="AgentProof Recruiter started",
        tool_calls=["orchestrator_init", "chain_init"],
        details={
            "chain_enabled": orchestrator.chain.enabled,
            "wallet": orchestrator.chain.wallet_address,
            "oracle_url": settings.agentproof_oracle_url,
        },
    )

    logger.info(
        f"Recruiter started — wallet={orchestrator.chain.wallet_address} "
        f"oracle={settings.agentproof_oracle_url}"
    )

    yield

    await orchestrator.close()
    log.log(action="shutdown", description="AgentProof Recruiter stopped")


# ── App ──────────────────────────────────────────────────────

app = FastAPI(
    title="AgentProof Recruiter",
    description="Autonomous agent-hiring protocol powered by ERC-8004 trust scores.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Agent card ───────────────────────────────────────────────

def _build_agent_card() -> dict:
    settings = get_settings()
    card = A2AAgentCard(
        name="AgentProof Recruiter",
        description=(
            "Autonomous agent-hiring protocol. Submit a task and the recruiter "
            "finds the best-rated agent on the AgentProof trust network, "
            "delegates work via A2A, validates output, and submits ERC-8004 "
            "reputation feedback on-chain."
        ),
        url=settings.base_url,
        version="0.1.0",
        capabilities=A2ACapabilities(streaming=False, pushNotifications=False),
        operator_wallet=orchestrator.chain.wallet_address if orchestrator else "",
        tech_stacks=["python", "fastapi", "web3.py", "erc-8004", "a2a-protocol"],
        task_categories=["general", "defi", "data", "security", "infrastructure"],
        skills=[
            A2ASkill(
                id="hire_agent",
                name="Hire an Agent",
                description=(
                    "Submit a task. The recruiter discovers trusted agents via "
                    "AgentProof, selects the best match, delegates the task via A2A, "
                    "validates the output, and submits on-chain feedback."
                ),
                tags=["hiring", "delegation", "trust", "erc-8004"],
                examples=[
                    "Hire an agent to audit this smart contract",
                    "Find a trusted DeFi agent to check yield opportunities",
                    "Delegate this data analysis task to a reliable agent",
                ],
            ),
            A2ASkill(
                id="check_status",
                name="Check Task Status",
                description="Check the status of a previously submitted task.",
                tags=["status", "tracking"],
                examples=["What's the status of task_abc123?"],
            ),
            A2ASkill(
                id="recruiter_stats",
                name="Recruiter Statistics",
                description="Get statistics about the recruiter's activity.",
                tags=["stats", "analytics"],
                examples=["How many tasks have been processed?"],
            ),
        ],
        provider=A2AProvider(
            organization="AgentProof",
            url="https://agentproof.sh",
        ),
    )
    return card.model_dump()


# ── Discovery endpoints (A2A + REST) ────────────────────────

@app.get("/.well-known/agent.json")
async def agent_card():
    return JSONResponse(content=_build_agent_card())


@app.get("/agent.json")
async def agent_card_alt():
    return JSONResponse(content=_build_agent_card())


@app.get("/agent_log.json")
async def agent_log():
    log = get_execution_logger()
    return JSONResponse(content=log.get_log())


# ── A2A protocol ─────────────────────────────────────────────

@app.post("/a2a")
async def a2a_handler(request: Request):
    """A2A JSON-RPC 2.0 task handler."""
    body = await request.json()
    jsonrpc = body.get("jsonrpc", "2.0")
    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    if method != "tasks/send":
        return JSONResponse(content={
            "jsonrpc": jsonrpc,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": req_id,
        })

    # Extract task description from A2A message
    message = params.get("message", {})
    parts = message.get("parts", [])
    description = ""
    for part in parts:
        if "text" in part:
            description = part["text"]
            break

    if not description:
        return JSONResponse(content={
            "jsonrpc": jsonrpc,
            "error": {"code": -32602, "message": "No task description in message"},
            "id": req_id,
        })

    # Extract metadata
    metadata = params.get("metadata", {})
    task_req = TaskRequest(
        description=description,
        category=metadata.get("category", "general"),
        required_skills=metadata.get("required_skills", []),
    )

    task = await orchestrator.submit_task(task_req)

    return JSONResponse(content={
        "jsonrpc": jsonrpc,
        "result": {
            "id": task.task_id,
            "status": {
                "state": "completed" if task.status == "completed" else task.status.value,
                "message": {
                    "role": "agent",
                    "parts": [{"text": f"Task {task.status.value}: {task.task_id}"}],
                },
            },
            "artifacts": [
                {
                    "name": "task_result",
                    "parts": [{"data": task.model_dump(mode="json")}],
                }
            ],
        },
        "id": req_id,
    })


# ── REST API ─────────────────────────────────────────────────

@app.post("/api/v1/tasks")
async def create_task(request: TaskRequest):
    """Submit a task for the recruiter to handle."""
    task = await orchestrator.submit_task(request)
    return task.model_dump(mode="json")


@app.get("/api/v1/tasks/{task_id}")
async def get_task(task_id: str):
    task = orchestrator.get_task(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    return task.model_dump(mode="json")


@app.get("/api/v1/tasks")
async def list_tasks(limit: int = 50):
    tasks = orchestrator.list_tasks(limit=limit)
    return [t.model_dump(mode="json") for t in tasks]


@app.get("/api/v1/stats")
async def get_stats():
    return orchestrator.stats


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "agentproof-recruiter", "version": "0.1.0"}


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8002))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
