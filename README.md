# 📦 Hoyu Tracking Bot

![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)
![Python Version](https://img.shields.io/badge/Python-3.8%2B-brightgreen)
![Platform](https://img.shields.io/badge/Platform-Telegram%20%7C%20Discord-blueviolet)

**Hoyu Tracking** là một Bot mã nguồn mở giúp bạn theo dõi hành trình đơn hàng tự động dành cho Telegram và Discord. Hiện tại bot đang hỗ trợ tra cứu các đơn vị vận chuyển như **SPX Express** và **J&T Express**, và sẽ còn mở rộng thêm trong tương lai!

🌐 **Hàng ăn sẵn:** [https://hoyuuna.qzz.io/hoyu-tracking/](https://hoyuuna.qzz.io/hoyu-tracking/)

---

## ✨ Tính năng nổi bật

- 🤖 **Đa nền tảng:** Hỗ trợ hoạt động song song trên cả **Telegram** và **Discord**.
- 🔄 **Cập nhật tự động (Cronjob):** Tự động quét và thông báo khi có thay đổi trạng thái đơn hàng.
- 🔒 **Bảo mật & Tiện lợi:** Cung cấp Link Web UI để nhập mã vận đơn với Token bảo mật.
- ✅ **Quản lý thông minh:** Tự động gửi lại toàn bộ lịch sử khi mới thêm mã, và tự động xóa khỏi danh sách theo dõi khi đơn hàng báo "Giao thành công".
- 🗄️ **Lưu trữ nhẹ nhàng:** Không cần cài đặt Database phức tạp, dữ liệu được lưu trực tiếp vào file `track.json`.

---

## 🚀 Hướng dẫn cài đặt & Chạy Bot

Dự án đã được cung cấp đầy đủ các file cần thiết. Bạn chỉ cần Fork về, cài đặt thư viện và chạy là bot có thể hoạt động ngay!

### Bước 1: Clone kho lưu trữ
Hãy **Fork** repository này về tài khoản Github của bạn, sau đó clone về máy:
```bash
git clone https://github.com/TÊN_USER_CỦA_BẠN/hoyu-tracking.git
cd hoyu-tracking
```

### Bước 2: Cài đặt thư viện yêu cầu
Đảm bảo bạn đã cài đặt Python (phiên bản 3.8 trở lên). Chạy lệnh sau để cài đặt các dependencies:
```bash
pip install -r requirements.txt
```

### Bước 3: Cấu hình biến môi trường
Đổi tên file `.env.example` -> `.env` và thay thế các thông tin:
```env
TELEGRAM_BOT_TOKEN=nhập_token_telegram_của_bạn_ở_đây
DISCORD_BOT_TOKEN=nhập_token_discord_của_bạn_ở_đây
WEB_DOMAIN=http://127.0.0.1:5000
PORT=5000
```
*(Lưu ý: Nếu bạn chỉ muốn dùng Telegram, bạn có thể bỏ trống Discord token và ngược lại).*

### Bước 4: Khởi chạy Bot
Chạy lệnh sau để khởi động Bot và Web server:
```bash
python main.py
```
*(Lưu ý: Thay `main.py` bằng tên file code python của bạn nếu bạn đặt tên khác).*

---

## 🎮 Hướng dẫn sử dụng (Commands)

Sử dụng các lệnh sau trên Telegram hoặc Discord:

- `/setup` hoặc `/start`: Bot sẽ gửi cho bạn một đường link Web UI an toàn (có hiệu lực trong 5 phút). Nhấn vào link để chọn Đơn vị vận chuyển, nhập Mã vận đơn (và số điện thoại nếu là J&T) để bắt đầu theo dõi.
- `/reset`: Hủy bỏ và xóa **TOÀN BỘ** tiến trình theo dõi đơn hàng hiện tại của bạn.

---

## 📂 Cấu trúc dự án yêu cầu
Để code chạy trơn tru, hãy chắc chắn repo của bạn có đủ các file sau:
- `main.py` (File code python chính)
- `setup.html` (Giao diện Web UI để người dùng nhập mã vận đơn)
- `.env` (Đổi tên từ `.env.example`)

---

## 🛠️ Đóng góp (Contributing)
Vì các đơn vị vận chuyển thường xuyên thay đổi API và cấu trúc HTML (đặc biệt là J&T Express), code crawl dữ liệu (scrape) có thể cần được cập nhật theo thời gian. 
Mọi đóng góp (Pull Requests) để tối ưu code, sửa lỗi, hoặc thêm các đơn vị vận chuyển mới (GHTK, GHN, Viettel Post...) đều được chào đón nhiệt tình! 💖

---

## 📜 Giấy phép (License)

Dự án này được phân phối dưới giấy phép **GNU General Public License v3.0 (GPL-3.0)**. 

Bạn được tự do sử dụng, sao chép, sửa đổi và phân phối dự án này. Tuy nhiên, bất kỳ phần mềm phái sinh nào cũng phải được phát hành dưới cùng một giấy phép GPL-3.0 và phải công khai mã nguồn. Xem file `LICENSE` để biết thêm chi tiết.
