# TÀI LIỆU TRIỂN KHAI: TỐI ƯU HÓA VÀ LƯU TRỮ MODEL 3D

Tài liệu này mô tả **kỹ thuật đang dùng thực tế trong project**:
- Tạo model 3D bằng TripoSR
- Nén Draco bằng `gltf-pipeline`
- Upload lên **Cloudinary**
- Lưu metadata vào **SQLite**
- Cung cấp API cho frontend lấy `user` và `model`

---

## 1. Nén Draco (Draco Compression)

Sử dụng `gltf-pipeline` để nén dữ liệu hình học, giảm dung lượng file `.glb`.

### Cài đặt
```bash
npm install -g gltf-pipeline
```

### Thực thi
```bash
gltf-pipeline -i input.glb -o output.glb -d -s
```

---

## 2. Thiết kế Cơ sở dữ liệu (SQLite Schema)

Project lưu metadata cục bộ trong file `rapidforce.db`.

```sql
CREATE TABLE models (
    model_id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,                -- URL Cloudinary
    size REAL,                        -- Dung lượng file (MB)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL,
    model_id INT,
    CONSTRAINT fk_model
        FOREIGN KEY(model_id)
        REFERENCES models(model_id)
        ON DELETE SET NULL
);
```

---

## 3. Triển khai Cloudinary Storage (Python SDK)

### Cài đặt thư viện
```bash
pip install cloudinary
```

### Biến môi trường
```env
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
CLOUDINARY_FOLDER=outputs
```

### Logic upload (đang dùng)
```python
import os
from pathlib import Path
import cloudinary
import cloudinary.uploader

def upload_model_and_get_meta(local_path, cloud_name, api_key, api_secret, folder="outputs"):
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )

    local_file = Path(local_path)
    result = cloudinary.uploader.upload(
        str(local_file),
        folder=folder.strip("/"),
        resource_type="raw",   # GLB/OBJ upload ổn định
        use_filename=True,
        unique_filename=True,
        overwrite=False,
    )

    return {
        "url": result.get("secure_url") or result.get("url"),
        "size": os.path.getsize(local_file) / (1024 * 1024),
        "blob_name": result.get("public_id", ""),
    }
```

---

## 4. API đã tích hợp cho Frontend

### Tạo + lưu model
- `POST /generate/store`
  - Input: ảnh + tham số generate + `user_id` hoặc `user_name`
  - Output: `model_id`, `url`, `size_mb`, `user_id`, `blob_name`

### Lấy dữ liệu model
- `GET /models`
- `GET /models/{model_id}`

### Lấy dữ liệu user
- `GET /users`
- `GET /users/{user_id}`

---

## 5. Quy trình vận hành (Execution Workflow)

1. **Generation:** Backend tạo file `.glb`/`.obj` từ ảnh đầu vào.
2. **Compression:** Nếu là `.glb` và `compress_draco=true`, chạy Draco bằng `gltf-pipeline`.
3. **Storage Upload:** Upload file cuối lên Cloudinary (`resource_type=raw`).
4. **Database Sync:**
   - Chèn `url`, `size` vào bảng `models`
   - Lấy `model_id` vừa tạo và liên kết với `users.model_id`
5. **Delivery:** Frontend lấy URL qua API `/models` hoặc `/users` rồi hiển thị/model-view.

---

## 6. Test nhanh end-to-end

```bash
curl -X POST http://localhost:8000/generate/store \
  -F "image=@examples/chair.png" \
  -F "output_format=glb" \
  -F "compress_draco=true" \
  -F "user_name=demo_user"
```

Ví dụ response:
```json
{
  "model_id": 1,
  "url": "https://res.cloudinary.com/<cloud>/raw/upload/.../outputs/xxx_draco.glb",
  "size_mb": 0.0011,
  "user_id": 1,
  "blob_name": "outputs/xxx_draco.glb"
}
```