import pyperclip
from pynput import keyboard
import pyautogui
import tkinter as tk
from tkinter import messagebox
import time
import threading
import requests
import queue


# --- AYARLAR ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_ADI = "gemma3:1b"  # Ana model (F8)
TEXT_MODEL_CANDIDATES = [
    MODEL_ADI,
    "gemma3:4b",
    "gemma3:12b",
    "codellama",
    "deepseek-coder",
]

KISAYOL_METIN = keyboard.Key.f8  # Kod seçimi için kısayol


# Global değişkenler
root = None
gui_queue = queue.Queue()
kisayol_basildi = False
menu_acik = False  # Menü açıkken tekrar tetiklemeyi önlemek için


# --- MENÜ SEÇENEKLERİ VE PROMPT'LAR ---
ISLEMLER = {
    "🔍 Kodu Satır Satır Açıkla": (
        "Sen deneyimli bir yazılım mühendisi ve teknik eğitmensin. "
        "Aşağıdaki kod parçasını satır satır veya blok blok Türkçe olarak açıkla. "
        "Kurallar:\n"
        "- Her önemli satır veya mantıksal blok için ne yaptığını açıkla\n"
        "- Kullanılan dil/framework'e özgü kavramları da kısaca anlat\n"
        "- Teknik terimleri Türkçe açıkla ama terimin kendisini de yaz\n"
        "- Yeni başlayanların da anlayabileceği sade bir dil kullan\n"
        "- Format: önce genel özet (2-3 cümle), sonra satır/blok açıklamaları\n"
        "Sadece açıklamayı ver, fazladan yorum ekleme.\n\nKod:"
    ),
    "♻️ Kodu Refactor Et (Temizle & İyileştir)": (
        "Sen clean code ve best practice konusunda uzman bir senior yazılım mühendisisin. "
        "Aşağıdaki kodu refactor et: daha okunabilir, daha verimli ve daha bakımı kolay hale getir. "
        "Kurallar:\n"
        "- Orijinal işlevselliği KORU, sadece yapıyı iyileştir\n"
        "- Değişken/fonksiyon isimlerini anlamlı hale getir\n"
        "- Tekrar eden kodları fonksiyona al\n"
        "- Gereksiz karmaşıklığı azalt\n"
        "- Kodun altına kısa bir 'Ne Değişti?' özeti ekle (madde madde)\n"
        "- Dili değiştirme (Python ise Python kal, JS ise JS kal)\n"
        "Sadece refactor edilmiş kodu ve değişiklik özetini ver.\n\nKod:"
    ),
    "🐛 Bug & Güvenlik Açığı Tara": (
        "Sen uygulama güvenliği ve hata ayıklama konusunda uzman bir yazılım mühendisisin. "
        "Aşağıdaki kodu analiz et ve olası hataları, güvenlik açıklarını, edge case'leri tespit et. "
        "Format:\n"
        "🔴 KRİTİK HATALAR (varsa)\n"
        "▸ [satır/blok]: [sorun açıklaması] → [öneri]\n\n"
        "🟡 UYARILAR & İYİLEŞTİRME ÖNERİLERİ\n"
        "▸ [satır/blok]: [sorun açıklaması] → [öneri]\n\n"
        "🟢 GENEL DEĞERLENDİRME\n"
        "[2-3 cümle genel yorum]\n\n"
        "Eğer kod sağlıklıysa bunu da belirt. Türkçe yaz.\n\nKod:"
    ),
    "📝 Docstring & Yorum Satırı Ekle": (
        "Sen yazılım dokümantasyonu konusunda uzman bir mühendissin. "
        "Aşağıdaki koda uygun docstring'ler ve açıklayıcı yorum satırları ekle. "
        "Kurallar:\n"
        "- Fonksiyon/sınıf varsa standart docstring formatı kullan (Google Style veya NumPy Style)\n"
        "- Parametreler, dönüş değerleri ve olası exceptionları belgele\n"
        "- Karmaşık mantık bloklarına inline yorum ekle\n"
        "- Yorumlar Türkçe olsun ama kod (değişken/fonksiyon adları) değişmesin\n"
        "- Aşırı yorum ekleme — sadece gerçekten açıklanması gereken yerlere ekle\n"
        "Sadece yorumlanmış kodu ver, başka açıklama ekleme.\n\nKod:"
    ),
    "🔄 Farklı Dile/Yaklaşıma Çevir": (
        "Sen çok dilli yazılım geliştirme konusunda uzman bir mühendissin. "
        "Aşağıdaki kodu analiz et. Önce hangi dilde yazıldığını tespit et, "
        "sonra aşağıdaki seçenekleri sun:\n\n"
        "1. Kodun yazıldığı dili belirt\n"
        "2. Kodu şu dillerde/yaklaşımlarda yeniden yaz (uygun olanları seç):\n"
        "   - Eğer Python ise: JavaScript/TypeScript versiyonu\n"
        "   - Eğer JS/TS ise: Python versiyonu\n"
        "   - Her iki durumda da: fonksiyonel yaklaşım (eğer orijinal OOP ise) veya tersi\n"
        "3. Çevirinin altına kısa notlar ekle (dil farklılıklarını açıkla)\n"
        "Türkçe notlar, ama kod hedef dilde olsun.\n\nKod:"
    ),
}


def get_available_text_model():
    """Kullanılabilir modeli seçer."""
    preferred_models = []
    for model in TEXT_MODEL_CANDIDATES:
        if model and model not in preferred_models:
            preferred_models.append(model)

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code != 200:
            return MODEL_ADI

        models = response.json().get("models", [])
        installed_lower = {m.get("name", "").lower(): m.get("name", "") for m in models}

        for candidate in preferred_models:
            candidate_lower = candidate.lower()
            if candidate_lower in installed_lower:
                return installed_lower[candidate_lower]

            candidate_base = candidate_lower.split(":")[0]
            for installed_name_lower, installed_name in installed_lower.items():
                if installed_name_lower.startswith(candidate_base + ":"):
                    return installed_name
    except Exception:
        pass

    return MODEL_ADI


def ollama_cevap_al(prompt):
    """Ollama API'den cevap al."""
    try:
        aktif_model = get_available_text_model()
        payload = {
            "model": aktif_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.4,
                "top_p": 0.90,
            },
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=180)

        if response.status_code == 200:
            result = response.json()
            return result.get("response", "").strip()

        err_msg = (
            f"Ollama API Hatası: {response.status_code}\n"
            f"Model: {aktif_model}\n"
            f"Cevap: {response.text}"
        )
        print(f"❌ {err_msg}")
        # BUG DÜZELTMESİ 1: messagebox artık doğrudan tuple değil, lambda ile kuyruğa ekleniyor
        gui_queue.put(lambda em=err_msg: messagebox.showerror("API Hatası", em))
        return None

    except requests.exceptions.ConnectionError:
        err_msg = (
            "Ollama'ya bağlanılamadı.\n"
            "Programın çalıştığından emin olun!\n"
            "(http://localhost:11434)"
        )
        print(f"❌ {err_msg}")
        gui_queue.put(lambda em=err_msg: messagebox.showerror("Bağlantı Hatası", em))
        return None
    except Exception as e:
        err_msg = f"Beklenmeyen Hata: {e}"
        print(f"❌ {err_msg}")
        gui_queue.put(lambda em=err_msg: messagebox.showerror("Hata", em))
        return None


def strip_code_fence(text):
    if not text:
        return text
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = lines[1:] if lines else []
        while lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def secili_metni_kopyala(max_deneme=5):
    """
    BUG DÜZELTMESİ 2: Sleep süresi artırıldı (0.2s → 0.35s),
    deneme sayısı 4'ten 5'e çıkarıldı.
    Ağır uygulamalarda Ctrl+C gecikmeli yanıt veriyordu.
    """
    sentinel = f"__KOD_ASISTAN__{time.time_ns()}__"
    try:
        pyperclip.copy(sentinel)
    except Exception:
        pass

    metin = ""
    for _ in range(max_deneme):
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.35)  # 0.2 → 0.35 (daha güvenilir)
        try:
            metin = pyperclip.paste()
        except Exception:
            continue
        if metin and metin.strip() and metin != sentinel:
            return metin

    try:
        if pyperclip.paste() == sentinel:
            pyperclip.copy("")
    except Exception:
        pass

    return ""


def sonuc_penceresi_goster(baslik, icerik):
    pencere = tk.Toplevel(root)
    pencere.title(f"🧠 {baslik}")
    pencere.geometry("900x620")
    pencere.minsize(640, 420)
    pencere.attributes("-topmost", True)
    pencere.configure(bg="#0d1117")

    baslik_frame = tk.Frame(pencere, bg="#161b22", pady=10)
    baslik_frame.pack(fill="x")
    tk.Label(
        baslik_frame,
        text=baslik,
        bg="#161b22",
        fg="#58a6ff",
        font=("Cascadia Code", 11, "bold"),
    ).pack(padx=15)

    frame = tk.Frame(pencere, bg="#0d1117")
    frame.pack(fill="both", expand=True, padx=12, pady=10)

    text_alani = tk.Text(
        frame,
        wrap="word",
        bg="#161b22",
        fg="#c9d1d9",
        insertbackground="#58a6ff",
        font=("Cascadia Code", 10),
        padx=14,
        pady=12,
        relief="flat",
        selectbackground="#264f78",
        selectforeground="#ffffff",
    )
    kaydirma = tk.Scrollbar(frame, command=text_alani.yview, bg="#161b22", troughcolor="#0d1117")
    text_alani.configure(yscrollcommand=kaydirma.set)

    text_alani.pack(side="left", fill="both", expand=True)
    kaydirma.pack(side="right", fill="y")

    text_alani.insert("1.0", icerik)
    text_alani.config(state="disabled")

    alt_frame = tk.Frame(pencere, bg="#0d1117")
    alt_frame.pack(fill="x", padx=12, pady=(0, 12))

    def panoya_kopyala():
        pyperclip.copy(icerik)
        kopyala_btn.config(text="✅ Kopyalandı!")
        pencere.after(2000, lambda: kopyala_btn.config(text="📋 Panoya Kopyala"))

    kopyala_btn = tk.Button(
        alt_frame,
        text="📋 Panoya Kopyala",
        command=panoya_kopyala,
        bg="#238636",
        fg="#ffffff",
        activebackground="#2ea043",
        activeforeground="#ffffff",
        relief="flat",
        font=("Segoe UI", 9, "bold"),
        padx=14,
        pady=7,
        cursor="hand2",
    )
    kopyala_btn.pack(side="left")

    tk.Button(
        alt_frame,
        text="Kapat",
        command=pencere.destroy,
        bg="#21262d",
        fg="#8b949e",
        activebackground="#30363d",
        activeforeground="white",
        relief="flat",
        font=("Segoe UI", 9),
        padx=14,
        pady=7,
        cursor="hand2",
    ).pack(side="right")

    pencere.focus_force()
    pencere.lift()


def islemi_yap(komut_adi, secili_metin):
    prompt_emri = ISLEMLER[komut_adi]
    full_prompt = f"{prompt_emri}\n\n{secili_metin}"

    print(f"⚙️  İşlem: {komut_adi}")
    print("⏳ Ollama ile analiz yapılıyor...")

    sonuc = ollama_cevap_al(full_prompt)
    if not sonuc:
        print("❌ Sonuç alınamadı.")
        return

    sonuc = strip_code_fence(sonuc)

    # BUG DÜZELTMESİ 1 (devam): lambda ile kuyruk — tuple unpack hatası yok
    gui_queue.put(lambda b=komut_adi, s=sonuc: sonuc_penceresi_goster(b, s))
    print("✅ Analiz tamamlandı, pencerede gösteriliyor.")


def process_queue():
    """
    BUG DÜZELTMESİ 3: Eski kod (func, args) tuple bekliyordu.
    Yeni kod callable (lambda) bekliyor — daha sade ve hatasız.
    """
    try:
        while True:
            try:
                task = gui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                task()  # lambda'yı doğrudan çağır
            except Exception as e:
                print(f"❌ GUI görev hatası: {e}")
    finally:
        if root:
            root.after(100, process_queue)


def menu_goster():
    """
    BUG DÜZELTMESİ 4: menu_acik bayrağı artık güvenilir şekilde sıfırlanıyor.
    Eski kodda finally bloğu menu_acik = False yapıyordu ama
    <Unmap> callback'i de aynı şeyi yapmaya çalışıyordu — çakışma vardı.
    Şimdi tek bir reset noktası var: menu.unpost() sonrası.
    """
    global menu_acik

    if menu_acik:
        return

    secili_metin = secili_metni_kopyala()
    if not secili_metin.strip():
        gui_queue.put(
            lambda: messagebox.showwarning(
                "Seçim Bulunamadı",
                "Lütfen önce bir kod bloğu seçin, sonra F8 ile menüyü açın.",
            )
        )
        return

    menu_acik = True

    menu = tk.Menu(
        root,
        tearoff=0,
        bg="#161b22",
        fg="#c9d1d9",
        activebackground="#58a6ff",
        activeforeground="#0d1117",
        font=("Segoe UI", 10),
    )

    menu.add_command(
        label="🧠 Kod Açıklama & Refactor Asistanı",
        state="disabled",
        font=("Segoe UI", 9, "bold"),
    )
    menu.add_separator()

    def komut_olustur(k_adi, s_metin):
        def komut_calistir():
            threading.Thread(
                target=islemi_yap, args=(k_adi, s_metin), daemon=True
            ).start()
        return komut_calistir

    for baslik in ISLEMLER.keys():
        menu.add_command(label=baslik, command=komut_olustur(baslik, secili_metin))

    menu.add_separator()
    menu.add_command(label="❌ İptal", command=lambda: None)

    try:
        x, y = pyautogui.position()
        menu.tk_popup(x, y)
    finally:
        # BUG DÜZELTMESİ 4: grab_release her durumda çağrılır, bayrak burada sıfırlanır
        try:
            menu.grab_release()
        except Exception:
            pass
        menu_acik = False


def on_press(key):
    global kisayol_basildi
    if key == KISAYOL_METIN and not kisayol_basildi:
        kisayol_basildi = True
        # BUG DÜZELTMESİ 5: menu_goster lambda olarak kuyruğa ekleniyor
        # Eski: gui_queue.put((menu_goster, ())) → process_queue func(*args) yapıyordu
        # ama args = () olduğunda menu_goster(()) → TypeError
        gui_queue.put(menu_goster)


def on_release(key):
    global kisayol_basildi
    if key == KISAYOL_METIN:
        kisayol_basildi = False


if __name__ == "__main__":
    print("=" * 60)
    print("🧠 Kod Açıklama & Refactor Asistanı")
    print("=" * 60)
    aktif_text_model = get_available_text_model()
    print(f"📦 Aktif Model (F8): {aktif_text_model}")
    print()
    print("🔧 Kullanım:")
    print("   1) Herhangi bir editörde veya tarayıcıda kod seçin")
    print("   2) F8 tuşuna basın")
    print("   3) Yapmak istediğiniz işlemi seçin")
    print()
    print("📋 Mevcut İşlemler:")
    for islem in ISLEMLER.keys():
        print(f"   {islem}")
    print()
    print("⚠️  Programı kapatmak için bu pencereyi kapatın veya Ctrl+C yapın.")
    print("=" * 60)

    try:
        test_response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if test_response.status_code == 200:
            print("✅ Ollama bağlantısı başarılı!")
        else:
            print("⚠️  Ollama'ya bağlanılamadı, servisi kontrol edin!")
    except Exception:
        print("⚠️  Ollama çalışmıyor olabilir! 'ollama serve' ile başlatın.")

    print()

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    root = tk.Tk()
    root.withdraw()
    root.after(100, process_queue)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Kapatılıyor...")
