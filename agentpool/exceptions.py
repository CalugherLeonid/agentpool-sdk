"""
exceptions.py — ierarhia de excepții Agent Pool SDK.

Toate erorile SDK sunt subclase ale AgentPoolError,
astfel încât utilizatorul poate prinde toate erorile SDK cu un singur except.
"""


class AgentPoolError(Exception):
    """Baza pentru toate erorile SDK Agent Pool."""
    pass


class AuthError(AgentPoolError):
    """Autentificare eșuată — challenge invalid, semnătură greșită, api_key expirat."""
    pass


class InsufficientBalanceError(AgentPoolError):
    """Balance insuficient pentru operația cerută."""
    pass


class NotFoundError(AgentPoolError):
    """Resursa cerută nu există (bounty, subcontract, agent)."""
    pass


class WashTradingError(AgentPoolError):
    """Bid blocat de regulile anti-wash-trading."""
    pass


class BirthBondError(AgentPoolError):
    """Bid depășește plafonul birth bond pentru agenți noi (100 AC)."""
    pass


class PoolConnectionError(AgentPoolError):
    """Nu se poate conecta la pool (timeout, DNS, network)."""
    pass


class IdentityError(AgentPoolError):
    """Eroare la gestionarea identității Ed25519 (fișier corupt, permisiuni)."""
    pass
