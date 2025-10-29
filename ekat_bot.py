import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os

URL = "https://ekat.euas.gov.tr"
BOT_TOKEN = os.environ.get("BOT_TOKEN")  #
SUBSCRIBERS_FILE = "subscribers.json"

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []

def telegram_send_message(chat_id, text):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(api, data=data)

def ekat_check_and_notify():
    try:
        r = requests.get(URL, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        egitimler = soup.find_all("div", class_="training-card")

        zaman = datetime.now().strftime('%d/%m/%Y %H:%M')
        if not egitimler:
            mesaj = f"[{zaman}] ❌ Aktif eğitim yoktur."
        else:
            mesaj = f"[{zaman}] ✅ Aktif eğitimler:\n"
            for e in egitimler:
                title = e.find("h3", class_="training-title").get_text(strip=True)
                mesaj += f"• {title}\n"

        subscribers = load_subscribers()
        for cid in subscribers:
            telegram_send_message(cid, mesaj)
        print("Mesaj gönderildi:", mesaj)
    except Exception as e:
        print("Hata:", e)

if _name_ == "_main_":
    ekat_check_and_notify()
