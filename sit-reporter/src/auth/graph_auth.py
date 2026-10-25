"""
Microsoft Graph API authentication via MSAL.
Usa device_code_flow para que el usuario autentique con su cuenta Accenture (SSO).
El token se cachea en .graph_token_cache.bin.
"""
import msal

SCOPES = ["Mail.Send", "User.Read"]
CACHE_FILE = ".graph_token_cache.bin"


def _load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    try:
        with open(CACHE_FILE, "r") as f:
            cache.deserialize(f.read())
    except FileNotFoundError:
        pass
    return cache


def _save_cache(cache: msal.SerializableTokenCache):
    if cache.has_state_changed:
        with open(CACHE_FILE, "w") as f:
            f.write(cache.serialize())


def get_graph_token(tenant_id: str, client_id: str) -> str:
    """Devuelve un access_token válido para Microsoft Graph. Usa SSO Accenture."""
    cache = _load_cache()
    app = msal.PublicClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
    )

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            _save_cache(cache)
            return result["access_token"]

    # Device code flow: el usuario va a aka.ms/devicelogin con un codigo
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise ValueError(f"Error iniciando device flow: {flow.get('error_description')}")

    print("\n" + "="*60)
    print("[Graph Auth] Para enviar emails con tu cuenta Accenture:")
    print(f"  1. Ve a: {flow['verification_uri']}")
    print(f"  2. Introduce el codigo: {flow['user_code']}")
    print("="*60 + "\n")

    result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise ValueError(f"Error de autenticacion Graph: {result.get('error_description')}")

    _save_cache(cache)
    print("[Graph Auth] Autenticacion con Microsoft completada.\n")
    return result["access_token"]
