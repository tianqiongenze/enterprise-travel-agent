"""Reproduce the /recommend hang seen in the kind staging retest.

Runs the FastAPI app in-process with the same env the staging pod gets
(minus k8s-only URLs pointed at unreachable local ports) and dumps the
stack after 10s if the request has not returned.
"""
import faulthandler
import os
import sys
import threading
import time

os.environ.setdefault("TRAVEL_RANKER_BACKEND", "go")
os.environ.setdefault("TRAVEL_GO_RANKER_URL", "http://127.0.0.1:8090")
os.environ.setdefault("TRAVEL_GO_RANKER_TIMEOUT", "0.4")
os.environ.setdefault("TRAVEL_NACOS_BACKEND", "nacos-real")
os.environ.setdefault("TRAVEL_NACOS_URL", "http://127.0.0.1:18848")
os.environ.setdefault("TRAVEL_ETCD_ENDPOINTS", "127.0.0.1:12379")
os.environ.setdefault("TRAVEL_ETCD_BACKEND", "legacy")
# smoke-window env overrides under test (staging-retest.yml "Fit smoke workload"):
os.environ.setdefault("TRAVEL_EVENT_BUS", "local")
os.environ.setdefault("TRAVEL_A2A_TRANSPORT", "mock")
os.environ.setdefault("TRAVEL_A2A_AUDIT_MIRROR_PULSAR", "false")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "services", "techgroup-enterprise-travel-runtime"))

faulthandler.enable()
from fastapi.testclient import TestClient  # noqa: E402
from src.travel_agent.api.app import app  # noqa: E402

client = TestClient(app)
result = {}


def call():
    t0 = time.perf_counter()
    try:
        r = client.post("/recommend", json={})
        result["status"] = r.status_code
        result["ms"] = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as exc:  # noqa: BLE001
        result["error"] = repr(exc)
        result["ms"] = round((time.perf_counter() - t0) * 1000, 1)


t = threading.Thread(target=call, daemon=True)
t.start()
t.join(timeout=25)
if t.is_alive():
    print("HANG CONFIRMED: request did not return in 25s; stack of all threads:")
    faulthandler.dump_traceback(file=sys.stdout)
else:
    print("RETURNED:", result)
