"""Digital signatures for evidence records (Phase 5.2).

Every completed analysis is signed with the server's Ed25519 private key so a
court/reviewer can later prove the stored record was not altered. The key is
auto-generated on first use at SIGNING_KEY_PATH (default: backend/keys/
server_signing_key.pem) — that folder must stay out of git.

Canonicalization: the payload dict is serialized as compact JSON with sorted
keys (UTF-8); those exact bytes are signed. `verify_record()` rebuilds the same
bytes from the stored `signed_payload`, so any change to the record breaks the
signature.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_private_key: Ed25519PrivateKey | None = None


def _key_path() -> Path:
    return Path(os.getenv("SIGNING_KEY_PATH", "keys/server_signing_key.pem"))


def _load_or_create_key() -> Ed25519PrivateKey:
    global _private_key
    if _private_key is not None:
        return _private_key

    path = _key_path()
    if path.exists():
        _private_key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        _private_key = Ed25519PrivateKey.generate()
        path.write_bytes(
            _private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    return _private_key


def canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def public_key_hex() -> str:
    pub = _load_or_create_key().public_key()
    return pub.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    ).hex()


def key_fingerprint() -> str:
    """SHA-256 of the raw 32-byte Ed25519 public key."""
    return hashlib.sha256(bytes.fromhex(public_key_hex())).hexdigest()


def sign_record(payload: dict) -> dict:
    """Sign a record payload. Returns signature metadata to persist alongside it."""
    key = _load_or_create_key()
    signature = key.sign(canonical_bytes(payload))
    return {
        "algorithm": "Ed25519",
        "signature": signature.hex(),
        "public_key": public_key_hex(),
        "key_fingerprint": key_fingerprint(),
        "signed_at": datetime.now(timezone.utc).isoformat(),
    }


def verify_record(payload: dict, signature_hex: str, public_key_hex_str: str | None = None) -> bool:
    """Verify a signature over a payload. Uses the server key if none given."""
    try:
        if public_key_hex_str:
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex_str))
        else:
            pub = _load_or_create_key().public_key()
        pub.verify(bytes.fromhex(signature_hex), canonical_bytes(payload))
        return True
    except Exception:
        return False
