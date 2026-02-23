"""
Script tạo StringSession để dùng trên Railway.
Chạy trên máy local 1 lần → copy string session → paste vào biến SESSION_STRING trên Railway.
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = input("Nhap API_ID: ").strip()
API_HASH = input("Nhap API_HASH: ").strip()
PHONE = input("Nhap so dien thoai (VD: +84...): ").strip()


async def main():
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start(phone=PHONE)

    session_string = client.session.save()
    print("\n" + "=" * 60)
    print("SESSION STRING CUA BAN (copy toan bo dong duoi):")
    print("=" * 60)
    print(session_string)
    print("=" * 60)
    print("\nPaste string nay vao bien SESSION_STRING tren Railway.")
    print("KHONG chia se string nay cho ai!")

    await client.disconnect()


asyncio.run(main())
