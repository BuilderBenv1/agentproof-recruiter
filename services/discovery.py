"""Agent discovery via AgentProof oracle.

Queries the trust oracle to find agents matching task requirements,
ranked by composite score. Filters by category, minimum score, minimum tier,
and required skills (via capability search).
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
        required_skills: list[str] | None = None,
        limit: int = 10,
    ) -> list[AgentCandidate]:
        """Query the oracle for trusted agents matching criteria.

        If required_skills are provided, searches by capability first.
        Falls back to category-based discovery.
        """
        settings = get_settings()
        score_threshold = min_score or settings.min_agent_score

        # Try capability search first if skills are specified
        if required_skills:
            candidates = []
            for skill in required_skills:
                found = await self._search_by_capability(skill, score_threshold, limit)
                candidates.extend(found)
            if candidates:
                # Deduplicate by agent_id, keep highest score
                seen: dict[int, AgentCandidate] = {}
                for c in candidates:
                    if c.agent_id not in seen or c.score > seen[c.agent_id].score:
                        seen[c.agent_id] = c
                result = sorted(seen.values(), key=lambda c: c.score, reverse=True)
                return result[:limit]

        # Fallback to category-based discovery
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
                name=a.get("name") or "",
                score=float(a.get("score", a.get("composite_score", 0))),
                tier=a.get("tier") or "unranked",
                category=a.get("category") or "",
                endpoint=a.get("endpoint") or "",
                risk_level=a.get("risk_level") or "unknown",
            ))

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    async def _search_by_capability(
        self, capability: str, min_score: float, limit: int
    ) -> list[AgentCandidate]:
        """Search agents by capability via the oracle's capability search endpoint."""
        url = f"{self._oracle_url}/api/v1/agents/search"
        params = {"capability": capability, "min_score": min_score, "limit": limit}
        try:
            resp = await self._http.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.info(f"Capability search for '{capability}' failed: {e}")
            return []

        agents = data if isinstance(data, list) else []
        candidates = []
        for a in agents:
            endpoint = ""
            # Try indexed endpoints first
            for ep in a.get("indexed_endpoints", []):
                if ep.get("endpoint_type") == "a2a":
                    endpoint = ep.get("endpoint_url", "")
                    break
            # Fallback to agent endpoints field
            if not endpoint:
                eps = a.get("endpoints", [])
                if eps and isinstance(eps, list):
                    first = eps[0]
                    endpoint = first if isinstance(first, str) else first.get("url", "")

            candidates.append(AgentCandidate(
                agent_id=a.get("agent_id", 0),
                name=a.get("name") or "",
                score=float(a.get("composite_score", 0)),
                tier=a.get("tier") or "unranked",
                category=a.get("category") or "",
                endpoint=endpoint,
                risk_level="unknown",
            ))

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
