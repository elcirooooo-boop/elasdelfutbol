import subprocess
import time
import requests
import json
import os
import sys
from urllib.parse import urlparse

BOT_TOKEN = "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs"
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CHANNELS_FILE = os.path.join(os.path.dirname(__file__), "channels_local.json")

def load_channels():
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "1": "4394528713:myDTS60UhFs8Q1cpXDDyaQ",
        "2": "4400198885:PcUiiv-__sV28_Hnyq83Ew",
        "3": "3936015063:nG8N_no46UfNuA6jXewiag"
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

def start_single_stream(stream_id, source_url, stream_key, label=None):
    if stream_id in active_streams:
        stop_single_stream(stream_id)

    source_url = clean_arg(source_url)
    stream_key = clean_arg(stream_key)

    destination = RTMP_SERVER + stream_key
    referer = extract_referer(source_url)
    
    headers = (
        f"Referer: {referer}\r\n"
        f"Origin: {referer.rstrip('/')}\r\n"
    )

    # Configuración de FFmpeg con -user_agent nativo para IPTV
    cmd = [
        "ffmpeg",
        "-user_agent", "IPTVSmartersPro",
        "-re",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "3",
        "-fflags", "+nobuffer+genpts+igndts+discardcorrupt",
        "-headers", headers,
        "-i", source_url,
        "-vf", "scale=1280:720",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-threads", "4",
        "-b:v", "1200k",
        "-maxrate", "1400k",
        "-bufsize", "2400k",
        "-pix_fmt", "yuv420p",
        "-g", "60",
        "-c:a", "aac",
        "-b:a", "96k",
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
        return False, "FFmpeg no pudo conectar a la señal."

    active_streams[stream_id] = {
        "process": proc,
        "url": source_url,
        "key": stream_key,
        "name": label if label else f"Canal {stream_id}",
        "start_time": time.time()
    }
    return True, "OK"

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
            "💻 *BOT DE TRANSMISIÓN (IPTV / Xtream Codes Optimizado)*\n\n"
            "📺 *Transmitir canal:*\n"
            "• `/c1 <URL>` $\\rightarrow$ Transmitir en Canal 1\n"
            "• `/c2 <URL>` $\\rightarrow$ Transmitir en Canal 2\n"
            "• `/stream <URL> <STREAM_KEY>` $\\rightarrow$ Personalizado\n\n"
            "🔑 *Claves:*\n"
            "• `/set1 <KEY>` | `/set2 <KEY>` | `/canales`\n\n"
            "🛑 *Detener:*\n"
            "• `/stop1` | `/stop2` | `/stopall`\n\n"
            "📊 *Estado:*\n"
            "• `/status` $\\rightarrow$ Ver partidos emitiéndose"
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
        send_msg(chat_id, f"✅ *¡Clave del Canal {cid} actualizada!*\n🔑 Nueva Stream Key: `{new_key}`")

    elif text.startswith("/c"):
        parts = text.split()
        cid = parts[0][2:]
        if not cid.isalnum():
            return
        if len(parts) < 2:
            send_msg(chat_id, f"⚠️ *Uso:* `/c{cid} URL_DEL_CANAL`")
            return
        
        m3u8_url = clean_arg(parts[1])
        stream_key = clean_arg(CHANNELS.get(cid))
        if not stream_key:
            send_msg(chat_id, f"❌ El Canal {cid} no tiene clave.\nConfigúrala con: `/set{cid} <STREAM_KEY>`")
            return

        send_msg(chat_id, f"⏳ *Iniciando transmisión en Canal {cid}...*")
        ok, res = start_single_stream(cid, m3u8_url, stream_key, f"Canal {cid}")
        if ok:
            send_msg(chat_id, f"✅ *¡Transmisión ACTIVA en Canal {cid}!* 🚀\n📡 Key: `{stream_key[:8]}...`\n⚡ Estado: 100% Fluido")
        else:
            send_msg(chat_id, f"❌ *Error al iniciar:* {res}")

    elif text.startswith("/stream"):
        parts = text.split()
        if len(parts) < 3:
            send_msg(chat_id, "⚠️ *Uso:* `/stream URL_DEL_CANAL STREAM_KEY`")
            return
        m3u8_url = clean_arg(parts[1])
        custom_key = clean_arg(parts[2])
        custom_id = f"custom_{len(active_streams) + 1}"
        send_msg(chat_id, "⏳ *Iniciando transmisión personalizada...*")
        ok, res = start_single_stream(custom_id, m3u8_url, custom_key, f"Personalizado ({custom_id})")
        if ok:
            send_msg(chat_id, f"✅ *¡Transmisión ACTIVA!* 🚀\nID: `{custom_id}`\n📡 Key: `{custom_key[:8]}...`\n⚡ Estado: 100% Fluido")
        else:
            send_msg(chat_id, f"❌ *Error al iniciar:* {res}")

    elif text.startswith("/stop") and text != "/stopall":
        cid = clean_arg(text[5:])
        if not cid:
            send_msg(chat_id, "⚠️ *Uso:* `/stop1`, `/stop2` o `/stopall`")
            return
        if stop_single_stream(cid):
            send_msg(chat_id, f"🛑 *Canal {cid} detenido correctamente.*")
        else:
            send_msg(chat_id, "ℹ️ Ese canal no estaba transmitiendo.")

    elif text.startswith("/stopall"):
        count = stop_all_streams()
        send_msg(chat_id, f"🛑 *Se han detenido todas las transmisiones ({count} canales cerrados).*")

    elif text.startswith("/status"):
        if not active_streams:
            send_msg(chat_id, "🔴 *No hay ninguna transmisión activa actualmente.*")
            return

        status_text = "🟢 *CANALES EN DIRECTO EN TELEGRAM:*\n\n"
        for sid, info in active_streams.items():
            elapsed = int(time.time() - info["start_time"])
            mins = elapsed // 60
            secs = elapsed % 60
            status_text += f"📺 *{info['name']}:*\n• ⏱️ Tiempo: `{mins}m {secs}s`\n• 📡 Key: `{info['key'][:8]}...`\n• 🔗 URL: `{info['url'][:35]}...`\n\n"
        send_msg(chat_id, status_text)

def main():
    print("=" * 65)
    print("     BOT @Elasdelfutbolbot CONECTADO CON SERVIDOR IPTV        ")
    print("=" * 65)
    print("\nEl bot está escuchando tus comandos en Telegram...")
    
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
