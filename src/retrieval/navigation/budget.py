"""Navigation budget state from graph_navigation.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class NavigationBudgetLimits(BaseModel):
    meso_discovery_mode: str = "toc_planner"
    meso_max_hops_per_filing: int = 24
    meso_max_visits_per_filing: int = 80
    micro_max_hops_per_section: int = 12
    micro_max_visits_per_section: int = 40
    query_max_total_visits: int = 200
    max_candidates_per_proposal: int = 3
    top_sections_per_filing: int = 3


class NavigationBudgetState(BaseModel):
    limits: NavigationBudgetLimits = Field(default_factory=NavigationBudgetLimits)
    meso_hops: dict[str, int] = Field(default_factory=dict)
    meso_visits: dict[str, int] = Field(default_factory=dict)
    micro_hops: dict[str, int] = Field(default_factory=dict)
    micro_visits: dict[str, int] = Field(default_factory=dict)
    total_visits: int = 0

    def can_visit(self, stage: str, scope_key: str) -> tuple[bool, str]:
        lim = self.limits
        if self.total_visits >= lim.query_max_total_visits:
            return False, "budget_exceeded"
        if stage == "meso":
            if self.meso_hops.get(scope_key, 0) >= lim.meso_max_hops_per_filing:
                return False, "budget_exceeded"
            if self.meso_visits.get(scope_key, 0) >= lim.meso_max_visits_per_filing:
                return False, "budget_exceeded"
        elif stage == "micro":
            if self.micro_hops.get(scope_key, 0) >= lim.micro_max_hops_per_section:
                return False, "budget_exceeded"
            if self.micro_visits.get(scope_key, 0) >= lim.micro_max_visits_per_section:
                return False, "budget_exceeded"
        return True, ""

    def record_visit(self, stage: str, scope_key: str) -> None:
        self.total_visits += 1
        if stage == "meso":
            self.meso_visits[scope_key] = self.meso_visits.get(scope_key, 0) + 1
            self.meso_hops[scope_key] = self.meso_hops.get(scope_key, 0) + 1
        elif stage == "micro":
            self.micro_visits[scope_key] = self.micro_visits.get(scope_key, 0) + 1
            self.micro_hops[scope_key] = self.micro_hops.get(scope_key, 0) + 1


def load_navigation_budget(config_path: Path | None = None) -> NavigationBudgetState:
    path = config_path or Path("configs/graph_navigation.yaml")
    if not path.exists():
        return NavigationBudgetState()
    raw = yaml.safe_load(path.read_text()) or {}
    meso = raw.get("meso") or {}
    micro = raw.get("micro") or {}
    query = raw.get("query") or {}
    llm = raw.get("llm") or {}
    handoff = raw.get("handoff") or {}
    limits = NavigationBudgetLimits(
        meso_discovery_mode=str(meso.get("discovery_mode", "toc_planner")),
        meso_max_hops_per_filing=int(meso.get("max_hops_per_filing", 24)),
        meso_max_visits_per_filing=int(meso.get("max_visits_per_filing", 80)),
        micro_max_hops_per_section=int(micro.get("max_hops_per_section", 12)),
        micro_max_visits_per_section=int(micro.get("max_visits_per_section", 40)),
        query_max_total_visits=int(query.get("max_total_visits", 200)),
        max_candidates_per_proposal=int(llm.get("max_candidates_per_proposal", 3)),
        top_sections_per_filing=int(handoff.get("top_sections_per_filing", 3)),
    )
    return NavigationBudgetState(limits=limits)
