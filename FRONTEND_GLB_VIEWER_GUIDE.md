# Frontend JS+HTML: Lấy GLB từ Backend và Hiển Thị Model

## Mục tiêu

File này hướng dẫn cách để một frontend `HTML + JavaScript`:

1. upload ảnh lên backend `FastAPI`
2. nhận file `GLB` trả về từ API
3. hiển thị model 3D trực tiếp trên màn hình

Backend giả định đang chạy từ file `fastapi_app.py` với endpoint:

- `POST /generate`

## 1. Điều kiện trước khi làm frontend

Backend phải chạy trước:

```bash
.\.venv\Scripts\python.exe -m uvicorn fastapi_app:app --host 0.0.0.0 --port 8000
```

Mặc định API sẽ ở:

- `http://localhost:8000`

## 2. Cách frontend lấy file GLB từ backend

Frontend sẽ gửi `multipart/form-data` tới:

- `POST http://localhost:8000/generate`

Các field cần gửi:

- `image`: file ảnh
- `remove_background_flag`: `true` hoặc `false`
- `foreground_ratio`: ví dụ `0.85`
- `mc_resolution`: ví dụ `256`
- `output_format`: phải là `glb`

Backend sẽ trả về file `.glb` dạng binary response.

## 3. Luồng hiển thị model trên màn hình

Luồng frontend:

1. người dùng chọn ảnh
2. frontend gọi API `/generate`
3. backend trả về file `GLB`
4. frontend chuyển response thành `Blob`
5. frontend tạo `blob URL`
6. dùng `Three.js` + `GLTFLoader` để load model
7. render model lên `canvas`

## 4. Cấu trúc file frontend tối thiểu

Bạn có thể tạo 2 file:

- `index.html`
- `app.js`

## 5. File `index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>RapidForce GLB Viewer</title>
    <style>
      body {
        font-family: Arial, sans-serif;
        margin: 20px;
      }

      #viewer {
        width: 100%;
        height: 600px;
        border: 1px solid #ccc;
        margin-top: 16px;
      }

      #controls {
        display: flex;
        gap: 12px;
        align-items: center;
        flex-wrap: wrap;
      }

      #status {
        margin-top: 12px;
      }
    </style>
  </head>
  <body>
    <h1>RapidForce GLB Viewer</h1>

    <div id="controls">
      <input type="file" id="imageInput" accept="image/*" />
      <button id="generateBtn">Generate and Show GLB</button>
    </div>

    <p id="status">Ready.</p>
    <div id="viewer"></div>

    <script type="module" src="./app.js"></script>
  </body>
</html>
```

## 6. File `app.js`

```js
import * as THREE from "https://unpkg.com/three@0.165.0/build/three.module.js";
import { OrbitControls } from "https://unpkg.com/three@0.165.0/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "https://unpkg.com/three@0.165.0/examples/jsm/loaders/GLTFLoader.js";

const API_URL = "http://localhost:8000/generate";

const imageInput = document.getElementById("imageInput");
const generateBtn = document.getElementById("generateBtn");
const statusText = document.getElementById("status");
const viewer = document.getElementById("viewer");

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf3f4f6);

const camera = new THREE.PerspectiveCamera(
  45,
  viewer.clientWidth / viewer.clientHeight,
  0.1,
  1000
);
camera.position.set(0, 1, 3);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(viewer.clientWidth, viewer.clientHeight);
renderer.setPixelRatio(window.devicePixelRatio);
viewer.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 1.5);
scene.add(hemiLight);

const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
dirLight.position.set(3, 5, 2);
scene.add(dirLight);

const grid = new THREE.GridHelper(10, 10);
scene.add(grid);

const loader = new GLTFLoader();

let currentModel = null;
let currentBlobUrl = null;

function clearCurrentModel() {
  if (currentModel) {
    scene.remove(currentModel);
    currentModel.traverse((child) => {
      if (child.geometry) child.geometry.dispose?.();
      if (child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach((material) => material.dispose?.());
        } else {
          child.material.dispose?.();
        }
      }
    });
    currentModel = null;
  }

  if (currentBlobUrl) {
    URL.revokeObjectURL(currentBlobUrl);
    currentBlobUrl = null;
  }
}

async function requestGlb(file) {
  const formData = new FormData();
  formData.append("image", file);
  formData.append("remove_background_flag", "true");
  formData.append("foreground_ratio", "0.85");
  formData.append("mc_resolution", "256");
  formData.append("output_format", "glb");

  const response = await fetch(API_URL, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || "Failed to generate GLB");
  }

  return await response.blob();
}

function showGlb(blob) {
  clearCurrentModel();

  currentBlobUrl = URL.createObjectURL(blob);

  loader.load(
    currentBlobUrl,
    (gltf) => {
      currentModel = gltf.scene;
      scene.add(currentModel);

      const box = new THREE.Box3().setFromObject(currentModel);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);

      currentModel.position.sub(center);

      camera.position.set(0, maxDim * 0.8, maxDim * 2.2);
      camera.lookAt(0, 0, 0);
      controls.target.set(0, 0, 0);
      controls.update();

      statusText.textContent = "Model loaded successfully.";
    },
    undefined,
    (error) => {
      statusText.textContent = `Viewer error: ${error.message || error}`;
    }
  );
}

generateBtn.addEventListener("click", async () => {
  const file = imageInput.files[0];
  if (!file) {
    statusText.textContent = "Please choose an image first.";
    return;
  }

  try {
    statusText.textContent = "Generating GLB from backend...";
    generateBtn.disabled = true;

    const blob = await requestGlb(file);
    showGlb(blob);
  } catch (error) {
    statusText.textContent = `Error: ${error.message}`;
  } finally {
    generateBtn.disabled = false;
  }
});

window.addEventListener("resize", () => {
  const width = viewer.clientWidth;
  const height = viewer.clientHeight;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
});

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

animate();
```

## 7. Cách chạy frontend này

Vì file `app.js` dùng `type="module"`, bạn nên chạy frontend bằng web server đơn giản thay vì mở file HTML trực tiếp bằng `file://`.

Ví dụ:

```bash
python -m http.server 5500
```

Sau đó mở:

- `http://localhost:5500`

## 8. Nếu frontend bị lỗi CORS

Nếu frontend chạy ở:

- `http://localhost:5500`

và backend chạy ở:

- `http://localhost:8000`

thì backend cần bật CORS.

Ví dụ thêm vào `fastapi_app.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 9. Vì sao nên dùng GLB thay vì OBJ

Để hiển thị trực tiếp trên web, `GLB` phù hợp hơn `OBJ` vì:

- là một file duy nhất
- load nhanh và gọn hơn
- hỗ trợ tốt với `GLTFLoader`
- ít phải xử lý thêm ở frontend

Nếu mục tiêu là "show trực tiếp như Gradio", hãy ưu tiên `GLB`.

## 10. Điểm khác với `gradio_app.py`

Trong `gradio_app.py`, Gradio dùng `gr.Model3D` để tự render file 3D.

Ở frontend `JS + HTML`, bạn không có component đó, nên cần thay bằng:

- `Three.js`
- `GLTFLoader`
- `canvas` của WebGL

Nói cách khác:

- Gradio: render file 3D bằng component sẵn có
- Frontend web: render file 3D bằng viewer 3D trong browser

## 11. Tóm tắt nhanh

Để show model trực tiếp trên màn hình:

1. frontend gửi ảnh tới `POST /generate`
2. backend trả về file `GLB`
3. frontend chuyển response thành `Blob`
4. dùng `URL.createObjectURL(blob)`
5. load URL đó bằng `GLTFLoader`
6. render model bằng `Three.js`

Đây là cách gần nhất với trải nghiệm hiển thị model trực tiếp như `gradio_app.py`.
