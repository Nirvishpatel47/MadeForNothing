"""
Media Router for MADE FOR NOTHING.
Streams and caches featured images and media assets stored in Cloudflare R2.
Provides browser delivery without requiring a paid custom domain or r2.dev setup.
"""
import logging
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
import botocore.exceptions
from core.config import settings
import r2_storage

logger = logging.getLogger("made_for_nothing.media")
router = APIRouter(tags=["media"])


@router.get("/media/{file_path:path}")
async def serve_media(file_path: str):
    """
    Streams media directly from Cloudflare R2 with high-performance caching headers.
    """
    clean_path = file_path.strip().lstrip("/")
    if not clean_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    if not r2_storage.is_r2_configured():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Storage not configured")

    try:
        client = r2_storage.get_r2_client()
        obj = client.get_object(Bucket=settings.R2_BUCKET_NAME, Key=clean_path)

        content_type = obj.get("ContentType") or "image/webp"
        content_length = obj.get("ContentLength")
        etag = obj.get("ETag")

        headers = {
            "Cache-Control": "public, max-age=31536000, immutable",
        }
        if etag:
            headers["ETag"] = etag
        if content_length:
            headers["Content-Length"] = str(content_length)

        return StreamingResponse(
            obj["Body"],
            media_type=content_type,
            headers=headers
        )
    except botocore.exceptions.ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
        logger.warning(f"R2 error serving media {clean_path}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching media")
    except Exception as e:
        logger.error(f"Unexpected error serving media {clean_path}: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
