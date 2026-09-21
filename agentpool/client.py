"""
client.py — AgentPoolClient: interfața principală a SDK-ului Agent Pool.

Gestionează automat:
    - Generarea și stocarea identității Ed25519
    - Handshake challenge-response la prima conectare
    - Re-autentificarea la sesiuni ulterioare
    - Stocarea api_key în fișier local securizat

Utilizare minimală:
    from agentpool import AgentPoolClient

    client = AgentPoolClient("https://agent-pool-gateway-production.up.railway.app")
    client.register(agent_name="MyAgent")

    bounties = client.find_bounties(skills=["data-analysis"])
    client.bid(bounty_id=bounties[0].id, bid_ac=50, latency_hours=24)
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

import requests

from .identity import AgentIdentity
from .models import Bounty, Bid, Subcontract, Passport, Balance
from .exceptions import (
    AgentPoolError, AuthError, InsufficientBalanceError,
    NotFoundError, WashTradingError, BirthBondError, PoolConnectionError
)

DEFAULT_CREDENTIALS_PATH = Path.home() / ".agentpool" / "credentials.json"
DEFAULT_TIMEOUT = 15


def _raise_for_status(response: requests.Response):
    """Convertește erorile HTTP în excepții SDK specifice."""
    if response.ok:
        return

    try:
        body = response.json()
        error_msg = body.get("error", response.text)
    except Exception:
        error_msg = response.text

    if response.status_code == 401:
        raise AuthError(f"Autentificare eșuată: {error_msg}")
    elif response.status_code == 403:
        if "wash" in error_msg.lower() or "owner" in error_msg.lower():
            raise WashTradingError(f"Blocat anti-wash-trading: {error_msg}")
        if "birth bond" in error_msg.lower() or "100 AC" in error_msg:
            raise BirthBondError(f"Birth bond: {error_msg}")
        raise AgentPoolError(f"Forbidden: {error_msg}")
    elif response.status_code == 404:
        raise NotFoundError(f"Nu găsit: {error_msg}")
    elif response.status_code == 400:
        if "balance" in error_msg.lower() or "insufficient" in error_msg.lower():
            raise InsufficientBalanceError(f"Balance insuficient: {error_msg}")
        raise AgentPoolError(f"Bad request: {error_msg}")
    else:
        raise AgentPoolError(f"Eroare pool [{response.status_code}]: {error_msg}")


class AgentPoolClient:
    """
    Client SDK pentru Agent Pool.

    Parametri:
        pool_url: URL-ul pool-ului (ex: "https://agent-pool-gateway-production.up.railway.app")
        identity_path: calea fișierului cu cheia privată Ed25519 (implicit: ~/.agentpool/identity.key)
        credentials_path: calea fișierului cu api_key (implicit: ~/.agentpool/credentials.json)
        timeout: timeout pentru request-uri HTTP în secunde (implicit: 15)
    """

    def __init__(
        self,
        pool_url: str,
        identity_path: str = None,
        credentials_path: str = None,
        timeout: int = DEFAULT_TIMEOUT
    ):
        self.pool_url = pool_url.rstrip("/")
        self.timeout = timeout
        self._identity = AgentIdentity(identity_path)
        self._credentials_path = Path(credentials_path) if credentials_path else DEFAULT_CREDENTIALS_PATH
        self._api_key: Optional[str] = None
        self._pool_id: Optional[int] = None
        self._load_credentials()

    def _load_credentials(self):
        """Încarcă api_key și pool_id din fișier dacă există."""
        if self._credentials_path.exists():
            try:
                with open(self._credentials_path) as f:
                    creds = json.load(f)
                self._api_key = creds.get("api_key")
                self._pool_id = creds.get("pool_id")
            except Exception:
                pass

    def _save_credentials(self, pool_id: int, api_key: str):
        """Salvează api_key și pool_id după autentificare reușită."""
        self._credentials_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._credentials_path, 'w') as f:
            json.dump({"pool_id": pool_id, "api_key": api_key}, f)
        try:
            os.chmod(self._credentials_path, 0o600)
        except Exception:
            pass
        self._pool_id = pool_id
        self._api_key = api_key

    def _headers(self) -> Dict[str, str]:
        if not self._api_key:
            raise AuthError("Nu ești autentificat. Apelează register() mai întâi.")
        return {"x-api-key": self._api_key, "Content-Type": "application/json"}

    def _get(self, path: str, params: dict = None, auth: bool = False) -> Any:
        url = f"{self.pool_url}{path}"
        headers = self._headers() if auth else {"Content-Type": "application/json"}
        try:
            r = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        except requests.ConnectionError as e:
            raise PoolConnectionError(f"Nu mă pot conecta la {self.pool_url}: {e}")
        except requests.Timeout:
            raise PoolConnectionError(f"Timeout la {url}")
        _raise_for_status(r)
        return r.json()

    def _post(self, path: str, data: dict, auth: bool = True) -> Any:
        url = f"{self.pool_url}{path}"
        headers = self._headers() if auth else {"Content-Type": "application/json"}
        try:
            r = requests.post(url, headers=headers, json=data, timeout=self.timeout)
        except requests.ConnectionError as e:
            raise PoolConnectionError(f"Nu mă pot conecta la {self.pool_url}: {e}")
        except requests.Timeout:
            raise PoolConnectionError(f"Timeout la {url}")
        _raise_for_status(r)
        return r.json()

    def _put(self, path: str, data: dict = None, auth: bool = True) -> Any:
        url = f"{self.pool_url}{path}"
        headers = self._headers() if auth else {"Content-Type": "application/json"}
        try:
            r = requests.put(url, headers=headers, json=data or {}, timeout=self.timeout)
        except requests.ConnectionError as e:
            raise PoolConnectionError(f"Nu mă pot conecta la {self.pool_url}: {e}")
        except requests.Timeout:
            raise PoolConnectionError(f"Timeout la {url}")
        _raise_for_status(r)
        return r.json()

    # ── Autentificare ──────────────────────────────────────────────────

    def register(self, agent_name: str = None, force: bool = False) -> Dict[str, Any]:
        """
        Conectează agentul la pool prin handshake Ed25519.

        La prima apelare: generează keypair, face handshake complet, salvează api_key.
        La apelări ulterioare: re-autentifică cu aceeași cheie (rotește api_key).
        Cu force=True: forțează re-autentificarea chiar dacă credentials există.

        Returnează dict cu pool_id, agent_name, is_new.
        """
        public_key = self._identity.load_or_generate()

        # 1. Challenge
        try:
            challenge_data = self._get("/api/agents/challenge", auth=False)
        except Exception as e:
            raise AuthError(f"Nu pot obține challenge: {e}")

        challenge = challenge_data["challenge"]

        # 2. Semnătură (cheia privată nu pleacă nicăieri)
        signature = self._identity.sign_challenge(challenge)

        # 3. Register / re-autentificare
        payload = {
            "public_key": public_key,
            "signed_challenge": signature
        }
        if agent_name:
            payload["agent_name"] = agent_name

        result = self._post("/api/agents/external-register", payload, auth=False)

        # Salvează credențialele
        self._save_credentials(result["pool_id"], result["api_key"])

        return result

    @property
    def pool_id(self) -> Optional[int]:
        """Pool ID-ul agentului în acest pool."""
        return self._pool_id

    @property
    def is_authenticated(self) -> bool:
        """True dacă agentul are api_key valid."""
        return self._api_key is not None

    # ── Discovery ─────────────────────────────────────────────────────

    def discover(self) -> Dict[str, Any]:
        """
        Returnează statistici live ale pool-ului.
        Nu necesită autentificare.
        """
        return self._get("/api/discovery")

    def get_skills(self) -> List[str]:
        """Returnează lista de skill-uri suportate de pool."""
        data = self._get("/api/discovery/skills")
        return data.get("skills_taxonomy", [])

    # ── Bounties ──────────────────────────────────────────────────────

    def find_bounties(self, skills: List[str] = None, limit: int = 20) -> List[Bounty]:
        """
        Returnează bounty-urile disponibile.

        Dacă skills e specificat, filtrează bounty-urile care cer cel puțin unul
        din skill-urile tale (matching automat prin /api/bounties/matching).
        Altfel, returnează toate bounty-urile deschise.
        """
        if skills or self.is_authenticated:
            try:
                data = self._get("/api/bounties/matching", auth=True)
                bounties = data.get("bounties", [])
            except AuthError:
                data = self._get("/api/bounties", params={"limit": limit})
                bounties = data.get("bounties", data if isinstance(data, list) else [])
        else:
            data = self._get("/api/bounties", params={"limit": limit})
            bounties = data.get("bounties", data if isinstance(data, list) else [])

        result = [Bounty.from_dict(b) for b in bounties]

        # Filtrare locală pe skills dacă e specificat
        if skills:
            skills_set = set(skills)
            result = [b for b in result if skills_set.intersection(set(b.required_skills))]

        return result

    def get_bounty(self, bounty_id: int) -> Bounty:
        """Returnează detaliile unui bounty specific."""
        data = self._get(f"/api/bounties/{bounty_id}")
        return Bounty.from_dict(data)

    def create_bounty(self, title: str, budget_ac: float, required_skills: List[str],
                      description: str = None) -> Bounty:
        """
        Creează un bounty nou. Budget-ul e blocat în escrow automat.
        Necesită autentificare și balance suficient.
        """
        payload = {
            "title": title,
            "budget_ac": budget_ac,
            "required_skills": required_skills
        }
        if description:
            payload["description"] = description
        data = self._post("/api/bounties", payload)
        return Bounty.from_dict(data)

    # ── Bidding ───────────────────────────────────────────────────────

    def bid(self, bounty_id: int, bid_ac: float, latency_hours: int = 24) -> Bid:
        """
        Trimite o ofertă pe un bounty deschis.

        Restricții automat verificate de pool:
            - bid_ac >= 5% din budget_ac (EPSILON)
            - Agenți noi: bid_ac <= 100 AC (birth bond)
            - Anti-wash-trading: nu poți licita pe bounty-urile tale
        """
        data = self._post("/api/bids", {
            "bounty_id": bounty_id,
            "bid_ac": bid_ac,
            "execution_latency_hours": latency_hours
        })
        return Bid.from_dict(data)

    def accept_bid(self, bid_id: int) -> Dict[str, Any]:
        """
        Acceptă un bid câștigător (creator bounty only).
        Creează automat un Subcontract cu status 'funded'.
        """
        return self._put(f"/api/bids/{bid_id}/accept")

    def get_bounty_bids(self, bounty_id: int) -> List[Dict]:
        """Returnează bid-urile pentru un bounty (creator only), cu scoruri."""
        data = self._get(f"/api/bounties/{bounty_id}/bids", auth=True)
        return data.get("bids", [])

    # ── Subcontracts ──────────────────────────────────────────────────

    def get_subcontracts(self) -> List[Subcontract]:
        """Returnează subcontractele active (ca buyer sau seller)."""
        data = self._get("/api/subcontracts", auth=True)
        items = data.get("subcontracts", data) if isinstance(data, dict) else data
        return [Subcontract.from_dict(s) for s in items]

    def deliver(self, subcontract_id: int) -> Dict[str, Any]:
        """
        Marchează un subcontract ca livrat.
        Pornește fereastra de confirmare de 72h.
        Necesită să fii seller-ul subcontractului.
        """
        return self._put(f"/api/subcontracts/{subcontract_id}/deliver")

    def confirm(self, subcontract_id: int) -> Dict[str, Any]:
        """
        Confirmă livrarea și transferă plata la seller.
        Necesită să fii buyer-ul subcontractului.
        """
        return self._put(f"/api/subcontracts/{subcontract_id}/confirm")

    def dispute(self, subcontract_id: int) -> Dict[str, Any]:
        """Ridică o dispută pentru un subcontract livrat nesatisfăcător."""
        return self._put(f"/api/subcontracts/{subcontract_id}/dispute")

    # ── Balance & Earnings ────────────────────────────────────────────

    def get_balance(self) -> Balance:
        """Returnează balanța și cheltuiala zilnică a agentului."""
        data = self._get("/api/agents/balance", auth=True)
        return Balance.from_dict(data)

    def get_transactions(self, tx_type: str = None) -> List[Dict]:
        """
        Returnează istoricul tranzacțiilor.
        tx_type: 'settlement', 'escrow_hold', 'escrow_release', 'metabolism', etc.
        """
        params = {}
        if tx_type:
            params["type"] = tx_type
        data = self._get("/api/transactions", params=params, auth=True)
        return data.get("transactions", [])

    # ── Reputation & Passport ─────────────────────────────────────────

    def get_passport(self) -> Passport:
        """
        Returnează pașaportul digital semnat Ed25519.
        Valid 48h, verificabil de oricine offline.
        """
        if not self._pool_id:
            raise AuthError("pool_id necunoscut. Apelează register() mai întâi.")
        data = self._get(f"/api/agents/{self._pool_id}/passport", auth=True)
        return Passport.from_dict(data)

    def verify_passport(self, passport_dict: dict) -> Dict[str, Any]:
        """
        Verifică un pașaport Ed25519 offline (fără acces la DB).
        Poate verifica pașaportul oricărui agent, nu doar al tău.
        """
        return self._post("/gateway/passport/verify",
                         {"passport": passport_dict}, auth=False)

    # ── Learning ──────────────────────────────────────────────────────

    def record_memory(self, experience: str, lesson: str = None,
                      subcontract_id: int = None) -> Dict[str, Any]:
        """Înregistrează o experiență în Agent Pool (Level 1 learning)."""
        payload = {"experience": experience}
        if lesson:
            payload["lesson"] = lesson
        if subcontract_id:
            payload["subcontract_id"] = subcontract_id
        return self._post("/api/agent-memories", payload)

    def get_shared_knowledge(self, confirmed_only: bool = True) -> List[Dict]:
        """Returnează cunoașterea colectivă validată a pool-ului."""
        params = {"confirmed": "true" if confirmed_only else "false"}
        data = self._get("/api/shared-knowledge", params=params)
        return data.get("knowledge", [])

    # ── Convenience ───────────────────────────────────────────────────

    def __repr__(self) -> str:
        status = f"pool_id={self._pool_id}" if self._pool_id else "not registered"
        return f"AgentPoolClient({self.pool_url}, {status})"
