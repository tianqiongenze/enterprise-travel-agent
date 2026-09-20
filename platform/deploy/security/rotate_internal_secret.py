#!/usr/bin/env python
"""Two-phase internal-secret rotation for the travel-agent internal HMAC (Gap1).

The runtime (Python) and the gateway (Java) share
TRAVEL_INTERNAL_SHARED_SECRET and verify it with the same
HMAC-SHA256(payload + "." + clientId) scheme. Rotation is dual-window:

  Phase 1 (this script): generate a fresh secret, set
      TRAVEL_INTERNAL_SHARED_SECRET = <new>
      TRAVEL_INTERNAL_SHARED_SECRET_PREVIOUS = <current>
  Phase 2 (after rollout): once every runtime and gateway pod has been
      restarted on the new values, clear PREVIOUS (set it to empty) and
      the rotation window closes.

Rollout order inside a phase: runtime first, then gateway — the runtime
accepts both secrets while the gateway signs with only one, so any
ordering is safe; runtime-first is still the documented convention.

Usage:
  python rotate_internal_secret.py --current-env platform/deploy/env/prod.env
  python rotate_internal_secret.py --current-env prod.env --close-window
"""

from __future__ import annotations

import argparse
import base64
import re
import secrets
import sys
from pathlib import Path

CURRENT_KEY = "TRAVEL_INTERNAL_SHARED_SECRET"
PREVIOUS_KEY = "TRAVEL_INTERNAL_SHARED_SECRET_PREVIOUS"


def generate_secret() -> str:
    """32 bytes of CSPRNG entropy, url-safe base64 (no shell-hostile chars)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def read_current(path: Path) -> str | None:
    if not path.exists():
        return None
    pattern = re.compile(rf"^export {CURRENT_KEY}=(.+)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if match:
            value = match.group(1).strip().strip('"').strip("'")
            if value and value != "demo-internal-secret":
                return value
    return None


def write_updated_env(path: Path, current: str, previous: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    wanted = {CURRENT_KEY: current, PREVIOUS_KEY: previous}
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        replaced = False
        for key, value in wanted.items():
            if stripped.startswith(f"export {key}=") or stripped.startswith(f"{key}="):
                out.append(f"export {key}={value}")
                seen.add(key)
                replaced = True
                break
        if not replaced:
            out.append(line)
    for key, value in wanted.items():
        if key not in seen:
            out.append(f"export {key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dual-window internal-secret rotation")
    parser.add_argument("--current-env", required=True, help="env file that carries the current secret")
    parser.add_argument(
        "--close-window",
        action="store_true",
        help="phase 2: clear TRAVEL_INTERNAL_SHARED_SECRET_PREVIOUS instead of rotating",
    )
    args = parser.parse_args(argv)

    env_path = Path(args.current_env)
    if args.close_window:
        write_updated_env(env_path, read_current(env_path) or "", "")
        print(f"[rotation] window closed: {PREVIOUS_KEY} cleared in {env_path}")
        print("[rotation] redeploy runtime, then gateway; rotation complete")
        return 0

    current = read_current(env_path)
    if not current:
        print(
            f"[rotation] ERROR: no usable {CURRENT_KEY} found in {env_path} "
            "(missing or demo placeholder); set it explicitly first",
            file=sys.stderr,
        )
        return 2
    new_secret = generate_secret()
    write_updated_env(env_path, new_secret, current)
    print(f"[rotation] phase 1 written to {env_path}:")
    print(f"[rotation]   {CURRENT_KEY}=<new 256-bit secret>")
    print(f"[rotation]   {PREVIOUS_KEY}=<old secret, accepted until window closes>")
    print("[rotation] rollout order: redeploy runtime first, then gateway")
    print("[rotation] after all pods are on the new secret, rerun with --close-window")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
