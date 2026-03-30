"""Module provides memory backends and access helpers."""

from typing import Dict, List, Set


class GraphRAGContextBuilder:
    """Builds lightweight entity graph context for itinerary ranking."""

    def build_hints(self, rows: List[Dict[str, object]], preferences: List[str], limit: int = 5) -> List[str]:
        if not rows:
            return []
        graph: Dict[str, Set[str]] = {}
        for row in rows:
            name = str(row.get("name", ""))
            tags = [str(item) for item in row.get("tags", []) if str(item)]
            if not name:
                continue
            graph.setdefault(name, set()).update(tags)
            for tag in tags:
                graph.setdefault(tag, set()).add(name)
        seeds = [item for item in preferences if item in graph]
        if not seeds:
            return []
        scores: Dict[str, int] = {}
        for seed in seeds:
            for neighbor in graph.get(seed, set()):
                scores[neighbor] = scores.get(neighbor, 0) + 1
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return [name for name, _ in ranked[:limit]]

