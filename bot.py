import time
import logging
import os
from difflib import SequenceMatcher

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from config import BOT_TOKEN, CHANNEL
from database import add_song, search_songs, init_db

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------- CACHE ----------------
user_last_time = {}

# ---------------- SCORE ----------------
def score(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_prefix(s):
    if s >= 0.85:
        return "🟢"
    elif s >= 0.6:
        return "🟡"
    return "⚪"

# ---------------- MEMBER CHECK ----------------
async def is_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.warning(f"member check failed: {e}")
        return False

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎧 RadioHiss Music Bot\n\n"
        "اسم آهنگ یا خواننده را ارسال کنید 👇"
    )

# ---------------- CHANNEL SAVE ----------------
async def channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    if not msg:
        return

    text = msg.text or msg.caption or ""

    song = ""
    artist = ""

    for line in text.split("\n"):
        low = line.lower()

        if "song" in low or "آهنگ" in low:
            song = line.split(":", 1)[-1].strip()

        if "artist" in low or "singer" in low or "خواننده" in low:
            artist = line.split(":", 1)[-1].strip()

    if song and artist:
        try:
            add_song(msg.chat.id, msg.message_id, song, artist)
            logging.info(f"SAVED: {song}")
        except Exception as e:
            logging.error(f"DB save error: {e}")

# ---------------- SEARCH ----------------
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    # anti spam
    now = time.time()
    if user_id in user_last_time:
        if now - user_last_time[user_id] < 1:
            return
    user_last_time[user_id] = now

    # membership check
    if not await is_member(user_id, context):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL.replace('@','')}")],
            [InlineKeyboardButton("🔄 Check Again", callback_data="CHECK_MEMBER")]
        ])

        await update.message.reply_text(
            "❌ برای استفاده باید عضو کانال باشید",
            reply_markup=keyboard
        )
        return

    query = update.message.text.strip()
    results = search_songs(query)

    if not results:
        await update.message.reply_text("❌ چیزی پیدا نشد")
        return

    scored = []

    for chat_id, message_id, song, artist in results:
        s = max(score(query, song), score(query, artist))
        scored.append((s, chat_id, message_id, song, artist))

    scored.sort(reverse=True, key=lambda x: x[0])

    text = f"🎧 RadioHiss Results\n🔎 Query: {query}\n\n"
    keyboard = []

    for s, chat_id, message_id, song, artist in scored[:10]:

        prefix = get_prefix(s)
        text += f"{prefix} {song} | {artist}\n"

        keyboard.append([
            InlineKeyboardButton(
                f"▶ {song}",
                callback_data=f"PLAY|{chat_id}|{message_id}"
            )
        ])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- CALLBACK ----------------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    try:
        await query.answer()
    except:
        pass

    data = query.data.split("|")

    # check member button
    if data[0] == "CHECK_MEMBER":
        ok = await is_member(query.from_user.id, context)
        await query.message.reply_text("✅ OK" if ok else "❌ Not Member")
        return

    # play song
    if data[0] == "PLAY":
        chat_id = int(data[1])
        message_id = int(data[2])

        try:
            await context.bot.forward_message(
                chat_id=query.message.chat.id,
                from_chat_id=chat_id,
                message_id=message_id
            )
        except Exception as e:
            await query.message.reply_text(f"❌ Error: {e}")

# ---------------- MAIN ----------------
def main():

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing in environment variables")

    # init database
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post))

    print("🚀 RadioHiss Bot Running...")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()