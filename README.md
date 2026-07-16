# UptoLink Monitor Mini App

Telegram Mini App để kiểm tra link Uptolink, phát hiện mã mới và tìm text/label "VƯỢT MÃ STEP 1".

## Tính năng

- ✅ Giao diện hiện đại, responsive
- ✅ Dữ liệu thực (Selenium + OCR)
- ✅ Chỉ 1 user kiểm tra tại 1 thời điểm
- ✅ Hàng đợi cho user chờ
- ✅ Cooldown 30 phút giữa các phiên
- ✅ Thông báo qua Telegram

## Deploy lên Railway

1. Fork repo này
2. Tạo project trên Railway
3. Thêm biến môi trường:
   - `TELEGRAM_TOKEN`: token bot
   - `BASE_URL`: URL của app
4. Deploy

## Cấu hình Webhook

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-project.railway.app/webhook"
