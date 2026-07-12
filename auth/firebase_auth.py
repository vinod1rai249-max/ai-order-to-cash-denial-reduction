import os
import logging
import firebase_admin
from firebase_admin import credentials, auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK idempotently
if not firebase_admin._apps:
    try:
        logger.info("Initializing Firebase Admin SDK...")
        firebase_admin.initialize_app()
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin: {e}")
        # In a local development environment, fallback if credentials are not set
        # but initialize_app() without arguments uses default application credentials.

def verify_firebase_token(token: str) -> dict:
    """
    Verifies Firebase ID token.
    Raises ValueError on invalid/expired token.
    """
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        logger.error(f"Firebase token verification failed: {e}")
        raise ValueError(f"Invalid or expired Firebase ID token: {str(e)}")
