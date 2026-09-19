import hashlib
import json
import os
import random
import time

from locust import HttpUser, task, between


def _signature(idempotency_key: str, secret: str) -> str:
    raw = f"{idempotency_key}.{secret}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class RuntimeRecommendUser(HttpUser):
    wait_time = between(0.01, 0.05)

    def on_start(self) -> None:
        self.secret = os.getenv("TRAVEL_INTERNAL_SHARED_SECRET", "demo-internal-secret")
        self.client_id = os.getenv("TRAVEL_INTERNAL_CLIENT_ID", "techgroup-enterprise-travel-gateway")
        self.tenant = os.getenv("TRAVEL_TEST_TENANT", "tenant-loadtest")
        self.user_prefix = os.getenv("TRAVEL_TEST_USER_PREFIX", "user-locust")
        self.cities = ["北京", "上海", "深圳", "广州", "成都", "杭州"]

    @task
    def runtime_recommend(self) -> None:
        now_ms = int(time.time() * 1000)
        idem = f"idem-{self.user_prefix}-{now_ms}-{random.randint(1, 10_000_000)}"
        trace_id = f"trace-{self.user_prefix}-{now_ms}-{random.randint(1, 10_000_000)}"
        user_id = f"{self.user_prefix}-{random.randint(1, 1_000_000)}"
        conversation_id = f"conv-{user_id}-{random.randint(1, 1_000_000)}"

        payload = {
            "tenantId": self.tenant,
            "userId": user_id,
            "conversationId": conversation_id,
            "idempotencyKey": idem,
            "membershipTier": random.choice(["basic", "silver", "gold", "platinum"]),
            "city": random.choice(self.cities),
            "days": random.choice([2, 3, 4, 5]),
            "budget": random.choice([2000, 2600, 3200, 4000, 5200]),
            "travelers": random.choice([1, 2, 3, 4]),
            "preferences": random.choice([
                ["family"],
                ["budget"],
                ["comfort"],
                ["family", "budget"],
            ]),
            "maxAgentSteps": 10,
            "maxToolCalls": 10,
            "allowedTools": ["search_hotels", "search_transports", "search_attractions"],
        }

        headers = {
            "Content-Type": "application/json",
            "X-Trace-Id": trace_id,
            "X-Internal-Client-Id": self.client_id,
            "X-Internal-Signature": _signature(idem, self.secret),
        }

        with self.client.post(
            "/runtime/recommend",
            data=json.dumps(payload, ensure_ascii=False),
            headers=headers,
            name="POST /runtime/recommend",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code}")
            else:
                response.success()
