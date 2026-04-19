# Research Presentation Guide for RapidForce

## 1. Mục đích của tài liệu này

File này giúp trình bày `RapidForce` như một dự án nghiên cứu khoa học máy tính theo hướng:

- `Computer Vision`
- `3D Reconstruction`
- `Applied AI Systems`
- `Web-based AI Deployment`

Lưu ý quan trọng:

- Dự án này **không nên được trình bày như một mô hình AI mới do nhóm tự đề xuất**
- Dự án này **nên được trình bày như một hệ thống/pipeline ứng dụng hóa mô hình TripoSR**

## 2. Có thể gọi đề tài là gì?

Một số tên đề tài phù hợp:

- `Xây dựng hệ thống tái dựng mô hình 3D từ ảnh đơn dựa trên mô hình TripoSR`
- `Nghiên cứu triển khai mô hình tái tạo 3D từ ảnh 2D trong ứng dụng web`
- `Thiết kế pipeline sinh mô hình 3D từ ảnh đơn phục vụ hiển thị và tích hợp frontend`
- `Ứng dụng học sâu trong tái tạo mô hình 3D từ ảnh đầu vào đơn`

Nếu muốn nhấn mạnh tính hệ thống:

- `Thiết kế và triển khai hệ thống ảnh 2D sang mô hình 3D cho môi trường web`

## 3. Bài toán nghiên cứu

Bài toán trung tâm của dự án là:

- nhận một ảnh 2D của vật thể
- xử lý ảnh đầu vào
- dùng mô hình học sâu để suy ra biểu diễn 3D
- trích xuất mesh 3D
- xuất file `GLB` hoặc `OBJ`
- hiển thị hoặc tích hợp vào ứng dụng web

Bạn có thể phát biểu bài toán theo ngôn ngữ học thuật như sau:

> Nghiên cứu này tập trung vào bài toán tái dựng hình học 3D của một đối tượng từ một ảnh RGB đơn, kết hợp tiền xử lý ảnh, suy luận bằng mô hình học sâu, trích xuất lưới tam giác và triển khai kết quả trong môi trường web.

## 4. Mục tiêu nghiên cứu

### Mục tiêu tổng quát

Xây dựng một hệ thống có khả năng sinh mô hình 3D từ ảnh đầu vào đơn và tích hợp được vào frontend web.

### Mục tiêu cụ thể

- khảo sát pipeline ảnh 2D sang mô hình 3D
- tích hợp mô hình `TripoSR` vào ứng dụng thực tế
- đánh giá ảnh hưởng của tiền xử lý ảnh đến chất lượng đầu ra
- thử nghiệm các tham số như `foreground_ratio` và `mc_resolution`
- triển khai giao diện demo và backend API để phục vụ tích hợp hệ thống

## 5. Đóng góp của dự án

Để trình bày đúng bản chất, nên chia đóng góp thành 2 nhóm.

### 5.1. Thành phần kế thừa

- sử dụng mô hình `TripoSR` làm lõi tái dựng 3D từ ảnh đơn
- sử dụng `rembg` để hỗ trợ xóa nền
- sử dụng `PyTorch`, `trimesh`, `xatlas`, `Gradio`

### 5.2. Thành phần do dự án xây dựng/tích hợp

- thiết kế pipeline hoàn chỉnh từ ảnh đầu vào đến file mesh 3D
- xây dựng bước tiền xử lý ảnh:
  - xóa nền
  - căn đối tượng
  - scale foreground
- bổ sung khả năng xuất `OBJ` và `GLB`
- xây dựng giao diện demo bằng `Gradio`
- mở rộng thành backend `FastAPI` để frontend khác có thể gọi qua HTTP
- xây dựng hướng dẫn tích hợp với frontend `HTML + JavaScript`

## 6. Kiến trúc hệ thống

Bạn có thể trình bày kiến trúc của dự án theo 4 tầng:

1. `Input Layer`
   - nhận ảnh người dùng upload

2. `Preprocessing Layer`
   - xóa nền
   - resize foreground
   - chuẩn hóa đầu vào cho model

3. `Inference and Reconstruction Layer`
   - nạp model `TripoSR`
   - sinh `scene_codes`
   - trích xuất mesh bằng marching cubes

4. `Output and Deployment Layer`
   - export `OBJ` / `GLB`
   - hiển thị bằng `Gradio`
   - expose qua `FastAPI`
   - tích hợp vào frontend web

## 7. Luồng xử lý của hệ thống

Luồng hoạt động có thể mô tả như sau:

1. người dùng cung cấp ảnh đầu vào
2. hệ thống kiểm tra định dạng ảnh
3. ảnh được tiền xử lý bằng:
   - `remove_background(...)`
   - `resize_foreground(...)`
4. ảnh được đưa vào model `TSR`
5. model sinh ra `scene_codes`
6. hệ thống dùng `extract_mesh(...)` để tạo mesh 3D
7. mesh được export sang `GLB` hoặc `OBJ`
8. kết quả được hiển thị hoặc trả về cho frontend

## 8. Các thành phần kỹ thuật có thể trình bày

### 8.1. Tiền xử lý ảnh

File liên quan:

- `tsr/utils.py`
- `gradio_app.py`
- `fastapi_app.py`

Các kỹ thuật:

- phát hiện và xóa nền
- căn vật thể vào trung tâm
- điều chỉnh tỉ lệ foreground
- chuyển đổi ảnh về định dạng phù hợp cho model

### 8.2. Mô hình tái dựng 3D

File liên quan:

- `tsr/system.py`

Vai trò:

- nạp model pretrained
- chạy inference từ ảnh 2D
- sinh biểu diễn 3D trung gian
- tạo mesh đầu ra

### 8.3. Hậu xử lý và xuất dữ liệu

File liên quan:

- `run.py`
- `tsr/bake_texture.py`

Vai trò:

- extract mesh
- render preview từ nhiều góc
- bake texture
- lưu video
- xuất file `OBJ` hoặc `GLB`

### 8.4. Triển khai hệ thống

File liên quan:

- `gradio_app.py`
- `fastapi_app.py`

Vai trò:

- trình diễn mô hình bằng web UI
- triển khai API cho frontend ngoài
- minh họa khả năng áp dụng thực tế

## 9. Câu hỏi nghiên cứu có thể dùng

Nếu muốn báo cáo theo phong cách nghiên cứu, bạn nên nêu 1-3 câu hỏi nghiên cứu.

Ví dụ:

- Tiền xử lý ảnh có ảnh hưởng như thế nào tới chất lượng tái dựng 3D?
- Giá trị `foreground_ratio` ảnh hưởng ra sao đến độ đầy đủ của mesh đầu ra?
- Tham số `mc_resolution` ảnh hưởng như thế nào đến chất lượng hình học và thời gian suy luận?
- Một mô hình single-image-to-3D có thể được tích hợp hiệu quả vào kiến trúc frontend-backend hay không?

## 10. Biến thực nghiệm có thể khảo sát

Bạn có thể thiết kế thực nghiệm dựa trên các biến đã có sẵn trong dự án:

- `remove_background_flag`
- `foreground_ratio`
- `mc_resolution`
- định dạng output `glb` / `obj`
- môi trường chạy `cpu` / `gpu`

## 11. Chỉ số đánh giá có thể sử dụng

Nếu không có benchmark chính thức, bạn vẫn có thể dùng các chỉ số thực nghiệm sau:

- thời gian xử lý mỗi ảnh
- thời gian suy luận model
- thời gian extract mesh
- kích thước file output
- số lượng vertices/faces của mesh
- mức độ đầy đủ hình dạng vật thể
- chất lượng hiển thị trên viewer web

Ngoài ra có thể đánh giá định tính:

- model có giữ đúng hình khối tổng quát không
- chi tiết có bị méo không
- ảnh nền phức tạp có làm kết quả xấu đi không
- output có phù hợp để hiển thị trực tiếp trên frontend không

## 12. Thiết kế thực nghiệm gợi ý

### Thực nghiệm 1: Ảnh hưởng của tiền xử lý nền

So sánh:

- có remove background
- không remove background

Đầu ra quan sát:

- độ rõ của mesh
- mức độ nhiễu
- thời gian xử lý

### Thực nghiệm 2: Ảnh hưởng của foreground ratio

So sánh các giá trị:

- `0.70`
- `0.85`
- `1.00`

Đầu ra quan sát:

- vật thể có bị crop hay không
- mesh có đầy đủ hay không
- mức độ ổn định của reconstruction

### Thực nghiệm 3: Ảnh hưởng của marching cubes resolution

So sánh các giá trị:

- `128`
- `256`
- `320`

Đầu ra quan sát:

- độ chi tiết mesh
- thời gian xử lý
- kích thước file đầu ra

### Thực nghiệm 4: Khả năng tích hợp web

So sánh 2 cách triển khai:

- dùng trực tiếp `Gradio`
- dùng `FastAPI` + frontend web riêng

Đầu ra quan sát:

- mức độ linh hoạt
- khả năng tích hợp hệ thống
- độ thuận tiện khi mở rộng

## 13. Cách viết phần phương pháp

Bạn có thể viết ngắn gọn như sau:

> Hệ thống được xây dựng theo pipeline gồm bốn giai đoạn: tiền xử lý ảnh, suy luận 3D bằng mô hình TripoSR, trích xuất mesh và triển khai đầu ra trên giao diện web. Ở giai đoạn tiền xử lý, ảnh được xóa nền và căn chỉnh đối tượng để tăng chất lượng đầu vào. Ở giai đoạn suy luận, ảnh đã chuẩn hóa được đưa qua mô hình pretrained để sinh biểu diễn 3D trung gian. Từ biểu diễn này, hệ thống thực hiện marching cubes để tạo mesh tam giác và xuất ra định dạng `GLB` hoặc `OBJ`. Cuối cùng, kết quả được hiển thị qua Gradio hoặc cung cấp qua FastAPI cho frontend bên ngoài.

## 14. Cách viết phần đóng góp

Bạn có thể viết:

> Đóng góp chính của đề tài không nằm ở việc đề xuất một mô hình học sâu mới, mà ở việc thiết kế, triển khai và đánh giá một pipeline hoàn chỉnh cho bài toán tái dựng mô hình 3D từ ảnh đơn. Hệ thống tích hợp mô hình TripoSR với các bước tiền xử lý, trích xuất mesh, export dữ liệu và triển khai frontend-backend nhằm phục vụ mục tiêu ứng dụng thực tế.

## 15. Cách viết phần giới hạn của đề tài

Đây là phần nên có trong báo cáo để thể hiện tính khoa học và trung thực.

Ví dụ:

- mô hình lõi là pretrained model kế thừa, không phải mô hình do nhóm tự huấn luyện
- chất lượng tái dựng phụ thuộc mạnh vào ảnh đầu vào
- ảnh có nền phức tạp hoặc vật thể bị che khuất có thể làm kết quả suy giảm
- đánh giá chủ yếu mang tính thực nghiệm ứng dụng, chưa có benchmark chuẩn lớn
- hiệu năng trên CPU còn hạn chế với một số trường hợp

## 16. Cách trình bày trong slide

Một bài trình bày ngắn có thể chia như sau:

1. Bài toán và động lực
2. Mục tiêu nghiên cứu
3. Kiến trúc hệ thống
4. Pipeline xử lý ảnh sang 3D
5. Các công nghệ sử dụng
6. Thực nghiệm và tham số khảo sát
7. Kết quả minh họa
8. Hạn chế và hướng phát triển

## 17. Hướng phát triển tiếp theo

Nếu cần phần future work, có thể nêu:

- thay thế hoặc so sánh với các mô hình 3D reconstruction khác
- tự xây dựng benchmark ảnh đầu vào cho nhiều nhóm vật thể
- bổ sung đánh giá định lượng chính thức
- triển khai cơ chế async job queue cho backend
- tối ưu hiển thị trực tiếp `GLB` trên frontend
- hỗ trợ texture tốt hơn hoặc hậu xử lý mesh nâng cao

## 18. Cách kết luận đề tài

Bạn có thể kết luận theo hướng:

> Đề tài đã xây dựng thành công một hệ thống tái dựng mô hình 3D từ ảnh đơn dựa trên mô hình pretrained TripoSR. Kết quả cho thấy việc kết hợp tiền xử lý ảnh, suy luận 3D, trích xuất mesh và triển khai web có thể tạo thành một pipeline khả thi cho các ứng dụng tương tác 3D. Dù chưa đề xuất mô hình mới, hệ thống thể hiện giá trị ở khía cạnh tích hợp kỹ thuật, triển khai thực tế và khả năng mở rộng cho các nghiên cứu tiếp theo.

## 19. Tóm tắt ngắn để phát biểu miệng

Nếu cần nói ngắn gọn trong buổi bảo vệ:

> RapidForce là một hệ thống chuyển ảnh 2D thành mô hình 3D dựa trên TripoSR. Đề tài tập trung vào việc tích hợp mô hình pretrained vào một pipeline hoàn chỉnh gồm tiền xử lý ảnh, tái dựng mesh, xuất dữ liệu 3D và triển khai qua web UI/API. Giá trị chính của hệ thống nằm ở khả năng ứng dụng và đánh giá thực nghiệm, thay vì ở việc đề xuất kiến trúc học sâu mới.


Làm sao để nâng tầm mà không phải viết model mới
Bạn không cần tự train model mới. Bạn vẫn có thể làm đề tài khá tốt nếu thêm:

một bộ dữ liệu test nhỏ do bạn tự xây
bảng so sánh nhiều cấu hình input
đánh giá định tính/định lượng đầu ra
đo hiệu năng hệ thống
thử triển khai frontend thật và đánh giá usability/kỹ thuật tích hợp
đề xuất cải tiến pipeline của riêng bạn
Ví dụ phần đóng góp có thể là:

thiết kế pipeline frontend-backend cho 2D-to-3D
đánh giá vai trò của preprocessing với mô hình pretrained
đề xuất quy trình triển khai web cho mô hình 3D reconstruction
so sánh tác động của các tham số reconstruction lên chất lượng mesh  