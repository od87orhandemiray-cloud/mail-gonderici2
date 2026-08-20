"""
Streamlit uygulamasinda import edilip kullanilir.
Sifre / App Password YOK, sadece OAuth2 refresh token ile calisir.

Kurulum:
    pip install google-auth google-api-python-client

requirements.txt'e eklenmesi gerekenler:
    google-auth
    google-api-python-client

Streamlit Secrets (Settings > Secrets) icerigi:

    GMAIL_CLIENT_ID = "xxxx.apps.googleusercontent.com"
    GMAIL_CLIENT_SECRET = "xxxx"
    GMAIL_REFRESH_TOKEN = "xxxx"
    GMAIL_SENDER = "sirket-maili@sirketiniz.com"
"""

import base64
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _get_gmail_service():
    """Secrets'taki refresh token ile Gmail servisine baglanir."""
    creds = Credentials(
        token=None,
        refresh_token=st.secrets["GMAIL_REFRESH_TOKEN"],
        client_id=st.secrets["GMAIL_CLIENT_ID"],
        client_secret=st.secrets["GMAIL_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds)


def secrets_configured() -> bool:
    """Gerekli secret'larin hepsi tanimli mi kontrol eder."""
    required = ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN", "GMAIL_SENDER"]
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
    ve istege bagli unsubscribe linkli mail gonderir.

    to: alici mail adresi
    subject: konu
    html_body: HTML icerik (icinde cid:resim1 gibi referanslar olabilir)
    images: {"resim1": bytes, "resim2": bytes, ...} seklinde gomulu gorseller
    unsubscribe_url: verilirse hem mail sonuna bir link eklenir hem de
                      List-Unsubscribe header'i ayarlanir (spam skorunu dusurur)

    Donus: (basarili_mi, hata_mesaji) -- basariliysa hata_mesaji bos string
    """
    try:
        service = _get_gmail_service()

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
        msg["From"] = st.secrets["GMAIL_SENDER"]
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

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True, ""

    except Exception as e:
        return False, str(e)
