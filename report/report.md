# CS 145 Project 4

## Author and collaborators
### Author name
Phạm Xuân Đạt - MSV: 24020439

### Collaborators
Không có.

## Report

### Tổng quan
Dự án cài đặt giao thức truyền tin cậy RTP (Reliable Transport Protocol) chạy trên UDP. Giao thức đảm bảo dữ liệu đến nơi đầy đủ, đúng thứ tự khi mạng bị mất gói, trùng gói, đảo thứ tự hoặc hỏng dữ liệu (được giả lập bởi `test_scripts/proxy.py`).

Mỗi gói gồm header 16 byte (`type`, `seq_num`, `length`, `checksum` CRC32) và tối đa 1456 byte dữ liệu (1472 - 16), để vừa một gói UDP.

### RTP-base (Go-Back-N, ACK cộng dồn)
- **Kết nối:** sender gửi `START` (seq 0) và chờ ACK seq 1. Sau khi gửi hết dữ liệu, sender gửi `END` và chờ ACK tối đa 500ms rồi thoát (trong 500ms này gửi lại `END` mỗi 100ms phòng khi gói bị mất).
- **Sender:** chia dữ liệu thành các gói `DATA` đánh số từ 1 và gửi theo cửa sổ trượt kích thước `window_size`. Khi nhận ACK lớn hơn `base`, cửa sổ trượt tới và timer được đặt lại. Nếu quá 500ms mà cửa sổ không tiến, gửi lại toàn bộ gói trong cửa sổ.
- **Receiver:** kiểm tra checksum, bỏ gói hỏng (không ACK). Gói nằm trong cửa sổ `[N, N + window_size)` được lưu đệm, kể cả gói đến sai thứ tự. Các gói liên tiếp được ghi ra stdout, sau đó receiver gửi ACK cộng dồn với seq của gói tiếp theo đang chờ.

### RTP-opt (ACK từng gói, chỉ gửi lại gói thiếu)
- **Receiver:** không ACK cộng dồn nữa mà ACK đúng `seq_num` của gói vừa nhận. Gói có `seq_num >= N + window_size` bị bỏ qua.
- **Sender:** dùng mảng `acked[]` để đánh dấu gói đã được ACK trong cửa sổ. `base` trượt qua các gói liên tiếp đã ACK. Vẫn dùng một timer 500ms cho cả cửa sổ, nhưng khi hết giờ chỉ gửi lại các gói **chưa được ACK**, giảm việc truyền lại không cần thiết.

### Kiểm thử
Chạy các bước của `test_scripts/test.sh` cho cả `RTP-base` và `RTP-opt` với các loại lỗi `0`, `1`, `2`, `3`, `0123` và kích thước cửa sổ 1, 4, 128: tất cả đều cho file nhận khớp file gửi, thời gian truyền khoảng 2-3 giây.

## Citations
- Đề bài và mã khung: https://github.com/Harvard-CS145/reliable_transport

## Grading notes (if any)
Không sửa chương trình giả lập (`test_scripts/`, `utils.py`).

## Extra credit attempted (if any)
Không.
