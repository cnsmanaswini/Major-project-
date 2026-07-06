"""
Media upload service
Uses Cloudinary when configured, otherwise saves files locally for development.
"""

import os
import uuid
from pathlib import Path

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile, HTTPException
import logging

logger = logging.getLogger("mindgram.cloudinary")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"

ALLOWED_IMAGE_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif", "image/heic",
}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}

MAX_IMAGE_SIZE_MB = 10
MAX_VIDEO_SIZE_MB = 100


def _cloudinary_configured() -> bool:
    return bool(
        os.getenv("CLOUDINARY_CLOUD_NAME")
        and os.getenv("CLOUDINARY_API_KEY")
        and os.getenv("CLOUDINARY_API_SECRET")
    )


def _resolve_extension(filename: str | None, allowed: set[str]) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in allowed:
        return ext
    return next(iter(allowed))


async def _read_and_validate(
    file: UploadFile,
    allowed_types: set[str],
    allowed_extensions: set[str],
    max_size_mb: int,
) -> bytes:
    ext = Path(file.filename or "").suffix.lower()
    content_type = (file.content_type or "").lower()

    type_ok = content_type in allowed_types or ext in allowed_extensions
    if not type_ok:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type or ext or 'unknown'}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f}MB). Max is {max_size_mb}MB.",
        )
    return contents


def _save_local(contents: bytes, folder: str, extension: str) -> dict:
    subfolder = folder.replace("mindgram/", "")
    target_dir = UPLOAD_ROOT / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{extension}"
    filepath = target_dir / filename
    filepath.write_bytes(contents)

    public_id = f"local:{subfolder}/{filename}"
    return {
        "url": f"/uploads/{subfolder}/{filename}",
        "public_id": public_id,
    }


async def upload_image(file: UploadFile, folder: str = "mindgram/posts") -> dict:
    """
    Uploads an image to Cloudinary or local storage.
    Returns dict with url, public_id, width, height.
    """
    contents = await _read_and_validate(
        file, ALLOWED_IMAGE_TYPES, IMAGE_EXTENSIONS, MAX_IMAGE_SIZE_MB
    )
    extension = _resolve_extension(file.filename, IMAGE_EXTENSIONS)

    if not _cloudinary_configured():
        logger.info("Cloudinary not configured — saving image locally")
        return _save_local(contents, folder, extension)

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            resource_type="image",
            transformation=[{"quality": "auto", "fetch_format": "auto"}],
        )
    except Exception as e:
        logger.error(f"Cloudinary image upload failed: {e}")
        raise HTTPException(status_code=502, detail="Image upload failed")

    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "width": result.get("width"),
        "height": result.get("height"),
    }


async def upload_video(file: UploadFile, folder: str = "mindgram/reels") -> dict:
    """
    Uploads a video to Cloudinary or local storage.
    Returns dict with url, public_id, duration, thumbnail_url.
    """
    contents = await _read_and_validate(
        file, ALLOWED_VIDEO_TYPES, VIDEO_EXTENSIONS, MAX_VIDEO_SIZE_MB
    )
    extension = _resolve_extension(file.filename, VIDEO_EXTENSIONS)

    if not _cloudinary_configured():
        logger.info("Cloudinary not configured — saving video locally")
        return _save_local(contents, folder, extension)

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            resource_type="video",
            eager=[{"format": "jpg", "start_offset": "0"}],
        )
    except Exception as e:
        logger.error(f"Cloudinary video upload failed: {e}")
        raise HTTPException(status_code=502, detail="Video upload failed")

    thumbnail_url = None
    if result.get("eager"):
        thumbnail_url = result["eager"][0].get("secure_url")

    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "duration": result.get("duration"),
        "thumbnail_url": thumbnail_url,
    }


async def upload_avatar(file: UploadFile, identifier: str | int) -> dict:
    """
    Uploads a profile avatar. Fixed folder + overwrite so each user has one avatar.
    """
    contents = await _read_and_validate(
        file, ALLOWED_IMAGE_TYPES, IMAGE_EXTENSIONS, MAX_IMAGE_SIZE_MB
    )
    extension = _resolve_extension(file.filename, IMAGE_EXTENSIONS)

    if not _cloudinary_configured():
        logger.info("Cloudinary not configured — saving avatar locally")
        return _save_local(contents, "mindgram/avatars", extension)

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder="mindgram/avatars",
            public_id=f"user_{identifier}",
            overwrite=True,
            resource_type="image",
            transformation=[
                {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
                {"quality": "auto", "fetch_format": "auto"},
            ],
        )
    except Exception as e:
        logger.error(f"Cloudinary avatar upload failed: {e}")
        raise HTTPException(status_code=502, detail="Avatar upload failed")

    return {"url": result["secure_url"], "public_id": result["public_id"]}


def delete_asset(public_id: str, resource_type: str = "image") -> bool:
    """Deletes an asset from Cloudinary or local storage."""
    if public_id.startswith("local:"):
        relative = public_id.removeprefix("local:")
        filepath = UPLOAD_ROOT / relative
        try:
            if filepath.is_file():
                filepath.unlink()
            return True
        except Exception as e:
            logger.error(f"Local delete failed for {public_id}: {e}")
            return False

    try:
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        return True
    except Exception as e:
        logger.error(f"Cloudinary delete failed for {public_id}: {e}")
        return False