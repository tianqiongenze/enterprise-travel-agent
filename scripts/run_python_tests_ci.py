"""Module provides service components and helpers."""

import os
import subprocess
import sys


def main() -> int:
    env = os.environ.copy()
    # Force local-only event paths during CI to avoid external Pulsar dependency.
    env.setdefault("TRAVEL_EVENT_BUS", "local")
    env.setdefault("TRAVEL_EVENT_BUS_STRICT", "false")
    env.setdefault("TRAVEL_A2A_AUDIT_MIRROR_PULSAR", "false")
    # Set PYTHONPATH for Phase-2 migration: point to new service location
    env.setdefault("PYTHONPATH", os.path.join(os.getcwd(), "services", "techgroup-enterprise-travel-runtime"))

    args = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]
    if len(sys.argv) > 1:
        args = [sys.executable, "-m", "unittest", *sys.argv[1:]]
    completed = subprocess.run(args, env=env)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
