# RapidForce

## 1. Tổng quan dự án

RapidForce là hệ thống backend phục vụ bài toán **chuyển đổi ảnh 2D thành mô hình 3D** và **quản lý dữ liệu mô hình 3D theo người dùng**. Dự án cho phép frontend tải ảnh lên, xử lý ảnh bằng mô hình AI, sinh ra file 3D dạng `.glb` hoặc `.obj`, sau đó lưu trữ mô hình lên cloud và ghi nhận metadata vào cơ sở dữ liệu.

Ngoài chức năng tạo mô hình 3D, dự án còn tích hợp một service chatbot sử dụng Qwen3 và RAG để hỗ trợ hỏi đáp về kiến thức nội bộ, quy trình xử lý 3D và nội dung liên quan đến dự án.

## 2. Mục đích dự án

RapidForce được xây dựng với các mục tiêu chính:

- Tự động hóa quy trình tạo mô hình 3D từ một ảnh đầu vào.
- Cung cấp REST API để frontend có thể tích hợp chức năng tạo, lưu, xem và quản lý mô hình 3D.
- Lưu trữ file 3D trên Cloudinary để thuận tiện cho việc tải, chia sẻ và hiển thị trên web.
- Quản lý người dùng, lịch sử mô hình và metadata bằng SQLite.
- Tối ưu dung lượng mô hình 3D bằng Draco compression trước khi lưu trữ.
- Cung cấp chatbot AI có khả năng trả lời câu hỏi dựa trên tài liệu nội bộ của dự án.

## 3. Bài toán giải quyết

Trong nhiều ứng dụng 3D, game, thương mại điện tử, giáo dục hoặc thiết kế sản phẩm, việc tạo mô hình 3D thủ công thường tốn thời gian và đòi hỏi kỹ năng chuyên môn. RapidForce giải quyết vấn đề này bằng cách dùng mô hình AI để suy luận hình học 3D từ ảnh 2D, từ đó tạo ra mô hình có thể dùng trong các môi trường web hoặc phần mềm 3D.

Luồng sử dụng cơ bản:

1. Người dùng tải lên một ảnh 2D.
2. Backend tiền xử lý ảnh, ví dụ xóa nền và căn chỉnh đối tượng.
3. Mô hình TripoSR suy luận hình dạng 3D từ ảnh.
4. Hệ thống xuất file 3D dạng `.glb` hoặc `.obj`.
5. File có thể được nén bằng Draco để giảm dung lượng.
6. Mô hình được upload lên Cloudinary.
7. Metadata được lưu vào SQLite để frontend truy vấn lại.

## 4. Kiến trúc tổng quan

Dự án gồm hai backend chính:

| Thành phần | File/Module | Port | Vai trò |
|---|---|---:|---|
| 3D Generation API | `fastapi_app.py` | `8000` | Nhận ảnh, sinh mô hình 3D, lưu model, quản lý user/model |
| Qwen3 Chatbot API | `qwen3/` | `8001` | Chatbot AI, hỏi đáp bằng LLM kết hợp RAG |
| Model Storage | `model_storage/` | - | Nén Draco, upload Cloudinary, lưu metadata SQLite |
| 3D Reconstruction Core | `tsr/` | - | Cài đặt pipeline TripoSR và các thành phần xử lý mesh |

Frontend chỉ cần gọi REST API. Việc chạy mô hình AI, xử lý ảnh, lưu trữ và truy vấn dữ liệu đều được thực hiện ở backend.

## 5. Công nghệ sử dụng

### 5.1 Backend API

- **Python**: ngôn ngữ chính của backend.
- **FastAPI**: xây dựng REST API cho service tạo mô hình 3D và chatbot.
- **Uvicorn**: ASGI server để chạy FastAPI.
- **Pydantic**: định nghĩa schema request/response và validate dữ liệu.
- **CORS Middleware**: cho phép frontend gọi API từ domain khác.

### 5.2 AI và xử lý 3D

- **TripoSR (`stabilityai/TripoSR`)**: mô hình AI dùng cho bài toán single-image 3D reconstruction.
- **PyTorch**: framework chạy suy luận mô hình AI trên CPU hoặc GPU.
- **rembg**: tự động xóa nền ảnh đầu vào.
- **Pillow**: đọc, chuyển đổi và xử lý ảnh.
- **NumPy**: xử lý dữ liệu ảnh dạng mảng.
- **trimesh**: thao tác và xuất mesh 3D.
- **torchmcubes**: hỗ trợ thuật toán Marching Cubes để trích xuất bề mặt 3D.
- **xatlas** và **moderngl**: hỗ trợ xử lý UV, texture và rendering liên quan đến mesh.

### 5.3 Lưu trữ và cơ sở dữ liệu

- **SQLite**: lưu metadata người dùng và mô hình trong file `rapidforce.db`.
- **Cloudinary**: lưu trữ file mô hình 3D dạng raw asset và trả về URL công khai.
- **python-dotenv**: đọc cấu hình từ file `.env`.
- **Draco compression**: nén file `.glb` để giảm dung lượng truyền tải.
- **gltf-pipeline**: công cụ Node.js dùng để chạy nén Draco.

### 5.4 Chatbot và RAG

- **Qwen3**: mô hình ngôn ngữ dùng cho service chatbot.
- **llama.cpp / GGUF**: backend suy luận LLM tối ưu cho CPU.
- **ChromaDB**: vector database để lưu và truy xuất embedding tài liệu.
- **sentence-transformers**: tạo embedding phục vụ truy hồi ngữ nghĩa.
- **RAG (Retrieval-Augmented Generation)**: bổ sung ngữ cảnh từ tài liệu nội bộ trước khi chatbot trả lời.

## 6. Các chức năng chính

### 6.1 Tạo mô hình 3D từ ảnh

Endpoint chính:

- `POST /generate`

Chức năng:

- Nhận file ảnh từ frontend.
- Kiểm tra định dạng ảnh.
- Xóa nền nếu được bật.
- Điều chỉnh tỷ lệ đối tượng trong ảnh.
- Chạy TripoSR để sinh mesh 3D.
- Trả trực tiếp file `.glb` hoặc `.obj` về client.

Các tham số đáng chú ý:

| Tham số | Ý nghĩa |
|---|---|
| `image` | Ảnh đầu vào |
| `remove_background_flag` | Có xóa nền ảnh hay không |
| `foreground_ratio` | Tỷ lệ đối tượng chính trong ảnh |
| `mc_resolution` | Độ phân giải Marching Cubes, ảnh hưởng đến chất lượng mesh |
| `output_format` | Định dạng xuất: `glb` hoặc `obj` |

### 6.2 Tạo và lưu mô hình 3D

Endpoint chính:

- `POST /generate/store`

Chức năng:

- Sinh mô hình 3D từ ảnh.
- Nén Draco nếu file đầu ra là `.glb`.
- Upload mô hình lên Cloudinary.
- Lưu metadata vào SQLite.
- Liên kết mô hình với người dùng nếu có `user_id` hoặc `user_name`.
- Trả về URL mô hình, dung lượng, `model_id` và thông tin liên quan.

### 6.3 Quản lý người dùng và mô hình

Các endpoint chính:

- `POST /auth/register`: đăng ký tài khoản.
- `POST /auth/login`: đăng nhập.
- `GET /models`: lấy danh sách mô hình.
- `GET /models/{model_id}`: lấy thông tin một mô hình.
- `GET /users`: lấy danh sách người dùng.
- `GET /users/{user_id}`: lấy thông tin một người dùng.
- `GET /users/{user_id}/models`: lấy danh sách mô hình của một người dùng.
- `DELETE /users/{user_id}/models/{model_id}`: xóa mô hình thuộc một người dùng.

Hệ thống xác thực dùng email và mật khẩu. Mật khẩu không được lưu trực tiếp mà được băm bằng **PBKDF2-HMAC-SHA256** kết hợp salt.

### 6.4 Chatbot hỏi đáp nội bộ

Service chatbot nằm trong thư mục `qwen3/`.

Các endpoint chính:

- `GET /health`: kiểm tra trạng thái chatbot.
- `POST /chat`: gửi câu hỏi và nhận câu trả lời.
- `POST /rag/index`: tạo lại chỉ mục tài liệu RAG.
- `GET /rag/stats`: xem thống kê dữ liệu RAG.

Chatbot có thể tự động truy xuất tài liệu trong `qwen3/knowledge/` để bổ sung ngữ cảnh trước khi sinh câu trả lời.

## 7. Cấu trúc thư mục chính

```text
RapidForce/
├── fastapi_app.py              # API chính cho tạo và quản lý mô hình 3D
├── requirements.txt            # Danh sách thư viện Python
├── rapidforce.db               # Cơ sở dữ liệu SQLite
├── model_storage/              # Lưu trữ model, Cloudinary, SQLite, Draco
├── tsr/                        # Thành phần TripoSR và xử lý 3D
├── qwen3/                      # Service chatbot Qwen3 + RAG
├── examples/                   # Ảnh mẫu để thử nghiệm
├── figures/                    # Hình minh họa dự án
└── MARKDOWN/                   # Tài liệu hướng dẫn chi tiết
```

## 8. Luồng xử lý kỹ thuật

### 8.1 Luồng tạo file 3D

```text
Frontend
  -> Upload ảnh
  -> FastAPI /generate
  -> Tiền xử lý ảnh bằng Pillow, rembg, NumPy
  -> TripoSR suy luận mô hình 3D
  -> Trích xuất mesh
  -> Xuất file .glb hoặc .obj
  -> Trả file về frontend
```

### 8.2 Luồng tạo và lưu file 3D

```text
Frontend
  -> Upload ảnh
  -> FastAPI /generate/store
  -> Sinh file 3D
  -> Nén Draco nếu cần
  -> Upload Cloudinary
  -> Ghi metadata vào SQLite
  -> Trả JSON chứa URL và thông tin model
```

### 8.3 Luồng chatbot RAG

```text
Người dùng
  -> Gửi câu hỏi
  -> FastAPI /chat
  -> Truy xuất tài liệu liên quan trong ChromaDB
  -> Ghép ngữ cảnh vào prompt
  -> Qwen3 sinh câu trả lời
  -> Trả kết quả cho frontend
```

## 9. Cài đặt và chạy nhanh

### 9.1 Tạo môi trường ảo

```powershell
python -m venv venv
venv\Scripts\activate.bat
```

### 9.2 Cài thư viện

```powershell
pip install -r requirements.txt
```

Một số thành phần như `torchmcubes` hoặc `llama-cpp-python` có thể cần cài riêng tùy môi trường. Xem chi tiết tại:

- `MARKDOWN/SETUP_GUIDE.md`
- `MARKDOWN/FRONTEND_API_USAGE.md`
- `MARKDOWN/DATA.md`

### 9.3 Cấu hình Cloudinary

Tạo file `.env` từ `.env.example` và điền thông tin:

```env
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

### 9.4 Chạy backend tạo mô hình 3D

```powershell
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000
```

Kiểm tra:

```powershell
curl http://localhost:8000/health
```

### 9.5 Chạy chatbot Qwen3

```powershell
python -m qwen3
```

Kiểm tra:

```powershell
curl http://localhost:8001/health
```

## 10. Giá trị và ý nghĩa của dự án

RapidForce thể hiện cách kết hợp các công nghệ AI hiện đại vào một hệ thống backend hoàn chỉnh:

- Ứng dụng AI thị giác máy tính để tái tạo mô hình 3D từ ảnh 2D.
- Tổ chức pipeline xử lý ảnh, sinh mesh, nén mô hình và lưu trữ cloud.
- Xây dựng REST API phục vụ tích hợp frontend.
- Quản lý dữ liệu người dùng và lịch sử mô hình bằng cơ sở dữ liệu quan hệ nhẹ.
- Tích hợp chatbot AI và RAG để hỗ trợ tra cứu kiến thức dự án.

Về mặt báo cáo, dự án có thể được trình bày như một hệ thống AI ứng dụng trong xử lý 3D, kết hợp giữa **computer vision**, **deep learning**, **3D reconstruction**, **cloud storage**, **database management** và **large language model**.

## 11. Kết luận

RapidForce là một nền tảng backend thử nghiệm cho bài toán image-to-3D. Hệ thống không chỉ dừng ở việc chạy mô hình AI để sinh file 3D, mà còn hoàn thiện các thành phần cần thiết để triển khai thực tế như API, xác thực người dùng, lưu trữ cloud, cơ sở dữ liệu metadata, nén mô hình và chatbot hỗ trợ.

Dự án phù hợp để dùng làm minh chứng cho việc ứng dụng AI hiện đại trong xây dựng hệ thống phần mềm xử lý dữ liệu 3D.
