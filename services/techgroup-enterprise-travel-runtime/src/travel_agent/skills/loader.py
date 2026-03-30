"""Module provides service components and helpers."""

import json
import os
from typing import Dict, List


class SkillLoader:
    def __init__(self, skills_dir: str) -> None:
        self.skills_dir = skills_dir

    def load(self, skill_names: List[str]) -> Dict[str, float]:
        merged: Dict[str, float] = {}
        baseline = os.getenv("TRAVEL_BASE_SKILLS", "").strip()
        if baseline:
            for item in baseline.split(","):
                name = item.strip()
                if name and name not in skill_names:
                    skill_names.append(name)
        for skill_name in skill_names:
            path = os.path.join(self.skills_dir, "%s.skill.json" % skill_name)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            weights = payload.get("weights", {})
            for key, value in weights.items():
                merged[key] = merged.get(key, 1.0) * float(value)

        # Optional context knobs for classroom/enterprise simulation.
        if os.getenv("TRAVEL_SKILL_CONTEXT", "").strip().lower() == "peak-season":
            merged["price"] = merged.get("price", 1.0) * 1.1
            merged["comfort"] = merged.get("comfort", 1.0) * 1.05
        return merged
