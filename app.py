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
    """Obtiene el número de seguidores de una cuenta pública de Instagram."""
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()
    count = data["data"]["user"]["edge_followed_by"]["count"]
    return int(count)


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
