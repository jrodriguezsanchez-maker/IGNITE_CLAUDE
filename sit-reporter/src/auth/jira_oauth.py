"""
JIRA Cloud OAuth 2.0 (3-Legged OAuth) authentication.
Abre el navegador para que el usuario autorice con su cuenta Accenture (SSO federado).
El token se guarda localmente en .jira_token.json para reutilizarlo.
"""
import json
import os
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse, urlencode
import requests


TOKEN_FILE = ".jira_token.json"
AUTH_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
SCOPES = "read:jira-work read:jira-user offline_access"
AUDIENCE = "api.atlassian.com"


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code = None
    state = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        _OAuthCallbackHandler.auth_code = params.get("code", [None])[0]
        _OAuthCallbackHandler.state = params.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Autorizacion completada. Puedes cerrar esta ventana.</h2>")

    def log_message(self, *args):
        pass


def _run_callback_server(port: int):
    server = HTTPServer(("localhost", port), _OAuthCallbackHandler)
    server.handle_request()


def _load_token() -> dict | None:
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return None


def _save_token(token: dict):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f)


def _refresh_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    resp = requests.post(TOKEN_URL, json={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    })
    resp.raise_for_status()
    token = resp.json()
    token["expires_at"] = time.time() + token.get("expires_in", 3600)
    _save_token(token)
    return token


def get_jira_token(client_id: str, client_secret: str, redirect_uri: str) -> str:
    """Devuelve un access_token válido para JIRA Cloud. Abre el navegador si es necesario."""
    token = _load_token()

    if token:
        if time.time() < token.get("expires_at", 0) - 60:
            return token["access_token"]
        if "refresh_token" in token:
            print("[JIRA Auth] Renovando token...")
            token = _refresh_token(client_id, client_secret, token["refresh_token"])
            return token["access_token"]

    # First-time auth: open browser
    port = int(redirect_uri.split(":")[-1].split("/")[0])
    state = os.urandom(16).hex()

    auth_params = urlencode({
        "audience": AUDIENCE,
        "client_id": client_id,
        "scope": SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    })
    auth_full_url = f"{AUTH_URL}?{auth_params}"

    thread = Thread(target=_run_callback_server, args=(port,), daemon=True)
    thread.start()

    print(f"\n[JIRA Auth] Abriendo navegador para autorizar con tu cuenta Accenture...")
    print(f"  URL manual: {auth_full_url}\n")
    webbrowser.open(auth_full_url)

    thread.join(timeout=120)

    if not _OAuthCallbackHandler.auth_code:
        raise TimeoutError("No se recibio el codigo de autorizacion en 2 minutos.")

    resp = requests.post(TOKEN_URL, json={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": _OAuthCallbackHandler.auth_code,
        "redirect_uri": redirect_uri,
    })
    resp.raise_for_status()
    token = resp.json()
    token["expires_at"] = time.time() + token.get("expires_in", 3600)
    _save_token(token)
    print("[JIRA Auth] Autenticacion completada y token guardado.\n")
    return token["access_token"]
