# Project Requirements Document

## Hệ thống Data Lakehouse Phát hiện Gian lận Tài chính trong Thời gian thực

**Phiên bản:** 1.0
**Ngày:** 9/11/2025

---

### 1. Giới thiệu và Bối cảnh

#### 1.1. Vấn đề

Gian lận thẻ tín dụng, đặc biệt là các giao dịch không xuất trình thẻ (Card-Not-Present), gây ra thiệt hại tài chính lớn cho cả khách hàng và tổ chức tài chính. Các phương pháp phát hiện truyền thống dựa trên quy tắc (rule-based) thường cứng nhắc và không thể bắt kịp các thủ đoạn gian lận ngày càng tinh vi.

#### 1.2. Mục tiêu dự án

Xây dựng một nền tảng dữ liệu hiện đại (Data Lakehouse) có khả năng phân tích luồng giao dịch thẻ tín dụng trong thời gian thực, tự động phát hiện các hành vi đáng ngờ bằng Machine Learning và cung cấp công cụ thông minh để hỗ trợ các chuyên viên phân tích xác minh cảnh báo một cách nhanh chóng.

### 2. Đối tượng người dùng (User Personas)

1. **Data Engineer (Kỹ Sư Dữ liệu):**

   - **Nhu cầu:** Cần một hệ thống ổn định, dễ bảo trì và có khả năng mở rộng để xử lý lượng lớn dữ liệu giao dịch.
   - **Vai trò trong hệ thống:** Xây dựng và duy trì pipeline dữ liệu.
2. **Fraud Analyst (Chuyên Viên Phân tích Gian Lận):**

   - **Nhu cầu:** Cần được cảnh báo ngay lập tức về các giao dịch đáng ngờ. Cần có công cụ trực quan và linh hoạt để điều tra lịch sử giao dịch, tìm kiếm các mẫu bất thường và đưa ra quyết định (chặn/cho phép giao dịch) một cách nhanh chóng.
   - **Vai trò trong hệ thống:** Người dùng cuối, sử dụng Dashboard và Chatbot.

### 3. Yêu cầu Chức năng (Functional Requirements)

| ID              | Chức năng                                    | Mô tả chi tiết                                                                                                                                                                                                                                                                                                                         |
| :-------------- | :--------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FR-01** | **Thu thập dữ liệu thời gian thực** | Hệ thống phải có khả năng tiếp nhận luồng dữ liệu giao dịch từ các hệ thống nguồn (giả lập qua Kafka) với độ trễ dưới 1 giây.                                                                                                                                                                                   |
| **FR-02** | **Phát hiện gian lận bằng ML**       | Đối với mỗi giao dịch đến, hệ thống phải áp dụng một mô hình Machine Learning đã được huấn luyện để tính toán điểm số rủi ro (fraud score) và đưa ra dự đoán (gian lận / không gian lận). Quá trình này phải hoàn thành trong vòng vài trăm mili giây.                                   |
| **FR-03** | **Lưu trữ dữ liệu tin cậy**         | Toàn bộ dữ liệu giao dịch (thô và đã xử lý) phải được lưu trữ trên một Data Lakehouse, đảm bảo tính toàn vẹn (ACID) và khả năng truy vết lịch sử (Time Travel).                                                                                                                                            |
| **FR-04** | **Dashboard giám sát**                 | Cung cấp một Dashboard trực quan (Metabase) hiển thị các thông tin quan trọng trong thời gian thực: số lượng cảnh báo, tổng giá trị giao dịch bị nghi ngờ, phân bố địa lý (nếu có), hiệu suất mô hình...                                                                                                  |
| **FR-05** | **Chatbot xác minh thông minh**        | Cung cấp một giao diện Chatbot (Streamlit) cho phép Chuyên viên Phân tích Gian lận đặt câu hỏi bằng ngôn ngữ tự nhiên để điều tra một tài khoản hoặc giao dịch. Ví dụ: "Hiển thị 5 giao dịch gần nhất của tài khoản X", "Tài khoản Y đã giao dịch ở những quốc gia nào trong 24 giờ qua?". |
| **FR-06** | **Huấn luyện lại mô hình**          | Hệ thống phải có một pipeline tự động (Airflow) để huấn luyện lại mô hình học máy định kỳ (ví dụ: hàng đêm) trên dữ liệu mới nhất để chống lại sự thay đổi trong hành vi gian lận (concept drift).                                                                                                 |

### 4. Yêu cầu Phi chức năng (Non-Functional Requirements)

| ID               | Yêu cầu                         | Tiêu chí đo lường                                                                                                                        |
| :--------------- | :-------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------- |
| **NFR-01** | **Hiệu năng (Độ trễ)** | Thời gian từ lúc một giao dịch được đẩy vào Kafka đến khi có kết quả dự đoán từ mô hình ML phải dưới 5 giây.        |
| **NFR-02** | **Tính sẵn sàng**        | Các thành phần cốt lõi của pipeline thời gian thực (Kafka, Spark Streaming) phải có khả năng tự phục hồi sau lỗi.             |
| **NFR-03** | **Khả năng mở rộng**    | Kiến trúc phải có khả năng mở rộng theo chiều ngang (thêm các node Spark worker) để xử lý khối lượng giao dịch tăng lên. |
| **NFR-04** | **Bảo mật**               | Các thông tin nhạy cảm như API keys, mật khẩu phải được quản lý an toàn qua biến môi trường, không được hardcode.       |

---
