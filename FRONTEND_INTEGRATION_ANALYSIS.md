# RapidForce Frontend Integration Analysis

## 1. Frontend của dự án chạy như thế nào?

Dự án hiện tại dùng `Gradio` làm frontend demo. File chính là `gradio_app.py`.

Luồng chạy:

1. Khi start app, model được load ngay từ đầu:
   - `TSR.from_pretrained("stabilityai/TripoSR", ...)`
   - set `chunk_size`
   - chuyển model sang `cuda:0` nếu có GPU, ngược lại dùng `cpu`
2. Người dùng upload ảnh trên giao diện Gradio.
3. Khi bấm `Generate`, Gradio chạy chuỗi callback:
   - `check_input_image(...)`
   - `preprocess(...)`
   - `generate(...)`
4. `generate(...)` gọi model để sinh `scene_codes`, sau đó extract mesh và export ra file `.obj` / `.glb`.
5. Gradio hiển thị file 3D bằng `gr.Model3D`.

## 2. Cách chạy frontend hiện tại

### Cài dependency

```bash
pip install -r requirements.txt
```

Lưu ý:
- Cần `PyTorch` phù hợp với máy/GPU của bạn.
- Model `stabilityai/TripoSR` sẽ được tải từ Hugging Face trong lần chạy đầu tiên.

### Chạy local

```bash
python gradio_app.py
```

Mặc định:
- port: `7860`
- chỉ listen local

### Một số option hữu ích

```bash
python gradio_app.py --port 7860 --listen
python gradio_app.py --port 7860 --share
python gradio_app.py --username admin --password 123456
```

Ý nghĩa:
- `--listen`: bind `0.0.0.0`, cho phép máy khác trong mạng truy cập
- `--share`: tạo public share link của Gradio
- `--username` / `--password`: bật basic auth cho UI
- `--queuesize`: giới hạn queue request của Gradio

## 3. `run.py` dùng để làm gì?

`run.py` không phải frontend. Đây là script CLI để chạy inference từ command line.

Ví dụ:

```bash
python run.py path/to/image.png --output-dir output --model-save-format glb
```

Script này phù hợp nếu bạn muốn:
- batch process ảnh
- gọi từ pipeline backend
- không cần giao diện web

## 4. Model được gọi ở chỗ nào?

### Trong `gradio_app.py`

#### Load model

Model được khởi tạo tại phần top-level của file:

```python
model = TSR.from_pretrained(
    "stabilityai/TripoSR",
    config_name="config.yaml",
    weight_name="model.ckpt",
)
```

Điều này nghĩa là model chỉ load một lần khi app start, không load lại mỗi request.

#### Gọi inference

Trong hàm `generate(image, mc_resolution, formats=["obj", "glb"])`:

```python
scene_codes = model(image, device=device)
mesh = model.extract_mesh(scene_codes, True, resolution=mc_resolution)[0]
```

Đây là 2 bước chính:

1. `model(image, device=device)`
   - chạy forward của `TSR`
   - biến ảnh đầu vào thành `scene_codes`

2. `model.extract_mesh(...)`
   - chuyển `scene_codes` thành mesh 3D
   - trả về `trimesh.Trimesh`

Sau đó mesh được export ra file tạm:

```python
mesh.export(mesh_path.name)
```

### Trong `run.py`

Tương tự, inference xảy ra ở:

```python
scene_codes = model([image], device=device)
meshes = model.extract_mesh(scene_codes, not args.bake_texture, resolution=args.mc_resolution)
```

Nếu bật `--render`, script còn gọi:

```python
render_images = model.render(scene_codes, n_views=30, return_type="pil")
```

Nếu bật `--bake-texture`, script gọi thêm:

```python
bake_output = bake_texture(meshes[0], model, scene_codes[0], args.texture_resolution)
```

## 5. Những hàm quan trọng nếu muốn tái sử dụng sang frontend khác

### Tầng UI hiện tại

Trong `gradio_app.py`, các hàm frontend đang dùng là:

- `check_input_image(input_image)`
- `preprocess(input_image, do_remove_background, foreground_ratio)`
- `generate(image, mc_resolution, formats=["obj", "glb"])`
- `run_example(image_pil)`

Trong đó:

- `preprocess(...)` là bước xử lý ảnh trước inference
- `generate(...)` là hàm quan trọng nhất để sinh output 3D

### Tầng model core

Trong `tsr/system.py`, các API code-level quan trọng là:

- `TSR.from_pretrained(...)`
  - load model từ Hugging Face hoặc local folder
- `TSR.forward(image, device)`
  - được gọi gián tiếp khi dùng `model(image, device=device)`
  - sinh `scene_codes`
- `TSR.extract_mesh(scene_codes, has_vertex_color, resolution=256, threshold=25.0)`
  - tạo mesh 3D
- `TSR.render(...)`
  - render nhiều góc nhìn 2D từ `scene_codes`

### Hàm preprocess dùng lại được

Trong `tsr/utils.py`:

- `remove_background(...)`
- `resize_foreground(...)`
- `to_gradio_3d_orientation(...)`

Lưu ý:
- `to_gradio_3d_orientation(...)` chỉ là transform để model nhìn đúng trong viewer của Gradio.
- Nếu frontend khác dùng Three.js / Babylon.js / React Three Fiber, bạn có thể không cần hàm này hoặc cần đổi orientation khác.

## 6. Frontend hiện tại gọi hàm nào / API nào?

### Câu trả lời ngắn

Hiện tại **không có REST API hoặc HTTP API riêng** kiểu `POST /generate`.

Frontend Gradio gọi trực tiếp callback Python:

- `check_input_image`
- `preprocess`
- `generate`

Thông qua event chain:

```python
submit.click(fn=check_input_image, inputs=[input_image]).success(
    fn=preprocess,
    inputs=[input_image, do_remove_background, foreground_ratio],
    outputs=[processed_image],
).success(
    fn=generate,
    inputs=[processed_image, mc_resolution],
    outputs=[output_model_obj, output_model_glb],
)
```

Nói cách khác:
- UI không gọi một backend REST endpoint tự định nghĩa
- Gradio tự quản lý request nội bộ và invoke Python function tương ứng

## 7. Nếu muốn áp dụng sang một project frontend khác thì cần làm gì?

Có 2 hướng chính.

### Hướng A: Giữ Python model, viết backend API mới

Đây là hướng thực tế nhất nếu frontend mới là:
- React
- Next.js
- Vue
- Angular
- mobile app

Bạn nên tách phần inference thành service Python, ví dụ:

1. Load model một lần khi server start
2. Tạo API như:
   - `POST /generate`
   - `POST /preprocess`
   - `GET /health`
3. Frontend upload ảnh qua multipart/form-data
4. Backend trả về:
   - file `.glb` / `.obj`
   - hoặc URL tới file đã generate
   - hoặc metadata job nếu chạy async

#### Hàm nên gọi trong backend API

Backend mới có thể tái sử dụng gần như nguyên xi:

- `preprocess(...)` từ `gradio_app.py` hoặc tách logic sang module riêng
- `model(image, device=device)`
- `model.extract_mesh(...)`

Nếu dùng viewer web hiện đại, ưu tiên trả về `.glb` vì dễ preview hơn `.obj`.

#### Gợi ý contract API

`POST /generate`

Input:
- file ảnh
- `remove_background: boolean`
- `foreground_ratio: float`
- `mc_resolution: int`
- `format: "glb" | "obj"`

Output:
- file 3D trực tiếp
hoặc
- JSON chứa đường dẫn file / URL download

### Hướng B: Dùng trực tiếp Gradio như backend UI độc lập

Nếu project frontend khác chỉ cần embed hoặc mở link ngoài:

- chạy `gradio_app.py` thành service riêng
- frontend khác chỉ link tới Gradio app

Hướng này nhanh nhưng coupling cao, khó customize UX và khó tích hợp sâu.

## 8. Nên refactor gì trước khi tích hợp sang frontend khác?

Để tái sử dụng tốt hơn, nên tách logic từ `gradio_app.py` thành module service, ví dụ:

- `services/inference.py`
  - `load_model()`
  - `preprocess_image(...)`
  - `generate_mesh(...)`
  - `export_mesh(...)`

Sau đó:
- `gradio_app.py` chỉ còn phần UI
- backend FastAPI/Flask cũng dùng lại cùng service

Lợi ích:
- tránh duplicate code
- dễ test
- dễ expose REST API
- dễ scale sang async queue / worker

## 9. Mapping nhanh: project khác nên gọi vào đâu?

Nếu bạn muốn reuse tối thiểu, hãy xem đây là entry points:

- Khởi tạo model:
  - `TSR.from_pretrained(...)`
- Tiền xử lý ảnh:
  - `preprocess(...)`
  - hoặc `remove_background(...)` + `resize_foreground(...)`
- Chạy model:
  - `model(image, device=device)`
- Lấy mesh:
  - `model.extract_mesh(...)`
- Export file:
  - `mesh.export(path)`

## 10. Cách bọc bằng FastAPI

Để frontend `JS + HTML` của project khác dùng được dự án này, cách tốt nhất là dựng một API Python riêng và expose đúng các bước inference.

### File mẫu

Repo hiện đã có file mẫu:

- `fastapi_app.py`

File này bọc trực tiếp các entry point sau:

- `TSR.from_pretrained(...)`
- `remove_background(...)`
- `resize_foreground(...)`
- `model(image, device=device)`
- `model.extract_mesh(...)`
- `mesh.export(path)`

### Cài package cần thiết

Ngoài các package hiện có trong `requirements.txt`, bạn cần cài thêm:

```bash
pip install fastapi uvicorn python-multipart
```

`python-multipart` là package cần để FastAPI nhận file upload từ form.

### Chạy API server

```bash
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000
```

Sau khi chạy:

- Swagger UI: `http://localhost:8000/docs`
- Health check: `GET http://localhost:8000/health`

### API được expose

#### `GET /health`

Trả về trạng thái server:

```json
{
  "status": "ok",
  "device": "cuda:0",
  "model": "stabilityai/TripoSR"
}
```

#### `POST /generate`

Input dạng `multipart/form-data`:

- `image`: file ảnh
- `remove_background_flag`: `true` / `false`
- `foreground_ratio`: ví dụ `0.85`
- `mc_resolution`: ví dụ `256`
- `output_format`: `obj` hoặc `glb`

Output:

- trả thẳng file 3D để frontend tải xuống hoặc render tiếp

### Luồng xử lý bên trong `fastapi_app.py`

1. Nhận ảnh từ `UploadFile`
2. Đọc ảnh bằng `PIL.Image`
3. Chạy `preprocess_image(...)`
4. Chạy:
   - `scene_codes = model(image, device=device)`
   - `mesh = model.extract_mesh(scene_codes, True, resolution=mc_resolution)[0]`
5. Export mesh ra file tạm
6. Trả file bằng `FileResponse`

### Cách frontend JS gọi API này

Ví dụ `fetch` từ frontend khác:

```js
const formData = new FormData();
formData.append("image", fileInput.files[0]);
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

const blob = await response.blob();
const url = URL.createObjectURL(blob);
```

Nếu frontend của bạn dùng `Three.js`, hãy ưu tiên `glb` vì dễ preview trực tiếp hơn `obj`.

### HTML tối thiểu để test nhanh

```html
<input type="file" id="imageInput" accept="image/*" />
<button id="generateBtn">Generate 3D</button>
<a id="downloadLink" style="display:none">Download result</a>
```

```js
document.getElementById("generateBtn").addEventListener("click", async () => {
  const input = document.getElementById("imageInput");
  const file = input.files[0];
  if (!file) return;

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
    const errorText = await response.text();
    throw new Error(errorText);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.getElementById("downloadLink");
  link.href = url;
  link.download = "rapidforce_result.glb";
  link.style.display = "inline-block";
  link.textContent = "Download GLB";
});
```

### Khi đưa sang project khác cần lưu ý gì?

- Frontend browser không chạy trực tiếp model này được; phải gọi backend Python.
- Nên load model đúng một lần khi server start, không load mỗi request.
- Nếu frontend khác chạy domain khác, cần bật CORS trong FastAPI.
- Nếu muốn scale lớn hơn, nên đổi `POST /generate` sang cơ chế async job queue.
- Nếu viewer web dùng `Three.js`, định dạng `glb` thường phù hợp hơn `obj`.

### Nếu project frontend khác cần preview ngay trên web

Bạn có thể:

1. gọi `POST /generate`
2. nhận file `.glb`
3. dùng `Three.js` + `GLTFLoader` để render

Nếu cần, bước tiếp theo nên là thêm một endpoint kiểu:

- `POST /generate-json`

Endpoint này có thể trả JSON chứa:

- `file_url`
- `filename`
- `content_type`

Để frontend quản lý file thuận tiện hơn thay vì nhận blob trực tiếp.

## 11. Kết luận

Frontend hiện tại của dự án là Gradio app trong `gradio_app.py`, không phải `run.py`.

Nếu muốn tích hợp vào frontend khác, cách phù hợp nhất là:

1. giữ phần model/inference ở Python
2. bọc nó bằng FastAPI hoặc Flask
3. để frontend mới gọi qua HTTP API

Phần cốt lõi cần reuse là:

- `preprocess(...)`
- `TSR.from_pretrained(...)`
- `model(image, device=device)`
- `model.extract_mesh(...)`

Hiện tại không có API public tự định nghĩa sẵn; chỉ có callback nội bộ của Gradio.
