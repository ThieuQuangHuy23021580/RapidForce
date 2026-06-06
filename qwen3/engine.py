"""
LLM inference engine with automatic backend selection.

Priority: llama-cpp-python (GGUF) → HuggingFace transformers
"""

from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Generator, List

from qwen3.config import Settings

log = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_thinking(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


class BaseLLMEngine(ABC):
    """Common interface for all LLM backends."""

    @abstractmethod
    def generate(
        self,
        messages: List[dict],
        max_new_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str: ...

    @abstractmethod
    def generate_stream(
        self,
        messages: List[dict],
        max_new_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Generator[str, None, None]: ...

    @property
    @abstractmethod
    def backend_name(self) -> str: ...


# ────────────────────────────────────────────────────────────────────
# llama-cpp-python backend  (fast CPU inference with GGUF)
# ────────────────────────────────────────────────────────────────────

class LlamaCppEngine(BaseLLMEngine):
    def __init__(self, cfg: Settings):
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama

        log.info("Downloading GGUF model %s / %s …", cfg.gguf_repo, cfg.gguf_file)
        model_path = hf_hub_download(repo_id=cfg.gguf_repo, filename=cfg.gguf_file)
        log.info("GGUF path: %s", model_path)

        self._llm = Llama(
            model_path=model_path,
            n_ctx=cfg.n_ctx,
            n_threads=cfg.n_threads,
            n_gpu_layers=cfg.n_gpu_layers,
            verbose=False,
        )
        log.info(
            "LlamaCppEngine ready  (ctx=%d, threads=%d, gpu_layers=%d)",
            cfg.n_ctx, cfg.n_threads, cfg.n_gpu_layers,
        )

    @property
    def backend_name(self) -> str:
        return "llama.cpp (GGUF)"

    def generate(self, messages, max_new_tokens=512, temperature=0.7) -> str:
        t0 = time.perf_counter()
        resp = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_new_tokens,
            temperature=temperature,
        )
        text = resp["choices"][0]["message"]["content"]
        elapsed = time.perf_counter() - t0
        log.info("Generated %d chars in %.2fs", len(text), elapsed)
        return _strip_thinking(text)

    def generate_stream(self, messages, max_new_tokens=512, temperature=0.7):
        stream = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_new_tokens,
            temperature=temperature,
            stream=True,
        )
        buf: list[str] = []
        for chunk in stream:
            delta = chunk["choices"][0].get("delta", {})
            token = delta.get("content", "")
            if token:
                buf.append(token)
                yield token

        full = "".join(buf)
        if "<think>" in full:
            cleaned = _strip_thinking(full)
            yield f"\n[cleaned]{cleaned}"


# ────────────────────────────────────────────────────────────────────
# HuggingFace transformers backend  (fallback)
# ────────────────────────────────────────────────────────────────────

class TransformersEngine(BaseLLMEngine):
    def __init__(self, cfg: Settings):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        log.info("Loading HF model %s …", cfg.hf_model_id)
        self._tokenizer = AutoTokenizer.from_pretrained(cfg.hf_model_id)
        self._model = AutoModelForCausalLM.from_pretrained(
            cfg.hf_model_id, torch_dtype="auto", device_map="auto"
        )
        self._model.eval()
        self._torch = torch
        self._device = str(self._model.device)
        log.info("TransformersEngine ready on %s", self._device)

    @property
    def backend_name(self) -> str:
        return "transformers (HF)"

    def generate(self, messages, max_new_tokens=512, temperature=0.7) -> str:
        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)

        gen_kwargs: dict = {
            **inputs,
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self._tokenizer.eos_token_id,
        }
        if temperature > 0:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["do_sample"] = True

        t0 = time.perf_counter()
        with self._torch.no_grad():
            outputs = self._model.generate(**gen_kwargs)
        elapsed = time.perf_counter() - t0

        new_ids = outputs[0][inputs["input_ids"].shape[1] :]
        raw = self._tokenizer.decode(new_ids, skip_special_tokens=True)
        log.info("Generated in %.2fs", elapsed)
        return _strip_thinking(raw)

    def generate_stream(self, messages, max_new_tokens=512, temperature=0.7):
        from threading import Thread

        from transformers import TextIteratorStreamer

        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)

        streamer = TextIteratorStreamer(
            self._tokenizer, skip_prompt=True, skip_special_tokens=True
        )
        gen_kwargs: dict = {
            **inputs,
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self._tokenizer.eos_token_id,
            "streamer": streamer,
        }
        if temperature > 0:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["do_sample"] = True

        thread = Thread(target=self._model.generate, kwargs=gen_kwargs)
        thread.start()
        for tok in streamer:
            yield tok
        thread.join()


# ────────────────────────────────────────────────────────────────────
# Factory – tries llama.cpp first, then transformers
# ────────────────────────────────────────────────────────────────────

def create_engine(cfg: Settings | None = None) -> BaseLLMEngine:
    cfg = cfg or Settings()

    try:
        return LlamaCppEngine(cfg)
    except Exception as exc:
        log.warning("llama-cpp-python unavailable (%s), falling back to transformers", exc)

    return TransformersEngine(cfg)
