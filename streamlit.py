import streamlit as st
from seleniumbase import Driver
import urllib.request
import pandas as pd
import json
import time
import os

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title="G2G Fiyat Tarayıcı & SGV Hesaplayıcı",
    page_icon="🎮",
    layout="wide"
)

# --- CANLI KUR ÇEKME ---
@st.cache_data(ttl=600)  # Kuru 10 dakikada bir günceller
def get_live_usd_try_rate():
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return float(data['rates']['TRY'])
    except Exception:
        return 47.0

# --- FİYAT TARAMA FONKSİYONU ---
def run_scraper(target_jobs, usd_rate):
    results = []
    
    # Streamlit Cloud (Linux) ortamına uyumlu Chromium ayarları
    driver = Driver(
        uc=True, 
        headless=True, 
        agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        window_size="1920,1080"
    )

    progress_bar = st.progress(0)
    status_text = st.empty()
    total_jobs = len(target_jobs)

    try:
        for idx, job in enumerate(target_jobs):
            game_name = job["name"]
            url = job["url"]
            servers = job["servers"] if job["servers"] else ["Genel"]

            status_text.text(f"⏳ Taranıyor ({idx+1}/{total_jobs}): {game_name}")
            
            try:
                driver.get(url)
                time.sleep(6)
                driver.execute_script("window.scrollTo(0, 600);")
                time.sleep(3)

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
                                        matchedPrices.push({
                                            length: el.innerText.length,
                                            price: pVal
                                        });
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

                for server_name in servers:
                    found_price = driver.execute_script(js_find_exact_price, server_name)

                    if found_price:
                        sgv_usd = found_price * 0.8
                        sgv_tr = sgv_usd * usd_rate

                        results.append({
                            "Oyun / Dosya": game_name,
                            "Aranan Server / Ürün": server_name,
                            "G2G USD": round(found_price, 6),
                            "SGV Alış USD": round(sgv_usd, 6),
                            "SGV Alış TR (TL)": round(sgv_tr, 4)
                        })
                    else:
                        results.append({
                            "Oyun / Dosya": game_name,
                            "Aranan Server / Ürün": server_name,
                            "G2G USD": None,
                            "SGV Alış USD": None,
                            "SGV Alış TR (TL)": "Bulunamadı"
                        })

            except Exception:
                results.append({
                    "Oyun / Dosya": game_name,
                    "Aranan Server / Ürün": "Hata",
                    "G2G USD": None,
                    "SGV Alış USD": None,
                    "SGV Alış TR (TL)": "Hata Oluştu"
                })

            progress_bar.progress((idx + 1) / total_jobs)

        status_text.text("✅ Tüm taramalar başarıyla tamamlandı!")
        return results

    finally:
        driver.quit()

# --- ARAYÜZ (STREAMLIT) ---
st.title("🎮 G2G Otomatik Fiyat Tarayıcı Panel")
st.caption("Pazar yeri ilanlarını anlık canlı kur üzerinden hesaplar.")

usd_rate = get_live_usd_try_rate()

# Üst Bilgi Kartları
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Anlık Canlı USD Kuru", value=f"{usd_rate:.4f} TL")
with col2:
    st.metric(label="SGV Hesap Katsayısı", value="0.80 (USD * 0.8)")

st.divider()

# Yan Menü / Dosya Yükleme Alanı
st.sidebar.header("📁 Yapılandırma Dosyaları")
uploaded_files = st.sidebar.file_uploader(
    "Taranacak .txt dosyalarını seçin veya sürükleyin", 
    type=["txt"], 
    accept_multiple_files=True
)

target_jobs = []

if uploaded_files:
    for uploaded_file in uploaded_files:
        game_name = os.path.splitext(uploaded_file.name)[0]
        content = uploaded_file.read().decode("utf-8")
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        if lines:
            url = lines[0]
            servers = lines[1:]
            target_jobs.append({
                "name": game_name,
                "url": url,
                "servers": servers
            })

    st.sidebar.success(f"{len(target_jobs)} adet dosya yüklendi.")

# Tarama Başlatma Butonu
if st.button("🚀 Fiyat Taramasını Başlat", type="primary", use_container_width=True):
    if not target_jobs:
        st.warning("⚠️ Lütfen sol menüden en az bir adet `.txt` dosyası yükleyin!")
    else:
        with st.spinner("Tarayıcı çalışıyor, lütfen bekleyin..."):
            data = run_scraper(target_jobs, usd_rate)
            df = pd.DataFrame(data)

            # Tablo Gösterimi
            st.subheader("📊 Fiyat Raporu")
            st.dataframe(df, use_container_width=True)

            # İndirme Butonu (CSV)
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 Raporu CSV Olarak İndir",
                data=csv_data,
                file_name=f"fiyat_raporu_{int(time.time())}.csv",
                mime="text/csv"
            )
