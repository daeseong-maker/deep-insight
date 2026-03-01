"""
Cognito JWT Authentication — FastAPI dependency for admin routes.

Validates JWT tokens from HTTP-only cookies against Cognito JWKS public keys.
Used as a dependency on all /admin/* routes (except login/change-password).

Environment variables:
  COGNITO_USER_POOL_ID: Cognito User Pool ID (e.g., us-west-2_XXXXXXXXX)
  COGNITO_CLIENT_ID: Cognito App Client ID
"""

import json
import logging
import os
import time
import urllib.request

import jwt
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")

# JWKS cache (loaded once, refreshed on key miss)
_jwks_cache: dict = {}
_jwks_last_fetched: float = 0
_JWKS_CACHE_TTL = 3600  # 1 hour


def _get_jwks_url() -> str:
    """Build the JWKS URL from the User Pool ID."""
    region = COGNITO_USER_POOL_ID.split("_")[0] if "_" in COGNITO_USER_POOL_ID else "us-west-2"
    return f"https://cognito-idp.{region}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"


def _fetch_jwks() -> dict:
    """Fetch JWKS from Cognito and return as {kid: key} mapping."""
    global _jwks_cache, _jwks_last_fetched

    now = time.time()
    if _jwks_cache and (now - _jwks_last_fetched) < _JWKS_CACHE_TTL:
        return _jwks_cache

    try:
        url = _get_jwks_url()
        with urllib.request.urlopen(url, timeout=5) as resp:
            jwks = json.loads(resp.read().decode("utf-8"))

        _jwks_cache = {}
        for key in jwks.get("keys", []):
            kid = key.get("kid")
            if kid:
                _jwks_cache[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))

        _jwks_last_fetched = now
        logger.info(f"JWKS fetched: {len(_jwks_cache)} keys cached")
    except Exception as e:
        logger.error(f"Failed to fetch JWKS: {e}")
        if not _jwks_cache:
            raise HTTPException(status_code=503, detail="Auth service unavailable")

    return _jwks_cache


def _get_signing_key(token: str):
    """Extract the signing key for a token from JWKS cache."""
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Invalid token header")

    jwks = _fetch_jwks()
    key = jwks.get(kid)

    if not key:
        # Key not found — force refresh and retry once
        global _jwks_last_fetched
        _jwks_last_fetched = 0
        jwks = _fetch_jwks()
        key = jwks.get(kid)

    if not key:
        raise HTTPException(status_code=401, detail="Unknown signing key")

    return key


def require_admin(request: Request) -> dict:
    """FastAPI dependency: validate JWT from cookie, return claims.

    Raises HTTPException(401) if token is missing, expired, or invalid.
    """
    if not COGNITO_USER_POOL_ID or not COGNITO_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Cognito not configured")

    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        key = _get_signing_key(token)
        region = COGNITO_USER_POOL_ID.split("_")[0] if "_" in COGNITO_USER_POOL_ID else "us-west-2"
        issuer = f"https://cognito-idp.{region}.amazonaws.com/{COGNITO_USER_POOL_ID}"

        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=COGNITO_CLIENT_ID,
        )
        return claims

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
