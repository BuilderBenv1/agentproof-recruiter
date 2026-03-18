"""Agent discovery via AgentProof oracle.

Queries the trust oracle to find agents matching task requirements,
ranked by composite score. Filters by category, minimum score, minimum tier,
and required skills.
"""

import logging
from typing import Any

import httpx

from config import get_settings
from models import AgentCandidate

logger = logging.getLogger(__name__)

TIER_ORDER = {"unranked": 0, "bronze": 1, "silver": 2, "gold": 3, "platinum": 4, "diamond": 5}


class DiscoveryService:
    """Finds and ranks agents using the AgentProof oracle API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._oracle_url = settings.agentproof_oracle_url.rstrip("/")
        self._headers = {
            "X-API-Key": settings.agentproof_api_key,
            "Accept": "application/json",
        }
        self._http = httpx.AsyncClient(timeout=15.0, headers=self._headers)

    async def find_agents(
        self,
        category: str = "general",
        min_score: float | None = None,
        min_tier: str | None = None,
        limit: int = 10,
    ) -> list[AgentCandidate]:
        """Query the oracle for trusted agents matching criteria."""
        settings = get_settings()
        score_threshold = min_score or settings.min_agent_score
        tier_threshold = min_tier or settings.min_agent_tier

        params: dict[str, Any] = {
            "category": category,
            "min_score": score_threshold,
            "min_tier": tier_threshold,
            "limit": limit,
        }

        url = f"{self._oracle_url}/api/v1/agents/trusted"
        try:
            resp = await self._http.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Discovery query failed: {e}")
            return []

        agents = data if isinstance(data, list) else data.get("agents", [])
        candidates = []
        for a in agents:
            candidates.append(AgentCandidate(
                agent_id=a.get("agent_id") or a.get("id", 0),
                name=a.get("name", ""),
                score=float(a.get("score", a.get("composite_score", 0))),
                tier=a.get("tier", "unranked"),
                category=a.get("category", ""),
                endpoint=a.get("endpoint", ""),
                risk_level=a.get("risk_level", "unknown"),
            ))

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    async def evaluate_agent(self, agent_id: int) -> dict[str, Any] | None:
        """Get full trust evaluation for a specific agent."""
        url = f"{self._oracle_url}/api/v1/trust/{agent_id}"
        try:
            resp = await self._http.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Agent evaluation failed for #{agent_id}: {e}")
            return None

    async def risk_check(self, agent_id: int) -> dict[str, Any] | None:
        """Get risk assessment for an agent."""
        url = f"{self._oracle_url}/api/v1/trust/{agent_id}/risk"
        try:
            resp = await self._http.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Risk check failed for #{agent_id}: {e}")
            return None

    async def close(self) -> None:
        await self._http.aclose()
