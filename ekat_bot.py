import json
import os
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import traceback

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment değişkeni eksik!")

SUBSCRIBERS_FILE = "subscribers.json"


def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


def save_subscribers(subs):
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)


def egitimleri_cek():
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)

        driver.get("https://ekat.euas.gov.tr")
        driver.implicitly_wait(6)
        html = driver.page_source
        driver.quit()

        soup = BeautifulSoup(html, "html.parser")

        cards = soup.find_all("div", class_="training-card")
        egitimler = []
        for card in cards:
            baslik = card.find("h5").get_text(strip=True) if card.find("h5") else "Bilinmiyor"
            yer = baslama = bitis = dolu = kontenjan = kalan = "Bilinmiyor"

            for p in card.find_all("p"):
                text = p.get_text(strip=True)
                if "Eğitim Yeri" in text:
                    yer = text.split(":")[-1].strip()
                elif "Başlama" in text:
                    baslama = text.split(":")[-1].strip()
                elif "Bitiş" in text:
                    bitis = text.split(":")[-1].strip()
                elif "Dolu" in text:
                    dolu = text.split(":")[-1].strip()
                elif "Kontenjan" in text and "Kalan" not in text:
                    kontenjan = text.split(":")[-1].strip()
                elif "Kalan" in text:
                    kalan = text.split(":")[-1].strip()

            egitimler.append({
                "baslik": baslik,
                "yer": yer,
                "baslama": baslama,
                "bitis": bitis,
                "dolu": dolu,
                "kontenjan": kontenjan,
                "kalan": kalan
            })
        return egitimler

    except Exception as e:
        print("❌ Eğitim çekme hatası:", e)
        traceback.print_exc()
        try:
            driver.quit()
        except Exception:
            pass
        return []


def _now_str():
    try:
        if ZoneInfo is not None:
            now = datetime.now(ZoneInfo("Europe/Istanbul"))
        else:
            now = datetime.now()
    except Exception:
        now = datetime.now()
    return now.strftime("[%d/%m/%Y %H:%M]")


def gonder_egitimler(bot: Bot, chat_id: int, egitimler):
    tarih = _now_str()

    if not egitimler:
        mesaj = f"{tarih} ❌ *Aktif eğitim yoktur.*"
    else:
        mesaj = f"{tarih} ✅ *{len(egitimler)} adet aktif eğitim bulundu:*\n\n"
        for e in egitimler:
            mesaj += (
                f"📘 *{e.get('baslik','Bilinmiyor')}*\n"
                f"🏫 _Eğitim yeri:_ {e.get('yer','Bilinmiyor')}\n"
                f"🗓️ _Başlama:_ {e.get('baslama','Bilinmiyor')}\n"
                f"📅 _Bitiş:_ {e.get('bitis','Bilinmiyor')}\n"
                f"👥 _Dolu Kontenjan:_ {e.get('dolu','Bilinmiyor')}\n"
                f"🎯 _Eğitim Kontenjanı:_ {e.get('kontenjan','Bilinmiyor')}\n"
                f"🧮 _Kalan:_ {e.get('kalan','Bilinmiyor')}\n"
                "────────────────────\n"
            )

    keyboard = [
        [InlineKeyboardButton("🎓 Eğitimleri Gör", callback_data='show')],
        [InlineKeyboardButton("📩 Bildirimleri Kapat", callback_data='stop')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(chat_id=chat_id, text=mesaj, parse_mode='Markdown', reply_markup=reply_markup)


def button(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    subs = load_subscribers()
    try:
        if query.data == 'stop':
            if chat_id in subs:
                subs.remove(chat_id)
                save_subscribers(subs)
            query.answer(text="🔕 Bildirimler devre dışı bırakıldı.")
            keyboard = [[InlineKeyboardButton("🔔 Bildirimleri Aç", callback_data='start')],
                        [InlineKeyboardButton("🎓 Eğitimleri Gör", callback_data='show')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_reply_markup(reply_markup=reply_markup)

        elif query.data == 'start':
            if chat_id not in subs:
                subs.append(chat_id)
                save_subscribers(subs)
            query.answer(text="✅ Bildirimler aktif edildi.")
            keyboard = [[InlineKeyboardButton("📩 Bildirimleri Kapat", callback_data='stop')],
                        [InlineKeyboardButton("🎓 Eğitimleri Gör", callback_data='show')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.edit_message_reply_markup(reply_markup=reply_markup)

        elif query.data == 'show':
            query.answer("🔍 Eğitimler yükleniyor...")
            egitimler = egitimleri_cek()
            gonder_egitimler(context.bot, chat_id, egitimler)

    except Exception as e:
        print("Callback hata:", e)
        traceback.print_exc()


def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    subs = load_subscribers()
    if chat_id not in subs:
        subs.append(chat_id)
        save_subscribers(subs)
    keyboard = [
        [InlineKeyboardButton("🎓 Eğitimleri Gör", callback_data='show')],
        [InlineKeyboardButton("📩 Bildirimleri Kapat", callback_data='stop')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("✅ Bildirimler aktif edildi. Eğitim bildirimleri gönderilecektir.",
                              reply_markup=reply_markup)


def stop(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    subs = load_subscribers()
    if chat_id in subs:
        subs.remove(chat_id)
        save_subscribers(subs)
    keyboard = [
        [InlineKeyboardButton("🔔 Bildirimleri Aç", callback_data='start')],
        [InlineKeyboardButton("🎓 Eğitimleri Gör", callback_data='show')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🔕 Bildirimler devre dışı bırakıldı. Artık bildirim almayacaksınız.",
                              reply_markup=reply_markup)


def egitimler_komutu(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    update.message.reply_text("🔍 Eğitimler yükleniyor, lütfen bekleyin...")
    egitimler = egitimleri_cek()
    gonder_egitimler(context.bot, chat_id, egitimler)


def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("egitimler", egitimler_komutu))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
