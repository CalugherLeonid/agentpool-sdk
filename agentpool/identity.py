"""
identity.py — gestionarea identității Ed25519 pentru SDK.

Principiu fundamental:
    Cheia privată rămâne LOCAL, pe mașina agentului.
    Nu pleacă niciodată din process — nici în log-uri, nici în requests.
    Agent Pool stochează DOAR cheia publică (external_public_key).

Stocare:
    Implicit: ~/.agentpool/identity.key (user home directory)
    Custom: orice path specificat la inițializare
"""

import os
import base64
from pathlib import Path
from .exceptions import IdentityError

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption
    )
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


DEFAULT_KEY_PATH = Path.home() / ".agentpool" / "identity.key"


class AgentIdentity:
    """
    Identitatea criptografică Ed25519 a agentului.

    Generată o singură dată și reutilizată la fiecare sesiune.
    Cheia privată e stocată local — nu e transmisă niciodată.
    """

    def __init__(self, key_path: str = None):
        if not CRYPTO_AVAILABLE:
            raise IdentityError(
                "Pachetul 'cryptography' nu este instalat. "
                "Rulează: pip install agentpool[crypto]"
            )
        self._key_path = Path(key_path) if key_path else DEFAULT_KEY_PATH
        self._private_key = None
        self._public_key_hex = None

    def load_or_generate(self) -> str:
        """
        Încarcă cheia privată din fișier sau generează una nouă.
        Returnează public_key_hex (identitatea globală a agentului).
        """
        if self._key_path.exists():
            try:
                with open(self._key_path, 'rb') as f:
                    raw = f.read()
                self._private_key = Ed25519PrivateKey.from_private_bytes(raw)
            except Exception as e:
                raise IdentityError(f"Nu pot citi cheia de identitate: {e}")
        else:
            # Generează cheie nouă
            self._key_path.parent.mkdir(parents=True, exist_ok=True)
            self._private_key = Ed25519PrivateKey.generate()
            raw = self._private_key.private_bytes(
                Encoding.Raw, PrivateFormat.Raw, NoEncryption()
            )
            try:
                with open(self._key_path, 'wb') as f:
                    f.write(raw)
                # Permisiuni restrictive pe Unix (ignorat pe Windows)
                try:
                    os.chmod(self._key_path, 0o600)
                except Exception:
                    pass
            except Exception as e:
                raise IdentityError(f"Nu pot salva cheia de identitate: {e}")

        pub_raw = self._private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        self._public_key_hex = pub_raw.hex()
        return self._public_key_hex

    @property
    def public_key_hex(self) -> str:
        if not self._public_key_hex:
            raise IdentityError("Identitatea nu e încărcată. Apelează load_or_generate() mai întâi.")
        return self._public_key_hex

    @property
    def key_path(self) -> Path:
        return self._key_path

    def sign_challenge(self, challenge: str) -> str:
        """
        Semnează un challenge cu cheia privată.
        Returnează semnătura în format base64.
        Cheia privată NU părăsește această metodă.
        """
        if not self._private_key:
            raise IdentityError("Identitatea nu e încărcată.")
        signature = self._private_key.sign(challenge.encode('utf-8'))
        return base64.b64encode(signature).decode('utf-8')

    def exists(self) -> bool:
        """Verifică dacă există deja o identitate salvată."""
        return self._key_path.exists()
