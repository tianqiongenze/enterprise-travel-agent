"""Skill weighting loader with strict path-safety validation."""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List

# Skill names are identifiers into <name>.skill.json under skills_dir; anything
# else (e.g. "../x", "a/b", absolute paths) is rejected outright.
_SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class SkillLoader:
    def __init__(self, skills_dir: str) -> None:
        self.skills_dir = os.path.realpath(skills_dir)

    def load(self, skill_names: List[str]) -> Dict[str, float]:
        merged: Dict[str, float] = {}
        baseline = os.getenv("TRAVEL_BASE_SKILLS", "").strip()
        if baseline:
            for item in baseline.split(","):
                name = item.strip()
                if name and name not in skill_names:
                    skill_names.append(name)
        for skill_name in skill_names:
            path = self._resolve_skill_path(skill_name)
            if path is None or not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            weights = payload.get("weights", {})
            if not isinstance(weights, dict):
                raise ValueError(f"skill file {path} has a non-object 'weights' section")
            for key, value in weights.items():
                merged[key] = merged.get(key, 1.0) * float(value)

        # Optional context knobs for classroom/enterprise simulation.
        if os.getenv("TRAVEL_SKILL_CONTEXT", "").strip().lower() == "peak-season":
            merged["price"] = merged.get("price", 1.0) * 1.1
            merged["comfort"] = merged.get("comfort", 1.0) * 1.05
        return merged

    def _resolve_skill_path(self, skill_name: object) -> str | None:
        if not isinstance(skill_name, str) or not _SKILL_NAME_PATTERN.match(skill_name):
            raise ValueError(f"invalid skill name: {skill_name!r}")
        path = os.path.realpath(os.path.join(self.skills_dir, f"{skill_name}.skill.json"))
        if os.path.commonpath([self.skills_dir, path]) != self.skills_dir:
            raise ValueError(f"skill path escapes skills directory: {skill_name!r}")
        return path
