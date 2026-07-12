import os
import logging
import time
from dotenv import load_dotenv
load_dotenv()
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth.firebase_auth import verify_firebase_token

try:
    from google.cloud import firestore
except ImportError:  # pragma: no cover - exercised in local/demo environments
    firestore = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

security = HTTPBearer()
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    FastAPI dependency to authenticate requests using Firebase ID token.
    Extracts the user identity and fetches their role from Firestore.
    """
    token = credentials.credentials
    if token.startswith("mock-token-") or os.environ.get("USE_MOCK_AUTH") == "true":
        role = "admin"
        return {
            "uid": "mock-uid",
            "email": "admin@hospital.org",
            "role": role,
            "display_name": "OTC Administrator"
        }

    if not GCP_PROJECT_ID or firestore is None:
        logger.warning("GCP_PROJECT_ID not configured or Firestore client unavailable; using local admin fallback for authentication")
        return {
            "uid": "local-dev-user",
            "email": "local-dev@hospital.org",
            "role": "admin",
            "display_name": "Local Dev Administrator"
        }

    try:
        decoded_token = verify_firebase_token(token)
        uid = decoded_token.get("uid")
        email = decoded_token.get("email")
        
        # Lookup user role in Firestore
        db = firestore.Client(project=GCP_PROJECT_ID)
        user_doc = db.collection("users").document(uid).get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            role = user_data.get("role", "admin")  # Default to admin for POC
            display_name = user_data.get("display_name", email or uid)
        else:
            role = "admin"
            display_name = email or uid
            
        return {
            "uid": uid,
            "email": email,
            "role": role,
            "display_name": display_name
        }
    except Exception as e:
        logger.error(f"Authentication dependency error: {e}")
        # Always return 401 with trace identifier details
        trace_id = f"TRC-AUTH-ERR-{int(time.time())}"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Authentication failed",
                "message": str(e),
                "trace_id": trace_id
            }
        )

def require_role(allowed_roles: list[str]):
    """Gating mechanism to restrict route access by role."""
    def dependency(user: dict = Depends(get_current_user)):
        user_role = user.get("role")
        if user_role != "admin" and user_role not in allowed_roles:
            logger.warning(f"Access Denied: User role '{user_role}' not in permitted {allowed_roles}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Insufficient permissions to access this endpoint."
            )
        return user
    return dependency
