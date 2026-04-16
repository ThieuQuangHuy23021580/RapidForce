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
