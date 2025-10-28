import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# ==============================
# 🔧 CONFIGURACIÓN DEL USUARIO
# ==============================
GMAIL_USER = "mytoyotapartsbot@gmail.com"
GMAIL_APP_PASSWORD = "jawm xgdo myxs ehjb"  # Tu contraseña de aplicación de Gmail
TELEGRAM_BOT_TOKEN = "8029188534:AAFxcqUHqGZxX_8ewFNCq5Adapt7LlKe1cI"  # Token del bot de Telegram
TELEGRAM_CHAT_ID = "5739742449"  # 

# Página a monitorear (puedes agregar más luego)
URL = "https://autoparts.toyotaofnorthmiami.com/"

# Palabras clave que indican ofertas
KEYWORDS = ["% off", "descuento", "free shipping", "$", "percent", "%", "rebate", "special", "save"]


# ==============================
# ✉️ FUNCIÓN PARA ENVIAR EMAIL
# ==============================
def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
    server.quit()


# ==============================
# 🤖 FUNCIÓN PARA ENVIAR TELEGRAM
# ==============================
def send_telegram(message):
    if TELEGRAM_CHAT_ID == "":
        print("⚠️ CHAT ID no configurado todavía")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    requests.post(url, data=payload)


# ==============================
# 🔍 FUNCIÓN PRINCIPAL
# ==============================
def check_discounts():
    response = requests.get(URL)
    content = response.text.lower()

    found = False
    offers = []

    for keyword in KEYWORDS:
        if keyword in content:
            offers.append(keyword)
            found = True

    if found:
        message = f"🎉 ¡Nueva oferta detectada el {datetime.now()}!\nURL: {URL}\nPalabras encontradas: {offers}"
        send_email("Nueva oferta Toyota", message)
        send_telegram(message)
        print("✅ Oferta detectada y notificada:", offers)
    else:
        print("🔎 No se encontraron nuevas ofertas hoy.")


# ==============================
# 🚀 EJECUTAR
# ==============================
if __name__ == "__main__":
    check_discounts()
