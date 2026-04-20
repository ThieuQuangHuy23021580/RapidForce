from __future__ import annotations

import os
import subprocess
from pathlib import Path

from model_storage.errors import CompressionError


def compress_glb_with_draco(
    input_path: str | Path,
    output_path: str | Path,
    command: str = "gltf-pipeline",
) -> Path:
    src = Path(input_path)
    dst = Path(output_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    cmd = [command, "-i", str(src), "-o", str(dst), "-d", "-s"]
    try:
        if os.name == "nt":
            cmdline = " ".join(
                [f'"{cmd[0]}"', f'"{cmd[2]}"', f'"{cmd[4]}"', cmd[5], cmd[6]]
            )
            cmdline = f'{cmd[0]} -i "{src}" -o "{dst}" -d -s'
            subprocess.run(cmdline, check=True, capture_output=True, text=True, shell=True)
        else:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise CompressionError(
            "gltf-pipeline not found. Install globally: npm install -g gltf-pipeline"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise CompressionError(
            f"Draco compression failed: {exc.stderr.strip() or exc.stdout.strip()}"
        ) from exc

    return dst
