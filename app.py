from flask import Flask, jsonify
from instagrapi import Client
import time
import os

# Carga el .env solo si existe (desarrollo local)
# En Render las variables ya están en el entorno, no necesita .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

_cache = {}
CACHE_TTL = 240

_ig_client = None

def get_client():
    global _ig_client
    if _ig_client is None:
        username = os.environ.get("IG_USERNAME")
        password = os.environ.get("IG_PASSWORD")
        if not username or not password:
            raise RuntimeError("Faltan variables IG_USERNAME e IG_PASSWORD")
        cl = Client()
        cl.login(username, password)
        _ig_client = cl
        print(f"[IG] Login exitoso como @{username}")
    return _ig_client

def fetch_followers(username: str):
    cl = get_client()
    user_id = cl.user_id_from_username(username)
    info = cl.user_info(user_id)
    return info.follower_count

@app.route("/ping")
def ping():
    return jsonify({"ok": True, "ts": int(time.time())})

@app.route("/followers/<username>")
def followers(username: str):
    username = username.lower().strip()
    if not username or len(username) > 30:
        return jsonify({"ok": False, "error": "usuario inválido"}), 400

    cached = _cache.get(username)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL:
        return jsonify({"ok": True, "count": cached["count"], "username": username, "cached": True})

    try:
        count = fetch_followers(username)
        _cache[username] = {"count": count, "ts": time.time()}
        return jsonify({"ok": True, "count": count, "username": username, "cached": False})
    except Exception as e:
        if cached:
            return jsonify({"ok": True, "count": cached["count"], "username": username, "cached": True, "warning": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
