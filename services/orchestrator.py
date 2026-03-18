"""Task orchestrator — the recruiter's brain.

Coordinates the full lifecycle:
  discover → evaluate → select → delegate → validate → settle → feedback
"""

import logging
import uuid
from typing import Any

from models import Task, TaskRequest, TaskStatus, AgentCandidate
from services.discovery import DiscoveryService
from services.delegation import DelegationService
from services.chain import ChainService
from services.logger import get_execution_logger

logger = logging.getLogger(__name__)


class Orchestrator:
    """Manages the full task-to-settlement lifecycle."""

    def __init__(self) -> None:
        self.discovery = DiscoveryService()
        self.delegation = DelegationService()
        self.chain = ChainService()
        self._tasks: dict[str, Task] = {}
        self._log = get_execution_logger()

    # ── Public API ───────────────────────────────────────────

    async def submit_task(self, request: TaskRequest) -> Task:
        """Accept a new task and begin the hiring pipeline."""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = Task(task_id=task_id, request=request)
        self._tasks[task_id] = task

        self._log.log(
            action="task_received",
            description=f"New task: {request.description[:100]}",
            tool_calls=["task_create"],
            details={"task_id": task_id, "category": request.category},
        )

        # Run the pipeline
        await self._execute_pipeline(task)
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 50) -> list[Task]:
        tasks = list(self._tasks.values())
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    @property
    def stats(self) -> dict[str, Any]:
        total = len(self._tasks)
        by_status = {}
        for t in self._tasks.values():
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1

        return {
            "total_tasks": total,
            "by_status": by_status,
            "chain_enabled": self.chain.enabled,
            "wallet": self.chain.wallet_address,
        }

    # ── Pipeline ─────────────────────────────────────────────

    async def _execute_pipeline(self, task: Task) -> None:
        """Run the full discover → delegate → validate → feedback pipeline."""

        # Step 1: Discover agents
        candidates = await self._discover(task)
        if not candidates:
            task.update_status(TaskStatus.FAILED, error="No agents found matching criteria")
            self._log.log(
                action="discovery_failed",
                description=f"No agents found for task {task.task_id}",
                outcome="error",
                details={"category": task.request.category},
            )
            return

        task.candidates = candidates

        # Step 2: Evaluate top candidates and select best
        selected = await self._select_agent(task, candidates)
        if not selected:
            task.update_status(TaskStatus.FAILED, error="All candidates failed risk check")
            self._log.log(
                action="selection_failed",
                description=f"All {len(candidates)} candidates failed risk check",
                outcome="error",
            )
            return

        task.update_status(TaskStatus.MATCHED, selected_agent=selected)
        self._log.log(
            action="agent_selected",
            description=f"Selected agent #{selected.agent_id} ({selected.name}) — score={selected.score}, tier={selected.tier}",
            tool_calls=["agentproof_evaluate", "agentproof_risk_check"],
            details={
                "agent_id": selected.agent_id,
                "score": selected.score,
                "tier": selected.tier,
                "candidates_evaluated": len(candidates),
            },
        )

        # Step 3: Delegate task
        task.update_status(TaskStatus.DELEGATED)
        result = await self.delegation.delegate(task, selected)

        if result is None:
            # Try fallback to next candidate
            fallback = await self._try_fallbacks(task, candidates, selected)
            if fallback is None:
                task.update_status(TaskStatus.FAILED, error="Delegation failed for all candidates")
                self._log.log(
                    action="delegation_failed",
                    description=f"All delegation attempts failed for task {task.task_id}",
                    outcome="error",
                )
                return
            result = fallback

        task.delegation_response = result

        # Step 4: Validate output
        validation = self._validate_output(task, result)
        task.validation_result = validation

        if validation.get("passed"):
            task.update_status(TaskStatus.COMPLETED)
            score = self._compute_feedback_score(task, validation)

            self._log.log(
                action="task_completed",
                description=f"Task {task.task_id} completed by agent #{selected.agent_id}",
                tool_calls=["a2a_delegate", "validate_output"],
                details={
                    "agent_id": selected.agent_id,
                    "feedback_score": score,
                    "validation": validation,
                },
            )

            # Step 5: Submit on-chain feedback
            await self._submit_feedback(task, selected, score, passed=True)

        else:
            task.update_status(TaskStatus.DISPUTED)
            self._log.log(
                action="task_disputed",
                description=f"Task {task.task_id} output validation failed",
                outcome="error",
                tool_calls=["validate_output"],
                details={"validation": validation},
            )

            # Submit negative feedback
            await self._submit_feedback(task, selected, score=25, passed=False)

    # ── Discovery ────────────────────────────────────────────

    async def _discover(self, task: Task) -> list[AgentCandidate]:
        """Find agents matching the task requirements."""
        return await self.discovery.find_agents(
            category=task.request.category,
            min_score=task.request.min_agent_score,
            min_tier=task.request.min_agent_tier,
            limit=10,
        )

    # ── Selection ────────────────────────────────────────────

    async def _select_agent(
        self, task: Task, candidates: list[AgentCandidate]
    ) -> AgentCandidate | None:
        """Evaluate candidates and pick the best one that passes risk checks."""
        for candidate in candidates[:5]:  # Check top 5
            risk = await self.discovery.risk_check(candidate.agent_id)
            if risk is None:
                continue

            risk_level = risk.get("risk_level", "unknown")
            candidate.risk_level = risk_level

            if risk_level in ("low", "medium"):
                return candidate

            self._log.log(
                action="candidate_rejected",
                description=f"Agent #{candidate.agent_id} rejected — risk={risk_level}",
                tool_calls=["agentproof_risk_check"],
                details={"agent_id": candidate.agent_id, "risk": risk},
            )

        return None

    # ── Fallback ─────────────────────────────────────────────

    async def _try_fallbacks(
        self,
        task: Task,
        candidates: list[AgentCandidate],
        already_tried: AgentCandidate,
    ) -> dict[str, Any] | None:
        """Try delegating to next-best candidates if primary fails."""
        for candidate in candidates:
            if candidate.agent_id == already_tried.agent_id:
                continue
            if candidate.risk_level in ("high", "critical"):
                continue

            self._log.log(
                action="delegation_fallback",
                description=f"Trying fallback agent #{candidate.agent_id}",
                tool_calls=["a2a_delegate"],
                retry_count=1,
            )

            result = await self.delegation.delegate(task, candidate)
            if result is not None:
                task.selected_agent = candidate
                return result

        return None

    # ── Validation ───────────────────────────────────────────

    def _validate_output(self, task: Task, result: dict[str, Any]) -> dict[str, Any]:
        """Validate the delegated task output."""
        state = result.get("status", {}).get("state", "unknown")

        # Check for completion
        if state != "completed":
            return {"passed": False, "reason": f"Task state is '{state}', expected 'completed'"}

        # Check for artifacts
        artifacts = result.get("artifacts", [])
        if not artifacts:
            return {"passed": False, "reason": "No artifacts returned"}

        # Check artifact has content
        for artifact in artifacts:
            parts = artifact.get("parts", [])
            has_content = any(
                p.get("text") or p.get("data")
                for p in parts
            )
            if has_content:
                return {"passed": True, "artifacts_count": len(artifacts)}

        return {"passed": False, "reason": "Artifacts contain no meaningful content"}

    # ── Feedback scoring ─────────────────────────────────────

    def _compute_feedback_score(self, task: Task, validation: dict[str, Any]) -> int:
        """Compute a 1-100 feedback score based on task outcome."""
        base_score = 70  # completed task baseline

        # Bonus for rich output
        artifact_count = validation.get("artifacts_count", 0)
        if artifact_count > 1:
            base_score += 10

        return min(100, base_score)

    # ── On-chain feedback ────────────────────────────────────

    async def _submit_feedback(
        self,
        task: Task,
        agent: AgentCandidate,
        score: int,
        passed: bool,
    ) -> None:
        """Submit ERC-8004 reputation feedback on-chain."""
        comment = (
            f"Task {task.task_id} {'completed' if passed else 'disputed'}: "
            f"{task.request.description[:100]}"
        )

        tx_hash = self.chain.submit_feedback(
            agent_id=agent.agent_id,
            score=score,
            comment=comment,
            tag1="delegation",
            tag2="recruiter-verdict",
        )

        if tx_hash:
            task.feedback_tx = tx_hash
            self._log.log(
                action="feedback_submitted",
                description=f"On-chain feedback for agent #{agent.agent_id}: score={score}",
                tool_calls=["erc8004_giveFeedback"],
                details={
                    "agent_id": agent.agent_id,
                    "score": score,
                    "tx_hash": tx_hash,
                    "chain": "base",
                },
            )
        else:
            self._log.log(
                action="feedback_skipped",
                description=f"Feedback not submitted for agent #{agent.agent_id} (chain disabled or error)",
                outcome="skipped",
            )

    async def close(self) -> None:
        await self.discovery.close()
        await self.delegation.close()
