import subprocess
import time
import requests
import json
import os
from urllib.parse import urlparse

# ==============================================================================
# CONFIGURACIÓN DEL BOT
# ==============================================================================
# 1. Pega aquí el Token que te da @BotFather en Telegram:
BOT_TOKEN = "PEGA_AQUI_TU_BOT_TOKEN_DE_BOTFATHER"

# 2. Tu ID de usuario de Telegram (para que solo tú puedas controlar el bot):
# Puedes obtener tu ID enviando un mensaje a @userinfobot en Telegram
ADMIN_USER_ID = None  # Ejemplo: 123456789 (o déjalo en None para permitirte a ti)

# 3. Datos por defecto de Telegram RTMP:
DEFAULT_RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
DEFAULT_STREAM_KEY = "4394528713:myDTS60UhFs8Q1cpXDDyaQ"

# ==============================================================================
# GESTIÓN DEL PROCESO DE STREAMING
# ==============================================================================
current_process = None
active_stream_info = None

def extract_referer(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/"
    except Exception:
        pass
    return "https://google.com/"

def start_stream(source_url, stream_key=None, server_url=None):
    global current_process, active_stream_info
    
    stop_stream() # Detener cualquier transmisión previa

    key = stream_key if stream_key else DEFAULT_STREAM_KEY
    server = server_url if server_url else DEFAULT_RTMP_SERVER
    if not server.endswith("/"):
        server += "/"
    rtmp_destination = server + key

    referer = extract_referer(source_url)
    headers = (
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n"
        f"Referer: {referer}\r\n"
        f"Origin: {referer.rstrip('/')}\r\n"
    )

    cmd = [
        "ffmpeg",
        "-reconnect", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-rw_timeout", "10000000",
        "-fflags", "+genpts+igndts+discardcorrupt",
        "-analyzeduration", "1000000",
        "-probesize", "1000000",
        "-headers", headers,
        "-i", source_url,
        "-vf", "fps=30,scale=1280:720",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-threads", "0",
        "-b:v", "1500k",
        "-maxrate", "1800k",
        "-bufsize", "3000k",
        "-pix_fmt", "yuv420p",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-bf", "0",
        "-af", "aresample=async=1000:min_hard_comp=0.100000:first_pts=0",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-bsf:a", "aac_adtstoasc",
        "-max_muxing_queue_size", "4096",
        "-max_interleave_delta", "0",
        "-flvflags", "no_duration_filesize",
        "-f", "flv",
        rtmp_destination
    ]

    current_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    active_stream_info = {
        "url": source_url,
        "key": key,
        "start_time": time.time()
    }
    return True

def stop_stream():
    global current_process, active_stream_info
    if current_process:
        try:
            current_process.terminate()
            current_process.wait(timeout=3)
        except Exception:
            current_process.kill()
        current_process = None
        active_stream_info = None
        return True
    return False

def is_streaming():
    global current_process
    if current_process and current_process.poll() is None:
        return True
    return False

# ==============================================================================
# BOT TELEGRAM (LONG POLLING SIMPLE)
# ==============================================================================
def send_msg(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def handle_message(msg):
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = msg.get("text", "").strip()

    if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
        send_msg(chat_id, "⛔ No tienes permisos para usar este bot.")
        return

    if text.startswith("/start") or text.startswith("/ayuda"):
        help_text = (
            "🤖 *Bot de Transmisión en la Nube*\n\n"
            "Comandos disponibles:\n"
            "• `/stream <URL_M3U8>` - Inicia la transmisión del partido.\n"
            "• `/stream <URL_M3U8> <STREAM_KEY>` - Inicia con otra clave.\n"
            "• `/stop` - Detiene la transmisión actual.\n"
            "• `/status` - Muestra el estado del stream."
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/stream"):
        parts = text.split()
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ *Uso:* `/stream <URL_DEL_M3U8>`")
            return
        
        m3u8_url = parts[1]
        custom_key = parts[2] if len(parts) > 2 else None

        send_msg(chat_id, "⏳ *Iniciando transmisión en la nube...*")
        success = start_stream(m3u8_url, custom_key)
        if success:
            send_msg(chat_id, f"✅ *¡Transmisión iniciada con éxito!*\n\n📡 Canal: `{custom_key if custom_key else DEFAULT_STREAM_KEY}`\n⚽ Fuente: {m3u8_url[:40]}...")
        else:
            send_msg(chat_id, "❌ Error al iniciar FFmpeg.")

    elif text.startswith("/stop"):
        if is_streaming():
            stop_stream()
            send_msg(chat_id, "🛑 *Transmisión detenida correctamente.*")
        else:
            send_msg(chat_id, "ℹ️ No hay ninguna transmisión activa.")

    elif text.startswith("/status"):
        if is_streaming():
            elapsed = int(time.time() - active_stream_info["start_time"])
            mins = elapsed // 60
            secs = elapsed % 60
            send_msg(chat_id, f"🟢 *EN VIVO (Activo)*\n⏱️ Tiempo: `{mins}m {secs}s`\n📡 Canal: `{active_stream_info['key']}`")
        else:
            send_msg(chat_id, "🔴 *Inactivo:* No hay ningún partido emitiéndose.")

def main():
    if BOT_TOKEN == "PEGA_AQUI_TU_BOT_TOKEN_DE_BOTFATHER":
        print("❌ Por favor edita el archivo bot_stream.py y coloca tu BOT_TOKEN.")
        return

    print("🤖 Bot de streaming iniciado y esperando comandos...")
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
