from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent


@dataclass
class Settings:
    # ── llama.cpp (primary – fast on CPU/GPU) ──────────────────────
    gguf_repo: str = "lmstudio-community/Qwen3-1.7B-GGUF"
    gguf_file: str = "Qwen3-1.7B-Q4_K_M.gguf"
    n_ctx: int = 4096
    n_threads: int = os.cpu_count() or 4
    # Set > 0 to offload layers to GPU (e.g. 20 for partial, -1 for all layers)
    n_gpu_layers: int = int(os.environ.get("N_GPU_LAYERS", "0"))

    # ── HuggingFace transformers (fallback) ────────────────────────
    hf_model_id: str = "rd211/Qwen3-1.7B-Instruct"

    # ── Generation defaults ────────────────────────────────────────
    max_new_tokens: int = 512
    temperature: float = 0.7

    # ── RAG ────────────────────────────────────────────────────────
    knowledge_dir: Path = field(default_factory=lambda: _PKG_DIR / "knowledge")
    chroma_dir: Path = field(default_factory=lambda: _PKG_DIR / ".chromadb")
    embed_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 800
    chunk_overlap: int = 100
    rag_top_k: int = 3

    # ── API ────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8001
