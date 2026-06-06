import io
import os
import tempfile
from typing import Literal

import numpy as np
import rembg
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel

from model_storage import db
from model_storage.config import StorageSettings
from model_storage.errors import DatabaseError
from model_storage.errors import StorageError
from model_storage.service import ModelStorageService
from tsr.system import TSR
from tsr.utils import remove_background, resize_foreground
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="RapidForce API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if torch.cuda.is_available():
    device = "cuda:0"
else:
    device = "cpu"


model = TSR.from_pretrained(
    "stabilityai/TripoSR",
    config_name="config.yaml",
    weight_name="model.ckpt",
)
model.renderer.set_chunk_size(8192)
model.to(device)
model.eval()

rembg_session = rembg.new_session()
output_dir = os.path.join(tempfile.gettempdir(), "rapidforce_api")
os.makedirs(output_dir, exist_ok=True)
storage_service = ModelStorageService(StorageSettings())


def fill_background(image: Image.Image) -> Image.Image:
    image_np = np.array(image).astype(np.float32) / 255.0
    image_np = image_np[:, :, :3] * image_np[:, :, 3:4] + (1 - image_np[:, :, 3:4]) * 0.5
    return Image.fromarray((image_np * 255.0).astype(np.uint8))


def preprocess_image(
    input_image: Image.Image,
    do_remove_background: bool,
    foreground_ratio: float,
) -> Image.Image:
    if do_remove_background:
        image = input_image.convert("RGB")
        image = remove_background(image, rembg_session)
        image = resize_foreground(image, foreground_ratio)
        image = fill_background(image)
        return image

    image = input_image
    if image.mode == "RGBA":
        image = fill_background(image)
    return image.convert("RGB")


def generate_mesh_file(
    image: Image.Image,
    mc_resolution: int,
    output_format: Literal["obj", "glb"],
) -> str:
    with torch.no_grad():
        scene_codes = model(image, device=device)
        mesh = model.extract_mesh(scene_codes, True, resolution=mc_resolution)[0]

    suffix = f".{output_format}"
    with tempfile.NamedTemporaryFile(dir=output_dir, suffix=suffix, delete=False) as temp_file:
        mesh.export(temp_file.name)
        return temp_file.name


class StoreModelResponse(BaseModel):
    model_id: int
    url: str
    image_url: str | None = None
    size_mb: float
    user_id: int | None = None
    blob_name: str


class ModelRecordResponse(BaseModel):
    model_id: int
    url: str
    image_url: str | None = None
    size_mb: float | None = None
    user_id: int | None = None
    created_at: str | None = None


class UserRecordResponse(BaseModel):
    user_id: int
    user_name: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    model_count: int = 0


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    user_id: int
    user_name: str
    first_name: str | None = None
    last_name: str | None = None
    email: str


class DeleteModelResponse(BaseModel):
    ok: bool = True
    model_id: int
    user_id: int


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "device": device,
        "model": "stabilityai/TripoSR",
    }


@app.post("/generate")
async def generate(
    image: UploadFile = File(...),
    remove_background_flag: bool = Form(True),
    foreground_ratio: float = Form(0.85),
    mc_resolution: int = Form(256),
    output_format: Literal["obj", "glb"] = Form("glb"),
):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    if not 0.5 <= foreground_ratio <= 1.0:
        raise HTTPException(status_code=400, detail="foreground_ratio must be between 0.5 and 1.0.")

    if mc_resolution not in {32, 64, 96, 128, 160, 192, 224, 256, 288, 320}:
        raise HTTPException(
            status_code=400,
            detail="mc_resolution must be one of: 32, 64, 96, 128, 160, 192, 224, 256, 288, 320.",
        )

    file_bytes = await image.read()
    try:
        input_image = Image.open(io.BytesIO(file_bytes))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read uploaded image.") from exc

    processed_image = preprocess_image(
        input_image=input_image,
        do_remove_background=remove_background_flag,
        foreground_ratio=foreground_ratio,
    )
    mesh_path = generate_mesh_file(
        image=processed_image,
        mc_resolution=mc_resolution,
        output_format=output_format,
    )

    media_type = "model/gltf-binary" if output_format == "glb" else "text/plain"
    filename = f"rapidforce_result.{output_format}"
    return FileResponse(mesh_path, media_type=media_type, filename=filename)


@app.post("/generate/store", response_model=StoreModelResponse)
async def generate_and_store(
    image: UploadFile = File(...),
    remove_background_flag: bool = Form(True),
    foreground_ratio: float = Form(0.85),
    mc_resolution: int = Form(256),
    output_format: Literal["obj", "glb"] = Form("glb"),
    user_id: int | None = Form(None),
    user_name: str | None = Form(None),
    image_url: str | None = Form(None),
    compress_draco: bool = Form(True),
):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    if not 0.5 <= foreground_ratio <= 1.0:
        raise HTTPException(status_code=400, detail="foreground_ratio must be between 0.5 and 1.0.")

    if mc_resolution not in {32, 64, 96, 128, 160, 192, 224, 256, 288, 320}:
        raise HTTPException(
            status_code=400,
            detail="mc_resolution must be one of: 32, 64, 96, 128, 160, 192, 224, 256, 288, 320.",
        )

    file_bytes = await image.read()
    try:
        input_image = Image.open(io.BytesIO(file_bytes))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read uploaded image.") from exc

    processed_image = preprocess_image(
        input_image=input_image,
        do_remove_background=remove_background_flag,
        foreground_ratio=foreground_ratio,
    )
    mesh_path = generate_mesh_file(
        image=processed_image,
        mc_resolution=mc_resolution,
        output_format=output_format,
    )

    try:
        result = storage_service.store_model(
            local_path=mesh_path,
            user_id=user_id,
            user_name=user_name,
            image_url=image_url,
            compress_draco=compress_draco,
        )
    except DatabaseError as exc:
        if "reached max 5 models" in str(exc):
            raise HTTPException(
                status_code=409,
                detail="User reached max 5 models. Delete old models or use another user.",
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return StoreModelResponse(**result)


def _validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Invalid email format.")
    return normalized


@app.post("/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest):
    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    email = _validate_email(payload.email)
    password = payload.password

    if not first_name:
        raise HTTPException(status_code=400, detail="first_name is required.")
    if not last_name:
        raise HTTPException(status_code=400, detail="last_name is required.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    try:
        user = db.create_auth_user(
            storage_service.settings.db_path,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
        )
        return AuthResponse(**user)
    except DatabaseError as exc:
        if "Email already registered" in str(exc):
            raise HTTPException(status_code=409, detail="Email already registered.") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    email = _validate_email(payload.email)
    password = payload.password
    if not password:
        raise HTTPException(status_code=400, detail="password is required.")

    try:
        user = db.get_auth_user_by_email(storage_service.settings.db_path, email=email)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if user is None or not user.get("password_hash") or not user.get("password_salt"):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not db.verify_password(password, user["password_hash"], user["password_salt"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return AuthResponse(
        user_id=user["user_id"],
        user_name=user["user_name"],
        first_name=user["first_name"],
        last_name=user["last_name"],
        email=user["email"],
    )


@app.get("/models", response_model=list[ModelRecordResponse])
def get_models(limit: int = 50, offset: int = 0):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    try:
        return db.list_models(storage_service.settings.db_path, limit=limit, offset=offset)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/models/{model_id}", response_model=ModelRecordResponse)
def get_model(model_id: int):
    try:
        record = db.get_model(storage_service.settings.db_path, model_id=model_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return record


@app.get("/users", response_model=list[UserRecordResponse])
def get_users(limit: int = 50, offset: int = 0):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    try:
        return db.list_users(storage_service.settings.db_path, limit=limit, offset=offset)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/users/{user_id}", response_model=UserRecordResponse)
def get_user(user_id: int):
    try:
        record = db.get_user(storage_service.settings.db_path, user_id=user_id)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return record


@app.get("/users/{user_id}/models", response_model=list[ModelRecordResponse])
def get_models_by_user(user_id: int, limit: int = 50, offset: int = 0):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    try:
        user = db.get_user(storage_service.settings.db_path, user_id=user_id)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        return db.list_models_by_user(storage_service.settings.db_path, user_id=user_id, limit=limit, offset=offset)
    except DatabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/users/{user_id}/models/{model_id}", response_model=DeleteModelResponse)
def delete_user_model(user_id: int, model_id: int):
    try:
        db.delete_model_for_user(storage_service.settings.db_path, user_id=user_id, model_id=model_id)
        return DeleteModelResponse(model_id=model_id, user_id=user_id)
    except DatabaseError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg) from exc
        if "does not belong" in msg or "not linked" in msg.lower():
            raise HTTPException(status_code=403, detail=msg) from exc
        raise HTTPException(status_code=500, detail=msg) from exc
