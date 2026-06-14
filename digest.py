#!/usr/bin/env python3
"""Resumen diario de noticias por correo."""

import smtplib
import ssl
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import xml.etree.ElementTree as ET
import urllib.request

FEEDS = {
    "🇨🇱 Nacional": [
        ("Emol", "https://www.emol.com/rss/nacional.xml"),
        ("La Tercera", "https://www.latercera.com/feed/"),
    ],
    "🌍 Internacional": [
        ("Emol", "https://www.emol.com/rss/internacional.xml"),
        ("Diario Financiero", "https://www.df.cl/feed/"),
    ],
    "⚽ Deportes": [
        ("Emol Deportes", "https://www.emol.com/rss/deportes.xml"),
        ("La Tercera Deportes", "https://www.latercera.com/el-deportivo/feed/"),
    ],
}

MAX_ITEMS = 5


def fetch_feed(url: str) -> list[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            tree = ET.parse(resp)
        items = []
        for item in tree.findall(".//item")[:MAX_ITEMS]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            if title and link:
                items.append({"title": title, "link": link})
        return items
    except Exception:
        return []


def build_html(sections: dict) -> str:
    date_str = datetime.now().strftime("%A %d de %B de %Y")
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
    recipient = os.environ["EMAIL_RECIPIENT"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📰 Noticias del día — {datetime.now().strftime('%d/%m/%Y')}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
    print("Correo enviado correctamente.")


def main() -> None:
    sections = {}
    for category, sources in FEEDS.items():
        items = []
        for _, url in sources:
            items.extend(fetch_feed(url))
        sections[category] = items[:MAX_ITEMS]

    html = build_html(sections)
    send_email(html)


if __name__ == "__main__":
    main()
