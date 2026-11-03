import os
import time
import base64
import logging
from typing import Optional, Tuple, Dict, Any
import requests
import jwt
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("made_for_nothing.mux")

MUX_TOKEN_ID = os.getenv("MUX_TOKEN_ID", "")
MUX_TOKEN_SECRET = os.getenv("MUX_TOKEN_SECRET", "")
MUX_SIGNING_KEY_ID = os.getenv("MUX_SIGNING_KEY_ID", "")
MUX_SIGNING_PRIVATE_KEY = os.getenv("MUX_SIGNING_PRIVATE_KEY", "")

MUX_API_BASE = "https://api.mux.com/video/v1"


def is_mux_configured() -> bool:
    """Returns True if Mux API and signing keys are provided."""
    return bool(MUX_TOKEN_ID and MUX_TOKEN_SECRET and MUX_SIGNING_KEY_ID and MUX_SIGNING_PRIVATE_KEY)


def _get_clean_private_key() -> str:
    """Cleans up and formats the RSA private key from environment variable."""
    key = MUX_SIGNING_PRIVATE_KEY.strip()
    if not key:
        return ""

    # If key is base64 encoded
    if not key.startswith("-----BEGIN"):
        try:
            decoded = base64.b64decode(key).decode("utf-8")
            if "BEGIN" in decoded:
                key = decoded
        except Exception:
            pass

    # Normalize escaped newlines
    if "\\n" in key:
        key = key.replace("\\n", "\n")

    return key


def _get_auth() -> Optional[Tuple[str, str]]:
    """Returns Basic Auth credentials for Mux API."""
    if not MUX_TOKEN_ID or not MUX_TOKEN_SECRET:
        return None
    return (MUX_TOKEN_ID, MUX_TOKEN_SECRET)


# =============================================================================
# MUX DIRECT UPLOAD
# =============================================================================

def create_direct_upload(cors_origin: str = "*") -> Dict[str, Any]:
    """
    Creates a Mux Direct Upload URL.
    Configured strictly with playback_policy: ["signed"] for video security.
    """
    auth = _get_auth()
    if not auth:
        logger.warning("Mux API credentials not configured. Returning mock upload data.")
        return {
            "success": False,
            "error": "MUX_TOKEN_ID or MUX_TOKEN_SECRET not configured in environment.",
            "upload_id": "mock-upload-id",
            "upload_url": ""
        }

    url = f"{MUX_API_BASE}/uploads"
    payload = {
        "cors_origin": cors_origin or "*",
        "new_asset_settings": {
            "playback_policy": ["signed"],
            "encoding_tier": "smart"
        }
    }

    try:
        response = requests.post(url, json=payload, auth=auth, timeout=15)
        response.raise_for_status()
        data = response.json().get("data", {})
        return {
            "success": True,
            "upload_id": data.get("id"),
            "upload_url": data.get("url"),
            "status": data.get("status")
        }
    except Exception as e:
        logger.error(f"Failed to create Mux direct upload: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def check_upload_status(upload_id: str) -> Dict[str, Any]:
    """
    Checks the status of a Mux Direct Upload.
    Returns upload status, and if an asset was created, the asset status and signed playback ID.
    """
    auth = _get_auth()
    if not auth:
        return {"status": "unconfigured", "error": "Mux credentials not configured."}

    url = f"{MUX_API_BASE}/uploads/{upload_id}"
    try:
        response = requests.get(url, auth=auth, timeout=15)
        response.raise_for_status()
        upload_data = response.json().get("data", {})
        upload_status = upload_data.get("status")  # 'waiting', 'asset_created', 'errored', 'cancelled'
        asset_id = upload_data.get("asset_id")

        if not asset_id:
            return {
                "status": upload_status or "waiting",
                "asset_id": None,
                "playback_id": None,
                "duration": None
            }

        # If asset is created, fetch asset details to obtain signed playback ID
        return check_asset_status(asset_id)

    except Exception as e:
        logger.error(f"Failed to check Mux upload status for {upload_id}: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def check_asset_status(asset_id: str) -> Dict[str, Any]:
    """
    Retrieves Mux Asset details, specifically extracting the signed playback ID and status.
    """
    auth = _get_auth()
    if not auth:
        return {"status": "unconfigured", "error": "Mux credentials not configured."}

    url = f"{MUX_API_BASE}/assets/{asset_id}"
    try:
        response = requests.get(url, auth=auth, timeout=15)
        response.raise_for_status()
        asset_data = response.json().get("data", {})

        asset_status = asset_data.get("status")  # 'preparing', 'ready', 'errored'
        duration = asset_data.get("duration")

        # Find signed playback ID
        playback_ids = asset_data.get("playback_ids", [])
        signed_playback_id = None
        for pb in playback_ids:
            if pb.get("policy") == "signed":
                signed_playback_id = pb.get("id")
                break

        # Fallback if policy is not marked or single playback ID
        if not signed_playback_id and playback_ids:
            signed_playback_id = playback_ids[0].get("id")

        return {
            "status": asset_status or "preparing",
            "asset_id": asset_id,
            "playback_id": signed_playback_id,
            "duration": round(float(duration)) if duration else 0
        }
    except Exception as e:
        logger.error(f"Failed to check Mux asset {asset_id}: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# =============================================================================
# SIGNED MUX PLAYBACK JWT GENERATION
# =============================================================================

def generate_playback_token(playback_id: str, expiration_seconds: int = 7200, aud: str = "v") -> Optional[str]:
    """
    Generates a secure, short-lived Mux Playback JWT signed with RS256.
    Audience claim 'v' specifies video playback, 't' thumbnail, 's' storyboard.
    """
    if not playback_id:
        return None

    private_key_pem = _get_clean_private_key()
    if not private_key_pem or not MUX_SIGNING_KEY_ID:
        logger.error("Cannot sign Mux playback token: MUX_SIGNING_KEY_ID or MUX_SIGNING_PRIVATE_KEY missing.")
        return None

    now = int(time.time())
    claims = {
        "sub": playback_id,
        "aud": aud,
        "exp": now + expiration_seconds,
        "kid": MUX_SIGNING_KEY_ID
    }

    headers = {
        "alg": "RS256",
        "typ": "JWT",
        "kid": MUX_SIGNING_KEY_ID
    }

    try:
        token = jwt.encode(
            payload=claims,
            key=private_key_pem,
            algorithm="RS256",
            headers=headers
        )
        return token
    except Exception as e:
        logger.error(f"Failed to generate Mux playback token for {playback_id} ({aud}): {e}")
        return None


def generate_all_tokens(playback_id: str, expiration_seconds: int = 7200) -> Dict[str, Optional[str]]:
    """
    Generates video (aud='v'), thumbnail (aud='t'), and storyboard (aud='s') tokens for Mux Player.
    """
    if not playback_id or not is_mux_configured():
        return {
            "playback": None,
            "thumbnail": None,
            "storyboard": None
        }

    return {
        "playback": generate_playback_token(playback_id, expiration_seconds, aud="v"),
        "thumbnail": generate_playback_token(playback_id, expiration_seconds, aud="t"),
        "storyboard": generate_playback_token(playback_id, expiration_seconds, aud="s")
    }
