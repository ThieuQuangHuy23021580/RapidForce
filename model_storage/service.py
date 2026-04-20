from __future__ import annotations

import tempfile
from pathlib import Path

from model_storage import db
from model_storage.cloudinary_uploader import upload_model_and_get_meta
from model_storage.config import StorageSettings
from model_storage.draco import compress_glb_with_draco


class ModelStorageService:
    """End-to-end pipeline: compress -> upload -> persist metadata."""

    def __init__(self, settings: StorageSettings | None = None):
        self.settings = settings or StorageSettings()
        db.init_schema(self.settings.db_path)

    def store_model(
        self,
        local_path: str | Path,
        user_id: int | None = None,
        user_name: str | None = None,
        compress_draco: bool = True,
    ) -> dict:
        src_path = Path(local_path)
        final_path = src_path

        if compress_draco and self.settings.draco_enabled and src_path.suffix.lower() == ".glb":
            compressed_dir = Path(tempfile.gettempdir()) / "rapidforce_compressed"
            compressed_name = src_path.stem + "_draco.glb"
            final_path = compress_glb_with_draco(
                src_path,
                compressed_dir / compressed_name,
                command=self.settings.gltf_pipeline_cmd,
            )

        upload_meta = upload_model_and_get_meta(
            local_path=final_path,
            cloud_name=self.settings.cloudinary_cloud_name,
            api_key=self.settings.cloudinary_api_key,
            api_secret=self.settings.cloudinary_api_secret,
            folder=self.settings.storage_prefix,
        )

        model_id = db.insert_model(
            db_path=self.settings.db_path,
            url=upload_meta["url"],
            size_mb=upload_meta["size"],
        )

        resolved_user_id = user_id
        if resolved_user_id is None and user_name:
            resolved_user_id = db.ensure_user(self.settings.db_path, user_name)

        if resolved_user_id is not None:
            db.link_model_to_user(self.settings.db_path, resolved_user_id, model_id)

        if not self.settings.keep_local_files and final_path != src_path and final_path.exists():
            final_path.unlink(missing_ok=True)

        return {
            "model_id": model_id,
            "url": upload_meta["url"],
            "size_mb": round(float(upload_meta["size"]), 4),
            "user_id": resolved_user_id,
            "blob_name": upload_meta["blob_name"],
        }
