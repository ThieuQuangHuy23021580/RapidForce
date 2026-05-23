"""
FastAPI application for the Qwen3 LLM service.

RAG is built-in: if knowledge documents exist, /chat automatically
retrieves relevant context before generating. No extra flag needed.

Endpoints:
    GET  /health    – service status
    POST /chat      – chat completion (RAG tự động)
    POST /rag/index – (re-)index knowledge documents
    GET  /rag/stats – RAG index statistics
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from qwen3.config import Settings
from qwen3.engine import BaseLLMEngine, create_engine
from qwen3.rag import RAGEngine

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)
STYLE_INSTRUCTION = (
    "Luôn trả lời ngắn gọn, dễ hiểu, và giới hạn trong tối đa 300 chữ."
)

cfg = Settings()

# ── Initialise engine + RAG ────────────────────────────────────────
log.info("Initialising LLM engine …")
engine: BaseLLMEngine = create_engine(cfg)
log.info("Backend: %s", engine.backend_name)

rag = RAGEngine(cfg)
try:
    if cfg.knowledge_dir.exists() and any(cfg.knowledge_dir.iterdir()):
        count = rag.index_documents()
        log.info("Auto-indexed %d RAG chunks on startup", count)
except Exception as exc:
    log.warning("RAG auto-index skipped: %s", exc)

# ── FastAPI app ────────────────────────────────────────────────────
app = FastAPI(title="Qwen3 Chat API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas (giữ nguyên API cũ) ───────────────────────────────────

class Message(BaseModel):
    role: str = Field(..., description="'system', 'user', or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    prompt: Optional[str] = Field(None, description="Simple prompt string.")
    messages: Optional[List[Message]] = Field(
        None, description="Full conversation history (takes priority over prompt)."
    )
    max_new_tokens: int = Field(512, ge=1, le=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    stream: bool = Field(False, description="Stream response token by token.")


class ChatResponse(BaseModel):
    answer: str
    backend: str
    rag_used: bool = False


# ── Helpers ────────────────────────────────────────────────────────

DEMO_QA_ANSWER = (
  "RapidForce là dự án nghiên cứu AI tích hợp để tái tạo 3D từ ảnh và hỗ trợ giải đáp các vấn đề liên quan đến xử lý mô hình 3D. "
   
    "Chức năng cốt lõi: Nền tảng tập trung vào việc xử lý và tạo mô hình 3D (3D modeling), cho phép người dùng đặt câu hỏi về quy trình sáng tạo hoặc thực hiện các tác vụ kỹ thuật. "
    
    "Chế độ Render 3D: Hệ thống sở hữu tính năng chuyển đổi hình ảnh tải lên thành mô hình 3D (image-to-3D). "
    
    "Môi trường làm việc (The Workshop): Cung cấp một giao diện làm việc bao gồm khu vực trò chuyện (Chat) và quản lý mô hình cá nhân (My Models). "
    
    "Công cụ hỗ trợ: Tích hợp các tính năng như tự động loại bỏ nền (Remove Background) khi xử lý hình ảnh để phục vụ việc tạo mô hình. "

)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _extract_latest_user_text(req: ChatRequest) -> str | None:
    if req.messages:
        for m in reversed(req.messages):
            if m.role == "user" and m.content:
                return m.content
    if req.prompt:
        return req.prompt
    return None


def _quick_demo_answer(req: ChatRequest) -> str | None:
    """Return canned answer for demo questions to bypass model inference."""
    user_text = _extract_latest_user_text(req)
    if not user_text:
        return None
    normalized = _normalize_text(user_text)
    if normalized in {
        "rapidforce là gì?",
        "rapidforce là gì",
        "rapidforce la gi?",
        "rapidforce la gi",
        "what is rapidforce?",
        "what is rapidforce",
    }:
        return DEMO_QA_ANSWER
    return None

def _resolve_messages(req: ChatRequest) -> tuple[list[dict], bool]:
    """Build the messages list. RAG context is injected automatically
    when the knowledge base has documents."""
    if req.messages:
        msgs = [m.model_dump() for m in req.messages]
    elif req.prompt:
        msgs = [
            {"role": "system", "content": "Bạn là trợ lý AI hữu ích và ngắn gọn."},
            {"role": "user", "content": req.prompt},
        ]
    else:
        raise HTTPException(400, "Either 'prompt' or 'messages' must be provided.")

    if msgs and msgs[0]["role"] == "system":
        if STYLE_INSTRUCTION not in msgs[0]["content"]:
            msgs[0]["content"] += f"\n\n{STYLE_INSTRUCTION}"
    else:
        msgs.insert(
            0,
            {
                "role": "system",
                "content": f"Bạn là trợ lý AI hữu ích và ngắn gọn.\n\n{STYLE_INSTRUCTION}",
            },
        )

    rag_used = False
    if rag.doc_count > 0:
        user_text = next(
            (m["content"] for m in reversed(msgs) if m["role"] == "user"), None
        )
        if user_text:
            context_chunks = rag.query(user_text)
            if context_chunks:
                rag_used = True
                context_block = "\n---\n".join(context_chunks)
                rag_addition = (
                    "\n\nThông tin tham khảo (truy xuất tự động):\n"
                    f"{context_block}"
                )
                if msgs and msgs[0]["role"] == "system":
                    msgs[0]["content"] += rag_addition
                else:
                    msgs.insert(0, {
                        "role": "system",
                        "content": "Bạn là trợ lý AI hữu ích và ngắn gọn." + rag_addition,
                    })

    return msgs, rag_used


# ── Endpoints ──────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "backend": engine.backend_name,
        "rag_docs": rag.doc_count,
    }


@app.post("/chat")
def chat(req: ChatRequest):
    quick_answer = _quick_demo_answer(req)
    if quick_answer is not None:
        if req.stream:
            return StreamingResponse(iter([quick_answer]), media_type="text/plain")
        return ChatResponse(answer=quick_answer, backend="demo-cached", rag_used=False)

    messages, rag_used = _resolve_messages(req)

    if req.stream:
        return StreamingResponse(
            engine.generate_stream(messages, req.max_new_tokens, req.temperature),
            media_type="text/plain",
        )

    answer = engine.generate(messages, req.max_new_tokens, req.temperature)
    return ChatResponse(
        answer=answer,
        backend=engine.backend_name,
        rag_used=rag_used,
    )


@app.post("/rag/index")
def rag_index():
    """Re-index all documents in the knowledge directory."""
    count = rag.index_documents()
    return {"indexed_chunks": count, "total_chunks": rag.doc_count}


@app.get("/rag/stats")
def rag_stats():
    return {
        "total_chunks": rag.doc_count,
        "knowledge_dir": str(cfg.knowledge_dir),
        "embed_model": cfg.embed_model,
    }
