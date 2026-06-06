"""
qwen3 – Fast Qwen3 LLM package with RAG support.

Uses llama-cpp-python (GGUF) for fast CPU inference,
falls back to HuggingFace transformers when GGUF is unavailable.
"""

from qwen3.config import Settings  # noqa: F401
