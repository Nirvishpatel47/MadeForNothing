"""
Unit tests for Cloudflare R2 Storage integration and WebP image optimization.
"""
import io
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

import r2_storage
from core.config import settings


def create_test_image(format="JPEG", size=(200, 150), color=(100, 150, 200), mode="RGB") -> bytes:
    """Helper to generate in-memory test image bytes."""
    img = Image.new(mode, size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def test_validate_image_file_valid():
    """Valid JPEG/PNG images pass validation without error."""
    jpeg_bytes = create_test_image(format="JPEG")
    r2_storage.validate_image_file(jpeg_bytes, "photo.jpg")

    png_bytes = create_test_image(format="PNG", mode="RGBA")
    r2_storage.validate_image_file(png_bytes, "graphic.png")


def test_validate_image_file_empty():
    """Empty files raise ImageValidationError."""
    with pytest.raises(r2_storage.ImageValidationError, match="empty"):
        r2_storage.validate_image_file(b"", "photo.jpg")


def test_validate_image_file_invalid_extension():
    """Disallowed file extensions raise ImageValidationError."""
    jpeg_bytes = create_test_image(format="JPEG")
    with pytest.raises(r2_storage.ImageValidationError, match="Unsupported file format"):
        r2_storage.validate_image_file(jpeg_bytes, "malicious.exe")


def test_validate_image_file_corrupted_data():
    """Non-image bytes with valid extension raise ImageValidationError."""
    fake_bytes = b"This is not a real image file content at all."
    with pytest.raises(r2_storage.ImageValidationError, match="Invalid or corrupted"):
        r2_storage.validate_image_file(fake_bytes, "photo.jpg")


def test_optimize_image_to_webp_rgb():
    """RGB images are converted into WebP with standardized 1280x720 (16:9) dimensions."""
    raw = create_test_image(format="JPEG", size=(320, 240), color=(50, 100, 150))
    webp_bytes, width, height = r2_storage.optimize_image_to_webp(raw)

    assert width == 1280
    assert height == 720
    assert len(webp_bytes) > 0

    # Verify output is valid WebP using PIL
    with Image.open(io.BytesIO(webp_bytes)) as out_img:
        assert out_img.format == "WEBP"
        assert out_img.size == (1280, 720)


def test_optimize_image_to_webp_preserves_alpha():
    """RGBA images retain alpha transparency when converted to WebP."""
    raw = create_test_image(format="PNG", size=(100, 100), color=(255, 0, 0, 128), mode="RGBA")
    webp_bytes, width, height = r2_storage.optimize_image_to_webp(raw)

    with Image.open(io.BytesIO(webp_bytes)) as out_img:
        assert out_img.format == "WEBP"
        assert out_img.mode == "RGBA"
        # Check pixel alpha channel
        pixel = out_img.getpixel((50, 50))
        assert len(pixel) == 4
        assert pixel[3] > 0  # Alpha preserved


def test_generate_unique_object_key():
    """Object keys are unique, include post type and clean slug, and end in .webp."""
    key1 = r2_storage.generate_unique_object_key("test.png", post_type="writing", slug="deliberate-systems")
    key2 = r2_storage.generate_unique_object_key("test.png", post_type="writing", slug="deliberate-systems")

    assert key1.startswith("images/writing/")
    assert key1.endswith(".webp")
    assert "deliberate-systems" in key1
    assert key1 != key2  # Unique UUID component


def test_upload_post_image_mocked():
    """Upload pipeline validates, converts to WebP, and calls S3 put_object."""
    mock_s3 = MagicMock()
    raw = create_test_image(format="JPEG", size=(400, 300))

    with patch.object(r2_storage, "is_r2_configured", return_value=True), \
         patch.object(r2_storage, "get_r2_client", return_value=mock_s3), \
         patch.object(settings, "R2_BUCKET_NAME", "test-bucket"), \
         patch.object(settings, "R2_PUBLIC_URL", "https://images.example.com"):

        result = r2_storage.upload_post_image(raw, "cover.jpg", post_type="experiments", post_slug="my-experiment")

        assert result["success"] is True
        assert result["url"].startswith("https://images.example.com/images/experiments/")
        assert result["url"].endswith(".webp")
        assert result["width"] == 1280
        assert result["height"] == 720
        assert result["mime"] == "image/webp"

        # Verify put_object was invoked with proper parameters
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["ContentType"] == "image/webp"
        assert "public, max-age=" in call_kwargs["CacheControl"]


def test_delete_image_from_r2_mocked():
    """Deleting an image calls S3 delete_object with the bucket and key."""
    mock_s3 = MagicMock()

    with patch.object(r2_storage, "is_r2_configured", return_value=True), \
         patch.object(r2_storage, "get_r2_client", return_value=mock_s3), \
         patch.object(settings, "R2_BUCKET_NAME", "test-bucket"):

        res = r2_storage.delete_image_from_r2("images/writing/2026/11/abc_test.webp")
        assert res is True
        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="images/writing/2026/11/abc_test.webp"
        )


def test_delete_image_empty_key():
    """Calling delete with empty key returns True without calling S3."""
    res = r2_storage.delete_image_from_r2("")
    assert res is True
