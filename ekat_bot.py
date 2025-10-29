import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import json

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment değişkeni eksik!")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SUBSCRIBERS_FILE = "subscribers.json"

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    with open(SUBSCRIBERS_FILE, "r") as f:
        return json.load(f)

def save_subscribers(subs):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subs, f)

def telegram_mesaj_gonder(chat_id, mesaj, reply_markup=None):
    url = f"{BASE_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": mesaj, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
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
            baslik = card.find("h3", class_="training-title")
            baslik = baslik.get_text(strip=True) if baslik else "Bilinmiyor"
            yer = baslama = bitis = dolu = kontenjan = kalan = "Bilinmiyor"
            for p in card.find_all("p"):
                label = p.find("span", class_="training-label")
                if not label: continue
                label_text = label.get_text(strip=True)
                if label_text == "Dolu Kontenjan:":
                    used = p.find("span", class_="used-quotas")
                    dolu = used.get_text(strip=True) if used else p.get_text(strip=True).replace("Dolu Kontenjan:", "").strip()
                elif label_text == "Eğitim Kontenjan:":
                    kontenjan = p.get_text(strip=True).replace("Eğitim Kontenjan:", "").strip()
                elif label_text == "Kalan Kontenjan:":
                    used = p.find("span", class_="used-quotas")
                    kalan = used.get_text(strip=True) if used else p.get_text(strip=True).replace("Kalan Kontenjan:", "").strip()
                elif label_text == "Eğitim Yeri:":
                    yer = p.get_text(strip=True).replace("Eğitim Yeri:", "").strip()
                elif label_text == "Eğitim Başlama Tarihi:":
                    baslama = p.get_text(strip=True).replace("Eğitim Başlama Tarihi:", "").strip()
                elif label_text == "Eğitim Bitiş Tarihi:":
                    bitis = p.get_text(strip=True).replace("Eğitim Bitiş Tarihi:", "").strip()
            egitimler.append({"baslik": baslik, "yer": yer, "baslama": baslama, "bitis": bitis, "dolu": dolu, "kontenjan": kontenjan, "kalan": kalan})
        return egitimler
    except Exception as e:
        print(f"❌ Eğitim çekme hatası: {e}")
        return []

def main():
    subs = load_subscribers()
    egitimler = egitimleri_cek()
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
    buttons = {"keyboard": [[{"text": "📩 Bildirimleri Kapat"}]], "resize_keyboard": True}
    for s in subs:
        telegram_mesaj_gonder(s, mesaj, reply_markup=buttons)
        print(f"Mesaj gönderildi → {s}")

if __name__ == "__main__":
    main()
