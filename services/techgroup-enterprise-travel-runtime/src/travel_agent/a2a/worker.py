"""A2A reply worker: closes the agent-to-agent request/reply loop.

The orchestrator publishes route/trip tasks onto the A2A transport; this worker
drains the receiver inboxes, executes the registered handler, and posts a reply
back to the requesting agent, so A2A traffic is a real round trip rather than
fire-and-forget logging.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List

from .router import A2ARouter

logger = logging.getLogger("travel_agent.a2a.worker")

Handler = Callable[[Dict[str, object]], Dict[str, object]]


class A2AWorker:
    def __init__(self, router: A2ARouter) -> None:
        self.router = router
        self._handlers: Dict[str, Dict[str, Handler]] = {}

    def register_handler(self, receiver: str, topic: str, handler: Handler) -> None:
        self._handlers.setdefault(receiver, {})[topic] = handler

    def drain(self, receiver: str, limit: int = 32) -> List[Dict[str, object]]:
        """Consume pending messages for ``receiver`` and reply to senders."""
        replies: List[Dict[str, object]] = []
        for message in self.router.inbox(receiver):
            if not isinstance(message, dict):
                continue
            topic = str(message.get("topic", ""))
            handler = self._handlers.get(receiver, {}).get(topic)
            if handler is None:
                logger.debug("a2a worker: no handler for receiver=%s topic=%s", receiver, topic)
                continue
            try:
                payload = handler(message.get("payload") or {})
            except Exception as error:
                logger.warning("a2a handler %s/%s failed: %s", receiver, topic, error)
                payload = {"error": str(error)}
            reply = self.router.send(
                receiver,
                str(message.get("sender", "manager-agent")),
                f"{topic}.reply",
                payload,
                correlation_id=message.get("correlationId"),
            )
            replies.append(reply.__dict__)
        return replies
