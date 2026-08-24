import subprocess
import time
import requests
import json
import os
import sys
import asyncio
from urllib.parse import urlparse

# ==============================================================================
# 1. CONFIGURACIÓN DEL BOT
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CHANNELS_FILE = "channels.json"

def load_channels():
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "1": os.environ.get("STREAM_KEY_1", "4394528713:myDTS60UhFs8Q1cpXDDyaQ"),
        "2": os.environ.get("STREAM_KEY_2", "4400198885:PcUiiv-__sV28_Hnyq83Ew"),
        "3": os.environ.get("STREAM_KEY_3", "3936015063:nG8N_no46UfNuA6jXewiag")
    }

def save_channels(channels_dict):
    try:
        with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump(channels_dict, f, indent=2)
    except Exception:
        pass

CHANNELS = load_channels()
ADMIN_USER_ID = None
active_streams = {}

# ==============================================================================
# 2. AUTO-EXTRACTOR DE ENLACES M3U8 CON NAVEGADOR HEADLESS EN LA NUBE
# ==============================================================================
async def extract_m3u8_from_page(web_url, timeout=25):
    found_urls = []
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            def on_request(request):
                url = request.url
                if any(ext in url.lower() for ext in [".m3u8", "mono.m3u8", "index.m3u8", "tracks-v1a1"]):
                    if not any(ign in url.lower() for ign in ["google", "analytics", "doubleclick", "adroll", "clarity"]):
                        found_urls.append(url)

            page.on("request", on_request)

            try:
                await page.goto(web_url, timeout=timeout * 1000, wait_until="domcontentloaded")
                await asyncio.sleep(4)
                try:
                    await page.evaluate("""() => {
                        const els = document.querySelectorAll('button, .play, .vjs-big-play-button, video, iframe');
                        els.forEach(el => { try { el.click(); } catch(e){} });
                    }""")
                except Exception:
                    pass
                await asyncio.sleep(6)
            except Exception as e:
                print(f"Playwright navigation log: {e}")
            finally:
                await browser.close()
    except Exception as e:
        print(f"Playwright error: {e}")

    if found_urls:
        return found_urls[-1]
    return None

def resolve_stream_url(input_url):
    clean = clean_arg(input_url)
    # Si ya es un enlace directo m3u8
    if ".m3u8" in clean.lower():
        return clean
    
    # Si es una página web de partido, el bot la visita en la nube para generar el token con la IP de Railway
    print(f"Extrayendo señal en la nube desde: {clean}...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        extracted = loop.run_until_complete(extract_m3u8_from_page(clean))
        loop.close()
        if extracted:
            print(f"¡Señal extraída con éxito!: {extracted}")
            return extracted
    except Exception as e:
        print(f"Error en extracción: {e}")
    
    return clean

# ==============================================================================
# 3. GESTOR DE MULTI-TRANSMISIÓN
# ==============================================================================
def clean_arg(val):
    if not val:
        return ""
    return val.strip().strip("<>").strip('"').strip("'").strip()

def extract_referer(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/"
    except Exception:
        pass
    return "https://google.com/"

def start_single_stream(stream_id, raw_url, stream_key, label=None):
    if stream_id in active_streams:
        stop_single_stream(stream_id)

    stream_key = clean_arg(stream_key)
    source_url = resolve_stream_url(raw_url)

    destination = RTMP_SERVER + stream_key
    referer = extract_referer(source_url)
    headers = (
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n"
        f"Referer: {referer}\r\n"
        f"Origin: {referer.rstrip('/')}\r\n"
    )

    cmd = [
        "ffmpeg",
        "-re",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-fflags", "+nobuffer+genpts+igndts+discardcorrupt",
        "-headers", headers,
        "-i", source_url,
        "-vf", "scale=1280:720",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-b:v", "1800k",
        "-maxrate", "2000k",
        "-bufsize", "3600k",
        "-pix_fmt", "yuv420p",
        "-g", "60",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-bsf:a", "aac_adtstoasc",
        "-max_interleave_delta", "0",
        "-flvflags", "no_duration_filesize",
        "-f", "flv",
        destination
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    if proc.poll() is not None:
        return False, "FFmpeg cerró inmediatamente (enlace no disponible o bloqueo del servidor)."

    active_streams[stream_id] = {
        "process": proc,
        "url": source_url,
        "key": stream_key,
        "name": label if label else f"Canal {stream_id}",
        "start_time": time.time()
    }
    return True, source_url

def stop_single_stream(stream_id):
    if stream_id in active_streams:
        proc = active_streams[stream_id]["process"]
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        del active_streams[stream_id]
        return True
    return False

def stop_all_streams():
    ids = list(active_streams.keys())
    for sid in ids:
        stop_single_stream(sid)
    return len(ids)

# ==============================================================================
# 4. INTERFAZ DE BOT DE TELEGRAM
# ==============================================================================
def send_msg(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def handle_message(msg):
    global CHANNELS
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = msg.get("text", "").strip()

    if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
        send_msg(chat_id, "⛔ No tienes permisos para usar este bot.")
        return

    if text.startswith("/start") or text.startswith("/ayuda"):
        help_text = (
            "⚽ *BOT DE TRANSMISIÓN INTELIGENTE EN LA NUBE*\n\n"
            "📺 *Transmitir en canales guardados:*\n"
            "• `/c1 <URL>` $\\rightarrow$ Transmitir en Canal 1\n"
            "• `/c2 <URL>` $\\rightarrow$ Transmitir en Canal 2\n"
            "• `/c3 <URL>` $\\rightarrow$ Transmitir en Canal 3\n\n"
            "🌐 *¿Qué URL puedes enviar?*\n"
            "1. El enlace web del partido (ej. `https://istreameast.cx/...`)\n"
            "2. O el enlace `.m3u8` directo\n\n"
            "🔑 *Cambiar la clave (Stream Key) de un canal:*\n"
            "• `/set1 <NUEVA_KEY>` $\\rightarrow$ Cambiar clave del Canal 1\n"
            "• `/set2 <NUEVA_KEY>` $\\rightarrow$ Cambiar clave del Canal 2\n"
            "• `/set3 <NUEVA_KEY>` $\\rightarrow$ Cambiar clave del Canal 3\n"
            "• `/canales` $\\rightarrow$ Ver canales y claves guardadas\n\n"
            "📡 *Transmitir al instante en cualquier canal:*\n"
            "• `/stream <URL> <STREAM_KEY>`\n\n"
            "🛑 *Detener transmisiones:*\n"
            "• `/stop1` | `/stop2` | `/stop3`\n"
            "• `/stopall` $\\rightarrow$ Detener TODOS los partidos\n\n"
            "📊 *Estado en vivo:*\n"
            "• `/status` $\\rightarrow$ Ver partidos en vivo"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/canales"):
        txt = "📋 *CANALES CONFIGURADOS ACTUALMENTE:*\n\n"
        for cid, k in sorted(CHANNELS.items()):
            txt += f"• *Canal {cid}:* `{k}`\n"
        txt += "\n💡 Para cambiar una clave escribe: `/set1 <nueva_clave>`"
        send_msg(chat_id, txt)

    elif text.startswith("/set"):
        parts = text.split()
        if text.startswith("/set1") or text.startswith("/set2") or text.startswith("/set3"):
            cid = text[4:5]
            if len(parts) < 2:
                send_msg(chat_id, f"⚠️ *Uso:* `/set{cid} NUEVA_STREAM_KEY`")
                return
            new_key = clean_arg(parts[1])
        else:
            if len(parts) < 3:
                send_msg(chat_id, "⚠️ *Uso:* `/set NUMERO_CANAL STREAM_KEY`")
                return
            cid = clean_arg(parts[1])
            new_key = clean_arg(parts[2])

        CHANNELS[cid] = new_key
        save_channels(CHANNELS)
        send_msg(chat_id, f"✅ *¡Clave del Canal {cid} actualizada con éxito!*\n🔑 Nueva Stream Key: `{new_key}`")

    elif text.startswith("/c"):
        parts = text.split()
        cid = parts[0][2:]
        if not cid.isalnum():
            return
        if len(parts) < 2:
            send_msg(chat_id, f"⚠️ *Uso:* `/c{cid} <URL_DEL_PARTIDO_O_M3U8>`")
            return
        
        raw_url = clean_arg(parts[1])
        stream_key = clean_arg(CHANNELS.get(cid))
        if not stream_key:
            send_msg(chat_id, f"❌ El Canal {cid} no tiene ninguna clave configurada.\nConfigúrala primero con: `/set{cid} <STREAM_KEY>`")
            return

        send_msg(chat_id, f"⏳ *Procesando señal en la nube para Canal {cid}...*")
        ok, res = start_single_stream(cid, raw_url, stream_key, f"Canal {cid}")
        if ok:
            send_msg(chat_id, f"✅ *¡Transmisión ACTIVA en Canal {cid}!* 🚀\n📡 Key: `{stream_key[:8]}...`\n🔗 Señal: `{res[:35]}...`")
        else:
            send_msg(chat_id, f"❌ *Error:* {res}")

    elif text.startswith("/stream"):
        parts = text.split()
        if len(parts) < 3:
            send_msg(chat_id, "⚠️ *Uso:* `/stream <URL> <STREAM_KEY>`")
            return
        raw_url = clean_arg(parts[1])
        custom_key = clean_arg(parts[2])
        custom_id = f"custom_{len(active_streams) + 1}"
        send_msg(chat_id, "⏳ *Procesando señal personalizada en la nube...*")
        ok, res = start_single_stream(custom_id, raw_url, custom_key, f"Personalizado ({custom_id})")
        if ok:
            send_msg(chat_id, f"✅ *¡Transmisión ACTIVA!* 🚀\nID: `{custom_id}`\n📡 Key: `{custom_key[:8]}...`\n🔗 Señal: `{res[:35]}...`")
        else:
            send_msg(chat_id, f"❌ *Error:* {res}")

    elif text.startswith("/stop") and text != "/stopall":
        cid = clean_arg(text[5:])
        if not cid:
            send_msg(chat_id, "⚠️ *Uso:* `/stop1`, `/stop2` o `/stopall`")
            return
        if stop_single_stream(cid):
            send_msg(chat_id, f"🛑 *Canal {cid} detenido correctamente.*")
        else:
            send_msg(chat_id, f"ℹ️ El Canal {cid} no estaba transmitiendo.")

    elif text.startswith("/stopall"):
        count = stop_all_streams()
        send_msg(chat_id, f"🛑 *Se han detenido todas las transmisiones ({count} partidos cerrados).*")

    elif text.startswith("/status"):
        if not active_streams:
            send_msg(chat_id, "🔴 *No hay ninguna transmisión activa actualmente.*")
            return

        status_text = "🟢 *PARTIDOS TRANSMITIÉNDOSE EN DIRECTO:*\n\n"
        for sid, info in active_streams.items():
            elapsed = int(time.time() - info["start_time"])
            mins = elapsed // 60
            secs = elapsed % 60
            status_text += f"📺 *{info['name']}:*\n• ⏱️ Tiempo: `{mins}m {secs}s`\n• 📡 Key: `{info['key'][:8]}...`\n• 🔗 URL: `{info['url'][:35]}...`\n\n"
        send_msg(chat_id, status_text)

def main():
    print("🤖 Bot Multi-Canal con Auto-Extractor iniciado en la nube...")
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            resp = requests.get(url, timeout=35).json()
            if resp.get("ok"):
                for update in resp.get("result", []):
                    offset = update["update_id"] + 1
                    if "message" in update:
                        handle_message(update["message"])
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    main()
