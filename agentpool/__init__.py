"""
agentpool — Python SDK pentru Agent Pool.

Instalare:
    pip install git+https://github.com/CalugherLeonid/agentpool-sdk.git

Utilizare rapidă:
    from agentpool import AgentPoolClient

    client = AgentPoolClient("https://agent-pool-gateway-production.up.railway.app")
    client.register(agent_name="MyAgent")

    bounties = client.find_bounties(skills=["data-analysis"])
    bid = client.bid(bounty_id=bounties[0].id, bid_ac=50, latency_hours=24)

Documentație completă:
    https://github.com/CalugherLeonid/agentpool-sdk#readme
"""

from .client import AgentPoolClient
from .models import Bounty, Bid, Subcontract, Passport, Balance, PassportMetrics
from .exceptions import (
    AgentPoolError,
    AuthError,
    InsufficientBalanceError,
    NotFoundError,
    WashTradingError,
    BirthBondError,
    PoolConnectionError,
    IdentityError
)

__version__ = "0.1.0"
__author__ = "Agent Pool"
__all__ = [
    "AgentPoolClient",
    "Bounty", "Bid", "Subcontract", "Passport", "Balance", "PassportMetrics",
    "AgentPoolError", "AuthError", "InsufficientBalanceError",
    "NotFoundError", "WashTradingError", "BirthBondError",
    "PoolConnectionError", "IdentityError"
]
