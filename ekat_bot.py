import json
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment değişkeni eksik!")

SUBSCRIBERS_FILE = "subscribers.json"

# ---------------- Abonelik yönetimi ----------------

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    with open(SUBSCRIBERS_FILE, "r") as f:
        return json.load(f)

def save_subscribers(subs):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subs, f)

# ---------------- Eğitimleri çekme ----------------

def egitimleri_cek():
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)

        driver.get("https://ekat.euas.gov.tr")
        driver.implicitly_wait(5)

        # Eğer eğitimler lazy load ise scroll eklenebilir
        # driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()

        cards = soup.find_all("div", class_="training-card")
        egitimler = []

        for card in cards:
            baslik_el = card.find("h3")
            baslik = baslik_el.get_text(strip=True) if baslik_el else "Bilinmiyor"

            yer = baslama = bitis = dolu = kontenjan = kalan = "Bilinmiyor"

            for p in card.find_all("p"):
                label = p.find("span", class_="training-label")
                if not label:
                    continue
                label_text = label.get_text(strip=True)

                value = p.get_text(strip=True).replace(label_text, "").strip()
                used = p.find("span", class_="used-quotas")
                if used:
                    value = used.get_text(strip=True)

                if label_text == "Eğitim Yeri:": yer = value
                elif label_text == "Eğitim Başlama Tarihi:": baslama = value
                elif label_text == "Eğitim Bitiş Tarihi:": bitis = value
                elif label_text == "Dolu Kontenjan:": dolu = value
                elif label_text == "Eğitim Kontenjan:": kontenjan = value
                elif label_text == "Kalan Kontenjan:": kalan = value

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
        print(f"❌ Eğitim çekme hatası: {e}")
        return []

# ---------------- Telegram Mesaj Gönderme ----------------

def gonder_egitimler(bot: Bot, chat_id: int, egitimler):
    tarih = datetime.now().strftime("[%d/%m/%Y %H:%M]")

    if not egitimler:
        mesaj = f"{tarih} ❌ *Aktif eğitim yoktur.*"
    else:
        mesaj = f"{tarih} ✅ *{len(egitimler)} adet aktif eğitim bulundu:*\n\n"
        for e in egitimler:
            mesaj += (
                f"📘 *{e['baslik']}*\n"
                f"🏫 _Eğitim yeri:_ {e['yer']}\n"
                f"🗓️ _Başlama:_ {e['baslama']}\n"
                f"📅 _Bitiş:_ {e['bitis']}\n"
                f"👥 _Dolu Kontenjan:_ {e['dolu']}\n"
                f"🎯 _Eğitim Kontenjanı:_ {e['kontenjan']}\n"
                f"🧮 _Kalan:_ {e['kalan']}\n"
                "────────────────────\n"
            )

    # Inline buton ile bildirim kapatma
    keyboard = [[InlineKeyboardButton("📩 Bildirimleri Kapat", callback_data='stop')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(chat_id=chat_id, text=mesaj, parse_mode='Markdown', reply_markup=reply_markup)

# ---------------- Callback Query ----------------

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    subs = load_subscribers()
    if query.data == 'stop':
        if chat_id in subs:
            subs.remove(chat_id)
            save_subscribers(subs)
        query.answer(text="Bildirimler kapatıldı ✅")
        query.edit_message_reply_markup(reply_markup=None)

# ---------------- /start komutu ----------------

def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    subs = load_subscribers()
    if chat_id not in subs:
        subs.append(chat_id)
        save_subscribers(subs)
    update.message.reply_text("✅ Abonelik aktif edildi. Eğitim bildirimleri gönderilecektir.")

# ---------------- Main ----------------

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()

    bot = updater.bot
    egitimler = egitimleri_cek()
    subs = load_subscribers()
    for s in subs:
        gonder_egitimler(bot, s, egitimler)

    updater.idle()

if __name__ == "__main__":
    main()
