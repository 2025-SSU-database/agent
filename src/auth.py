from jose import JWTError, jwt, jwk
import requests
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from dotenv import load_dotenv

load_dotenv()

# caching jwks
_jwks = None

COGNITO_REGION = os.getenv("COGNITO_REGION")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
COGNITO_ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"

security = HTTPBearer(auto_error=False)

def get_jwks():
    global _jwks
    if _jwks is None:
        jwks_url = COGNITO_ISSUER + "/.well-known/jwks.json"
        _jwks = requests.get(jwks_url).json()
    return _jwks

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    
    try:
        unverified_header = jwt.get_unverified_header(token)
        
        jwks = get_jwks()
        rsa_key = next(
            (key for key in jwks["keys"] if key["kid"] == unverified_header["kid"]),
            None
        )
        
        if not rsa_key:
            raise HTTPException(status_code=401, detail="Public key not found")
        
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=COGNITO_CLIENT_ID,
            issuer=COGNITO_ISSUER
        )
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )