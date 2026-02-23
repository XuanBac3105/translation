# 🌐 Telegram Mirror Translation Bot

Bot tự động mirror tin nhắn từ group Telegram kín, dịch sang tiếng Việt bằng Gemini AI, và gửi vào group/channel riêng.

Tối ưu cho **tin nhắn trading signal** (forex, vàng, crypto) — dịch chính xác thuật ngữ chuyên ngành.

## ⚡ Cài đặt nhanh

### 1. Lấy Telegram API credentials
1. Vào [my.telegram.org](https://my.telegram.org) → đăng nhập bằng số điện thoại
2. Chọn **API Development Tools**
3. Tạo app → copy **API ID** và **API Hash**

### 2. Lấy Gemini API Key
1. Vào [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Tạo API key → copy

### 3. Tìm ID group
Cách lấy ID group Telegram:
- Thêm bot [@userinfobot](https://t.me/userinfobot) vào group → nó sẽ trả về ID
- Hoặc dùng [@RawDataBot](https://t.me/RawDataBot) → forward tin nhắn từ group đó
- ID group thường có dạng: `-1001234567890`

### 4. Cấu hình
Copy file `.env.example` thành `.env` và điền thông tin:

```bash
cp .env.example .env
```

Sửa file `.env`:
```env
API_ID=12345678
API_HASH=abcdef1234567890
GEMINI_API_KEY=AIza...
SOURCE_GROUP=-1001234567890
MIRROR_GROUP=-1009876543210
TARGET_LANG=vi
```

### 5. Chạy local
```bash
pip install -r requirements.txt
python bot.py
```

> Lần đầu chạy, bot sẽ hỏi **số điện thoại** và **mã OTP** để đăng nhập Telegram.
> Sau đó tạo file session, lần sau không cần nhập lại.

## 🚀 Deploy lên Railway

### Bước 1: Tạo Session String (chạy trên máy local)
Vì Telegram cần xác thực OTP lần đầu, bạn phải tạo session trên máy local:

```bash
pip install -r requirements.txt
python generate_session.py
```

Nhập API_ID, API_HASH, số điện thoại, OTP → script sẽ in ra **Session String**. Copy lại.

### Bước 2: Push code lên GitHub
```bash
git init
git add .
git commit -m "init mirror bot"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Bước 3: Deploy trên Railway
1. Vào [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
2. Chọn repo vừa tạo
3. Vào **Variables** → thêm các biến:
   - `API_ID`
   - `API_HASH`
   - `GEMINI_API_KEY`
   - `SESSION_STRING` ← paste string từ bước 1
   - `SOURCE_GROUP`
   - `MIRROR_GROUP`
   - `TARGET_LANG`
4. Railway sẽ tự động build và chạy bot

## 📋 Cách hoạt động

```
Group kín (nguồn) → Bot lắng nghe → Gemini dịch → Group mirror (đích)
```

Mỗi tin nhắn mirror sẽ có format:
```
👤 Tên người gửi:
Nội dung đã dịch sang tiếng Việt
```

## 🛑 Dừng bot
- Local: `Ctrl + C`
- Railway: Vào Dashboard → Stop service
