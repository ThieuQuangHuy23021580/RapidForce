from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    # Load values from .env if present (local development).
    from dotenv import load_dotenv

    _ROOT_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(dotenv_path=_ROOT_DIR / ".env", override=True)
except Exception:
    # Keep working even if python-dotenv is not installed.
    pass


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class StorageSettings:
    db_path: Path = Path(os.getenv("RAPIDFORCE_DB_PATH", "rapidforce.db")).resolve()
    cloudinary_cloud_name: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    cloudinary_api_key: str = os.getenv("CLOUDINARY_API_KEY", "")
    cloudinary_api_secret: str = os.getenv("CLOUDINARY_API_SECRET", "")
    storage_prefix: str = os.getenv("CLOUDINARY_FOLDER", "outputs")
    draco_enabled: bool = _bool_env("DRACO_ENABLED", True)
    gltf_pipeline_cmd: str = os.getenv("GLTF_PIPELINE_CMD", "gltf-pipeline")
    keep_local_files: bool = _bool_env("KEEP_LOCAL_MODEL_FILES", False)
