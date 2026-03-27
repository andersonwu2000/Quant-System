"""Experience Memory — 持久化的研究經驗知識庫。

記錄成功模式、禁區、已探索方向、研究軌跡。
跨 session 持久化（JSON），供自動化 Alpha 研究 Agent 使用。
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_PATH = "data/research/memory.json"


@dataclass
class SuccessPattern:
    """成功的因子模式。"""
    name: str
    description: str
    factors: list[str]
    avg_icir: float
    avg_fitness: float = 0.0
    evidence: str = ""
    mutation_suggestions: list[str] = field(default_factory=list)


@dataclass
class ForbiddenRegion:
    """已知無效的方向。"""
    name: str
    reason: str
    factor_patterns: list[str] = field(default_factory=list)
    evidence: str = ""


@dataclass
class DirectionStatus:
    """研究方向狀態。"""
    name: str
    status: str = "pending"  # pending | exploring | strong | weak | exhausted
    priority: str = "P1"  # P0 | P1 | P2
    best_icir: float = 0.0
    hypothesis_count: int = 0
    pass_count: int = 0


@dataclass
class Hypothesis:
    """因子假說。"""
    name: str
    description: str
    formula_sketch: str
    expected_direction: int = 1  # +1 or -1
    academic_basis: str = ""
    data_requirements: list[str] = field(default_factory=list)
    direction: str = ""


@dataclass
class ResearchTrajectory:
    """完整研究軌跡 — 記錄每步，不只記結果。"""
    id: str
    timestamp: str
    hypothesis: dict[str, Any]
    implementation_success: bool = False
    eval_results: dict[str, float] = field(default_factory=dict)
    fitness: float = 0.0
    failure_step: str = ""  # "" | "hypothesis" | "implementation" | "L1" | "L2" | "L3" | "L4" | "L5"
    failure_reason: str = ""
    duration_seconds: float = 0.0
    passed: bool = False


@dataclass
class ExperienceMemory:
    """研究經驗知識庫。"""
    version: int = 2
    total_rounds: int = 0
    total_pass: int = 0
    total_fail: int = 0
    best_fitness: float = 0.0
    last_updated: str = ""
    success_patterns: list[SuccessPattern] = field(default_factory=list)
    forbidden_regions: list[ForbiddenRegion] = field(default_factory=list)
    directions: list[DirectionStatus] = field(default_factory=list)
    trajectories: list[ResearchTrajectory] = field(default_factory=list)

    @classmethod
    def load(cls, path: str = DEFAULT_MEMORY_PATH) -> ExperienceMemory:
        """從 JSON 載入。不存在則建立新的。"""
        p = Path(path)
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                mem = cls()
                mem.version = data.get("version", 2)
                mem.total_rounds = data.get("total_rounds", 0)
                mem.total_pass = data.get("total_pass", 0)
                mem.total_fail = data.get("total_fail", 0)
                mem.best_fitness = data.get("best_fitness", 0)
                mem.last_updated = data.get("last_updated", "")
                mem.success_patterns = [
                    SuccessPattern(**p) for p in data.get("success_patterns", [])
                ]
                mem.forbidden_regions = [
                    ForbiddenRegion(**r) for r in data.get("forbidden_regions", [])
                ]
                mem.directions = [
                    DirectionStatus(**d) for d in data.get("directions", [])
                ]
                mem.trajectories = [
                    ResearchTrajectory(**t) for t in data.get("trajectories", [])
                ]
                logger.info("Loaded memory: %d trajectories, %d patterns, %d forbidden",
                           len(mem.trajectories), len(mem.success_patterns), len(mem.forbidden_regions))
                return mem
            except Exception as e:
                logger.warning("Failed to load memory from %s: %s, starting fresh", path, e)
        return cls()

    def save(self, path: str = DEFAULT_MEMORY_PATH) -> None:
        """存到 JSON。"""
        self.last_updated = datetime.now().isoformat()
        # 限制軌跡數量
        if len(self.trajectories) > 500:
            self.trajectories = self.trajectories[-500:]
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self._to_dict(), f, indent=2, ensure_ascii=False)

    def _to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "total_rounds": self.total_rounds,
            "total_pass": self.total_pass,
            "total_fail": self.total_fail,
            "best_fitness": self.best_fitness,
            "last_updated": self.last_updated,
            "success_patterns": [asdict(p) for p in self.success_patterns],
            "forbidden_regions": [asdict(r) for r in self.forbidden_regions],
            "directions": [asdict(d) for d in self.directions],
            "trajectories": [asdict(t) for t in self.trajectories],
        }

    def get_next_direction(self) -> DirectionStatus | None:
        """取得下一個應探索的方向（優先級最高 + 假說數最少）。"""
        pending = [d for d in self.directions if d.status in ("pending", "exploring")]
        if not pending:
            return None
        # 按優先級排序，同優先級取假說數最少的
        def _sort_key(d: DirectionStatus) -> tuple[int, int]:
            try:
                p = int(str(d.priority).lstrip("P"))
            except (ValueError, TypeError):
                p = 99
            try:
                h = int(d.hypothesis_count)
            except (ValueError, TypeError):
                h = 0
            return (p, h)
        pending.sort(key=_sort_key)
        return pending[0]

    def is_forbidden(self, factor_name: str) -> bool:
        """檢查因子是否在禁區。"""
        for region in self.forbidden_regions:
            if factor_name in region.factor_patterns:
                return True
        return False

    def add_trajectory(self, trajectory: ResearchTrajectory) -> None:
        """記錄研究軌跡。"""
        self.trajectories.append(trajectory)
        self.total_rounds += 1
        if trajectory.passed:
            self.total_pass += 1
            if trajectory.fitness > self.best_fitness:
                self.best_fitness = trajectory.fitness
        else:
            self.total_fail += 1

        # 更新方向統計
        direction_name = trajectory.hypothesis.get("direction", "")
        for d in self.directions:
            if d.name == direction_name:
                d.hypothesis_count += 1
                if trajectory.passed:
                    d.pass_count += 1
                    d.best_icir = max(d.best_icir, trajectory.eval_results.get("best_icir", 0))
                    if d.status == "pending":
                        d.status = "exploring"
                break

    def add_forbidden(self, name: str, reason: str, patterns: list[str], evidence: str = "") -> None:
        """新增禁區。"""
        self.forbidden_regions.append(ForbiddenRegion(
            name=name, reason=reason, factor_patterns=patterns, evidence=evidence,
        ))

    def add_success(self, pattern: SuccessPattern) -> None:
        """新增成功模式。"""
        self.success_patterns.append(pattern)
