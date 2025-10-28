# main.py
# Requisitos: requests, beautifulsoup4, playwright
# (Se intenta primero con requests; si falla se usa Playwright como fallback)

import os
import re
import time
import traceback
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.message import EmailMessage
import smtplib

# ---------- CONFIG from ENV (recommend to set as secrets in GitHub) ----------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", GMAIL_USER)

# Page(s) to check
URLS = [
    "https://autoparts.toyotaofnorthmiami.com/"
]

# Patterns to detect offers (percent, $ discount, free shipping, sale words)
OFFER_PATTERNS = [
    re.compile(r"\b\d{1,2}%\s*off\b", re.I),
    re.compile(r"\b\d{1,2}\s*%\b", re.I),
    re.compile(r"\$ ?\d{1,4}\s*(off|de descuento)?", re.I),
    re.compile(r"\bfree shipping\b", re.I),
    re.compile(r"\benv[ií]o gratis\b", re.I),
    re.compile(r"\bsale\b", re.I),
    re.compile(r"\bdiscount\b", re.I),
    re.compile(r"\boff\b", re.I),
    re.compile(r"\bpromo\b", re.I),
]

# Countdown patterns (HH:MM:SS) or human like "ends in 2 days"
COUNTDOWN_PATTERNS = [
    re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b"),
    re.compile(r"\bends in\b", re.I),
    re.compile(r"\bexpir\w+\b", re.I),
    re.compile(r"\b\d+\s*days?\b", re.I),
    re.compile(r"\b\d+\s*horas?\b", re.I),
]

# ---------- Utilities ----------
def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[telegram] faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        print("[telegram] error:", e)
        return False

def send_email(subject, body):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("[email] faltan credenciales GMAIL_USER o GMAIL_APP_PASSWORD")
        return False
    try:
        msg = EmailMessage()
        msg["From"] = GMAIL_USER
        msg["To"] = RECIPIENT_EMAIL
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print("[email] error:", e)
        return False

def find_offers_in_text(text):
    found = []
    for p in OFFER_PATTERNS:
        for m in p.finditer(text):
            snippet = text[max(0, m.start()-80):m.end()+80].strip()
            found.append(("offer", m.group(0), snippet))
    for p in COUNTDOWN_PATTERNS:
        for m in p.finditer(text):
            snippet = text[max(0, m.start()-80):m.end()+80].strip()
            found.append(("countdown", m.group(0), snippet))
    return found

# Try lightweight scrape (requests)
def scrape_requests(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ToyotaPartsBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        # Try to extract top-of-page area: header, hero, first 2000 chars of body text
        top_elems = []
        # header
        header = soup.find("header")
        if header:
            top_elems.append(header.get_text(" ", strip=True))
        # hero/banner common classes
        for cls in ["hero", "banner", "top-bar", "promo", "specials", "site-banner"]:
            el = soup.select_one(f".{cls}")
            if el:
                top_elems.append(el.get_text(" ", strip=True))
        # fallback: first big section
        body_text = soup.get_text(" ", separator=" ")
        snippet = body_text[:4000]
        top_elems.append(snippet)
        combined = " ".join(filter(None, top_elems)).lower()
        return combined
    except Exception as e:
        print("[scrape_requests] error:", e)
        return ""

# Fallback: Playwright to render JS and get page content
def scrape_playwright(url):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print("[playwright] import error - ensure playwright is installed:", e)
        return ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(url, timeout=30000)
            # wait a little for dynamic banners
            time.sleep(2)
            # try to query top area HTML
            # heuristics: check header, first <div>, elements with class containing 'banner' or 'promo'
            content_parts = []
            try:
                header_handle = page.query_selector("header")
                if header_handle:
                    content_parts.append(header_handle.inner_text())
            except:
                pass
            # check for elements likely to be the top banner
            selectors = [
                "div[class*='banner']",
                "div[class*='promo']",
                "div[class*='hero']",
                "div[class*='top']",
                "section[class*='banner']",
                "section[class*='promo']"
            ]
            for sel in selectors:
                try:
                    el = page.query_selector(sel)
                    if el:
                        txt = el.inner_text()
                        content_parts.append(txt)
                except:
                    pass
            # fallback: body inner text limited
            try:
                body_txt = page.content()
                # remove tags, keep text roughly
                # simple approach: use inner_text of body
                body_handle = page.query_selector("body")
                if body_handle:
                    content_parts.append(body_handle.inner_text()[:8000])
            except:
                pass
            browser.close()
            combined = " ".join([c for c in content_parts if c]).lower()
            return combined
    except Exception as e:
        print("[scrape_playwright] error:", e)
        traceback.print_exc()
        return ""

def check_site(url):
    # 1) Try requests
    print(f"[{datetime.now()}] Comprobando (requests): {url}")
    text = scrape_requests(url)
    findings = find_offers_in_text(text)
    if findings:
        print("[check_site] encontrados con requests")
        return findings, "requests"
    # 2) fallback: Playwright
    print(f"[{datetime.now()}] No se detectó con requests — probando Playwright render (JS)")
    text2 = scrape_playwright(url)
    findings2 = find_offers_in_text(text2)
    if findings2:
        print("[check_site] encontrados con playwright")
        return findings2, "playwright"
    # nothing found
    return [], None

def compose_message(url, findings, method):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not findings:
        body = f"🔎 Revisión: {now}\nURL: {url}\nNo hay descuentos activos en el banner superior."
        return body
    lines = [f"🚨 Oferta detectada ({now})\nURL: {url}\nDetectado por: {method}\n"]
    offer_lines = []
    countdown_lines = []
    for kind, match, snippet in findings:
        if kind == "offer":
            offer_lines.append(f"- Oferta: {match}  \n  snippet: {snippet[:200]}")
        else:
            countdown_lines.append(f"- Tiempo detectado: {match}  \n  snippet: {snippet[:200]}")
    if offer_lines:
        lines.append("Ofertas encontradas:")
        lines.extend(offer_lines)
    if countdown_lines:
        lines.append("\nTiempos / conteos:")
        lines.extend(countdown_lines)
    return "\n".join(lines)

def main():
    all_ok = False
    for url in URLS:
        try:
            findings, method = check_site(url)
            message = compose_message(url, findings, method or "none")
            # Always notify (opcion B)
            send_telegram(message)
            send_email("Alerta Toyota Parts - Oferta detectada" if findings else "Toyota Parts - Sin ofertas", message)
            all_ok = True
        except Exception as e:
            print("[main] error:", e)
            traceback.print_exc()
    if not all_ok:
        print("Proceso finalizado con errores.")

if __name__ == "__main__":
    main()
