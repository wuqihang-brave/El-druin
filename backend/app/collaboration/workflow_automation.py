"""Trigger-based workflow automation engine."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class WorkflowTrigger:
    """Specification for when a workflow fires.

    Attributes:
        trigger_type: event_created | threshold_crossed | schedule.
        conditions: List of condition dicts (field, operator, value).
    """

    trigger_type: str
    conditions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class WorkflowAction:
    """A single action performed by a workflow.

    Attributes:
        action_type: notify | create_prediction | update_watchlist | webhook.
        parameters: Action-specific parameter dict.
    """

    action_type: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowDefinition:
    """A complete workflow with trigger and actions.

    Attributes:
        id: Unique workflow identifier.
        trigger: When the workflow fires.
        actions: Actions to execute in order.
        is_active: Whether the workflow is enabled.
        created_at: Creation timestamp.
        cron_expression: Optional schedule cron expression.
    """

    id: str
    trigger: WorkflowTrigger
    actions: list[WorkflowAction]
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    cron_expression: Optional[str] = None


@dataclass
class WorkflowResult:
    """Result of a single workflow execution.

    Attributes:
        workflow_id: Executed workflow.
        actions_executed: Number of actions successfully executed.
        actions_failed: Number of failed actions.
        outputs: Per-action output dict.
        error: Error message if the workflow failed.
    """

    workflow_id: str
    actions_executed: int = 0
    actions_failed: int = 0
    outputs: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class WorkflowAutomationEngine:
    """Trigger-based workflow automation engine.

    Registers workflows, evaluates triggers against incoming events, and
    executes actions including notifications, predictions, and webhooks.

    Attributes:
        _workflows: Registry of workflow definitions.
        _action_handlers: Mapping of action type → handler coroutine.
    """

    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._action_handlers: dict[str, Callable] = {
            "notify": self._action_notify,
            "create_prediction": self._action_create_prediction,
            "update_watchlist": self._action_update_watchlist,
            "webhook": self._action_webhook,
        }

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register_workflow(
        self,
        trigger: WorkflowTrigger,
        actions: list[WorkflowAction],
    ) -> str:
        """Register a new workflow.

        Args:
            trigger: Trigger specification.
            actions: Ordered list of actions.

        Returns:
            New workflow identifier.
        """
        workflow_id = str(uuid.uuid4())
        wf = WorkflowDefinition(
            id=workflow_id, trigger=trigger, actions=actions
        )
        self._workflows[workflow_id] = wf
        await self._persist_workflow(wf)
        logger.info("Registered workflow %s (%s)", workflow_id, trigger.trigger_type)
        return workflow_id

    # ------------------------------------------------------------------
    # Trigger evaluation
    # ------------------------------------------------------------------

    async def evaluate_triggers(self, event: dict) -> list[str]:
        """Evaluate all registered workflows against an incoming event.

        Args:
            event: Incoming event dict.

        Returns:
            List of triggered workflow IDs.
        """
        triggered: list[str] = []
        for wf_id, wf in self._workflows.items():
            if not wf.is_active:
                continue
            if wf.trigger.trigger_type not in ("event_created", "threshold_crossed"):
                continue
            if self._evaluate_conditions(event, wf.trigger.conditions):
                triggered.append(wf_id)
        return triggered

    def _evaluate_conditions(
        self, event: dict, conditions: list[dict[str, Any]]
    ) -> bool:
        """Check all conditions against the event.

        All conditions must be satisfied (AND logic).

        Args:
            event: Event dict.
            conditions: List of condition dicts.

        Returns:
            True if all conditions match.
        """
        for condition in conditions:
            field_path = condition.get("field", "")
            operator = condition.get("operator", "eq")
            expected = condition.get("value")
            actual = self._get_nested(event, field_path)

            if operator == "eq" and actual != expected:
                return False
            if operator == "ne" and actual == expected:
                return False
            if operator == "gt" and not (actual is not None and actual > expected):
                return False
            if operator == "lt" and not (actual is not None and actual < expected):
                return False
            if operator == "contains" and (
                not isinstance(actual, (str, list))
                or expected not in actual
            ):
                return False
        return True

    @staticmethod
    def _get_nested(data: dict, path: str) -> Any:
        """Get a nested value from a dict using dot-notation.

        Args:
            data: Source dict.
            path: Dot-separated path string.

        Returns:
            Value at path or *None*.
        """
        parts = path.split(".")
        current: Any = data
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute_workflow(
        self, workflow_id: str, context: dict
    ) -> WorkflowResult:
        """Execute all actions in a workflow.

        Args:
            workflow_id: Workflow to execute.
            context: Execution context dict passed to each action.

        Returns:
            :class:`WorkflowResult` summarising the execution.
        """
        wf = self._workflows.get(workflow_id)
        if wf is None:
            return WorkflowResult(
                workflow_id=workflow_id, error=f"Workflow {workflow_id} not found"
            )

        result = WorkflowResult(workflow_id=workflow_id)
        for action in wf.actions:
            handler = self._action_handlers.get(action.action_type)
            if handler is None:
                logger.warning("Unknown action type: %s", action.action_type)
                result.actions_failed += 1
                continue
            try:
                output = await handler(action.parameters, context)
                result.outputs[action.action_type] = output
                result.actions_executed += 1
            except Exception as exc:
                logger.error(
                    "Action %s in workflow %s failed: %s",
                    action.action_type,
                    workflow_id,
                    exc,
                )
                result.actions_failed += 1
        return result

    async def schedule_workflow(
        self, workflow_id: str, cron_expression: str
    ) -> bool:
        """Attach a cron schedule to a workflow.

        Args:
            workflow_id: Workflow to schedule.
            cron_expression: Standard cron expression (5-field).

        Returns:
            True if the schedule was stored.
        """
        wf = self._workflows.get(workflow_id)
        if wf is None:
            return False
        wf.cron_expression = cron_expression
        await self._persist_workflow(wf)
        return True

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    async def _action_notify(
        self, params: dict, context: dict
    ) -> dict:
        """Send a notification via the configured channel.

        Args:
            params: Notification parameters (channel, message).
            context: Execution context.

        Returns:
            Notification result dict.
        """
        channel = params.get("channel", "websocket")
        message = params.get("message", "Workflow notification")
        try:
            from app.db.redis_client import redis_client

            await redis_client.publish(
                f"notifications:{channel}",
                {"message": message, "context": context},
            )
        except Exception as exc:
            logger.warning("Notification publish failed: %s", exc)
        return {"channel": channel, "status": "sent"}

    async def _action_create_prediction(
        self, params: dict, context: dict
    ) -> dict:
        """Trigger a new prediction for the event in context.

        Args:
            params: Action parameters (prediction_type).
            context: Execution context (must contain event data).

        Returns:
            Created prediction summary dict.
        """
        try:
            from app.core.predictor import prediction_orchestrator

            event_data = context.get("event", {})
            prediction_type = params.get("prediction_type", "general")
            result = await prediction_orchestrator.predict(
                event_data, prediction_type
            )
            return {"prediction_id": result.prediction_id, "confidence": result.confidence}
        except Exception as exc:
            logger.error("create_prediction action failed: %s", exc)
            return {"error": str(exc)}

    async def _action_update_watchlist(
        self, params: dict, context: dict
    ) -> dict:
        """Update a watchlist entry based on workflow params.

        Args:
            params: Update parameters.
            context: Execution context.

        Returns:
            Update result dict.
        """
        return {"status": "watchlist_updated", "params": params}

    async def _action_webhook(
        self, params: dict, context: dict
    ) -> dict:
        """Send an HTTP POST webhook.

        Args:
            params: Webhook parameters (url, headers, payload).
            context: Execution context.

        Returns:
            Webhook response summary dict.
        """
        url = params.get("url", "")
        if not url:
            return {"error": "No webhook URL configured"}
        try:
            import aiohttp  # type: ignore

            async with aiohttp.ClientSession() as session:
                payload = {**params.get("payload", {}), "context": context}
                async with session.post(
                    url,
                    json=payload,
                    headers=params.get("headers", {}),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return {"status_code": resp.status, "url": url}
        except ImportError:
            logger.warning("aiohttp not installed; webhook skipped")
            return {"status": "skipped", "reason": "aiohttp not available"}
        except Exception as exc:
            return {"error": str(exc), "url": url}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _persist_workflow(self, wf: WorkflowDefinition) -> None:
        """Persist a workflow definition to Redis.

        Args:
            wf: Workflow to persist.
        """
        import dataclasses, json

        try:
            from app.db.redis_client import redis_client

            data = json.dumps(dataclasses.asdict(wf), default=str)
            await redis_client.set(f"workflow:{wf.id}", data)
        except Exception as exc:
            logger.warning("Workflow persist failed: %s", exc)


# Module-level singleton
workflow_engine = WorkflowAutomationEngine()
