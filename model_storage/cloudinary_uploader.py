from __future__ import annotations

import os
from pathlib import Path

from model_storage.errors import UploadError


def upload_model_and_get_meta(
    local_path: str | Path,
    cloud_name: str,
    api_key: str,
    api_secret: str,
    folder: str = "outputs",
) -> dict:
    if not cloud_name or not api_key or not api_secret:
        raise UploadError(
            "Cloudinary credentials are required: CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET"
        )

    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError as exc:
        raise UploadError("cloudinary is not installed. Run: pip install cloudinary") from exc

    local_file = Path(local_path)

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )

    # 3D assets are safest as "raw" in Cloudinary.
    resource_type = "raw"
    result = cloudinary.uploader.upload(
        str(local_file),
        folder=folder.strip("/"),
        resource_type=resource_type,
        use_filename=True,
        unique_filename=True,
        overwrite=False,
    )

    return {
        "url": result.get("secure_url") or result.get("url"),
        "size": os.path.getsize(local_file) / (1024 * 1024),
        "blob_name": result.get("public_id", ""),
    }
