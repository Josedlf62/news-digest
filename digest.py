#!/usr/bin/env python3
"""Resumen diario de noticias por correo via NewsAPI."""

import smtplib
import ssl
import os
import json
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta

NEWSAPI_KEY = os.environ["NEWSAPI_KEY"]

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

MAX_ITEMS = 7


def fecha_en_espanol() -> str:
    hoy = datetime.now()
    return f"{DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"


def fetch_news(query: str, language: str = "es") -> list[dict]:
    desde = (datetime.now() - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%S")
    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={urllib.request.quote(query)}"
        f"&language={language}"
        f"&from={desde}"
        f"&sortBy=publishedAt"
        f"&pageSize={MAX_ITEMS}"
        f"&apiKey={NEWSAPI_KEY}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "news-digest/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return [
            {"title": a["title"], "link": a["url"]}
            for a in data.get("articles", [])
            if a.get("title") and a.get("url") and "[Removed]" not in a["title"]
        ]
    except Exception as e:
        print(f"Error fetching '{query}': {e}")
        return []


SECTIONS = {
    "🇨🇱 Nacional": ('Chile AND (gobierno OR economía OR política OR sociedad)', "es"),
    "🌍 Internacional": ("(Estados Unidos OR Europa OR Asia OR guerra OR economía global)", "es"),
    "⚽ Deportes": ("(fútbol OR tenis OR Copa OR campeonato OR selección chilena)", "es"),
}


def build_html(sections: dict) -> str:
    date_str = fecha_en_espanol()
    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 680px; margin: auto; color: #222;">
    <h1 style="background:#c0392b;color:white;padding:16px;border-radius:6px;">
        📰 Resumen de Noticias — {date_str}
    </h1>
    """
    for category, items in sections.items():
        html += f'<h2 style="border-bottom:2px solid #c0392b;padding-bottom:4px;">{category}</h2>'
        if items:
            html += "<ul style='line-height:2;'>"
            for item in items:
                html += f'<li><a href="{item["link"]}" style="color:#2980b9;text-decoration:none;">{item["title"]}</a></li>'
            html += "</ul>"
        else:
            html += "<p style='color:#999;'>No se pudieron obtener noticias.</p>"
    html += "</body></html>"
    return html


def send_email(html: str) -> None:
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]
    recipients = [r.strip() for r in os.environ["EMAIL_RECIPIENT"].split(",")]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📰 Noticias del día — {datetime.now().strftime('%d/%m/%Y')}"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())
    print("Correo enviado correctamente.")


def main() -> None:
    sections = {}
    for category, (query, lang) in SECTIONS.items():
        sections[category] = fetch_news(query, lang)

    html = build_html(sections)
    send_email(html)


if __name__ == "__main__":
    main()
