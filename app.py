"""
app.py - Servidor intermediario IGDisplay
Desplegado en Render.com (plan gratuito)

El Pico W llama a:
  GET /followers/<username>
  → {"ok": true, "count": 12500, "username": "usuario"}

También expone:
  GET /ping  → {"ok": true}  (para mantener vivo el servidor)
"""

from flask import Flask, jsonify
import requests
import time
import os

app = Flask(__name__)

# Cache simple en memoria para no saturar Instagram
# { "usuario": {"count": 1234, "ts": 1234567890} }
_cache = {}
CACHE_TTL = 240  # segundos (4 minutos — el Pico consulta cada 5)

HEADERS = {
    "User-Agent": "Instagram 76.0.0.15.395 Android (24/7.0; 380dpi; 1080x1920; OnePlus; ONEPLUS A3010; OnePlus3T; qcom; en_US; 111396733)",
    "Accept": "*/*",
    "Accept-Language": "en-US",
    "Accept-Encoding": "gzip, deflate",
    "X-IG-Capabilities": "3brTvw==",
    "X-IG-Connection-Type": "WIFI",
    "X-IG-App-ID": "936619743392459",
}


def fetch_followers(username: str):
    """Obtiene seguidores desde la página pública de Instagram."""
    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()

    # Instagram embebe los datos en un JSON dentro del HTML
    html = r.text
    marker = '"edge_followed_by":{"count":'
    idx = html.find(marker)
    if idx == -1:
        raise ValueError("No se encontró el conteo en el HTML")
    start = idx + len(marker)
    end = html.index("}", start)
    count = int(html[start:end])
    return count


@app.route("/ping")
def ping():
    return jsonify({"ok": True, "ts": int(time.time())})


@app.route("/followers/<username>")
def followers(username: str):
    username = username.lower().strip()

    # Validación básica
    if not username or len(username) > 30:
        return jsonify({"ok": False, "error": "usuario inválido"}), 400

    # Revisar caché
    cached = _cache.get(username)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL:
        return jsonify({
            "ok": True,
            "count": cached["count"],
            "username": username,
            "cached": True
        })

    # Consultar Instagram
    try:
        count = fetch_followers(username)
        _cache[username] = {"count": count, "ts": time.time()}
        return jsonify({
            "ok": True,
            "count": count,
            "username": username,
            "cached": False
        })

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else 0
        if status == 404:
            return jsonify({"ok": False, "error": "usuario no encontrado"}), 404
        if status == 429:
            # Rate limit: devolver caché viejo si existe
            if cached:
                return jsonify({
                    "ok": True,
                    "count": cached["count"],
                    "username": username,
                    "cached": True,
                    "warning": "rate_limit"
                })
            return jsonify({"ok": False, "error": "rate_limit"}), 429
        return jsonify({"ok": False, "error": f"http_{status}"}), 502

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
