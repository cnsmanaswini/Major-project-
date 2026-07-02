"""
Cloudinary Service
Handles image and video uploads for posts, stories, reels and avatars
"""

import cloudinary
import cloudinary.uploader
import cloudinary.api
from fastapi import UploadFile, HTTPException
import logging

from config import settings

logger = logging.getLogger("mindgram.cloudinary")

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)

# Allowed file types
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB


async def upload_image(
    file: UploadFile,
    folder: str = "mindgram/posts",
    transformation: dict = None,
) -> dict:
    """
    Upload an image to Cloudinary.
    Returns dict with url, public_id, width, height.
    """
    # Validate type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {ALLOWED_IMAGE_TYPES}"
        )

    # Read file
    contents = await file.read()

    # Validate size
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Image too large. Max size is 10MB."
        )

    try:
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            transformation=transformation or [
                {"width": 1080, "crop": "limit"},
                {"quality": "auto"},
                {"fetch_format": "auto"},
            ],
            resource_type="image",
        )

        logger.info(f"Image uploaded: {result['public_id']}")
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "width": result.get("width"),
            "height": result.get("height"),
        }

    except Exception as e:
        logger.error(f"Cloudinary upload failed: {e}")
        raise HTTPException(status_code=500, detail="Image upload failed")


async def upload_video(
    file: UploadFile,
    folder: str = "mindgram/reels",
) -> dict:
    """
    Upload a video to Cloudinary.
    Returns dict with url, public_id, duration, thumbnail_url.
    """
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {ALLOWED_VIDEO_TYPES}"
        )

    contents = await file.read()

    if len(contents) > MAX_VIDEO_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Video too large. Max size is 100MB."
        )

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            resource_type="video",
            eager=[
                {"format": "mp4", "quality": "auto"},
            ],
            eager_async=True,
        )

        # Generate thumbnail
        thumbnail_url = cloudinary.utils.cloudinary_url(
            result["public_id"],
            resource_type="video",
            format="jpg",
            transformation=[
                {"width": 400, "height": 400, "crop": "fill"},
                {"quality": "auto"},
            ]
        )[0]

        logger.info(f"Video uploaded: {result['public_id']}")
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "thumbnail_url": thumbnail_url,
            "duration": result.get("duration", 0),
        }

    except Exception as e:
        logger.error(f"Cloudinary video upload failed: {e}")
        raise HTTPException(status_code=500, detail="Video upload failed")


async def upload_avatar(file: UploadFile, username: str) -> str:
    """Upload a profile avatar. Returns the URL."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid image type")

    contents = await file.read()

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder="mindgram/avatars",
            public_id=f"avatar_{username}",
            overwrite=True,
            transformation=[
                {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
                {"quality": "auto"},
                {"fetch_format": "auto"},
            ],
        )
        return result["secure_url"]

    except Exception as e:
        logger.error(f"Avatar upload failed: {e}")
        raise HTTPException(status_code=500, detail="Avatar upload failed")


async def delete_media(public_id: str, resource_type: str = "image"):
    """Delete a file from Cloudinary."""
    try:
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        logger.info(f"Deleted media: {public_id}")
    except Exception as e:
        logger.warning(f"Failed to delete media {public_id}: {e}")