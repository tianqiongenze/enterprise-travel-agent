"""Module provides service components and helpers."""

import time
import uuid
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class A2AMessage:
    id: str
    sender: str
    receiver: str
    topic: str
    payload: Dict[str, object]
    timestamp: float
    correlation_id: str
    metadata: Dict[str, object]


def new_message(
    sender: str,
    receiver: str,
    topic: str,
    payload: Dict[str, object],
    correlation_id: Optional[str] = None,
    metadata: Optional[Dict[str, object]] = None,
) -> A2AMessage:
    cid = correlation_id or str(uuid.uuid4())
    return A2AMessage(
        id=str(uuid.uuid4()),
        sender=sender,
        receiver=receiver,
        topic=topic,
        payload=payload,
        timestamp=time.time(),
        correlation_id=cid,
        metadata=metadata or {},
    )
