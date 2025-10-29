# Retry writing the file correctly (ensure imports available in this cell scope)
import os, json
content = r'''import json
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

# ---------------- Abonelik yönetimi ----------------

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

# ---------------- Eğitimleri çekme (daha dayanıklı hale getirildi) ----------------

def egitimleri_cek():
    """
    Site yapısı değişse bile biraz daha dayanıklı olması için birkaç olası selector denemesi ekledim.
    Eğer eğitim kartı bulunamazsa sayfadaki başlıklardan kaba bir liste oluşturmaya çalışır.
    """
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)

        driver.get("https://ekat.euas.gov.tr")
        driver.implicitly_wait(6)

        # Bazı sayfalarda lazy load olabilir; kısa bir scroll denemesi ekliyorum
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        except Exception:
            pass

        html = driver.page_source
        driver.quit()

        soup = BeautifulSoup(html, "html.parser")

        # Öncelikli olarak olası kart sınıflarını dene
        possible_card_selectors = [
            ("div", "training-card"),
            ("div", "card"),
            ("div", "course-card"),
            ("article", None),
            ("li", "training-item"),
        ]

        cards = []
        for tag, cls in possible_card_selectors:
            if cls:
                found = soup.find_all(tag, class_=cls)
            else:
                found = soup.find_all(tag)
            if found and len(found) >= 1:
                cards = found
                break

        egitimler = []

        # Eğer kart bulunamadıysa sayfadaki başlıkları ve yanlarındaki p/label'leri eşleştirerek kaba bir liste çıkar
        if not cards:
            # olası başlıklar h2/h3/h4 ile başlayan bloklar
            headers = soup.find_all(["h1", "h2", "h3", "h4"])
            for h in headers:
                title = h.get_text(strip=True)
                if not title:
                    continue
                # etraftaki p'leri topla
                details = []
                for sib in h.find_next_siblings(limit=6):
                    if sib.name in ["p", "div", "span", "li"]:
                        txt = sib.get_text(" ", strip=True)
                        if txt:
                            details.append(txt)
                egitimler.append({
                    "baslik": title,
                    "yer": details[0] if len(details) > 0 else "Bilinmiyor",
                    "baslama": details[1] if len(details) > 1 else "Bilinmiyor",
                    "bitis": details[2] if len(details) > 2 else "Bilinmiyor",
                    "dolu": "Bilinmiyor",
                    "kontenjan": "Bilinmiyor",
                    "kalan": "Bilinmiyor"
                })
            return egitimler

        # Kartlar üzerinden detay çek
        for card in cards:
            # başlık bul (h1-h4, strong, a)
            baslik = "Bilinmiyor"
            for tag in ["h1", "h2", "h3", "h4", "strong", "a"]:
                el = card.find(tag)
                if el and el.get_text(strip=True):
                    baslik = el.get_text(strip=True)
                    break

            yer = baslama = bitis = dolu = kontenjan = kalan = "Bilinmiyor"

            # label-value tarzı p/span listelerini tara
            for p in card.find_all(["p", "li", "div", "span"]):
                label = p.find("span", class_="training-label")
                label_text = ""
                if label:
                    label_text = label.get_text(strip=True)
                else:
                    # bazen label yok, "Eğitim Yeri:" gibi metin olabilir
                    text = p.get_text(" ", strip=True)
                    if ":" in text:
                        parts = text.split(":", 1)
                        label_text = parts[0] + ":"
                        value = parts[1].strip()
                    else:
                        value = text

                # override value if not set above
                if not label:
                    # value already from text split
                    pass
                else:
                    value = p.get_text(" ", strip=True).replace(label_text, "").strip()
                    used = p.find("span", class_="used-quotas")
                    if used:
                        value = used.get_text(strip=True)

                if label_text == "Eğitim Yeri:" or "Eğitim Yeri" in label_text:
                    yer = value
                elif label_text == "Eğitim Başlama Tarihi:" or "Başlama" in label_text:
                    baslama = value
                elif label_text == "Eğitim Bitiş Tarihi:" or "Bitiş" in label_text:
                    bitis = value
                elif "Dolu" in label_text:
                    dolu = value
                elif "Kontenjan" in label_text and "Kalan" not in label_text:
                    kontenjan = value
                elif "Kalan" in label_text:
                    kalan = value

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

# ---------------- Telegram Mesaj Gönderme ----------------

def _now_str():
    # Türkiye saat dilimi (Europe/Istanbul) kullan
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

    # Inline butonlar ile bildirim açma/kapama
    keyboard = [
        [InlineKeyboardButton("📩 Bildirimleri Kapat", callback_data='stop')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(chat_id=chat_id, text=mesaj, parse_mode='Markdown', reply_markup=reply_markup)

# ---------------- Callback Query ----------------

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
            # düzenlenmiş mesajın altına artık bildirim açma butonu ekle
            keyboard = [[InlineKeyboardButton("🔔 Bildirimleri Aç", callback_data='start')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                query.edit_message_reply_markup(reply_markup=reply_markup)
            except Exception:
                # bazı mesajlarda düzenleme mümkün olmayabilir
                pass

        elif query.data == 'start':
            if chat_id not in subs:
                subs.append(chat_id)
                save_subscribers(subs)
            query.answer(text="✅ Bildirimler aktif edildi.")
            keyboard = [[InlineKeyboardButton("📩 Bildirimleri Kapat", callback_data='stop')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                query.edit_message_reply_markup(reply_markup=reply_markup)
            except Exception:
                pass
    except Exception as e:
        print("Callback hata:", e)
        traceback.print_exc()

# ---------------- /start komutu ----------------

def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    subs = load_subscribers()
    if chat_id not in subs:
        subs.append(chat_id)
        save_subscribers(subs)
    # Her /start yazıldığında kullanıcıya artık daha uygun bir mesaj gönderiyoruz
    keyboard = [[InlineKeyboardButton("📩 Bildirimleri Kapat", callback_data='stop')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("✅ Bildirimler aktif edildi. Eğitim bildirimleri gönderilecektir.", reply_markup=reply_markup)

# ---------------- /stop komutu ----------------

def stop(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    subs = load_subscribers()
    if chat_id in subs:
        subs.remove(chat_id)
        save_subscribers(subs)
    # Bildirimler devre dışı bırakıldı ve bot artık kullanıcıya mesaj göndermeyecek
    keyboard = [[InlineKeyboardButton("🔔 Bildirimleri Aç", callback_data='start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🔕 Bildirimler devre dışı bırakıldı. Artık bildirim almayacaksınız.", reply_markup=reply_markup)

# ---------------- Main ----------------

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()

    bot = updater.bot

    # Bir kere çalıştırıp mevcut abonelere eğitimleri gönder
    egitimler = egitimleri_cek()
    subs = load_subscribers()
    for s in subs:
        try:
            gonder_egitimler(bot, s, egitimler)
        except Exception as e:
            print(f"Mesaj gönderme hatası {s}: {e}")

    updater.idle()

if __name__ == "__main__":
    main()
'''

path = "/mnt/data/ekat_bot_updated.py"
with open(path, "w", encoding="utf-8") as f:
    f.write(content)

subs_path = "/mnt/data/subscribers.json"
if not os.path.exists(subs_path):
    with open(subs_path, "w", encoding="utf-8") as f:
        json.dump([], f)

print("Wrote updated file to:", path)
