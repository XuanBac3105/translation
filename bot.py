import os
import logging
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import google.generativeai as genai

# ─── Load config ────────────────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
SOURCE_GROUP = os.getenv("SOURCE_GROUP", "")
MIRROR_GROUP = os.getenv("MIRROR_GROUP", "")
TARGET_LANG = os.getenv("TARGET_LANG", "vi")

# ─── Logging ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mirror-bot")

# ─── Validate config ────────────────────────────────────────
def validate_config():
    missing = []
    if not API_ID:
        missing.append("API_ID")
    if not API_HASH:
        missing.append("API_HASH")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not SOURCE_GROUP:
        missing.append("SOURCE_GROUP")
    if not MIRROR_GROUP:
        missing.append("MIRROR_GROUP")
    if missing:
        log.error(f"Thiếu biến môi trường: {', '.join(missing)}")
        log.error("Hãy kiểm tra file .env hoặc biến môi trường trên Railway.")
        raise SystemExit(1)

validate_config()

# ─── Gemini setup ────────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

TRANSLATE_PROMPT = """Bạn là một dịch giả chuyên ngành trading forex/vàng/crypto.
Dịch tin nhắn sau sang tiếng Việt.

Quy tắc:
- Dịch tự nhiên, dễ hiểu
- Giữ nguyên các con số, không thêm bớt
- Giữ nguyên các thuật ngữ phổ biến nếu cần (SL, TP, pips, entry...)
- Sửa lỗi chính tả trong bản gốc nếu có (VD: "bais" = "bias", "entery" = "entry")
- CHỈ trả về bản dịch, KHÔNG giải thích thêm gì
- Nếu tin nhắn đã là tiếng Việt hoặc chỉ là số/ký hiệu, giữ nguyên

Tin nhắn:
{message}"""

# ─── Translation function ───────────────────────────────────
async def translate_message(text: str) -> str:
    """Dịch tin nhắn bằng Gemini API."""
    if not text or not text.strip():
        return text

    try:
        prompt = TRANSLATE_PROMPT.format(message=text)
        response = await asyncio.to_thread(
            model.generate_content, prompt
        )
        translated = response.text.strip()
        return translated if translated else text
    except Exception as e:
        log.error(f"Lỗi dịch: {e}")
        return f"[Lỗi dịch] {text}"

# ─── Parse group ID ─────────────────────────────────────────
def parse_group_id(group_str: str):
    """Chuyển đổi string group thành ID hoặc username."""
    try:
        return int(group_str)
    except ValueError:
        return group_str

# ─── Main bot ───────────────────────────────────────────────
async def main():
    # Tạo client — dùng StringSession nếu có (Railway), không thì dùng file session (local)
    if SESSION_STRING:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        log.info("🔑 Sử dụng StringSession (Railway mode)")
    else:
        client = TelegramClient("mirror_bot_session", API_ID, API_HASH)
        log.info("📁 Sử dụng file session (local mode)")
    await client.start()

    me = await client.get_me()
    log.info(f"✅ Đã đăng nhập: {me.first_name} (@{me.username})")

    source = parse_group_id(SOURCE_GROUP)
    mirror = parse_group_id(MIRROR_GROUP)

    # Kiểm tra kết nối tới các group
    try:
        source_entity = await client.get_entity(source)
        log.info(f"📥 Group nguồn: {getattr(source_entity, 'title', source)}")
    except Exception as e:
        log.error(f"❌ Không thể kết nối group nguồn: {e}")
        raise SystemExit(1)

    try:
        mirror_entity = await client.get_entity(mirror)
        log.info(f"📤 Group mirror: {getattr(mirror_entity, 'title', mirror)}")
    except Exception as e:
        log.error(f"❌ Không thể kết nối group mirror: {e}")
        raise SystemExit(1)

    log.info("🚀 Bot đang chạy... Đang lắng nghe tin nhắn mới.")

    @client.on(events.NewMessage(chats=source_entity))
    async def handler(event):
        """Xử lý tin nhắn mới từ group nguồn."""
        msg = event.message

        # Bỏ qua tin nhắn hệ thống (join, leave, pin...)
        if not msg.text and not msg.media:
            return

        # Lấy tên người gửi
        sender = await msg.get_sender()
        sender_name = "Unknown"
        if sender:
            sender_name = getattr(sender, "first_name", "") or ""
            last = getattr(sender, "last_name", "") or ""
            if last:
                sender_name += f" {last}"
            sender_name = sender_name.strip() or getattr(sender, "title", "Unknown")

        # Xử lý text
        original_text = msg.text or ""
        if msg.media and not original_text:
            # Media không có caption → forward nguyên
            original_text = getattr(msg, "message", "") or ""

        # Dịch tin nhắn
        if original_text.strip():
            translated = await translate_message(original_text)
        else:
            translated = ""

        # Format tin nhắn mirror
        mirror_text = f"👤 **{sender_name}**:\n{translated}" if translated else f"👤 **{sender_name}**: [media]"

        try:
            if msg.media:
                # Gửi media kèm caption đã dịch
                await client.send_file(
                    mirror_entity,
                    file=msg.media,
                    caption=mirror_text,
                    parse_mode="md",
                )
            else:
                # Gửi text thuần
                await client.send_message(
                    mirror_entity,
                    mirror_text,
                    parse_mode="md",
                )
            log.info(f"📨 Đã mirror: {sender_name}: {original_text[:50]}...")
        except Exception as e:
            log.error(f"❌ Lỗi gửi tin nhắn mirror: {e}")

    # Giữ bot chạy liên tục
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
