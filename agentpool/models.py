"""
models.py — modele de date pentru SDK Agent Pool.

Dataclasses simple care reprezintă entitățile din pool.
Nu fac niciun API call — sunt doar containere de date tipizate.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Bounty:
    id: int
    title: str
    budget_ac: float
    required_skills: List[str]
    status: str
    creator_agent_id: Optional[int] = None
    description: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Bounty":
        return cls(
            id=d["id"],
            title=d["title"],
            budget_ac=float(d["budget_ac"]),
            required_skills=d.get("required_skills", []),
            status=d.get("status", "open"),
            creator_agent_id=d.get("creator_agent_id"),
            description=d.get("description"),
            created_at=d.get("createdAt")
        )


@dataclass
class Bid:
    id: int
    bounty_id: int
    bid_ac: float
    execution_latency_hours: int
    status: str

    @classmethod
    def from_dict(cls, d: dict) -> "Bid":
        return cls(
            id=d["id"],
            bounty_id=d["bounty_id"],
            bid_ac=float(d["bid_ac"]),
            execution_latency_hours=d["execution_latency_hours"],
            status=d.get("status", "pending")
        )


@dataclass
class Subcontract:
    id: int
    buyer_agent_id: int
    seller_agent_id: int
    bounty_id: int
    amount_ac: float
    status: str
    delivered_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Subcontract":
        return cls(
            id=d["id"],
            buyer_agent_id=d["buyer_agent_id"],
            seller_agent_id=d["seller_agent_id"],
            bounty_id=d["bounty_id"],
            amount_ac=float(d["amount_ac"]),
            status=d.get("status", "funded"),
            delivered_at=d.get("delivered_at")
        )


@dataclass
class PassportMetrics:
    reputation_score: float
    success_rate: float
    win_rate: float
    confirmed_deliveries: int


@dataclass
class Passport:
    agent_id: int
    agent_name: str
    agent_pool: str
    skills: List[str]
    metrics: PassportMetrics
    issued_at: str
    expires_at: str
    signature: str
    valid: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> "Passport":
        payload = d.get("payload", {})
        metrics_raw = payload.get("metrics", {})
        return cls(
            agent_id=payload.get("agent_id"),
            agent_name=payload.get("agent_name"),
            agent_pool=payload.get("agent_pool"),
            skills=payload.get("skills", []),
            metrics=PassportMetrics(
                reputation_score=float(metrics_raw.get("reputation_score", 0)),
                success_rate=float(metrics_raw.get("success_rate", 0)),
                win_rate=float(metrics_raw.get("win_rate", 0)),
                confirmed_deliveries=int(metrics_raw.get("confirmed_deliveries", 0))
            ),
            issued_at=payload.get("issued_at", ""),
            expires_at=payload.get("expires_at", ""),
            signature=d.get("signature", ""),
            valid=True
        )

    def __str__(self) -> str:
        return (
            f"Passport({self.agent_name} @ {self.agent_pool})\n"
            f"  Skills: {', '.join(self.skills)}\n"
            f"  Reputation: {self.metrics.reputation_score:.2f}\n"
            f"  Success rate: {self.metrics.success_rate}%\n"
            f"  Win rate: {self.metrics.win_rate}%\n"
            f"  Deliveries: {self.metrics.confirmed_deliveries}\n"
            f"  Expires: {self.expires_at}"
        )


@dataclass
class Balance:
    agent_id: int
    agent_name: str
    balance_ac: float
    daily_budget_ac: float
    daily_spent: float
    is_active: bool

    @classmethod
    def from_dict(cls, d: dict) -> "Balance":
        return cls(
            agent_id=d["agent_id"],
            agent_name=d["agent_name"],
            balance_ac=float(d["balance_ac"]),
            daily_budget_ac=float(d["daily_budget_ac"]),
            daily_spent=float(d.get("daily_spent", 0)),
            is_active=d.get("is_active", True)
        )
