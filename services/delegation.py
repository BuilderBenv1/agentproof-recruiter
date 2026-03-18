"""Task delegation via A2A protocol.

Sends tasks to selected agents using the Google A2A JSON-RPC 2.0 format.
Handles timeouts, retries, and fallback to next-best agent.
"""

import logging
import uuid
from typing import Any

import httpx

from models import AgentCandidate, Task, TaskStatus

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
DELEGATION_TIMEOUT = 30.0


class DelegationService:
    """Delegates tasks to agents via A2A protocol."""

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(timeout=DELEGATION_TIMEOUT)

    async def delegate(self, task: Task, agent: AgentCandidate) -> dict[str, Any] | None:
        """
        Send a task to an agent via A2A JSON-RPC.

        Returns the A2A task result on success, None on failure.
        """
        if not agent.endpoint:
            logger.warning(f"Agent #{agent.agent_id} has no endpoint — cannot delegate")
            return None

        # Normalize endpoint to A2A URL
        base = agent.endpoint.rstrip("/")
        a2a_url = f"{base}/a2a" if not base.endswith("/a2a") else base

        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "id": str(uuid.uuid4()),
            "params": {
                "id": task.task_id,
                "message": {
                    "role": "user",
                    "parts": [{"text": task.request.description}],
                },
                "metadata": {
                    "delegator": "agentproof-recruiter",
                    "category": task.request.category,
                    "required_skills": task.request.required_skills,
                },
            },
        }

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._http.post(a2a_url, json=payload)
                resp.raise_for_status()
                data = resp.json()

                if "error" in data:
                    logger.warning(
                        f"A2A error from agent #{agent.agent_id}: {data['error']}"
                    )
                    return None

                result = data.get("result", {})
                state = result.get("status", {}).get("state", "unknown")

                logger.info(
                    f"Delegation to agent #{agent.agent_id} — state={state}"
                )
                return result

            except httpx.TimeoutException:
                logger.warning(
                    f"Delegation timeout to agent #{agent.agent_id} "
                    f"(attempt {attempt + 1}/{MAX_RETRIES + 1})"
                )
            except Exception as e:
                logger.error(
                    f"Delegation failed to agent #{agent.agent_id}: {e} "
                    f"(attempt {attempt + 1}/{MAX_RETRIES + 1})"
                )

        return None

    async def close(self) -> None:
        await self._http.aclose()
