# qwen3 – Fast Qwen3 LLM Package with RAG

Package riêng cho Qwen3 LLM, tối ưu chạy **CPU** bằng **llama.cpp (GGUF)** kết hợp **RAG** (Retrieval-Augmented Generation).

## Kiến trúc

```
qwen3/
├── __init__.py        # Package exports
├── __main__.py        # python -m qwen3 → chạy API server
├── config.py          # Tất cả cấu hình tập trung
├── engine.py          # LLM engine (llama.cpp → transformers fallback)
├── rag.py             # RAG pipeline (sentence-transformers + ChromaDB)
├── api.py             # FastAPI endpoints
├── knowledge/         # Đặt file .txt/.md/.csv/.json để RAG đọc
│   └── .gitkeep
├── requirements.txt   # Dependencies
└── README.md
```

## Tại sao nhanh hơn?

| Phương pháp | Tốc độ (CPU, ~200 tokens) | Giải thích |
|---|---|---|
| `transformers` (FP32) | ~60-120 giây | Chạy model gốc, chưa tối ưu |
| `llama.cpp` (Q4_K_M) | ~5-15 giây | Model nén 4-bit, C++ tối ưu cho CPU (AVX2/NEON) |

**llama.cpp** nhanh hơn **5-10x** trên CPU vì:
- Model được **quantize** từ FP32 (6.4 GB) xuống Q4 (~1.0 GB)
- Inference engine viết bằng **C/C++**, tối ưu cho CPU instructions (AVX2, AVX-512)
- Không cần PyTorch runtime overhead

## Cài đặt

```bash
# Kích hoạt venv
.\.venv\Scripts\activate    # Windows
source .venv/bin/activate   # Linux/macOS

# Cài llama-cpp-python (prebuilt CPU wheel)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

# Cài RAG dependencies
pip install chromadb sentence-transformers

# Cài FastAPI
pip install fastapi uvicorn[standard]

# Cài fallback (nếu llama.cpp gặp lỗi)
pip install transformers accelerate torch huggingface_hub
```

## Chạy API Server

```bash
# Từ thư mục gốc RapidForce
python -m qwen3

# Hoặc dùng uvicorn trực tiếp
uvicorn qwen3.api:app --host 0.0.0.0 --port 8001
```

Server sẽ:
1. Tự tải model GGUF từ HuggingFace (~1 GB, chỉ lần đầu)
2. Nếu llama.cpp lỗi → tự chuyển sang transformers
3. Tự index tài liệu trong `qwen3/knowledge/` cho RAG

## API Endpoints

### `GET /health`
```json
{ "status": "ok", "backend": "llama.cpp (GGUF)", "rag_docs": 42 }
```

### `POST /chat` – Chat completion
```json
{
  "prompt": "TripoSR hoạt động thế nào?",
  "max_new_tokens": 512,
  "temperature": 0.7,
  "stream": false,
  "use_rag": true
}
```

**Response:**
```json
{
  "answer": "TripoSR là model tái tạo 3D từ ảnh đơn...",
  "backend": "llama.cpp (GGUF)",
  "rag_used": true
}
```

**Các field:**
| Field | Type | Default | Mô tả |
|---|---|---|---|
| `prompt` | string | — | Câu hỏi đơn giản |
| `messages` | array | — | Lịch sử hội thoại (ưu tiên hơn prompt) |
| `max_new_tokens` | int | 512 | Số token tối đa sinh ra |
| `temperature` | float | 0.7 | Độ sáng tạo (0 = deterministic) |
| `stream` | bool | false | Phản hồi từng token |
| `use_rag` | bool | false | Tìm context từ knowledge base |

### `POST /rag/index` – Re-index tài liệu
```bash
curl -X POST http://localhost:8001/rag/index
```
```json
{ "indexed_chunks": 156, "total_chunks": 156 }
```

### `GET /rag/stats` – Thống kê RAG
```json
{
  "total_chunks": 156,
  "knowledge_dir": "D:/path/to/qwen3/knowledge",
  "embed_model": "all-MiniLM-L6-v2"
}
```

## Sử dụng RAG

1. Đặt file `.txt`, `.md`, `.csv`, `.json` vào thư mục `qwen3/knowledge/`
2. Khởi động server (tự động index) hoặc gọi `POST /rag/index`
3. Gửi request với `"use_rag": true`

**Ví dụ:** Đặt file `triposr_docs.txt` mô tả cách TripoSR hoạt động → khi user hỏi "TripoSR làm gì?", RAG sẽ tìm đoạn liên quan và inject vào context → model trả lời chính xác hơn.

## RAG hoạt động thế nào?

```
User question
     │
     ▼
┌─────────────┐    ┌──────────────┐
│  Embedding  │───▶│   ChromaDB   │
│ (MiniLM)    │    │ Vector Store │
└─────────────┘    └──────┬───────┘
                          │ top-k chunks
                          ▼
                   ┌──────────────┐
                   │  Build Prompt│
                   │ system +     │
                   │ context +    │
                   │ question     │
                   └──────┬───────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  Qwen3 LLM  │
                   │ (llama.cpp)  │
                   └──────┬───────┘
                          │
                          ▼
                      Answer
```

## Cấu hình

Sửa `qwen3/config.py` để thay đổi:
- `gguf_repo` / `gguf_file` – model GGUF khác
- `n_threads` – số CPU threads (mặc định = tất cả cores)
- `n_ctx` – context window (mặc định 4096)
- `chunk_size` / `chunk_overlap` – cách chia tài liệu
- `rag_top_k` – số chunks truy xuất
