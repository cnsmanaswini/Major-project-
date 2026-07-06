"""
Cloudinary upload service
Handles image + video uploads for posts, reels, and profile avatars.
"""

import os
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

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}

MAX_IMAGE_SIZE_MB = 10
MAX_VIDEO_SIZE_MB = 100


async def _read_and_validate(file: UploadFile, allowed_types: set[str], max_size_mb: int) -> bytes:
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f}MB). Max is {max_size_mb}MB.",
        )
    return contents


async def upload_image(file: UploadFile, folder: str = "mindgram/posts") -> dict:
    """
    Uploads an image to Cloudinary.
    Returns dict with url, public_id, width, height.
    """
    contents = await _read_and_validate(file, ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE_MB)

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
    Uploads a video to Cloudinary.
    Returns dict with url, public_id, duration, thumbnail_url.
    """
    contents = await _read_and_validate(file, ALLOWED_VIDEO_TYPES, MAX_VIDEO_SIZE_MB)

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            resource_type="video",
            eager=[{"format": "jpg", "start_offset": "0"}],  # auto-generate a thumbnail
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
    `identifier` can be a user id or username — just needs to be unique per user.
    """
    contents = await _read_and_validate(file, ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE_MB)

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
    """Deletes an asset from Cloudinary (e.g. when a post is deleted)."""
    try:
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        return True
    except Exception as e:
        logger.error(f"Cloudinary delete failed for {public_id}: {e}")
        return False