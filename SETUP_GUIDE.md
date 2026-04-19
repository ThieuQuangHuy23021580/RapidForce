# RapidForce — Backend Setup Guide

Dự án có **2 backend chạy độc lập**:

| Backend | File | Port | Chức năng |
|---|---|---|---|
| **TripoSR** | `fastapi_app.py` | `8000` | Nhận ảnh → xuất file 3D (.glb/.obj) |
| **Qwen3 Chatbot** | `qwen3/` | `8001` | Chatbot AI hỏi đáp về dự án |

> **Windows:** Chạy `setup_backend.bat` để tự động cài tất cả.

> ⚠️ **Tất cả lệnh bên dưới đều phải chạy trong venv đã kích hoạt.**

---

## 1. Tạo & kích hoạt venv

```powershell
# Tạo (chỉ làm 1 lần)
python -m venv venv

# Kích hoạt (PowerShell) — làm mỗi lần mở terminal mới
.\venv\Scripts\Activate.ps1

# Kích hoạt (CMD)
venv\Scripts\activate.bat
```

Kích hoạt thành công khi thấy `(venv)` ở đầu dòng lệnh:
```
(venv) D:\...\RapidForce>
```

> Lỗi ExecutionPolicy trên PowerShell? Chạy một lần rồi thử lại:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

---

## 2. TripoSR Backend (`fastapi_app.py`)

### Cài dependencies

> ⚠️ Không dùng `pip install -r requirements.txt` — file đó có `transformers==4.35.0` sẽ conflict với Qwen3. Cài thủ công bên dưới.

```powershell
# (venv) phải đang active
pip install omegaconf==2.3.0 Pillow==10.1.0 einops==0.7.0 trimesh==4.0.5 rembg huggingface-hub "imageio[ffmpeg]" xatlas==0.0.9 moderngl==5.10.0 python-multipart
pip install git+https://github.com/tatsy/torchmcubes.git
```

### Chạy

```powershell
# (venv) phải đang active
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000
```

> Lần đầu chạy sẽ tự tải model `stabilityai/TripoSR` (~2 GB) từ HuggingFace.

Server sẵn sàng khi thấy:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Test

```powershell
# Kiểm tra trạng thái
curl http://localhost:8000/health
```
```json
{"status": "ok", "device": "cpu", "model": "stabilityai/TripoSR"}
```

```powershell
# Gửi ảnh → nhận file 3D (.glb)
curl -X POST http://localhost:8000/generate `
  -F "image=@path/to/your/image.png" `
  -F "output_format=glb" `
  --output result.glb
```

**Các tham số `/generate`:**

| Tham số | Mặc định | Mô tả |
|---|---|---|
| `image` | — | File ảnh upload (bắt buộc) |
| `remove_background_flag` | `true` | Tự động xoá nền |
| `foreground_ratio` | `0.85` | Tỉ lệ đối tượng trong ảnh (0.5–1.0) |
| `mc_resolution` | `256` | Độ phân giải mesh (32–320) |
| `output_format` | `glb` | Định dạng xuất: `glb` hoặc `obj` |

### Chạy bằng CLI (không cần server)

```powershell
# (venv) phải đang active
python run.py path/to/image.png --output-dir output/ --model-save-format glb
```

---

## 3. Qwen3 Chatbot Backend (`qwen3/`)

### Cài dependencies

```powershell
# (venv) phải đang active
pip install fastapi "uvicorn[standard]" pydantic huggingface_hub chromadb sentence-transformers transformers torch
```

### Cài llama-cpp-python (bắt buộc để chạy nhanh)

```powershell
# (venv) phải đang active
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

> Quá trình này mất 5–10 phút. Chờ đến khi thấy `Successfully installed llama-cpp-python`.

### Chạy

```powershell
# (venv) phải đang active
python -m qwen3
```

> Lần đầu chạy sẽ tự tải model `Qwen3-1.7B-Q4_K_M.gguf` (~1 GB) từ HuggingFace.

Server sẵn sàng khi thấy:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Test

```powershell
# Kiểm tra trạng thái
curl http://localhost:8001/health
```
```json
{"status": "ok", "backend": "llama.cpp (GGUF)", "rag_docs": 51}
```

```powershell
# Gửi câu hỏi
Set-Content -Path q.json -Value '{"prompt": "TripoSR là gì?"}' -Encoding UTF8
curl -X POST http://localhost:8001/chat -H "Content-Type: application/json" -d "@q.json"
Remove-Item q.json
```

---

## 4. Dừng Backend

```
Ctrl + C
```

---

## 5. Xử lý lỗi thường gặp

| Lỗi | Cách xử lý |
|---|---|
| Lệnh không nhận diện (`pip`, `python`...) | venv chưa được kích hoạt — chạy lại bước kích hoạt |
| `No module named 'llama_cpp'` | Cài lại llama-cpp-python (mục 3) |
| `No module named 'torchmcubes'` | `pip install git+https://github.com/tatsy/torchmcubes.git` |
| Port 8000/8001 bị chiếm | `netstat -ano \| findstr :8000` → `taskkill /PID <số> /F` |
| Chatbot dùng `transformers` (chậm) | llama-cpp chưa cài đúng, cài lại mục 3 |
| Lỗi tải model HuggingFace | Dùng VPN hoặc đặt `$env:HF_ENDPOINT="https://hf-mirror.com"` |
