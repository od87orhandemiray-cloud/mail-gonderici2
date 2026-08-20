"""
Streamlit uygulamasinda import edilip kullanilir.
Gmail SMTP + App Password ile calisir (OAuth2 DEGIL).

Kurulum:
    pip install (ek paket gerekmiyor, smtplib Python standart kutuphanesinde)

Streamlit Secrets (Settings > Secrets) icerigi (baslik/section KULLANMA):

    GMAIL_USER = "primportfoy@gmail.com"
    GMAIL_APP_PASSWORD = "xxxxxxxxxxxxxxxx"

Not: GMAIL_APP_PASSWORD, normal Gmail sifren DEGIL. Google hesabinda
2 adimli dogrulama acik olmali, sonra "Uygulama Sifreleri" (App Passwords)
sayfasindan 16 haneli bir sifre uretilir. Bu sifreyi asla kod icine yazma,
sadece Streamlit Secrets'a gir.
"""

import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import streamlit as st

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL


def secrets_configured() -> bool:
    """Gerekli secret'larin hepsi tanimli mi kontrol eder."""
    required = ["GMAIL_USER", "GMAIL_APP_PASSWORD"]
    return all(key in st.secrets for key in required)


def _html_to_plain_text(html: str) -> str:
    """
    HTML'den kaba bir duz metin versiyonu cikarir.
    Mukemmel bir donusum degil ama spam filtreleri icin yeterli.
    """
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)  # kalan tum etiketleri sil
    text = re.sub(r"\n{3,}", "\n\n", text)  # fazla bos satirlari sadelestir
    return text.strip()


def send_html_email(
    to: str,
    subject: str,
    html_body: str,
    images: dict | None = None,
    unsubscribe_url: str | None = None,
) -> tuple[bool, str]:
    """
    HTML icerikli, plain-text alternatifli, istege bagli gomulu gorselli (cid)
    ve istege bagli unsubscribe linkli mail gonderir. Gmail SMTP + App Password
    kullanir.

    to: alici mail adresi
    subject: konu
    html_body: HTML icerik (icinde cid:resim1 gibi referanslar olabilir)
    images: {"resim1": bytes, "resim2": bytes, ...} seklinde gomulu gorseller
    unsubscribe_url: verilirse hem mail sonuna bir link eklenir hem de
                      List-Unsubscribe header'i ayarlanir (spam skorunu dusurur)

    Donus: (basarili_mi, hata_mesaji) -- basariliysa hata_mesaji bos string
    """
    try:
        gmail_user = st.secrets["GMAIL_USER"]
        gmail_app_password = st.secrets["GMAIL_APP_PASSWORD"]

        final_html = html_body
        if unsubscribe_url:
            final_html += (
                f'<p style="font-size:12px;color:#888;margin-top:24px;">'
                f'Bu listeden çıkmak isterseniz <a href="{unsubscribe_url}">buraya tıklayın</a>.'
                f"</p>"
            )

        # Once "alternative" katmani: plain text + html
        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(_html_to_plain_text(final_html), "plain", "utf-8"))
        alt_part.attach(MIMEText(final_html, "html", "utf-8"))

        # Disina "related" katmani: gomulu resimler icin
        msg = MIMEMultipart("related")
        msg["Subject"] = subject
        msg["From"] = gmail_user
        msg["To"] = to

        if unsubscribe_url:
            msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        msg.attach(alt_part)

        if images:
            for cid_name, img_bytes in images.items():
                mime_img = MIMEImage(img_bytes)
                mime_img.add_header("Content-ID", f"<{cid_name}>")
                mime_img.add_header("Content-Disposition", "inline", filename=cid_name)
                msg.attach(mime_img)

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(gmail_user, gmail_app_password)
            server.sendmail(gmail_user, [to], msg.as_string())

        return True, ""

    except Exception as e:
        return False, str(e)
