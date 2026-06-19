#!/usr/bin/env python3
"""Resumen diario de noticias por correo."""

import smtplib
import ssl
import os
import json
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta

NEWSAPI_KEY = os.environ["NEWSAPI_KEY"]
GNEWS_KEY = os.environ["GNEWS_KEY"]

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

MAX_ITEMS = 7


def fecha_en_espanol() -> str:
    hoy = datetime.now()
    return f"{DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"


def fetch_newsapi(query: str) -> list[dict]:
    desde = (datetime.now() - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%S")
    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={urllib.request.quote(query)}"
        f"&language=es"
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
        print(f"Error NewsAPI '{query}': {e}")
        return []


def fetch_newsapi_deportes() -> list[dict]:
    """Usa el endpoint de top headlines con categoría sports para mayor precisión."""
    url = (
        f"https://newsapi.org/v2/top-headlines"
        f"?category=sports"
        f"&language=es"
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
        print(f"Error NewsAPI deportes: {e}")
        return []


def fetch_gnews(query: str) -> list[dict]:
    url = (
        f"https://gnews.io/api/v4/search"
        f"?q={urllib.request.quote(query)}"
        f"&lang=es"
        f"&max={MAX_ITEMS}"
        f"&sortby=publishedAt"
        f"&token={GNEWS_KEY}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "news-digest/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return [
            {"title": a["title"], "link": a["url"]}
            for a in data.get("articles", [])
            if a.get("title") and a.get("url")
        ]
    except Exception as e:
        print(f"Error GNews '{query}': {e}")
        return []


def fetch_finanzas() -> list[dict]:
    """Obtiene precios clave usando Yahoo Finance (sin API key)."""
    tickers = {
        "Dólar (USD/CLP)": "USDCLP=X",
        "IPSA (Chile)": "^IPSA",
        "Cobre (USD/lb)": "HG=F",
        "S&P 500": "^GSPC",
        "Petróleo Brent": "BZ=F",
    }
    items = []
    for nombre, ticker in tickers.items():
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(ticker)}?interval=1d&range=2d"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            result = data["chart"]["result"][0]
            closes = result["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]
            if len(closes) >= 2:
                hoy = closes[-1]
                ayer = closes[-2]
                cambio = ((hoy - ayer) / ayer) * 100
                flecha = "▲" if cambio >= 0 else "▼"
                color = "#27ae60" if cambio >= 0 else "#c0392b"
                items.append({
                    "title": f"{nombre}: {hoy:,.2f} <span style='color:{color}'>{flecha} {abs(cambio):.2f}%</span>",
                    "link": f"https://finance.yahoo.com/quote/{ticker}"
                })
        except Exception as e:
            print(f"Error Yahoo Finance '{ticker}': {e}")
    return items


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
            html += "<p style='color:#999;'>No se pudieron obtener datos.</p>"
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
    sections = {
        "🇨🇱 Nacional": fetch_newsapi('(Chile) AND (gobierno OR Boric OR Congreso OR ministro OR municipio OR crimen OR terremoto OR incendio OR salud OR educación) NOT deporte NOT fútbol NOT bolsa'),
        "🌍 Internacional": fetch_gnews("(guerra OR diplomacia OR elecciones OR economía mundial OR conflicto OR ONU OR Trump OR Europa OR Asia) NOT Chile NOT deporte"),
        "⚽ Deportes": fetch_newsapi_deportes(),
        "📈 Mercados": fetch_finanzas(),
    }
    html = build_html(sections)
    send_email(html)


if __name__ == "__main__":
    main()
