"""
Xray Cloud API authentication.
Xray Cloud usa client_id + client_secret para obtener un JWT.
"""
import time
import requests


_cached_token: dict = {}


def get_xray_token(client_id: str, client_secret: str, base_url: str) -> str:
    """Devuelve un JWT válido para Xray Cloud API."""
    if _cached_token.get("token") and time.time() < _cached_token.get("expires_at", 0) - 60:
        return _cached_token["token"]

    resp = requests.post(
        f"{base_url}/authenticate",
        json={"client_id": client_id, "client_secret": client_secret},
    )
    resp.raise_for_status()
    token = resp.text.strip('"')
    _cached_token["token"] = token
    _cached_token["expires_at"] = time.time() + 3600
    print("[Xray Auth] Token JWT obtenido correctamente.")
    return token
