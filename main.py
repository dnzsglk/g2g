import urllib.request
import requests
import json
import time
import glob
import os
from seleniumbase import Driver

# --- YAPILANDIRMA ---
TARGETS_FOLDER = "targets"
OUTPUT_FILE = "fiyat_raporu.txt"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def get_live_usd_try_rate():
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return float(data['rates']['TRY'])
    except Exception as e:
        print(f"[!] Canlı kur çekilemedi ({e}). Yedek kur kullanılıyor.")
        return 47.0

def send_discord_notification(results_summary, usd_rate, file_path):
    if not DISCORD_WEBHOOK_URL:
        print("[!] DISCORD_WEBHOOK_URL bulunamadı, bildirim atlanıyor.")
        return

    embed = {
        "title": "🎮 G2G Fiyat Tarama Raporu Bitti!",
        "color": 3066993,
        "fields": [
            {
                "name": "💵 Anlık USD Kuru",
                "value": f"1 USD = **{usd_rate:.4f} TL**",
                "inline": True
            },
            {
                "name": "📊 Toplam Taranan Oyun/Dosya",
                "value": f"**{len(results_summary)}** adet",
                "inline": True
            }
        ],
        "footer": {
            "text": "GitHub Actions Otomatik Tarayıcı Botu"
        },
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }

    summary_text = ""
    for item in results_summary[:10]:
        summary_text += f"• **{item['game']}** ({item['server']}): `{item['tr_price']}`\n"

    if summary_text:
        embed["fields"].append({
            "name": "🔍 Özet Fiyatlar",
            "value": summary_text[:1000],
            "inline": False
        })

    payload = {
        "content": "📢 **Otomatik Fiyat Taraması Tamamlandı!** Detaylı rapor ektedir.",
        "embeds": [embed]
    }

    try:
        with open(file_path, "rb") as f:
            files = {
                "file": (file_path, f, "text/plain"),
                "payload_json": (None, json.dumps(payload), "application/json")
            }
            res = requests.post(DISCORD_WEBHOOK_URL, files=files)
            if res.status_code in [200, 204]:
                print("[+] Discord bildirimi başarıyla gönderildi!")
            else:
                print(f"[!] Discord bildirim hatası: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[!] Discord gönderim hatası: {e}")

def load_all_target_files(folder_path):
    if not os.path.exists(folder_path):
        return []
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    jobs = []
    for file_path in txt_files:
        game_name = os.path.splitext(os.path.basename(file_path))[0]
        with open(file_path, "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip()]
        if len(lines) >= 1:
            jobs.append({
                "name": game_name,
                "url": lines[0],
                "servers": lines[1:]
            })
    return jobs

# --- ANA ÇALIŞMA AKIŞI ---
current_usd_rate = get_live_usd_try_rate()
valid_jobs = load_all_target_files(TARGETS_FOLDER)

if not valid_jobs:
    print("[!] Taranacak .txt dosyası bulunamadı.")
    exit()

print(f"[+] Toplam {len(valid_jobs)} adet dosya bulundu. Hızlı tarama başlatılıyor...")

# MAKSİMUM HIZ İÇİN OPTİMİZE EDİLMİŞ DRIVER
# Resim yükleme, ses, GPU ve gereksiz render bileşenleri kapatıldı
fast_chrome_args = (
    "--no-sandbox,"
    "--disable-dev-shm-usage,"
    "--disable-gpu,"
    "--blink-settings=imagesEnabled=false,"  # Görselleri yüklemez (Hız kazandırır)
    "--disable-extensions,"
    "--window-size=1920,1080"
)

driver = Driver(
    browser="chrome",
    headless=True,
    uc=False,
    agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    chromium_arg=fast_chrome_args
)

# Sayfa yüklenme zaman aşımını 15 saniyeye düşürüyoruz (Varsayılanı 60sn'dir)
driver.set_page_load_timeout(15)

results_summary = []

with open(OUTPUT_FILE, "w", encoding="utf-8") as out_file:
    out_file.write(f"RAPOR OLUŞTURULMA TARİHİ: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    out_file.write(f"HESAPLAMADA KULLANILAN ANLIK USD KURU: 1 USD = {current_usd_rate:.4f} TL\n")
    out_file.write("=" * 135 + "\n")
    out_file.write(
        f"{'OYUN':<18} | {'ARANAN SERVER / ÜRÜN (DETAY)':<55} | {'G2G USD':<12} | {'SGV ALIS USD':<14} | {'SGV ALIS TR':<14}\n"
    )
    out_file.write("=" * 135 + "\n")

    try:
        for job in valid_jobs:
            print(f"[+] '{job['name']}' taranıyor...")
            try:
                start_time = time.time()
                driver.get(job["url"])
                
                # Sabit 6 saniye yerine kısa ve dinamik bekleme
                time.sleep(2.5)
                driver.execute_script("window.scrollTo(0, 500);")
                time.sleep(1)

                js_find_exact_price = """
                    function getPriceForServer(targetName) {
                        var allElements = document.querySelectorAll('div, li, tr, article');
                        var matchedPrices = [];
                        allElements.forEach(function(el) {
                            if (el.innerText && el.innerText.toLowerCase().includes(targetName.toLowerCase())) {
                                var match = el.innerText.match(/(\\d[\\d\\.,]*)\\s*USD/);
                                if (match) {
                                    var pVal = parseFloat(match[1].replace(',', ''));
                                    if (pVal > 0) {
                                        matchedPrices.push({ length: el.innerText.length, price: pVal });
                                    }
                                }
                            }
                        });
                        if (matchedPrices.length > 0) {
                            matchedPrices.sort(function(a, b) { return a.length - b.length; });
                            return matchedPrices[0].price;
                        }
                        return null;
                    }
                    return getPriceForServer(arguments[0]);
                """

                target_servers = job["servers"] if job["servers"] else ["Genel"]

                for server_name in target_servers:
                    found_price = driver.execute_script(js_find_exact_price, server_name)

                    if found_price:
                        sgv_usd = found_price * 0.8
                        sgv_tr = sgv_usd * current_usd_rate
                        tr_str = f"{sgv_tr:.2f} TL"

                        out_file.write(
                            f"{job['name'][:18]:<18} | {server_name[:55]:<55} | {found_price:<12.6f} | {sgv_usd:<14.6f} | {sgv_tr:<14.4f}\n"
                        )
                        results_summary.append({
                            "game": job['name'],
                            "server": server_name,
                            "tr_price": tr_str
                        })
                    else:
                        out_file.write(
                            f"{job['name'][:18]:<18} | {server_name[:55]:<55} | Fiyat Bulunamadı\n"
                        )
                        results_summary.append({
                            "game": job['name'],
                            "server": server_name,
                            "tr_price": "Bulunamadı"
                        })

                out_file.write("-" * 135 + "\n")
                print(f"[✓] Tamamlandı ({time.time() - start_time:.2f} sn)")

            except Exception as e:
                out_file.write(f"{job['name'][:18]:<18} | Hata oluştu\n")
                out_file.write("-" * 135 + "\n")
                print(f"[!] Hata: {e}")

        out_file.write("=" * 135 + "\n")
        print("\nTaramalar tamamlandı!")

    finally:
        driver.quit()

send_discord_notification(results_summary, current_usd_rate, OUTPUT_FILE)
