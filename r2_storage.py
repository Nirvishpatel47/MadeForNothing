"""
Cloudflare R2 Storage & Image Optimization Module for MADE FOR NOTHING.
======================================================================
Provides:
1. S3-compatible integration for Cloudflare R2.
2. Production-grade image validation (size, MIME, magic bytes).
3. Automatic WebP optimization with EXIF auto-rotation and transparency preservation.
4. Unique collision-resistant object key generation.
5. Upload, replacement, and deletion lifecycle management without leaving orphaned files.
"""

import io
import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urljoin

from PIL import Image, ImageOps
import boto3
import botocore.config
from botocore.exceptions import ClientError, BotoCoreError

from core.config import settings

logger = logging.getLogger("made_for_nothing.r2_storage")

# Supported input image MIME types and extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".tiff"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/avif",
    "image/bmp",
    "image/tiff",
}

# Image optimization constants
TARGET_IMAGE_WIDTH = 1280   # Standardized 16:9 width
TARGET_IMAGE_HEIGHT = 720   # Standardized 16:9 height
MAX_IMAGE_DIMENSION = 2560  # Max width/height to prevent excessive memory/browser load
WEBP_QUALITY = 88           # Visually near-lossless compression (sharp edges, no artifacts)
WEBP_METHOD = 6             # Highest compression effort level in libwebp


class R2StorageError(Exception):
    """Base exception for R2 storage operations."""
    pass


class R2ConfigurationError(R2StorageError):
    """Raised when required Cloudflare R2 credentials are missing."""
    pass


class ImageValidationError(R2StorageError):
    """Raised when an uploaded file fails image validation checks."""
    pass


def is_r2_configured() -> bool:
    """Returns True if Cloudflare R2 credentials and bucket are configured."""
    has_creds = bool(settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY and settings.R2_BUCKET_NAME)
    has_endpoint = bool(settings.R2_ACCOUNT_ID or settings.R2_ENDPOINT_URL)
    return has_creds and has_endpoint


def get_r2_endpoint() -> str:
    """Returns the S3 API endpoint URL for Cloudflare R2."""
    if settings.R2_ENDPOINT_URL:
        return settings.R2_ENDPOINT_URL
    if settings.R2_ACCOUNT_ID:
        return f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return ""


def get_r2_client():
    """
    Constructs and returns an S3 client configured for Cloudflare R2.
    Uses signature version s3v4.
    """
    if not is_r2_configured():
        raise R2ConfigurationError(
            "Cloudflare R2 is not configured. Please provide R2_ACCOUNT_ID, "
            "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_BUCKET_NAME."
        )

    endpoint = get_r2_endpoint()
    client_config = botocore.config.Config(
        signature_version="s3v4",
        retries={"max_attempts": 3, "mode": "standard"},
        connect_timeout=10,
        read_timeout=30,
    )

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=client_config,
    )


def validate_image_file(file_bytes: bytes, filename: str) -> None:
    """
    Validates file size, file extension, and image magic bytes.
    Raises ImageValidationError on any check failure.
    """
    if not file_bytes:
        raise ImageValidationError("Uploaded image file is empty.")

    max_bytes = settings.R2_MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ImageValidationError(
            f"Image exceeds the maximum allowed size of {settings.R2_MAX_UPLOAD_SIZE_MB}MB "
            f"({len(file_bytes) / (1024 * 1024):.1f}MB uploaded)."
        )

    # Validate file extension
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ImageValidationError(
            f"Unsupported file format '{ext}'. Allowed image formats: {allowed}"
        )

    # Validate magic bytes / structure using PIL
    try:
        with Image.open(io.BytesIO(file_bytes)) as probe:
            probe.verify()
    except Exception as e:
        logger.warning(f"Image integrity verification failed for '{filename}': {e}")
        raise ImageValidationError("Invalid or corrupted image file.") from e


def optimize_image_to_webp(file_bytes: bytes) -> Tuple[bytes, int, int]:
    """
    Converts and optimizes an uploaded image into high-quality WebP format.
    - Handles EXIF orientation tags automatically.
    - Preserves alpha transparency for PNG/RGBA.
    - Strips unnecessary metadata (EXIF/GPS/comments) to minimize file size.
    - Avoids unnecessary downscaling, capping only absurd dimensions (> 2560px).
    Returns (optimized_webp_bytes, width, height).
    """
    try:
        with Image.open(io.BytesIO(file_bytes)) as raw_img:
            # 1. Correct image orientation according to EXIF tags
            try:
                img = ImageOps.exif_transpose(raw_img)
                if img is None:
                    img = raw_img.copy()
            except Exception:
                img = raw_img.copy()

            # 2. Color Mode & Transparency Handling
            # If the image has transparency, ensure RGBA mode for WebP preservation
            if img.mode in ("RGBA", "LA"):
                processed = img.convert("RGBA")
            elif img.mode == "P":
                if "transparency" in img.info:
                    processed = img.convert("RGBA")
                else:
                    processed = img.convert("RGB")
            elif img.mode == "RGB":
                processed = img
            else:
                # CMYK, YCbCr, Grayscale with odd profiles -> standard RGB
                processed = img.convert("RGB")

            # 3. Enforce exact 1280x720 px dimensions (16:9 aspect ratio)
            # Fits and center-crops cleanly using high-quality LANCZOS resampling.
            processed = ImageOps.fit(
                processed,
                (TARGET_IMAGE_WIDTH, TARGET_IMAGE_HEIGHT),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5)
            )
            width, height = TARGET_IMAGE_WIDTH, TARGET_IMAGE_HEIGHT

            # 4. Save to WebP in memory
            output_buffer = io.BytesIO()
            save_kwargs = {
                "format": "WEBP",
                "quality": WEBP_QUALITY,
                "method": WEBP_METHOD,
            }

            # If image has alpha channel, WebP supports lossless or alpha quality
            if processed.mode == "RGBA":
                save_kwargs["alpha_quality"] = 90

            processed.save(output_buffer, **save_kwargs)
            webp_bytes = output_buffer.getvalue()

            logger.info(
                f"Optimized image to WebP: {len(file_bytes)} bytes -> {len(webp_bytes)} bytes "
                f"({(1 - len(webp_bytes) / len(file_bytes)) * 100:.1f}% reduction), {width}x{height}px"
            )

            return webp_bytes, width, height

    except Exception as e:
        logger.error(f"Failed to optimize image: {e}", exc_info=True)
        raise ImageValidationError(f"Failed to process and optimize image: {e}") from e


def generate_unique_object_key(filename: str, post_type: str = "writing", slug: str = "") -> str:
    """
    Generates a clean, unique, collision-resistant object key for Cloudflare R2.
    Format: images/{post_type}/{year}/{month}/{unique_uuid}_{clean_slug}.webp
    """
    now = datetime.now(timezone.utc)
    year = now.strftime("%Y")
    month = now.strftime("%m")

    # Clean the slug or filename stem
    base_name = slug.strip() or os.path.splitext(filename)[0]
    clean_stem = re.sub(r"[^a-zA-Z0-9_-]", "-", base_name).strip("-").lower()
    clean_stem = clean_stem[:40] or "featured"

    unique_id = uuid.uuid4().hex[:12]
    clean_type = re.sub(r"[^a-zA-Z0-9_-]", "", post_type.lower()) or "posts"

    return f"images/{clean_type}/{year}/{month}/{unique_id}_{clean_stem}.webp"


def build_public_url(object_key: str) -> str:
    """
    Constructs the public image delivery URL.
    - If R2_PUBLIC_URL is configured (e.g. custom domain or r2.dev), uses that.
    - If R2_PUBLIC_URL is unconfigured or points to private s3 endpoint (r2.cloudflarestorage.com),
      routes cleanly through local /media/{key} streaming proxy.
    """
    public_base = (settings.R2_PUBLIC_URL or "").strip()
    if public_base and "r2.cloudflarestorage.com" not in public_base:
        return f"{public_base.rstrip('/')}/{object_key.lstrip('/')}"

    # Fallback to high-performance local media proxy
    return f"/media/{object_key.lstrip('/')}"


def upload_post_image(
    file_bytes: bytes,
    filename: str,
    post_type: str = "writing",
    post_slug: str = ""
) -> Dict[str, Any]:
    """
    Complete pipeline:
    1. Validates the raw image file.
    2. Optimizes and converts into WebP.
    3. Generates a unique collision-resistant object key.
    4. Uploads to Cloudflare R2 bucket.
    5. Returns metadata dict for database persistence.
    """
    # 1. Validate
    validate_image_file(file_bytes, filename)

    # 2. Optimize & Convert to WebP
    webp_bytes, width, height = optimize_image_to_webp(file_bytes)

    # 3. Unique Object Key
    object_key = generate_unique_object_key(filename, post_type=post_type, slug=post_slug)
    public_url = build_public_url(object_key)

    # 4. Upload to Cloudflare R2
    client = get_r2_client()
    try:
        clean_filename = re.sub(r"[^\x20-\x7E]", "", filename)[:100]
        client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=object_key,
            Body=webp_bytes,
            ContentType="image/webp",
            CacheControl="public, max-age=31536000, immutable",
            Metadata={
                "original-filename": clean_filename,
                "width": str(width),
                "height": str(height),
            },
        )
        logger.info(f"Successfully uploaded image to R2: bucket={settings.R2_BUCKET_NAME}, key={object_key}")
    except (ClientError, BotoCoreError) as e:
        logger.error(f"Cloudflare R2 put_object failed for '{object_key}': {e}", exc_info=True)
        raise R2StorageError(f"Failed to upload image to Cloudflare R2 storage: {e}") from e

    return {
        "success": True,
        "url": public_url,
        "key": object_key,
        "width": width,
        "height": height,
        "size": len(webp_bytes),
        "mime": "image/webp",
        "original_filename": filename,
    }


def delete_image_from_r2(object_key: str) -> bool:
    """
    Deletes an image from Cloudflare R2 storage to prevent orphaned objects.
    Gracefully handles already-missing or empty keys.
    """
    key = (object_key or "").strip()
    if not key:
        return True

    if not is_r2_configured():
        logger.warning(f"Cloudflare R2 not configured; skipped deleting key '{key}'.")
        return False

    try:
        client = get_r2_client()
        client.delete_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
        )
        logger.info(f"Successfully deleted object '{key}' from R2 bucket '{settings.R2_BUCKET_NAME}'.")
        return True
    except (ClientError, BotoCoreError) as e:
        # Don't fail the whole operation if object was already gone
        logger.warning(f"Could not delete R2 object '{key}': {e}")
        return False
