# RapidForce
RapidForce là hệ thống backend cho bài toán **chuyển ảnh 2D thành model 3D** và **quản lý dữ liệu model** cho frontend.
Dự án tập trung vào hai nhóm chức năng chính:

- Tạo model 3D từ ảnh đầu vào bằng TripoSR.
- Lưu trữ, truy vấn và quản lý metadata model/user qua Cloudinary + SQLite.

## 1) Tổng quan kiến trúc

Dự án gồm 2 service FastAPI:

- `fastapi_app.py` (port `8000`): API 3D generation, auth, lưu trữ model, truy vấn user/model.
- `qwen3` (port `8001`): chatbot AI Qwen3 + RAG (tra cứu tri thức nội bộ).

Frontend chỉ cần gọi REST API, không cần chạy trực tiếp model Python.

## 2) Kỹ thuật chuyên ngành đã sử dụng

### 2.1 Tạo mô hình 3D từ ảnh đơn (Single-view 3D Reconstruction)

- Áp dụng hướng tiếp cận **single-view reconstruction** để suy luận hình học 3D từ một ảnh đầu vào.
- Hệ thống hiện thực theo kiến trúc **neural surface/mesh reconstruction** để xuất trực tiếp lưới 3D dùng được trong ứng dụng.
- **Tiền xử lý ảnh**:
  - remove background (`rembg`)
  - căn chỉnh foreground ratio để ổn định kết quả
- **Marching Cubes resolution** (`mc_resolution`) cho phép cân bằng giữa chi phí tính toán và chất lượng mesh.
- Định dạng output hỗ trợ: `glb`, `obj`.

### 2.2 Tối ưu biểu diễn và dung lượng mô hình

- **Draco compression** qua `gltf-pipeline` cho file `.glb`.
- Giảm độ dư thừa của dữ liệu hình học trước khi lưu trữ/phân phối để giảm băng thông và tăng tốc độ tải.

### 2.3 Lưu trữ dữ liệu model (Cloud + Database)

- **Cloudinary**: lưu file model 3D (resource type `raw`), trả về URL công khai.
- **SQLite (`rapidforce.db`)**: lưu metadata:
  - bảng `users`: thông tin user, `model_count`
  - bảng `models`: `url`, `image_url`, `size`, `user_id`, `created_at`
- Có index `models(user_id)` để tăng tốc truy vấn danh sách model theo user.

### 2.4 Xác thực người dùng (Auth)

- Đăng ký/đăng nhập qua email + password.
- Password được băm **PBKDF2-HMAC-SHA256 + salt** (không lưu plaintext).
- Email được kiểm tra format cơ bản và chống trùng (unique).

### 2.5 Truy hồi ngữ nghĩa và trợ lý hội thoại

- Thành phần hội thoại được tối ưu suy luận trên CPU để phù hợp môi trường triển khai phổ thông.
- **RAG (Retrieval-Augmented Generation)** sử dụng truy hồi vector để bổ sung ngữ cảnh từ tài liệu miền tri thức nội bộ.

## 3) Luồng dữ liệu chính (3D + storage)

1. Frontend upload ảnh -> `POST /generate/store`.
2. Backend tiền xử lý ảnh và thực hiện suy luận tái tạo hình học 3D để tạo mesh.
3. (Tùy chọn) nén Draco cho file `.glb`.
4. Upload model lên Cloudinary.
5. Ghi metadata vào SQLite (link `user_id` -> `model_id`).
6. Trả JSON cho frontend: URL model, kích thước, thông tin user/model.

## 4) API chính (port 8000)

- Auth:
  - `POST /auth/register`
  - `POST /auth/login`
- 3D:
  - `POST /generate`
  - `POST /generate/store`
- User/Model:
  - `GET /models`
  - `GET /models/{model_id}`
  - `GET /users`
  - `GET /users/{user_id}`
  - `GET /users/{user_id}/models`
  - `DELETE /users/{user_id}/models/{model_id}`

Chi tiết request/response xem tại `FRONTEND_API_USAGE.md`.

## 5) Giá trị thực tế của RapidForce

- Tự động hóa pipeline tạo model 3D từ ảnh cho ứng dụng web.
- Mở rộng dễ dàng cho bài toán lưu trữ và truy vấn lịch sử model theo user.
- Tách biệt rõ giữa tầng suy luận, tầng lưu trữ và tầng API để dễ bảo trì, mở rộng và đánh giá thực nghiệm.
