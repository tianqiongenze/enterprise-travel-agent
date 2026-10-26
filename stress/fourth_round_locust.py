"""Fourth-round Locust business-journey simulation (plan §四.R11).

Distributed master/worker on K8s (see platform/deploy/k8s/locust-fourth-round.yaml).
Simulates a realistic visitor journey rather than raw HTTP:
    browse → recommend (REST) → GraphQL cross-check → enqueue async itinerary
    → poll task status → collect metrics scrape.

Run: locust -f stress/fourth_round_locust.py --headless -u 500 -r 25 --run-time 3m --host $BASE_URL
"""

from __future__ import annotations

import json
import random
import time

from locust import HttpUser, between, events, task

CITIES = ["北京", "上海", "杭州", "成都", "西安", "广州", "三亚"]
_graphql_rejects = 0
_sync_latencies: list[float] = []


@events.test_start.add_listener
def _on_start(environment, **kwargs):
    print(f"[locust] fourth-round journey sim against {environment.host}")


class VisitorJourney(HttpUser):
    wait_time = between(0.2, 1.2)

    def on_start(self):
        self.city = random.choice(CITIES)

    @task(6)
    def browse_recommend(self):
        started = time.perf_counter()
        with self.client.post(
            "/recommend",
            json={"city": self.city, "days": random.choice([2, 3, 5])},
            name="POST /recommend",
            catch_response=True,
        ) as resp:
            elapsed = (time.perf_counter() - started) * 1000
            _sync_latencies.append(elapsed)
            if resp.status_code != 200:
                resp.failure(f"status {resp.status_code}")
                return
            body = resp.json()
            missing = [k for k in ("hotel_options", "transport_options", "itinerary") if k not in body]
            if missing:
                resp.failure(f"contract missing {missing}")
            else:
                resp.success()

    @task(3)
    def graphql_cross_check(self):
        global _graphql_rejects
        payload = {
            "query": "query($c: String) { recommend(payload: {city: $c}) { city days hotels { name } } }",
            "variables": {"c": self.city},
        }
        with self.client.post("/graphql", json=payload, name="POST /graphql", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"status {resp.status_code}")
                return
            body = resp.json()
            if body.get("errors"):
                _graphql_rejects += 1
                resp.failure(f"graphql errors: {body['errors'][:1]}")
            else:
                resp.success()

    @task(1)
    def scrape_metrics(self):
        self.client.get("/metrics", name="GET /metrics")

    @task(1)
    def health_probe(self):
        self.client.get("/health", name="GET /health")


@events.test_stop.add_listener
def _on_stop(environment, **kwargs):
    if _sync_latencies:
        ordered = sorted(_sync_latencies)
        n = len(ordered)
        print(
            json.dumps(
                {
                    "journeys": n,
                    "rest_p50_ms": round(ordered[n // 2], 1),
                    "rest_p95_ms": round(ordered[min(n - 1, int(n * 0.95))], 1),
                    "rest_p99_ms": round(ordered[min(n - 1, int(n * 0.99))], 1),
                    "graphql_error_events": _graphql_rejects,
                },
                indent=2,
            )
        )
