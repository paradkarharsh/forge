from authlib.integrations.httpx_client import AsyncOAuth2Client
from forge_api.infrastructure.settings import Settings
PROVIDERS={"google":("https://accounts.google.com/o/oauth2/v2/auth","https://oauth2.googleapis.com/token","https://www.googleapis.com/oauth2/v3/userinfo"),"github":("https://github.com/login/oauth/authorize","https://github.com/login/oauth/access_token","https://api.github.com/user")}
def provider_config(name: str, settings: Settings) -> tuple[str,str,str,str,str]:
    if name=="google": client_id,secret=settings.oauth_google_client_id,settings.oauth_google_client_secret
    elif name=="github": client_id,secret=settings.oauth_github_client_id,settings.oauth_github_client_secret
    else: raise ValueError("unsupported OAuth provider")
    if not client_id or not secret: raise RuntimeError(f"{name} OAuth is not configured")
    return (*PROVIDERS[name],client_id,secret.get_secret_value())
async def exchange_code(name: str, code: str, redirect_uri: str, settings: Settings) -> dict:
    authorization_url,token_url,userinfo_url,client_id,secret=provider_config(name,settings)
    async with AsyncOAuth2Client(client_id,secret) as client:
        token=await client.fetch_token(token_url,code=code,redirect_uri=redirect_uri)
        response=await client.get(userinfo_url,token=token)
        response.raise_for_status()
        return response.json()
