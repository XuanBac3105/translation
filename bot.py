import os
import logging
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from groq import Groq

# ─── Load config ────────────────────────────────────────────
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
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
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not SOURCE_GROUP:
        missing.append("SOURCE_GROUP")
    if not MIRROR_GROUP:
        missing.append("MIRROR_GROUP")
    if missing:
        log.error(f"Thiếu biến môi trường: {', '.join(missing)}")
        log.error("Hãy kiểm tra file .env hoặc biến môi trường trên Railway.")
        raise SystemExit(1)

validate_config()

# ─── Groq setup ──────────────────────────────────────────────
client_groq = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """Ban la mot dich gia chuyen nganh trading forex/vang/crypto.
Dich tin nhan sang tieng Viet.

Quy tac:
- Dich tu nhien, de hieu
- Giu nguyen cac con so, khong them bot
- Giu nguyen thuat ngu pho bien (SL, TP, pips, entry...)
- Sua loi chinh ta neu co (bais=bias, entery=entry, los=low)
- CHI tra ve ban dich, KHONG giai thich them gi
- Neu da la tieng Viet hoac chi la so/ky hieu, giu nguyen"""

# ─── Translation function ───────────────────────────────────
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

async def translate_message(text: str) -> str:
    """Dich tin nhan bang Groq API (LLaMA 3)."""
    if not text or not text.strip():
        return text

    for attempt in range(MAX_RETRIES):
        try:
            response = await asyncio.to_thread(
                client_groq.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=500,
            )
            translated = response.choices[0].message.content.strip()
            return translated if translated else text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate" in error_str.lower():
                wait_time = RETRY_DELAY * (attempt + 1)
                log.warning(f"Groq rate limited, doi {wait_time}s... ({attempt+1}/{MAX_RETRIES})")
                await asyncio.sleep(wait_time)
            else:
                log.error(f"Groq loi: {e}")
                return text

    log.error("Groq het quota, gui ban goc")
    return text

# ─── Resolve group entity ────────────────────────────────────
async def resolve_group(client, group_str: str, label: str):
    """Resolve group from ID, username, or group title via dialogs."""
    # Try as numeric ID first
    group_id = None
    try:
        group_id = int(group_str)
    except ValueError:
        pass

    # Search in dialogs (most reliable method)
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        eid = entity.id

        # Match by full ID (e.g. -1005265504221)
        if group_id is not None:
            if eid == group_id or eid == abs(group_id):
                log.info(f"{label}: {dialog.title} (ID: {eid})")
                return entity
            # Handle -100 prefix: -1005265504221 -> 5265504221
            stripped = str(abs(group_id))
            if stripped.startswith("100") and str(eid) == stripped[3:]:
                log.info(f"{label}: {dialog.title} (ID: {eid})")
                return entity

        # Match by title
        if group_str and dialog.title and dialog.title.lower() == group_str.lower():
            log.info(f"{label}: {dialog.title} (matched by title)")
            return entity

    # If not found in dialogs, try direct get_entity
    if group_id is not None:
        try:
            entity = await client.get_entity(group_id)
            log.info(f"{label}: {getattr(entity, 'title', group_str)}")
            return entity
        except Exception:
            pass

    log.error(f"Khong the tim thay {label}: {group_str}")
    log.error("Thu doi MIRROR_GROUP thanh ten group (VD: dich fx)")
    raise SystemExit(1)

# ─── Main bot ───────────────────────────────────────────────
async def main():
    # Tạo client — dùng StringSession nếu có (Railway), không thì dùng file session (local)
    if SESSION_STRING:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        log.info("Su dung StringSession (Railway mode)")
    else:
        client = TelegramClient("mirror_bot_session", API_ID, API_HASH)
        log.info("Su dung file session (local mode)")
    await client.start()

    me = await client.get_me()
    log.info(f"Da dang nhap: {me.first_name} (@{me.username})")

    # Tải danh sách chat để populate entity cache (cần cho StringSession)
    log.info("Dang tai danh sach chat...")
    await client.get_dialogs()
    log.info("Da tai xong danh sach chat.")

    source_entity = await resolve_group(client, SOURCE_GROUP, "Group nguon")
    mirror_entity = await resolve_group(client, MIRROR_GROUP, "Group mirror")

    log.info("Bot dang chay... Dang lang nghe tin nhan moi.")

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
        mirror_text = f"**{sender_name}**:\n{translated}" if translated else f"**{sender_name}**: [media]"

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
            log.info(f"Da mirror: {sender_name}: {original_text[:50]}...")
        except Exception as e:
            log.error(f"Loi gui tin nhan mirror: {e}")

    # Giữ bot chạy liên tục
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
