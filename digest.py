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
        f"&pageSize=20"
        f"&apiKey={NEWSAPI_KEY}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "news-digest/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        items = []
        seen = set()
        for a in data.get("articles", []):
            title = a.get("title", "").strip()
            if not title or not a.get("url") or "[Removed]" in title:
                continue
            # Evitar duplicados: comparar primeras 40 letras en minúsculas
            key = title[:40].lower()
            if key not in seen:
                seen.add(key)
                items.append({"title": title, "link": a["url"]})
                if len(items) >= MAX_ITEMS:
                    break
        return items
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


def fetch_gnews_deportes() -> list[dict]:
    """Usa el endpoint de top headlines de GNews con categoría sports."""
    url = (
        f"https://gnews.io/api/v4/top-headlines"
        f"?category=sports"
        f"&lang=es"
        f"&max={MAX_ITEMS}"
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
        print(f"Error GNews deportes: {e}")
        return []


def fetch_ticker(ticker: str) -> dict | None:
    """Obtiene precio y variación de un ticker de Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(ticker)}?interval=1d&range=10d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        result = data["chart"]["result"][0]
        meta = result["meta"]
        closes = result["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        if len(closes) >= 2:
            hoy = closes[-1]
            ayer = closes[-2]
            cambio = ((hoy - ayer) / ayer) * 100
            return {"precio": hoy, "cambio": cambio, "ticker": ticker}
        # Respaldo: usar metadata cuando no hay suficientes cierres
        precio = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if precio and prev and prev > 0:
            cambio = ((precio - prev) / prev) * 100
            return {"precio": precio, "cambio": cambio, "ticker": ticker}
    except Exception as e:
        print(f"Error Yahoo Finance '{ticker}': {e}")
    return None


def formato_ticker(nombre: str, info: dict) -> dict:
    flecha = "▲" if info["cambio"] >= 0 else "▼"
    color = "#27ae60" if info["cambio"] >= 0 else "#c0392b"
    return {
        "title": f"{nombre}: {info['precio']:,.2f} <span style='color:{color}'>{flecha} {abs(info['cambio']):.2f}%</span>",
        "link": f"https://finance.yahoo.com/quote/{info['ticker']}"
    }


def fetch_finanzas() -> list[dict]:
    """Obtiene indicadores clave y mayores alzas del IPSA."""
    tickers_fijos = {
        "IPSA (Chile)": "^IPSA",
        "Dólar (USD/CLP)": "USDCLP=X",
        "Cobre (USD/lb)": "HG=F",
        "S&P 500": "^GSPC",
        "Petróleo Brent": "BZ=F",
        "LATAM Airlines": "LTM.SN",
        "Besalco": "BESALCO.SN",
    }

    items = []
    for nombre, ticker in tickers_fijos.items():
        info = fetch_ticker(ticker)
        if info:
            items.append(formato_ticker(nombre, info))

    # Mayores alzas del IPSA
    ipsa_tickers = {
        "Banco de Chile": "CHILE.SN", "BCI": "BCI.SN", "Banco Santander": "BSAN.SN",
        "CAP": "CAP.SN", "CCU": "CCU.SN", "Cencosud": "CENCOSUD.SN",
        "CMPC": "CMPC.SN", "Colbún": "COLBUN.SN", "Copec": "COPEC.SN",
        "Enel Chile": "ENELCHILE.SN", "Engie": "ECL.SN", "Falabella": "FALABELLA.SN",
        "ILC": "ILC.SN", "Itaú": "ITAUCL.SN", "LATAM": "LTM.SN",
        "Parque Arauco": "PARAUCO.SN", "Ripley": "RIPLEY.SN", "SQM-B": "SQM-B.SN",
        "Vapores": "VAPORES.SN", "Besalco": "BESALCO.SN",
    }

    alzas = []
    for nombre, ticker in ipsa_tickers.items():
        info = fetch_ticker(ticker)
        if info:
            alzas.append((nombre, info))

    alzas.sort(key=lambda x: x[1]["cambio"], reverse=True)
    if alzas:
        items.append({"title": "<b>📊 Mayores alzas del día:</b>", "link": "", "separator": True})
        for nombre, info in alzas[:2]:
            items.append(formato_ticker(nombre, info))

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
                if item.get("separator"):
                    html += f'</ul><p style="margin-top:12px;">{item["title"]}</p><ul style="line-height:2;">'
                elif item["link"]:
                    html += f'<li><a href="{item["link"]}" style="color:#2980b9;text-decoration:none;">{item["title"]}</a></li>'
                else:
                    html += f'<li>{item["title"]}</li>'
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
        "⚽ Deportes": fetch_gnews_deportes(),
        "📈 Mercados": fetch_finanzas(),
    }
    html = build_html(sections)
    send_email(html)


if __name__ == "__main__":
    main()
