# Frontend Guide: Using RapidForce API

## Mục tiêu

File này hướng dẫn cách để một project frontend khác gọi API của `RapidForce` sau khi backend `FastAPI` đã được dựng.

Dự án hiện có **2 backend API**:

- `fastapi_app.py` — ảnh 2D -> model 3D (`TripoSR`)
- `qwen3/` package — chat AI (`Qwen3-1.7B`) + RAG, tối ưu cho CPU bằng llama.cpp

Frontend có thể là:

- HTML + JavaScript thuần
- React
- Vue
- Angular
- Next.js

## 1. Backend cần chạy trước

Frontend không chạy trực tiếp model Python được. Trước tiên cần chạy API server.

### Service 1: 3D Generation (TripoSR)

```bash
.\.venv\Scripts\python.exe -m uvicorn fastapi_app:app --host 0.0.0.0 --port 8000
```

Sau khi chạy:

- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### Service 2: Chat AI + RAG (Qwen3-1.7B)

```bash
# Package mới (nhanh hơn 5-10x trên CPU nhờ llama.cpp + GGUF)
.\.venv\Scripts\python.exe -m qwen3
```

Sau khi chạy:

- Swagger UI: `http://localhost:8001/docs`
- Health check: `http://localhost:8001/health`
- Backend tự chọn: **llama.cpp (GGUF)** nếu có, fallback sang **transformers**

### Tổng quan kiến trúc

```
Frontend (HTML + JS)
    |
    |--- POST /generate   --> localhost:8000  (3D model)
    |--- POST /chat        --> localhost:8001  (AI chat)
    |--- POST /chat?rag    --> localhost:8001  (AI chat + RAG context)
    |--- POST /rag/index   --> localhost:8001  (re-index tài liệu)
    |--- GET  /rag/stats   --> localhost:8001  (thống kê RAG)
```

## 2. API Service 1: 3D Generation (port 8000)

### `GET /health`

Dùng để kiểm tra backend 3D còn hoạt động không.

Ví dụ response:

```json
{
  "status": "ok",
  "device": "cuda:0",
  "model": "stabilityai/TripoSR"
}
```

### `POST /generate`

Đây là endpoint chính để frontend gửi ảnh lên và nhận file 3D trả về.

#### Content-Type

`multipart/form-data`

#### Form fields

- `image`: file ảnh đầu vào
- `remove_background_flag`: `true` hoặc `false`
- `foreground_ratio`: số thực từ `0.5` đến `1.0`
- `mc_resolution`: một trong các giá trị:
  - `32`
  - `64`
  - `96`
  - `128`
  - `160`
  - `192`
  - `224`
  - `256`
  - `288`
  - `320`
- `output_format`: `glb` hoặc `obj`

#### Output

API trả trực tiếp file 3D:

- `glb` nếu `output_format=glb`
- `obj` nếu `output_format=obj`

Khuyến nghị:

- dùng `glb` nếu frontend muốn preview bằng `Three.js`
- dùng `obj` nếu project của bạn đang xử lý pipeline cũ đã quen với OBJ

## 3. API Service 2: Chat AI + RAG (port 8001)

> **Phiên bản mới**: package `qwen3/` thay thế `qwen_api.py` cũ, nhanh hơn 5-10x trên CPU nhờ llama.cpp + GGUF, và hỗ trợ RAG.

### `GET /health`

Dùng để kiểm tra backend chat còn hoạt động không.

Ví dụ response:

```json
{
  "status": "ok",
  "backend": "llama.cpp (GGUF)",
  "rag_docs": 42
}
```

### `POST /chat`

Endpoint chính để frontend gửi câu hỏi và nhận câu trả lời từ AI.

#### Content-Type

`application/json`

#### Request body

**Cách 1: gửi prompt đơn giản**

```json
{
  "prompt": "Giải thích machine learning ngắn gọn",
  "max_new_tokens": 512,
  "temperature": 0.7
}
```

**Cách 2: gửi conversation history**

```json
{
  "messages": [
    {"role": "system", "content": "Bạn là trợ lý AI."},
    {"role": "user", "content": "MongoDB là gì?"}
  ],
  "max_new_tokens": 512,
  "temperature": 0.7
}
```

**Cách 3: streaming (nhận từng token)**

```json
{
  "prompt": "Giải thích neural network",
  "max_new_tokens": 512,
  "stream": true
}
```

**Cách 4: sử dụng RAG (truy xuất context từ knowledge base)**

```json
{
  "prompt": "TripoSR hoạt động thế nào?",
  "max_new_tokens": 512,
  "use_rag": true
}
```

Khi `use_rag: true`, hệ thống sẽ tự động tìm các đoạn tài liệu liên quan từ knowledge base và inject vào system prompt trước khi gọi LLM.

#### Tham số

- `prompt`: chuỗi câu hỏi đơn giản (bỏ qua nếu có `messages`)
- `messages`: mảng conversation history đầy đủ (ưu tiên hơn `prompt`)
- `max_new_tokens`: số token tối đa sinh ra, từ `1` đến `4096`, mặc định `512`
- `temperature`: độ sáng tạo, từ `0.0` đến `2.0`, mặc định `0.7`
- `stream`: `true` để nhận streaming, `false` để nhận JSON, mặc định `false`
- `use_rag`: `true` để tìm context từ knowledge base, `false` để chat bình thường, mặc định `false`

#### Response (không stream)

```json
{
  "answer": "Machine learning là một nhánh của trí tuệ nhân tạo...",
  "backend": "llama.cpp (GGUF)",
  "rag_used": true
}
```

#### Response (stream)

Trả về `text/plain` với nội dung được gửi từng phần qua HTTP chunked response.

### `POST /rag/index`

Re-index tất cả tài liệu trong thư mục `qwen3/knowledge/`.

```js
const res = await fetch("http://localhost:8001/rag/index", { method: "POST" });
const data = await res.json();
// { "indexed_chunks": 156, "total_chunks": 156 }
```

### `GET /rag/stats`

Xem thống kê RAG hiện tại.

```json
{
  "total_chunks": 156,
  "knowledge_dir": "D:/path/to/qwen3/knowledge",
  "embed_model": "all-MiniLM-L6-v2"
}
```

### Ví dụ gọi `/chat` từ JS (không stream)

```js
async function askQwen(prompt, useRag = false) {
  const response = await fetch("http://localhost:8001/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: prompt,
      max_new_tokens: 512,
      temperature: 0.7,
      use_rag: useRag,
    }),
  });

  if (!response.ok) {
    throw new Error("Chat request failed");
  }

  const data = await response.json();
  return data.answer;
}

// Chat bình thường
const answer1 = await askQwen("Giải thích machine learning");

// Chat với RAG (tìm context từ knowledge base)
const answer2 = await askQwen("TripoSR hoạt động thế nào?", true);
```

### Ví dụ gọi `/chat` từ JS (streaming)

```js
async function askQwenStream(prompt, onToken) {
  const response = await fetch("http://localhost:8001/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: prompt,
      max_new_tokens: 200,
      temperature: 0.7,
      stream: true,
    }),
  });

  if (!response.ok) {
    throw new Error("Chat stream failed");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value, { stream: true });
    onToken(text);
  }
}

// Sử dụng:
askQwenStream("Giải thích AI", (token) => {
  document.getElementById("chatOutput").textContent += token;
});
```

### Ví dụ gọi `/chat` với conversation history

```js
async function chatWithHistory(messages) {
  const response = await fetch("http://localhost:8001/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: messages,
      max_new_tokens: 300,
      temperature: 0.7,
    }),
  });

  if (!response.ok) {
    throw new Error("Chat request failed");
  }

  const data = await response.json();
  return data.answer;
}

// Sử dụng:
const answer = await chatWithHistory([
  { role: "system", content: "Bạn là trợ lý AI về 3D modeling." },
  { role: "user", content: "GLB và OBJ khác nhau thế nào?" },
]);
```

## 4. Luồng tích hợp trong frontend

### Luồng 3D Generation

1. Người dùng chọn ảnh
2. Frontend tạo `FormData`
3. Frontend gọi `POST /generate` (port 8000)
4. Nhận `Blob` trả về
5. Tạo URL từ blob
6. Cho phép tải file hoặc đưa vào viewer 3D

### Luồng Chat AI

1. Người dùng nhập câu hỏi
2. Frontend gọi `POST /chat` (port 8001) bằng JSON
3. Nhận `answer` hoặc stream token
4. Hiển thị câu trả lời lên UI

## 5. Ví dụ HTML + JS tối thiểu cho 3D Generation

### HTML

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>RapidForce API Demo</title>
  </head>
  <body>
    <h1>RapidForce API Demo</h1>

    <input type="file" id="imageInput" accept="image/*" />
    <br /><br />

    <label>
      <input type="checkbox" id="removeBg" checked />
      Remove background
    </label>
    <br /><br />

    <label for="foregroundRatio">Foreground ratio:</label>
    <input type="number" id="foregroundRatio" value="0.85" min="0.5" max="1.0" step="0.05" />
    <br /><br />

    <label for="mcResolution">MC resolution:</label>
    <select id="mcResolution">
      <option value="128">128</option>
      <option value="256" selected>256</option>
      <option value="320">320</option>
    </select>
    <br /><br />

    <label for="outputFormat">Output format:</label>
    <select id="outputFormat">
      <option value="glb" selected>GLB</option>
      <option value="obj">OBJ</option>
    </select>
    <br /><br />

    <button id="generateBtn">Generate 3D</button>
    <p id="status"></p>
    <a id="downloadLink" style="display: none">Download result</a>

    <script src="./app.js"></script>
  </body>
</html>
```

### JavaScript

```js
const API_BASE_URL = "http://localhost:8000";

const imageInput = document.getElementById("imageInput");
const removeBg = document.getElementById("removeBg");
const foregroundRatio = document.getElementById("foregroundRatio");
const mcResolution = document.getElementById("mcResolution");
const outputFormat = document.getElementById("outputFormat");
const generateBtn = document.getElementById("generateBtn");
const statusText = document.getElementById("status");
const downloadLink = document.getElementById("downloadLink");

generateBtn.addEventListener("click", async () => {
  const file = imageInput.files[0];

  if (!file) {
    statusText.textContent = "Please choose an image first.";
    return;
  }

  const formData = new FormData();
  formData.append("image", file);
  formData.append("remove_background_flag", String(removeBg.checked));
  formData.append("foreground_ratio", foregroundRatio.value);
  formData.append("mc_resolution", mcResolution.value);
  formData.append("output_format", outputFormat.value);

  statusText.textContent = "Generating 3D model...";
  downloadLink.style.display = "none";

  try {
    const response = await fetch(`${API_BASE_URL}/generate`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || "Generate failed");
    }

    const blob = await response.blob();
    const fileExt = outputFormat.value;
    const url = URL.createObjectURL(blob);

    downloadLink.href = url;
    downloadLink.download = `rapidforce_result.${fileExt}`;
    downloadLink.textContent = `Download ${fileExt.toUpperCase()}`;
    downloadLink.style.display = "inline-block";

    statusText.textContent = "Done.";
  } catch (error) {
    statusText.textContent = `Error: ${error.message}`;
  }
});
```

## 6. Cách gọi từ React

Ví dụ ngắn:

```js
async function generateModel(file) {
  const formData = new FormData();
  formData.append("image", file);
  formData.append("remove_background_flag", "true");
  formData.append("foreground_ratio", "0.85");
  formData.append("mc_resolution", "256");
  formData.append("output_format", "glb");

  const response = await fetch("http://localhost:8000/generate", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Generate failed");
  }

  return await response.blob();
}
```

Bạn có thể:

- lưu blob để download
- tạo `URL.createObjectURL(blob)`
- đưa URL đó vào viewer `Three.js`

## 7. Preview bằng Three.js

Nếu backend trả về `glb`, frontend có thể preview bằng:

- `three`
- `GLTFLoader`

Luồng:

1. gọi API để lấy blob
2. tạo blob URL
3. load blob URL bằng `GLTFLoader`
4. render scene lên canvas

Khuyến nghị:

- ưu tiên `glb` thay vì `obj`
- `glb` gọn hơn và dễ load hơn trong trình duyệt

## 8. Kiểm tra backend trước khi gọi API

Frontend nên gọi `GET /health` khi khởi động hoặc trước khi submit để biết backend có sẵn sàng không.

Ví dụ:

```js
async function checkHealth(port) {
  const response = await fetch(`http://localhost:${port}/health`);
  if (!response.ok) {
    throw new Error(`Backend on port ${port} is unavailable`);
  }
  return await response.json();
}

// Kiểm tra cả 2 service
const health3D = await checkHealth(8000);
const healthChat = await checkHealth(8001);
```

## 9. Xử lý lỗi phía frontend

Frontend nên xử lý các trường hợp:

- chưa chọn file
- upload không phải ảnh
- backend chưa chạy
- backend trả lỗi `400`
- thời gian generate lâu

Khuyến nghị UI:

- disable nút submit trong lúc đang generate
- hiển thị trạng thái loading
- hiển thị lỗi rõ ràng cho người dùng

## 10. Vấn đề CORS

Nếu frontend chạy khác domain hoặc khác port với backend, bạn có thể gặp lỗi CORS.

Ví dụ:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`

Khi đó cần bật CORS trong `FastAPI`.

Ví dụ cấu hình:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Nếu frontend là HTML file chạy local hoặc project khác port, đây gần như là bước bắt buộc.

## 11. Những gì frontend cần biết, và không cần biết

Frontend cần biết:

- URL của 2 backend
- endpoint `/health` (cả 2 service)
- endpoint `/generate` (port 8000) — gửi `FormData`, nhận file 3D
- endpoint `/chat` (port 8001) — gửi `JSON`, nhận text
- tham số của từng endpoint

Frontend không cần biết:

- `TSR.from_pretrained(...)`
- `model.extract_mesh(...)`
- `remove_background(...)`
- `AutoModelForCausalLM.from_pretrained(...)`
- `tokenizer.apply_chat_template(...)`
- logic nội bộ của PyTorch / transformers

Những phần này nằm hoàn toàn ở backend Python.

## 12. Khuyến nghị tích hợp thực tế

Nếu project frontend của bạn là app thật, nên:

- dùng `glb` làm output mặc định
- thêm loading state
- thêm timeout/retry hợp lý
- lưu file vào storage riêng nếu cần dùng lại
- cân nhắc backend async nếu thời gian generate dài

## 13. Tóm tắt nhanh

Frontend cần nhớ:

### Cho 3D Generation (port 8000)

1. Chạy backend `fastapi_app.py`
2. Gọi `POST /generate` bằng `FormData`
3. Nhận file `.glb` hoặc `.obj`
4. Download hoặc preview bằng `Three.js`

### Cho Chat AI + RAG (port 8001)

1. Chạy backend `python -m qwen3`
2. (Tuỳ chọn) Đặt tài liệu vào `qwen3/knowledge/` để dùng RAG
3. Gọi `POST /chat` bằng `JSON`, thêm `"use_rag": true` nếu cần RAG
4. Nhận `answer` hoặc stream token
5. Gọi `POST /rag/index` nếu thêm tài liệu mới

### Bảng tham chiếu nhanh

| Chức năng       | Service          | Port   | Endpoint         | Input            | Output           |
|-----------------|------------------|--------|------------------|------------------|------------------|
| Health check 3D | `fastapi_app.py` | `8000` | `GET /health`    | —                | JSON status      |
| Generate 3D     | `fastapi_app.py` | `8000` | `POST /generate` | `FormData` ảnh   | file `.glb/.obj` |
| Health check AI | `qwen3` package  | `8001` | `GET /health`    | —                | JSON status      |
| Chat AI         | `qwen3` package  | `8001` | `POST /chat`     | JSON prompt      | JSON answer      |
| Chat AI + RAG   | `qwen3` package  | `8001` | `POST /chat`     | JSON + use_rag   | JSON answer      |
| Chat AI stream  | `qwen3` package  | `8001` | `POST /chat`     | JSON + stream    | text stream      |
| RAG re-index    | `qwen3` package  | `8001` | `POST /rag/index`| —                | JSON stats       |
| RAG stats       | `qwen3` package  | `8001` | `GET /rag/stats` | —                | JSON stats       |
