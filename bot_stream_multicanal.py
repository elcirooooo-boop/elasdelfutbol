import subprocess
import time
import requests
import json
import os
import sys
import re
from urllib.parse import urlparse

# ==============================================================================
# 1. CONFIGURACIÓN DEL BOT Y CLAVE STREAM
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CONFIG_FILE = "config_stream.json"

IPTV_USER = "BE15ERDV"
IPTV_PASS = "PXELERB9"
IPTV_SERVER = "http://evestv.ptjfj.com"
IPTV_SERVER_ALT = "http://evestv.leptis.live"
AGENDA_API = "https://futbollibretv.org.pe/diaries.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "stream_key": os.environ.get("STREAM_KEY", "3936015063:nG8N_no46UfNuA6jXewiag")
    }

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

CONFIG = load_config()
ADMIN_USER_ID = None
active_streams = {}

# CANALES DE AUTO-RESOLUCIÓN EN VIVO (100% LIBRES / EN ESPAÑOL LATAM)
AUTO_CHANNELS = {
    "espn2": "https://futbollibre.ch/1.php?stream=espn2",
    "espn": "https://futbollibre.ch/1.php?stream=espn",
    "espn3": "https://futbollibre.ch/1.php?stream=espn3",
    "espn4": f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/1201550.ts",
    "espnextra": f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/30329.ts",
    "espnpremium": f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/4883.ts",
    "espndeportes": f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/32038.ts",
    "tyc": "https://futbollibre.ch/1.php?stream=tyc",
    "dsports": "https://futbollibre.ch/1.php?stream=directvsports",
    "dsports2": "https://futbollibre.ch/1.php?stream=directvsports2",
    "foxsports": "https://futbollibre.ch/1.php?stream=foxsports",
    "tntsports": f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/5987.ts",
    "laliga": f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33866.ts",
    "universo": f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/32038.ts",
}

def resolve_live_stream_url(target):
    target_clean = target.lower().strip()
    
    # Si ingresaron un ID numérico de IPTV (ej. 30327)
    if target_clean.isdigit():
        target = f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/{target_clean}.ts"
        referer = "http://evestv.leptis.live/"
        headers = f"Referer: {referer}\r\nOrigin: {referer.rstrip('/')}\r\n"
        return target, headers

    if target_clean in AUTO_CHANNELS:
        portal_url = AUTO_CHANNELS[target_clean]
        if "futbollibre" in portal_url:
            try:
                headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://rojadirectatv.ec/"}
                r = requests.get(portal_url, headers=headers, timeout=4)
                m3u8 = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', r.text)
                if m3u8:
                    return m3u8[0], "Referer: https://futbollibre.ch/\r\nOrigin: https://futbollibre.ch\r\n"
            except Exception as e:
                print(f"Error resolviendo canal libre {target}: {e}")
        else:
            return portal_url, "Referer: http://evestv.leptis.live/\r\nOrigin: http://evestv.leptis.live\r\n"

    referer = "https://google.com/"
    if "tvlibre.pe" in target or "futbollibre" in target:
        referer = "https://futbollibre.ch/"
    elif "leptis.live" in target or "ptjfj.com" in target:
        referer = "http://evestv.leptis.live/"
    
    headers = f"Referer: {referer}\r\nOrigin: {referer.rstrip('/')}\r\n"
    return target, headers

AGENDA_CMD_MAP = [
    ("espn 2", "espn2"),
    ("espn ar", "espn"),
    ("espn 3", "espn3"),
    ("espn 4", "espn4"),
    ("espn extra", "espnextra"),
    ("espn premium", "espnpremium"),
    ("espn deportes", "espndeportes"),
    ("espn", "espn"),
    ("tyc", "tyc"),
    ("tnt", "tntsports"),
    ("dsports 2", "dsports2"),
    ("dsports", "dsports"),
    ("directv 2", "dsports2"),
    ("directv", "dsports"),
    ("fox sports", "foxsports"),
    ("laliga", "laliga"),
    ("universo", "universo"),
]

def map_channel_short(ch_name):
    ch_clean = ch_name.lower().strip()
    for key, cmd in AGENDA_CMD_MAP:
        if key in ch_clean:
            return cmd
    return None

TOP_SPORTS_CHANNELS = [
    {"name": "ESPN 2 Sur HD (Mariano Closs)", "cmd": "espn2"},
    {"name": "ESPN 1 Sur HD (Español Latam)", "cmd": "espn"},
    {"name": "ESPN 3 Sur HD (Español Latam)", "cmd": "espn3"},
    {"name": "ESPN 4 HD (Español)", "cmd": "espn4"},
    {"name": "ESPN Extra Sur HD", "cmd": "espnextra"},
    {"name": "ESPN Premium (Liga Argentina)", "cmd": "espnpremium"},
    {"name": "TyC Sports HD (Argentina)", "cmd": "tyc"},
    {"name": "Directv Sports 1 (DSPORTS)", "cmd": "dsports"},
    {"name": "Directv Sports 2 (DSPORTS 2)", "cmd": "dsports2"},
    {"name": "Fox Sports HD", "cmd": "foxsports"},
    {"name": "LaLiga TV (FHD)", "cmd": "laliga"},
]

cached_streams = []

def get_iptv_streams():
    global cached_streams
    if cached_streams:
        return cached_streams
    try:
        api_url = f"{IPTV_SERVER_ALT}/player_api.php?username={IPTV_USER}&password={IPTV_PASS}&action=get_live_streams"
        r = requests.get(api_url, timeout=15, headers={"User-Agent": "IPTVSmartersPro"})
        if r.status_code == 200:
            cached_streams = r.json()
            return cached_streams
    except Exception as e:
        print(f"Error cargando canales IPTV: {e}")
    return []

def search_iptv_channels(query, max_results=8):
    streams = get_iptv_streams()
    results = []
    query_clean = query.lower().strip()
    for ch in streams:
        name = ch.get("name", "")
        sid = ch.get("stream_id")
        clean_name = re.sub(r'[^\x00-\x7F]+', ' ', name).strip()
        if query_clean in clean_name.lower():
            link = f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/{sid}.ts"
            results.append((clean_name, sid, link))
            if len(results) >= max_results:
                break
    return results

def get_live_agenda_messages(curr_key):
    try:
        r = requests.get(AGENDA_API, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json().get("data", [])
        if not data:
            return ["🔴 No hay partidos programados en la agenda en este momento."]

        messages = []
        current_msg = "📅 *AGENDA DEPORTIVA DE HOY (FÚTBOL EN VIVO)*\n\n"
        
        for item in data:
            attrs = item.get("attributes", {})
            desc = attrs.get("diary_description", "").strip()
            desc = desc.replace("\n", " ").replace("\r", "")
            hour = attrs.get("diary_hour", "")[:5]
            embeds = attrs.get("embeds", {}).get("data", [])

            partido_block = f"⚽ *{desc}* (`{hour}`)\n"
            
            seen_cmds = set()
            for em in embeds:
                em_name = em.get("attributes", {}).get("embed_name", "").strip()
                cmd_code = map_channel_short(em_name)
                
                if cmd_code and cmd_code not in seen_cmds:
                    seen_cmds.add(cmd_code)
                    partido_block += f"  • ▶ *{em_name}:*\n  `/stream {cmd_code} {curr_key}`\n"
                elif not cmd_code:
                    partido_block += f"  • ▶ *{em_name}*\n"
            
            partido_block += "\n"

            if len(current_msg) + len(partido_block) > 3500:
                messages.append(current_msg)
                current_msg = partido_block
            else:
                current_msg += partido_block

        if current_msg.strip():
            messages.append(current_msg)

        return messages
    except Exception as e:
        return [f"⚠️ Error obteniendo la agenda: {e}"]

# ==============================================================================
# 2. GESTOR DE MULTI-TRANSMISIÓN DEFINITIVO (1.00x TIEMPO REAL EXACTO)
# ==============================================================================
def clean_arg(val):
    if not val:
        return ""
    return val.strip().strip("<>").strip('"').strip("'").strip()

def start_single_stream(stream_id, raw_url, stream_key, label=None):
    if stream_id in active_streams:
        stop_single_stream(stream_id)

    raw_url = clean_arg(raw_url)
    stream_key = clean_arg(stream_key)
    destination = RTMP_SERVER + stream_key

    source_url, headers = resolve_live_stream_url(raw_url)

    cmd = [
        "ffmpeg",
        "-user_agent", "IPTVSmartersPro",
        "-re",
        "-reconnect", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-fflags", "+nobuffer+genpts+igndts+discardcorrupt",
        "-avoid_negative_ts", "make_zero",
        "-headers", headers,
        "-i", source_url,
        "-max_muxing_queue_size", "4096",
        "-vf", "scale=854:480,fps=25",
        "-r", "25",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-threads", "0",
        "-b:v", "850k",
        "-maxrate", "1000k",
        "-bufsize", "1800k",
        "-pix_fmt", "yuv420p",
        "-g", "50",
        "-keyint_min", "50",
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", "96k",
        "-ar", "44100",
        "-bsf:a", "aac_adtstoasc",
        "-flvflags", "no_duration_filesize",
        "-f", "flv",
        destination
    ]

    log_file = f"/tmp/stream_{stream_id}.log" if os.name != 'nt' else f"stream_{stream_id}.log"
    out_f = open(log_file, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(cmd, stdout=out_f, stderr=out_f)
    
    time.sleep(1.5)
    if proc.poll() is not None:
        out_f.close()
        err_snippet = "No se pudo conectar a la fuente."
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                if lines:
                    err_snippet = lines[-1].strip()
        except Exception:
            pass
        return False, f"Error: {err_snippet}"

    active_streams[stream_id] = {
        "process": proc,
        "log_file": out_f,
        "url": source_url,
        "key": stream_key,
        "name": label if label else f"Emisión ({raw_url})",
        "start_time": time.time()
    }
    return True, source_url

def stop_single_stream(stream_id):
    if stream_id in active_streams:
        info = active_streams[stream_id]
        proc = info["process"]
        try:
            proc.kill()
            proc.wait(timeout=1)
        except Exception:
            pass
        try:
            if "log_file" in info and not info["log_file"].closed:
                info["log_file"].close()
        except Exception:
            pass
        del active_streams[stream_id]
        return True
    return False

def stop_all_streams():
    ids = list(active_streams.keys())
    for sid in ids:
        stop_single_stream(sid)
    return len(ids)

# ==============================================================================
# 3. INTERFAZ DE BOT DE TELEGRAM (TODO MEDIANTE /STREAM)
# ==============================================================================
def send_msg(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def handle_message(msg):
    global CONFIG
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = msg.get("text", "").strip()

    if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
        send_msg(chat_id, "⛔ No tienes permisos para usar este bot.")
        return

    curr_key = CONFIG.get("stream_key", "3936015063:nG8N_no46UfNuA6jXewiag")

    if text.startswith("/start") or text.startswith("/ayuda"):
        help_text = (
            "⚽ *BOT DE TRANSMISIÓN DEPORTIVA (VÍA /STREAM)*\n\n"
            "📺 *TRANSMITIR PARTIDO O CANAL:*\n"
            "• `/stream espn2` $\\rightarrow$ Transmitir ESPN 2 Sur\n"
            "• `/stream tyc` $\\rightarrow$ Transmitir TyC Sports\n"
            "• `/stream dsports` $\\rightarrow$ Transmitir Directv Sports\n"
            "• `/stream <CANAL_O_URL> [STREAM_KEY]` $\\rightarrow$ Con clave personalizada\n\n"
            "📋 *GUÍA DE PARTIDOS Y CANALES:*\n"
            "• `/partidos` $\\rightarrow$ Ver todos los partidos de hoy con comandos `/stream` listos para copiar\n"
            "• `/top` $\\rightarrow$ Lista de canales deportivos principales con comandos listos\n"
            "• `/buscar <nombre>` $\\rightarrow$ Buscar cualquier canal en tu IPTV (ej. `/buscar dazn`)\n\n"
            "🔑 *CLAVE DE TRANSMISIÓN (STREAM KEY):*\n"
            f"• 📡 Clave guardada actual: `{curr_key[:10]}...`\n"
            "• `/key <NUEVA_KEY>` $\\rightarrow$ Cambiar tu Stream Key por defecto\n\n"
            "🛑 *DETENER EMISIÓN:*\n"
            "• `/stop` o `/stopall` $\\rightarrow$ Detener la transmisión activa\n\n"
            "📊 *ESTADO EN VIVO:*\n"
            "• `/status` $\\rightarrow$ Ver qué partido está transmitiéndose"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/top") or text.startswith("/deportes"):
        msg_txt = "🌟 *CANALES DEPORTIVOS PRINCIPALES:*\n\n"
        for ch in TOP_SPORTS_CHANNELS:
            msg_txt += f"📺 *{ch['name']}:*\n`/stream {ch['cmd']} {curr_key}`\n\n"
        msg_txt += "💡 _Toca cualquier comando en gris para copiarlo y enviarlo al instante._"
        send_msg(chat_id, msg_txt)

    elif text.startswith("/partidos") or text.startswith("/hoy") or text.startswith("/agenda"):
        send_msg(chat_id, "⏳ *Cargando agenda de partidos de hoy con comandos /stream listos...*")
        agenda_msgs = get_live_agenda_messages(curr_key)
        for m in agenda_msgs:
            send_msg(chat_id, m)

    elif text.startswith("/buscar"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ *Uso:* `/buscar <palabra>` (ejemplo: `/buscar espn`, `/buscar dazn`, `/buscar fox`)")
            return
        query = parts[1].strip()
        send_msg(chat_id, f"🔍 *Buscando canales con:* `{query}`...")
        results = search_iptv_channels(query)
        if not results:
            send_msg(chat_id, f"❌ No se encontraron canales con `{query}`.")
            return

        resp_txt = f"🎯 *RESULTADOS PARA:* `{query}`\n\n"
        for name, sid, link in results:
            resp_txt += f"• *{name}* (ID `{sid}`):\n`/stream {sid} {curr_key}`\n\n"
        resp_txt += "💡 _Toca cualquier comando para copiarlo y transmitir._"
        send_msg(chat_id, resp_txt)

    elif text.startswith("/key") or text.startswith("/setkey"):
        parts = text.split()
        if len(parts) < 2:
            send_msg(chat_id, f"⚠️ *Uso:* `/key NUEVA_STREAM_KEY`\nClave actual: `{curr_key}`")
            return
        new_k = clean_arg(parts[1])
        CONFIG["stream_key"] = new_k
        save_config(CONFIG)
        send_msg(chat_id, f"✅ *¡Stream Key por defecto actualizada!*\n🔑 Nueva Key: `{new_k}`")

    elif text.startswith("/stream"):
        parts = text.split()
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ *Uso:* `/stream <CANAL_O_URL>` o `/stream <CANAL> <STREAM_KEY>`\nEjemplo: `/stream espn2`")
            return
        
        raw_url = clean_arg(parts[1])
        stream_key = clean_arg(parts[2]) if len(parts) >= 3 else curr_key
        
        custom_id = f"stream_{len(active_streams) + 1}"
        send_msg(chat_id, f"⏳ *Iniciando transmisión de {raw_url}...*")
        ok, res = start_single_stream(custom_id, raw_url, stream_key, f"Emisión ({raw_url})")
        if ok:
            send_msg(chat_id, f"✅ *¡Transmisión ACTIVA!* 🚀\n📡 Señal: `{raw_url}`\n🔑 Key: `{stream_key[:8]}...`\n⏱️ Sincronización: 1.00x Tiempo Real")
        else:
            send_msg(chat_id, f"❌ *Error al iniciar:* {res}")

    elif text.startswith("/stop") or text.startswith("/stopall"):
        count = stop_all_streams()
        if count > 0:
            send_msg(chat_id, f"🛑 *Se han detenido todas las transmisiones ({count} partidos cerrados).*")
        else:
            send_msg(chat_id, "ℹ️ No había ninguna transmisión activa.")

    elif text.startswith("/status"):
        if not active_streams:
            send_msg(chat_id, "🔴 *No hay ninguna transmisión activa actualmente.*")
            return

        status_text = "🟢 *CANALES EN DIRECTO:*\n\n"
        for sid, info in active_streams.items():
            elapsed = int(time.time() - info["start_time"])
            mins = elapsed // 60
            secs = elapsed % 60
            status_text += f"📺 *{info['name']}:*\n• ⏱️ Tiempo: `{mins}m {secs}s`\n• 📡 Key: `{info['key'][:8]}...`\n• 🔗 Señal: `{info['url'][:35]}...`\n\n"
        send_msg(chat_id, status_text)

def main():
    print("🤖 Bot Simplificado (100% mediante /stream) listo...")
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
