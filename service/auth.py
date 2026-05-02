from fastapi import Depends, HTTPException, Header
from fastapi.security import OAuth2PasswordBearer
from jose import jwt

SECRET = "your-secret"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        # In a real SaaS with Clerk, you would fetch Clerk's JWKS and use RS256
        # Or if you configured Clerk to use a custom JWT template with a symmetric secret, you could use HS256.
        # This is a placeholder MVP based on the requested specification.
        # We assume the JWT contains `tenant_id` or `sub` which we can use as the tenant.
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        
        # Ensure we return a dictionary that has tenant_id
        if "tenant_id" not in payload and "sub" in payload:
            payload["tenant_id"] = payload["sub"]
            
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

def validate_api_key(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    from core.db import get_tenant_for_api_key
    tenant_id = get_tenant_for_api_key(x_api_key)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return tenant_id
