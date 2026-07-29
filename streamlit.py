def run_scraper(target_jobs, usd_rate):
    results = []
    
    # Streamlit Cloud (Linux/Permission-safe) Driver Yapılandırması
    driver = Driver(
        browser="chrome",
        headless=True,
        uc=False,  # Cloud yetki hatalarını engellemek için uc kapalı olmalı
        agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--window-size=1920,1080"
    )

    progress_bar = st.progress(0)
    status_text = st.empty()
    total_jobs = len(target_jobs)

    try:
        for idx, job in enumerate(target_jobs):
            # ... (Geri kalan kod yapın birebir aynı kalıyor)
