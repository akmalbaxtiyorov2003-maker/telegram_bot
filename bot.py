# Kelajak Avlod 22 — Telegram bot (Python + python-telegram-bot)
# IT ga qiziqadigan bolalar uchun: ro'yxatdan o'tish + 15 ta oson kompyuter testi
import asyncio
import json
import logging
import math
import os
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None

if not BOT_TOKEN:
    print("BOT_TOKEN topilmadi. .env faylga BOT_TOKEN=... qo'ying.")
    sys.exit(1)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------- Oddiy JSON baza ----------
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")


def load_db():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


# ---------- 15 ta eng oson test savoli ----------
# correct — to'g'ri javobning indeksi (0 dan boshlanadi)
QUESTIONS = [
    {
        "q": 'Kompyuterning "miyasi" deb qaysi qism ataladi?',
        "options": ["Monitor", "Protsessor (CPU)", "Klaviatura", "Sichqoncha"],
        "correct": 1,
    },
    {
        "q": "Matn yozish uchun qaysi qurilma ishlatiladi?",
        "options": ["Klaviatura", "Printer", "Monitor", "Kolonka"],
        "correct": 0,
    },
    {
        "q": "Ekrandagi kursorni boshqaradigan qurilma qaysi?",
        "options": ["Skaner", "Mikrofon", "Sichqoncha", "Printer"],
        "correct": 2,
    },
    {
        "q": "Ma'lumotlarni ekranda ko'rsatadigan qurilma qaysi?",
        "options": ["Monitor", "Klaviatura", "Modem", "Sichqoncha"],
        "correct": 0,
    },
    {
        "q": "Fayl va dasturlarni doimiy saqlaydigan qism qaysi?",
        "options": ["Kuler", "Qattiq disk (HDD/SSD)", "Monitor", "Kolonka"],
        "correct": 1,
    },
    {
        "q": "Windows nima?",
        "options": ["O'yin", "Antivirus", "Brauzer", "Operatsion tizim"],
        "correct": 3,
    },
    {
        "q": "Internetga kirish uchun qaysi dastur ishlatiladi?",
        "options": ["Brauzer (Chrome)", "Kalkulyator", "Paint", "Bloknot"],
        "correct": 0,
    },
    {
        "q": "Matn hujjatlari yaratish uchun qaysi dastur mos?",
        "options": ["Paint", "Microsoft Word", "Chrome", "Telegram"],
        "correct": 1,
    },
    {
        "q": "1 bayt necha bitga teng?",
        "options": ["2", "4", "16", "8"],
        "correct": 3,
    },
    {
        "q": "Ma'lumotni qog'ozga chop etadigan qurilma qaysi?",
        "options": ["Monitor", "Printer", "Sichqoncha", "Router"],
        "correct": 1,
    },
    {
        "q": "Ctrl + C tugmalari nima qiladi?",
        "options": ["O'chiradi", "Saqlaydi", "Nusxa oladi", "Yopadi"],
        "correct": 2,
    },
    {
        "q": "Ctrl + V tugmalari nima qiladi?",
        "options": [
            "Nusxa olingan narsani qo'yadi",
            "Dasturni yopadi",
            "Faylni o'chiradi",
            "Yangi oyna ochadi",
        ],
        "correct": 0,
    },
    {
        "q": "Wi-Fi nima uchun kerak?",
        "options": [
            "Chop etish uchun",
            "Simsiz internet uchun",
            "Rasm chizish uchun",
            "Musiqa yozish uchun",
        ],
        "correct": 1,
    },
    {
        "q": ".jpg kengaytmali fayl qaysi turga kiradi?",
        "options": ["Musiqa", "Video", "Matn", "Rasm"],
        "correct": 3,
    },
    {
        "q": "Quyidagilardan qaysi biri dasturlash tili?",
        "options": ["Python", "Windows", "Chrome", "Excel"],
        "correct": 0,
    },
]

# ---------- Klaviaturalar ----------
BTN_REGISTER = "📝 Ro'yxatdan o'tish"
BTN_TEST = "🧠 Test ishlash"

MAIN_MENU = ReplyKeyboardMarkup([[BTN_REGISTER, BTN_TEST]], resize_keyboard=True)

# ---------- Vaqtinchalik holat (xotirada) ----------
reg_sessions = {}   # user_id -> {"step": "first"|"last", "first_name": str}
test_sessions = {}  # user_id -> {"q": int, "score": int}


def js_round(x):
    """JavaScript Math.round bilan bir xil yaxlitlash."""
    return math.floor(x + 0.5)


# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reg_sessions.pop(user.id, None)
    test_sessions.pop(user.id, None)
    await update.message.reply_text(
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        f'"Kelajak Avlod 22" botiga xush kelibsiz!\n'
        f"Bu bot IT ga qiziqadigan bolalar uchun.\n\n"
        f"1️⃣ Avval ro'yxatdan o'ting\n"
        f"2️⃣ Keyin kompyuter bo'yicha testni ishlang",
        reply_markup=MAIN_MENU,
    )


# ---------- Ro'yxatdan o'tish ----------
async def register_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = load_db()
    user = db.get(str(user_id))
    if user and user.get("firstName"):
        await update.message.reply_text(
            f"Siz allaqachon ro'yxatdan o'tgansiz ✅\n"
            f"👤 {user['firstName']} {user['lastName']}\n\n"
            f'Testni ishlash uchun "{BTN_TEST}" tugmasini bosing.',
            reply_markup=MAIN_MENU,
        )
        return
    test_sessions.pop(user_id, None)
    reg_sessions[user_id] = {"step": "first"}
    await update.message.reply_text("Ismingizni yozing:", reply_markup=ReplyKeyboardRemove())


# ---------- Test boshlash ----------
async def test_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = load_db()
    user = db.get(str(user_id))
    if not user or not user.get("firstName"):
        await update.message.reply_text(
            f"Testni ishlashdan oldin ro'yxatdan o'tishingiz kerak.\n"
            f'"{BTN_REGISTER}" tugmasini bosing.',
            reply_markup=MAIN_MENU,
        )
        return
    reg_sessions.pop(user_id, None)
    test_sessions[user_id] = {"q": 0, "score": 0}
    await update.message.reply_text(
        f"Test boshlandi! 🚀\nJami {len(QUESTIONS)} ta savol. Omad, {user['firstName']}!",
        reply_markup=ReplyKeyboardRemove(),
    )
    await send_question(update.effective_chat.id, context, 0)


async def send_question(chat_id, context: ContextTypes.DEFAULT_TYPE, index: int):
    item = QUESTIONS[index]
    buttons = [
        [InlineKeyboardButton(text, callback_data=f"ans_{index}_{i}")]
        for i, text in enumerate(item["options"])
    ]
    await context.bot.send_message(
        chat_id,
        f"❓ Savol {index + 1}/{len(QUESTIONS)}\n\n{item['q']}",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ---------- Javobni qabul qilish ----------
async def answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, q_str, opt_str = query.data.split("_")
    q_index = int(q_str)
    opt_index = int(opt_str)
    user_id = query.from_user.id
    session = test_sessions.get(user_id)

    # Eski yoki takroriy tugma bosilgan bo'lsa
    if not session or session["q"] != q_index:
        await query.answer("Bu savol allaqachon javob berilgan.")
        return

    item = QUESTIONS[q_index]
    is_correct = opt_index == item["correct"]
    if is_correct:
        session["score"] += 1
    session["q"] += 1

    await query.answer("✅ To'g'ri!" if is_correct else "❌ Noto'g'ri")

    # Savolni javob bilan yangilab, tugmalarni olib tashlaymiz
    if is_correct:
        mark = f"✅ To'g'ri: {item['options'][item['correct']]}"
    else:
        mark = f"❌ Noto'g'ri. To'g'ri javob: {item['options'][item['correct']]}"
    try:
        await query.edit_message_text(
            f"❓ Savol {q_index + 1}/{len(QUESTIONS)}\n\n{item['q']}\n\n{mark}"
        )
    except Exception:
        pass  # xabar o'zgarmagan bo'lsa e'tibor bermaymiz

    chat_id = query.message.chat_id
    if session["q"] < len(QUESTIONS):
        await send_question(chat_id, context, session["q"])
    else:
        await finish_test(chat_id, query.from_user, session, context)


async def finish_test(chat_id, tg_user, session, context: ContextTypes.DEFAULT_TYPE):
    test_sessions.pop(tg_user.id, None)
    total = len(QUESTIONS)
    percent = js_round((session["score"] / total) * 100)

    comment = "Yaxshi boshlanish! Kompyuter haqida ko'proq o'rganing 💪"
    if percent >= 90:
        comment = "Ajoyib! Siz haqiqiy IT iste'dodisiz! 🏆"
    elif percent >= 70:
        comment = "Zo'r natija! Davom eting! 🔥"
    elif percent >= 50:
        comment = "Yomon emas! Biroz mashq qilsangiz yanada yaxshi bo'ladi 👍"

    db = load_db()
    user = db[str(tg_user.id)]
    user["score"] = session["score"]
    user["total"] = total
    user["testDate"] = datetime.now(timezone.utc).isoformat()
    save_db(db)

    await context.bot.send_message(
        chat_id,
        f"🏁 Test yakunlandi!\n\n"
        f"👤 {user['firstName']} {user['lastName']}\n"
        f"📊 Natija: {session['score']}/{total} ({percent}%)\n\n{comment}",
        reply_markup=MAIN_MENU,
    )

    if ADMIN_ID:
        tg = f"@{tg_user.username}" if tg_user.username else tg_user.id
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🆕 Test natijasi\n\n"
                f"👤 {user['firstName']} {user['lastName']}\n"
                f"🔗 {tg}\n"
                f"📊 {session['score']}/{total} ({percent}%)",
            )
        except Exception:
            pass


# ---------- Admin: barcha natijalar ----------
async def results_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ADMIN_ID or update.effective_user.id != ADMIN_ID:
        return
    db = load_db()
    rows = list(db.values())
    if not rows:
        await update.message.reply_text("Hali hech kim ro'yxatdan o'tmagan.")
        return

    rows.sort(key=lambda u: -(u["score"] if u.get("score") is not None else -1))
    lines = []
    for i, u in enumerate(rows, start=1):
        if u.get("score") is not None:
            res = f"{u['score']}/{u['total']}"
        else:
            res = "test ishlamagan"
        lines.append(f"{i}. {u['firstName']} {u['lastName']} — {res}")

    text = f"📋 Ro'yxatdan o'tganlar: {len(rows)} ta\n\n" + "\n".join(lines)
    await update.message.reply_text(text[:4000])


# ---------- Matnli xabarlar (ro'yxatdan o'tish jarayoni) ----------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    s = reg_sessions.get(tg_user.id)
    if not s:
        return

    text = update.message.text.strip()
    if len(text) < 2 or len(text) > 40 or text.startswith("/"):
        await update.message.reply_text("Iltimos, to'g'ri yozing (kamida 2 ta harf).")
        return

    if s["step"] == "first":
        s["first_name"] = text
        s["step"] = "last"
        await update.message.reply_text("Familiyangizni yozing:")
        return

    if s["step"] == "last":
        db = load_db()
        db[str(tg_user.id)] = {
            "id": tg_user.id,
            "username": tg_user.username or None,
            "firstName": s["first_name"],
            "lastName": text,
            "registeredAt": datetime.now(timezone.utc).isoformat(),
        }
        save_db(db)
        reg_sessions.pop(tg_user.id, None)

        await update.message.reply_text(
            f"✅ Ro'yxatdan o'tdingiz!\n"
            f"👤 {s['first_name']} {text}\n\n"
            f'Endi "{BTN_TEST}" tugmasini bosib testni boshlang.',
            reply_markup=MAIN_MENU,
        )

        if ADMIN_ID:
            tg = f"@{tg_user.username}" if tg_user.username else tg_user.id
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"🆕 Yangi ro'yxatdan o'tish\n\n"
                    f"👤 {s['first_name']} {text}\n🔗 {tg}",
                )
            except Exception:
                pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Xatolik:", exc_info=context.error)


# ---------- Render (bepul Web Service) uchun kichik veb-server ----------
# Render port ochilishini kutadi, UptimeRobot esa shu manzilga so'rov
# yuborib, servis uxlab qolmasligini ta'minlaydi.
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Kelajak Avlod 22 boti ishlayapti")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # konsolni to'ldirmaslik uchun


def start_health_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Veb-server {port}-portda ishga tushdi")


def main():
    start_health_server()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("natijalar", results_command))
    app.add_handler(MessageHandler(filters.Text([BTN_REGISTER]), register_button))
    app.add_handler(MessageHandler(filters.Text([BTN_TEST]), test_button))
    app.add_handler(CallbackQueryHandler(answer_callback, pattern=r"^ans_\d+_\d+$"))
    app.add_handler(MessageHandler(filters.TEXT, text_handler))
    app.add_error_handler(error_handler)

    print("Kelajak Avlod 22 boti ishga tushdi ✅")
    asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling()


if __name__ == "__main__":
    main()
