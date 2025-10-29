import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import json

# Telegram bot ayarları
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment değişkeni eksik!")

BASE_URL = "https://api.telegram.org/bot" + BOT_TOKEN

# Abone listesi
SUBSCRIBERS_FILE = "subscribers.json"

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    with open(SUBSCRIBERS_FILE, "r") as f:
        return json.load(f)

def save_subscribers(subs):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subs, f)

def telegram_mesaj_gonder(chat_id, mesaj):
    url = f"{BASE_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": mesaj}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Telegram mesaj hatası: {e}")

def egitimleri_cek():
    try:
        url = "https://ekat.euas.gov.tr"
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.find_all("div", class_="training-card")
        egitimler = []

        for card in cards:
            baslik = card.find("h3", class_="training-title").get_text(strip=True)
            yer = None
            baslama = None
            bitis = None
            dolu = None
            kontenjan = None
            kalan = None

            for p in card.find_all("p"):
                t = p.get_text(strip=True)
                if "Eğitim Yeri:" in t:
                    yer = t.replace("Eğitim Yeri:", "").strip()
                elif "Eğitim Başlama Tarihi:" in t:
                    baslama = t.replace("Eğitim Başlama Tarihi:", "").strip()
                elif "Eğitim Bitiş Tarihi:" in t:
                    bitis = t.replace("Eğitim Bitiş Tarihi:", "").strip()
                elif "Dolu Kontenjan:" in t:
                    dolu = t.replace("Dolu Kontenjan:", "").strip()
                elif "Eğitim Kontenjan:" in t:
                    kontenjan = t.replace("Eğitim Kontenjan:", "").strip()
                elif "Kalan Kontenjan:" in t:
                    kalan = t.replace("Kalan Kontenjan:", "").strip()

            if yer or baslama or bitis:
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
        print(f"Eğitim çekme hatası: {e}")
        return []

def main():
    subs = load_subscribers()
    egitimler = egitimleri_cek()
    tarih = datetime.now().strftime("[%d/%m/%Y %H:%M]")

    if not egitimler:
        mesaj = f"{tarih} ❌ Aktif eğitim yoktur."
    else:
        mesaj = f"{tarih} ✅ {len(egitimler)} adet aktif eğitim bulundu:\n\n"
        for e in egitimler:
            mesaj += (
                f"📘 {e['baslik']}\n"
                f"🏫 Eğitim yeri: {e['yer']}\n"
                f"🗓️ Başlama: {e['baslama']}\n"
                f"📅 Bitiş: {e['bitis']}\n"
                f"👥 Dolu Kontenjan: {e['dolu']}\n"
                f"🎯 Eğitim Kontenjanı: {e['kontenjan']}\n"
                f"🧮 Kalan: {e['kalan']}\n"
                "-------------------------\n"
            )

    for s in subs:
        telegram_mesaj_gonder(s, mesaj)
        print(f"Mesaj gönderildi → {s}")

if __name__ == "__main__":
    main()
