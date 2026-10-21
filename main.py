import asyncio
import os
import platform
import re
import stat
import sys
import urllib.request
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Message, WebAppInfo
from aiohttp import ClientSession, ClientTimeout, web
from dotenv import load_dotenv

from webapp import create_app, init_db

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "5486146974"))
MANAGER = os.getenv("MANAGER_USERNAME", "savrrage").lstrip("@")
PORT = int(os.getenv("PORT", "8080"))


def cloudflared_url():
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe", ROOT / "cloudflared.exe"
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", ROOT / "cloudflared"
    raise RuntimeError("Для этой системы cloudflared нужно установить вручную")


def ensure_cloudflared():
    url, path = cloudflared_url()
    if not path.exists() or path.stat().st_size < 1_000_000:
        print("Скачиваю защищённый туннель Cloudflare...")
        urllib.request.urlretrieve(url, path)
        if platform.system().lower() != "windows":
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


async def start_tunnel():
    binary = await asyncio.to_thread(ensure_cloudflared)
    process = await asyncio.create_subprocess_exec(
        str(binary), "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--protocol", "http2",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    public_url = None
    registered = False
    pattern = re.compile(r"https://[a-z0-9-]+\\.trycloudflare\\.com")
    deadline = asyncio.get_running_loop().time() + 120
    while asyncio.get_running_loop().time() < deadline:
        if process.returncode is not None:
            raise RuntimeError("Cloudflare tunnel завершился раньше времени")
        try:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=5)
        except asyncio.TimeoutError:
            continue
        text = line.decode(errors="ignore")
        match = pattern.search(text)
        if match:
            public_url = match.group(0)
        if "Registered tunnel connection" in text:
            registered = True
        if public_url and registered:
            break
    if not public_url or not registered:
        process.terminate()
        raise RuntimeError("Не удалось запустить Cloudflare tunnel за 120 секунд")
    async with ClientSession(timeout=ClientTimeout(total=8)) as session:
        for _ in range(20):
            try:
                async with session.get(public_url + "/health") as response:
                    if response.status == 200 and (await response.text()).strip() == "ok":
                        return process, public_url
            except Exception:
                pass
            await asyncio.sleep(2)
    process.terminate()
    raise RuntimeError("Туннель создан, но магазин недоступен из интернета")


async def main():
    if not TOKEN or ":" not in TOKEN:
        raise RuntimeError("В .env не указан корректный BOT_TOKEN")
    init_db()
    bot = Bot(TOKEN)
    dp = Dispatcher()
    runner = web.AppRunner(create_app(TOKEN, ADMIN_ID, MANAGER))
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    tunnel = None
    try:
        print("Запускаю публичный адрес...")
        tunnel, public_url = await start_tunnel()
        webapp = WebAppInfo(url=public_url)

        @dp.message(CommandStart())
        async def start(message: Message):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Открыть AutoPrime", web_app=webapp)
            ]])
            await message.answer(
                "🏁 <b>AutoPrime</b>\\nРули с характером. Каталог, заказ и статус — в одном приложении.",
                reply_markup=keyboard, parse_mode="HTML",
            )

        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="AutoPrime", web_app=webapp))
        me = await bot.get_me()
        print(f"\\nГОТОВО: @{me.username}")
        print(f"Адрес магазина: {public_url}")
        print("Отправьте боту /start. Не закрывайте это окно.\\n")
        polling = asyncio.create_task(dp.start_polling(bot))
        while True:
            if tunnel.returncode is not None:
                polling.cancel()
                raise RuntimeError("Cloudflare tunnel отключился. Запустите START.bat заново")
            if polling.done():
                await polling
            await asyncio.sleep(5)
    finally:
        if tunnel and tunnel.returncode is None:
            tunnel.terminate()
            try:
                await asyncio.wait_for(tunnel.wait(), 5)
            except asyncio.TimeoutError:
                tunnel.kill()
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\nОстановлено.")
    except Exception as error:
        print(f"\\nОШИБКА: {type(error).__name__}: {error}")
        print("Исправьте причину и запустите START.bat снова.")
        sys.exit(1)