import logging
import re
from typing import List, Optional

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from threading import Thread

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

app = FastAPI(title="Qwen Chat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_ID = "rd211/Qwen3-1.7B-Instruct"

logging.info(f"Loading tokenizer from {MODEL_ID} ...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

logging.info(f"Loading model from {MODEL_ID} ...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype="auto",
    device_map="auto",
)
model.eval()
logging.info(f"Model loaded on {model.device}")


class Message(BaseModel):
    role: str = Field(..., description="'system', 'user', or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    prompt: Optional[str] = Field(
        None,
        description="Simple prompt string. Ignored if 'messages' is provided.",
    )
    messages: Optional[List[Message]] = Field(
        None,
        description="Full conversation history. Takes priority over 'prompt'.",
    )
    max_new_tokens: int = Field(200, ge=1, le=2048)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    stream: bool = Field(False, description="Stream response token by token.")


class ChatResponse(BaseModel):
    answer: str


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_thinking(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


def build_messages(req: ChatRequest) -> List[dict]:
    if req.messages:
        return [m.model_dump() for m in req.messages]

    if req.prompt:
        return [
            {"role": "system", "content": "Bạn là trợ lý AI hữu ích và ngắn gọn."},
            {"role": "user", "content": req.prompt},
        ]

    raise HTTPException(
        status_code=400,
        detail="Either 'prompt' or 'messages' must be provided.",
    )


def generate_answer(messages: List[dict], max_new_tokens: int, temperature: float) -> str:
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    do_sample = temperature > 0
    gen_kwargs = {
        **inputs,
        "max_new_tokens": max_new_tokens,
        "pad_token_id": tokenizer.eos_token_id,
    }
    if do_sample:
        gen_kwargs["temperature"] = temperature
        gen_kwargs["do_sample"] = True

    with torch.no_grad():
        outputs = model.generate(**gen_kwargs)

    generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
    raw = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
    return strip_thinking(raw)


def generate_stream(messages: List[dict], max_new_tokens: int, temperature: float):
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    do_sample = temperature > 0
    gen_kwargs = {
        **inputs,
        "max_new_tokens": max_new_tokens,
        "pad_token_id": tokenizer.eos_token_id,
        "streamer": streamer,
    }
    if do_sample:
        gen_kwargs["temperature"] = temperature
        gen_kwargs["do_sample"] = True

    thread = Thread(target=model.generate, kwargs=gen_kwargs)
    thread.start()

    for token_text in streamer:
        yield token_text

    thread.join()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL_ID,
        "device": str(model.device),
    }


@app.post("/chat")
def chat(req: ChatRequest):
    messages = build_messages(req)

    if req.stream:
        return StreamingResponse(
            generate_stream(messages, req.max_new_tokens, req.temperature),
            media_type="text/plain",
        )

    answer = generate_answer(messages, req.max_new_tokens, req.temperature)
    return ChatResponse(answer=answer)
