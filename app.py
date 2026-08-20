import streamlit as st
import re
import time
import base64

from gmail_sender import send_html_email, secrets_configured

st.set_page_config(page_title="Toplu Mail Gönderici", layout="wide")
st.title("📧 Toplu Mail Gönderici")

# ---------------------------------------------------------
# Session state başlangıç değerleri
# ---------------------------------------------------------
if "parsed_emails" not in st.session_state:
    st.session_state.parsed_emails = []
if "images" not in st.session_state:
    st.session_state.images = {}  # {"resim1": bytes, "resim2": bytes, ...}

EMAIL_REGEX = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"

# ===========================================================
# 1) MAİL LİSTESİ - Toplu yapıştır + ayrıştır
# ===========================================================
st.header("1️⃣ Alıcı Listesi")

raw_text = st.text_area(
    "Mail adreslerini buraya istediğin formatta yapıştır (virgülle, alt alta, karışık metin içinde fark etmez):",
    height=180,
    placeholder="ornek1@gmail.com, ornek2@hotmail.com\nornek3@yahoo.com ...",
)

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🔍 Ayrıştır", use_container_width=True):
        found = re.findall(EMAIL_REGEX, raw_text)
        # küçük harfe çevir + tekrarları temizle + sırayı koru
        seen = set()
        cleaned = []
        for e in found:
            e_low = e.strip().lower()
            if e_low not in seen:
                seen.add(e_low)
                cleaned.append(e_low)
        st.session_state.parsed_emails = cleaned

with col2:
    if st.session_state.parsed_emails:
        st.success(f"{len(st.session_state.parsed_emails)} adet geçerli, tekrarsız mail bulundu.")

if st.session_state.parsed_emails:
    edited = st.data_editor(
        {"Mail Adresi": st.session_state.parsed_emails},
        num_rows="dynamic",
        use_container_width=True,
        key="email_editor",
    )
    # kullanıcı tablo üzerinde satır silip ekleyebilir, güncel listeyi al
    st.session_state.parsed_emails = [e for e in edited["Mail Adresi"] if e and e.strip()]

st.divider()

# ===========================================================
# 2) MAİL İÇERİĞİ - Konu + HTML + Görseller
# ===========================================================
st.header("2️⃣ Mail İçeriği")

subject = st.text_input("Konu Başlığı", placeholder="Örn: Yeni Kampanyamızı Kaçırma!")

st.markdown(
    "Görselleri yükle, sana bir **cid** ismi vereceğim (örn. `resim1`). "
    "HTML içeriğinde görselin çıkmasını istediğin yere şunu yaz:\n\n"
    "`<img src=\"cid:resim1\" style=\"width:100%;\">`"
)

uploaded_images = st.file_uploader(
    "Görselleri yükle (birden fazla seçebilirsin)",
    type=["png", "jpg", "jpeg", "gif"],
    accept_multiple_files=True,
)

if uploaded_images:
    st.session_state.images = {}
    for i, img in enumerate(uploaded_images, start=1):
        cid_name = f"resim{i}"
        st.session_state.images[cid_name] = img.getvalue()
    cols = st.columns(len(uploaded_images))
    for i, (cid_name, img_bytes) in enumerate(st.session_state.images.items()):
        with cols[i]:
            st.image(img_bytes, caption=f'cid:{cid_name}', use_container_width=True)

html_body = st.text_area(
    "HTML İçerik",
    height=300,
    placeholder='<h1>Merhaba!</h1>\n<p>Kampanyamız başladı.</p>\n<img src="cid:resim1" style="width:100%;">',
)

with st.expander("👁️ Önizleme"):
    preview_html = html_body
    for cid_name, img_bytes in st.session_state.images.items():
        b64 = base64.b64encode(img_bytes).decode()
        preview_html = preview_html.replace(
            f'cid:{cid_name}', f'data:image/png;base64,{b64}'
        )
    st.markdown(preview_html, unsafe_allow_html=True)

st.divider()

# ===========================================================
# 3) SPAM'İ AZALTMA AYARLARI
# ===========================================================
st.header("3️⃣ Spam Önleme Ayarları")

unsubscribe_url = st.text_input(
    "Abonelikten çık (unsubscribe) linki",
    placeholder="https://sirketiniz.com/abonelikten-cik",
    help=(
        "Zorunlu değil ama şiddetle önerilir. Bu linki verirsen mail hem "
        "'List-Unsubscribe' header'ı ile işaretlenir hem de mail sonuna görünür "
        "bir link eklenir — bu, Gmail/Outlook gibi servislerin spam skorunu "
        "düşürmesine yardımcı olan önemli bir sinyaldir."
    ),
)

st.divider()

# ===========================================================
# 4) GÖNDER
# ===========================================================
st.header("4️⃣ Gönder")

st.info(
    "Gönderim, Gmail API (OAuth2) üzerinden yapılır. Şifre veya App Password "
    "kullanılmaz, koda hiçbir zaman yazılmaz. Her mail hem HTML hem düz metin "
    "olarak gönderilir (spam filtreleri için önemli)."
)

if not secrets_configured():
    st.warning(
        "⚠️ Secrets ayarlanmamış. Streamlit Cloud'da uygulama ayarlarından "
        "'Secrets' bölümüne şunları ekle (başında [section] başlığı OLMADAN):\n\n"
        'GMAIL_USER = "primportfoy@gmail.com"\n'
        'GMAIL_APP_PASSWORD = "..."'
    )

can_send = (
    bool(st.session_state.parsed_emails)
    and bool(subject)
    and bool(html_body)
    and secrets_configured()
)

delay = st.slider(
    "Her mail arası bekleme süresi (saniye) — Gmail'i yormamak ve spam'e düşmemek için önemli",
    1, 15, 5,
)

if len(st.session_state.parsed_emails) > 50:
    st.warning(
        f"⚠️ {len(st.session_state.parsed_emails)} alıcı var. Hesap bu tür gönderime "
        "yeniyse ilk günlerde daha küçük gruplarla (ör. 30-50 kişi) başlayıp zamanla "
        "artırman, spam'e düşme riskini azaltır."
    )

if st.button("🚀 Gönder", type="primary", disabled=not can_send, use_container_width=True):
    progress = st.progress(0)
    status = st.empty()
    success_count = 0
    fail_list = []

    total = len(st.session_state.parsed_emails)

    for i, recipient in enumerate(st.session_state.parsed_emails, start=1):
        basarili, hata = send_html_email(
            to=recipient,
            subject=subject,
            html_body=html_body,
            images=st.session_state.images,
            unsubscribe_url=unsubscribe_url or None,
        )

        if basarili:
            success_count += 1
            status.text(f"✅ Gönderildi: {recipient} ({i}/{total})")
        else:
            fail_list.append((recipient, hata))
            status.text(f"❌ Hata: {recipient} — {hata}")

        progress.progress(i / total)
        time.sleep(delay)

    st.success(f"Bitti! {success_count}/{total} mail başarıyla gönderildi.")
    if fail_list:
        st.error("Gönderilemeyenler:")
        for addr, err in fail_list:
            st.write(f"- {addr}: {err}")
