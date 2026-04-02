"""Research quality KPIs — computed from results.tsv and learnings.jsonl (AP-7)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from math import log2


def compute_kpis(
    results_path: Path | None = None,
    learnings_path: Path | None = None,
) -> dict:
    """Compute research quality KPIs from experiment data."""

    if results_path is None:
        # Try Docker work dir first, then local
        for p in [Path("docker/autoresearch/work/results.tsv"), Path("scripts/autoresearch/results.tsv")]:
            if p.exists():
                results_path = p
                break

    if learnings_path is None:
        for p in [Path("docker/autoresearch/watchdog_data/learnings.jsonl"), Path("scripts/autoresearch/learnings.jsonl")]:
            if p.exists():
                learnings_path = p
                break

    kpis = {}

    # 1. Gate conversion rate from results.tsv
    if results_path and results_path.exists():
        lines = [l for l in results_path.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#") and not l.startswith("commit")]

        total = len(lines)
        level_counts = Counter()
        status_counts = Counter()
        family_counts = Counter()

        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 5:
                level = parts[3].strip()
                status = parts[4].strip()
                level_counts[level] += 1
                status_counts[status] += 1
            if len(parts) >= 6:
                desc = parts[5] if len(parts) > 5 else ""
                # Detect family from description (same logic as evaluate.py _detect_family)
                desc_lower = desc.lower()
                if any(k in desc_lower for k in ("revenue", "營收")):
                    family_counts["revenue"] += 1
                elif any(k in desc_lower for k in ("value", "per", "pbr")):
                    family_counts["value"] += 1
                elif any(k in desc_lower for k in ("quality", "roe", "margin")):
                    family_counts["quality"] += 1
                elif any(k in desc_lower for k in ("momentum", "drift")):
                    family_counts["momentum"] += 1
                else:
                    family_counts["other"] += 1

        kpis["total_experiments"] = total
        kpis["gate_conversion"] = {
            level: {"count": count, "rate": f"{count/max(total,1):.0%}"}
            for level, count in sorted(level_counts.items())
        }
        kpis["status_distribution"] = dict(status_counts)

        # Novelty rate: keep vs discard vs crash
        keeps = sum(1 for s in status_counts if "keep" in s.lower())
        kpis["novelty_rate"] = f"{keeps}/{total}" if total > 0 else "N/A"

        # Family entropy (Shannon)
        if family_counts:
            total_fam = sum(family_counts.values())
            probs = [c / total_fam for c in family_counts.values() if c > 0]
            entropy = -sum(p * log2(p) for p in probs if p > 0)
            max_entropy = log2(len(family_counts)) if len(family_counts) > 1 else 1
            kpis["family_entropy"] = round(entropy, 3)
            kpis["family_entropy_normalized"] = round(entropy / max_entropy, 3) if max_entropy > 0 else 0
            kpis["family_distribution"] = dict(family_counts)

        # Research efficiency
        l4_plus = sum(c for l, c in level_counts.items() if l in ("L4", "L5"))
        kpis["research_efficiency"] = f"{l4_plus} L4+ from {total} experiments ({l4_plus/max(total,1):.1%})"

    # 2. Direction stats from learnings.jsonl
    if learnings_path and learnings_path.exists():
        directions = Counter()
        for line in learnings_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                d = entry.get("direction", "unknown")
                directions[d] += 1
            except json.JSONDecodeError:
                continue
        kpis["direction_coverage"] = len(directions)
        kpis["top_directions"] = dict(directions.most_common(10))

    return kpis


if __name__ == "__main__":
    import sys
    kpis = compute_kpis()
    json.dump(kpis, sys.stdout, indent=2, ensure_ascii=False)
    print()
