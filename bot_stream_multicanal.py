import subprocess
import time
import requests
import json
import os
import sys
import re
import html
import base64
import threading
from urllib.parse import urlparse

# ==============================================================================
# 1. CONFIGURACIÓN DEL BOT Y CLAVE STREAM (FUENTE OFICIAL: ROJADIRECTATV.EC)
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CONFIG_FILE = "config_stream.json"

IPTV_USER = "BE15ERDV"
IPTV_PASS = "PXELERB9"
IPTV_SERVER = "http://evestv.ptjfj.com"
IPTV_SERVER_ALT = "http://evestv.leptis.live"
AGENDA_API = "https://futbollibretv.org.pe/diaries.json?v=2.2"

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
stream_lock = threading.Lock()

# CANALES CON REDUNDANCIA MULTI-CAPA Y ALTA ESTABILIDAD
CHANNEL_FALLBACKS = {
    "dsports2": [
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33932.ts",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33866.ts",
        "https://futbollibre.ch/5.php?stream=dsports2",
        "https://futbollibre.ch/5.php?stream=dsports_eventos"
    ],
    "dsports": [
        "https://futbollibre.ch/5.php?stream=dsports",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33933.ts"
    ],
    "dsportsar": [
        "https://futbollibre.ch/5.php?stream=dsports_eventos",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33933.ts"
    ],
    "dsports_eventos": [
        "https://futbollibre.ch/5.php?stream=dsports_eventos",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33932.ts"
    ],
    "espn2": [
        "https://futbollibre.ch/5.php?stream=espn2",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/30327.ts"
    ],
    "espn": [
        "https://futbollibre.ch/5.php?stream=espn",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/30326.ts"
    ],
    "espn3": [
        "https://futbollibre.ch/5.php?stream=espn3",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/30328.ts"
    ],
    "espn4": [
        "https://futbollibre.ch/5.php?stream=espn4",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/30329.ts"
    ],
    "espn5": [
        "https://futbollibre.ch/5.php?stream=espn5",
    ],
    "espn6": [
        "https://futbollibre.ch/5.php?stream=espn6",
    ],
    "espn7": [
        "https://futbollibre.ch/5.php?stream=espn7",
    ],
    "espnextra": [
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/30329.ts",
    ],
    "espnpremium": [
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/4883.ts",
    ],
    "espndeportes": [
        "https://futbollibre.ch/5.php?stream=espndeportes",
    ],
    "espnplus1": [
        "https://futbollibre.ch/5.php?stream=espnplus1",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33866.ts"
    ],
    "espnplus2": [
        "https://futbollibre.ch/5.php?stream=espnplus2",
    ],
    "espnplus3": [
        "https://futbollibre.ch/5.php?stream=espnplus3",
    ],
    "tyc": [
        "https://futbollibre.ch/5.php?stream=tycsports",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/30365.ts"
    ],
    "tycsports": [
        "https://futbollibre.ch/5.php?stream=tycsports",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/30365.ts"
    ],
    "winsports": [
        "https://futbollibre.ch/5.php?stream=winsports2",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33945.ts"
    ],
    "winsports2": [
        "https://futbollibre.ch/5.php?stream=winsports2",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33945.ts"
    ],
    "foxsports": [
        "https://futbollibre.ch/5.php?stream=foxsports",
    ],
    "tntsports": [
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/5987.ts",
    ],
    "laliga": [
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33866.ts",
        "https://futbollibre.ch/5.php?stream=dsports"
    ],
    "disney1": [
        "https://futbollibre.ch/5.php?stream=disney1",
    ],
    "disney2": [
        "https://futbollibre.ch/5.php?stream=disney2",
    ],
    "even1": [
        "https://futbollibre.ch/5.php?stream=even1",
    ],
    "even2": [
        "https://futbollibre.ch/5.php?stream=even2",
    ]
}

def extract_stream_code(embed_iframe):
    if not embed_iframe:
        return None
    if "r=" in embed_iframe:
        try:
            b64 = embed_iframe.split("r=")[1].split("&")[0]
            dec = base64.b64decode(b64).decode('utf-8')
            if "stream=" in dec:
                return dec.split("stream=")[1].split("&")[0]
            if "tv-90.com/" in dec:
                return dec.split("tv-90.com/")[1].replace(".php", "").split("&")[0]
        except Exception:
            pass
    if "stream=" in embed_iframe:
        return embed_iframe.split("stream=")[1].split("&")[0]
    return embed_iframe

def resolve_channel_fallback(chan_key):
    sources = CHANNEL_FALLBACKS.get(chan_key, [])
    for src in sources:
        if "futbollibre" in src:
            try:
                r = requests.get(src, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://futbollibre.ch/"}, timeout=3)
                m3u8 = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', r.text)
                if m3u8:
                    m3u8_url = m3u8[0]
                    r_chk = requests.get(m3u8_url, headers={"User-Agent": "Mozilla/5.0", "Referer": src}, timeout=2.5)
                    if r_chk.status_code == 200:
                        return m3u8_url, f"Referer: https://futbollibre.ch/\r\nOrigin: https://futbollibre.ch\r\n", True
            except Exception:
                pass
        elif "live" in src:
            try:
                r = requests.get(src, headers={"User-Agent": "IPTVSmartersPro"}, stream=True, timeout=3)
                if r.status_code == 200:
                    referer = "http://evestv.leptis.live/"
                    return src, f"Referer: {referer}\r\nOrigin: {referer.rstrip('/')}\r\n", True
            except Exception:
                pass
    return None, None, False

def resolve_live_stream_url(target):
    target_clean = target.lower().strip()
    
    # 1. Si es ID de IPTV numérico (ej. 30327)
    if target_clean.isdigit():
        target_url = f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/{target_clean}.ts"
        referer = "http://evestv.leptis.live/"
        return target_url, f"Referer: {referer}\r\nOrigin: {referer.rstrip('/')}\r\n", True

    # 2. Si es clave directa con respaldo
    if target_clean in CHANNEL_FALLBACKS:
        url_fb, hdrs_fb, ok_fb = resolve_channel_fallback(target_clean)
        if ok_fb:
            return url_fb, hdrs_fb, True

    # 3. Si es un enlace con base64 (ej. embed/eventos.html?r=...)
    url_to_fetch = target
    if "r=" in target:
        try:
            b64_part = target.split("r=")[1].split("&")[0]
            url_to_fetch = base64.b64decode(b64_part).decode('utf-8')
        except Exception:
            pass

    if not url_to_fetch.startswith("http"):
        url_to_fetch = f"https://futbollibre.ch/{url_to_fetch.lstrip('/')}"

    if "leptis.live" in url_to_fetch or "ptjfj.com" in url_to_fetch:
        referer = "http://evestv.leptis.live/"
        return url_to_fetch, f"Referer: {referer}\r\nOrigin: {referer.rstrip('/')}\r\n", True

    # 4. Extracción inteligente de M3U8 en tiempo real desde rojadirectatv.ec
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://rojadirectatv.ec/"}
        r = requests.get(url_to_fetch, headers=headers, timeout=4)
        m3u8 = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', r.text)
        if m3u8:
            m3u8_url = m3u8[0]
            referer = url_to_fetch if "tv-90" in url_to_fetch or "futbollibre" in url_to_fetch else "https://futbollibre.ch/"
            try:
                r_chk = requests.get(m3u8_url, headers={"User-Agent": "Mozilla/5.0", "Referer": referer}, timeout=2.5)
                if r_chk.status_code == 404:
                    return None, "EVENT_NOT_STARTED", False
            except Exception:
                pass
            return m3u8_url, f"Referer: {referer}\r\nOrigin: {referer.rstrip('/')}\r\n", True

        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text)
        for ifr in iframes:
            ifr_url = ifr if ifr.startswith("http") else f"https://futbollibre.ch/{ifr.lstrip('/')}"
            r2 = requests.get(ifr_url, headers={"User-Agent": "Mozilla/5.0", "Referer": url_to_fetch}, timeout=4)
            m3u8_2 = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', r2.text)
            if m3u8_2:
                m3u8_url2 = m3u8_2[0]
                try:
                    r_chk2 = requests.get(m3u8_url2, headers={"User-Agent": "Mozilla/5.0", "Referer": ifr_url}, timeout=2.5)
                    if r_chk2.status_code == 404:
                        return None, "EVENT_NOT_STARTED", False
                except Exception:
                    pass
                return m3u8_url2, f"Referer: {ifr_url}\r\nOrigin: {ifr_url.rstrip('/')}\r\n", True
    except Exception as e:
        print(f"Error resolviendo stream {target}: {e}")

    return None, f"No se pudo resolver el canal '{target}'.", False

TOP_SPORTS_CHANNELS = [
    {"name": "ESPN 2 Sur HD (Mariano Closs)", "cmd": "espn2"},
    {"name": "ESPN 1 Sur HD (Español Latam)", "cmd": "espn"},
    {"name": "ESPN 3 Sur HD (Español Latam)", "cmd": "espn3"},
    {"name": "ESPN 4 HD (Español)", "cmd": "espn4"},
    {"name": "ESPN 5 HD", "cmd": "espn5"},
    {"name": "ESPN Extra Sur HD", "cmd": "espnextra"},
    {"name": "ESPN Premium (Liga Argentina)", "cmd": "espnpremium"},
    {"name": "TyC Sports HD (Argentina)", "cmd": "tyc"},
    {"name": "Directv Sports 1 (DSPORTS)", "cmd": "dsports"},
    {"name": "Directv Sports 2 (DSPORTS 2)", "cmd": "dsports2"},
    {"name": "Win Sports + HD (Colombia)", "cmd": "winsports"},
    {"name": "Fox Sports HD", "cmd": "foxsports"},
    {"name": "LaLiga TV (FHD)", "cmd": "laliga"},
]

def get_live_agenda_messages(curr_key):
    try:
        r = requests.get(AGENDA_API, timeout=10, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://rojadirectatv.ec/"})
        data = r.json().get("data", [])
        if not data:
            return ["🔴 No hay partidos programados en la agenda en este momento."]

        messages = []
        header = f"📅 <b>AGENDA DEPORTIVA ROJADIRECTA ({len(data)} EVENTOS DE HOY)</b>\n\n"
        current_msg = header
        
        for item in data:
            attrs = item.get("attributes", {})
            raw_desc = attrs.get("diary_description", "").strip()
            clean_desc = html.escape(" ".join(raw_desc.split()))
            hour = attrs.get("diary_hour", "")[:5]
            embeds = attrs.get("embeds", {}).get("data", [])

            partido_block = f"⚽ <b>{clean_desc}</b> (<code>{hour}</code>)\n"
            
            if not embeds:
                partido_block += "  • ⏳ <i>Señales disponibles cerca de la hora del partido</i>\n"
            else:
                for em in embeds:
                    em_attrs = em.get("attributes", {})
                    em_name = html.escape(em_attrs.get("embed_name", "").strip())
                    em_iframe = em_attrs.get("embed_iframe", "")
                    
                    cmd_code = extract_stream_code(em_iframe)
                    if not cmd_code and em_iframe:
                        cmd_code = em_iframe

                    if cmd_code:
                        partido_block += f"  • ▶ <b>{em_name}:</b>\n  <code>/stream {cmd_code} {curr_key}</code>\n"
                    else:
                        partido_block += f"  • ▶ <b>{em_name}</b>\n"
            
            partido_block += "\n"

            if len(current_msg) + len(partido_block) > 3400:
                messages.append(current_msg)
                current_msg = partido_block
            else:
                current_msg += partido_block

        if current_msg.strip():
            messages.append(current_msg)

        return messages
    except Exception as e:
        return [f"⚠️ Error obteniendo la agenda de rojadirectatv.ec: {e}"]

# ==============================================================================
# 2. MOTOR ANTI-CONGELAMIENTO (FFMPEG BLINDADO + WATCHDOG AUTORREPARADOR)
# ==============================================================================
def clean_arg(val):
    if not val:
        return ""
    return val.strip().strip("<>").strip('"').strip("'").strip()

def get_next_stream_id():
    for i in range(1, 100):
        sid = str(i)
        if sid not in active_streams:
            return sid
    return str(len(active_streams) + 1)

def launch_ffmpeg_process(source_url, headers, destination, stream_id):
    cmd = [
        "ffmpeg",
        "-user_agent", "IPTVSmartersPro",
        "-reconnect", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-rw_timeout", "8000000",                # 8s timeout de socket: evita cuelgues eternos
        "-fflags", "+nobuffer+genpts+igndts+discardcorrupt",
        "-avoid_negative_ts", "make_zero",
        "-max_interleave_delta", "0"
    ]

    # Pre-buffering para HLS / tiempo real para TS
    if not source_url.endswith(".m3u8"):
        cmd.extend(["-re"])

    if headers:
        cmd.extend(["-headers", headers])

    cmd.extend([
        "-i", source_url,
        "-max_muxing_queue_size", "8192",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-bsf:a", "aac_adtstoasc",
        "-flvflags", "no_duration_filesize",
        "-f", "flv",
        destination
    ])

    log_file = f"/tmp/stream_{stream_id}.log" if os.name != 'nt' else f"stream_{stream_id}.log"
    out_f = open(log_file, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(cmd, stdout=out_f, stderr=out_f)
    return proc, out_f, log_file

def start_single_stream(raw_url, stream_key):
    raw_url = clean_arg(raw_url)
    stream_key = clean_arg(stream_key)
    destination = RTMP_SERVER + stream_key

    with stream_lock:
        for sid, info in list(active_streams.items()):
            if info["key"] == stream_key:
                stop_single_stream(sid)

        stream_id = get_next_stream_id()
        source_url, headers, is_ok = resolve_live_stream_url(raw_url)

        if not is_ok:
            if headers == "EVENT_NOT_STARTED":
                return False, stream_id, (
                    f"⚠️ La señal '{raw_url}' es un canal de evento temporal que aún no ha iniciado en la fuente.\n"
                    f"💡 Te recomendamos usar las señales 24/7 activas (como /stream espn4, /stream espn2, /stream tyc o /stream dsports)."
                )
            return False, stream_id, f"Error: {headers}"

        proc, out_f, log_file = launch_ffmpeg_process(source_url, headers, destination, stream_id)
        
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
            return False, stream_id, f"Error: {err_snippet}"

        active_streams[stream_id] = {
            "process": proc,
            "log_file": out_f,
            "log_path": log_file,
            "raw_name": raw_url,
            "url": source_url,
            "headers": headers,
            "destination": destination,
            "key": stream_key,
            "start_time": time.time(),
            "auto_restart": True,
            "restart_count": 0
        }
        return True, stream_id, raw_url

def stop_single_stream(identifier):
    ident = str(identifier).strip().lower()
    
    with stream_lock:
        target_sid = None
        if ident in active_streams:
            target_sid = ident
        else:
            for sid, info in active_streams.items():
                if info["raw_name"].lower() == ident or info["key"].lower() == ident or ident in info["key"].lower():
                    target_sid = sid
                    break

        if target_sid and target_sid in active_streams:
            info = active_streams[target_sid]
            info["auto_restart"] = False  # Desactivar watchdog para este stream
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
            del active_streams[target_sid]
            return True, target_sid, info["raw_name"]
    return False, None, None

def stop_all_streams():
    count = 0
    for sid in list(active_streams.keys()):
        ok, _, _ = stop_single_stream(sid)
        if ok:
            count += 1
    return count

# WATCHDOG EN SEGUNDO PLANO (RECUPERACIÓN INMEDIATA SI UN CANAL FLUCTÚA)
def stream_watchdog():
    while True:
        try:
            time.sleep(3)
            with stream_lock:
                for sid, info in list(active_streams.items()):
                    if not info.get("auto_restart", False):
                        continue
                    
                    proc = info.get("process")
                    if proc and proc.poll() is not None:
                        # El proceso FFmpeg cayó por fluctuación de red de la fuente
                        print(f"⚠️ Watchdog: Canal #{sid} ({info['raw_name']}) cayó. Re-conectando en 1s...")
                        try:
                            if "log_file" in info and not info["log_file"].closed:
                                info["log_file"].close()
                        except Exception:
                            pass
                        
                        # Re-resolver fuente (con fallback automático)
                        new_url, new_hdrs, ok = resolve_live_stream_url(info["raw_name"])
                        if ok:
                            new_proc, new_out_f, new_log = launch_ffmpeg_process(
                                new_url, new_hdrs, info["destination"], sid
                            )
                            info["process"] = new_proc
                            info["log_file"] = new_out_f
                            info["url"] = new_url
                            info["headers"] = new_hdrs
                            info["restart_count"] = info.get("restart_count", 0) + 1
                            print(f"✅ Watchdog: Canal #{sid} reanudado exitosamente (Reconexión #{info['restart_count']}).")
        except Exception as e:
            print(f"Error en stream watchdog: {e}")

# ==============================================================================
# 3. INTERFAZ DE BOT DE TELEGRAM (HTML BLINDADO)
# ==============================================================================
def send_msg(chat_id, text, parse_mode="HTML"):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            plain_text = re.sub(r'<[^>]+>', '', text)
            requests.post(url, json={"chat_id": chat_id, "text": plain_text}, timeout=10)
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
            "⚽ <b>BOT DE TRANSMISIÓN DEPORTIVA ANTI-FREEZE (ROJADIRECTATV.EC)</b>\n\n"
            "📺 <b>TRANSMITIR:</b>\n"
            "• <code>/stream espn2</code> $\\rightarrow$ Transmitir ESPN 2 Sur\n"
            "• <code>/stream tyc</code> $\\rightarrow$ Transmitir TyC Sports\n"
            "• <code>/stream dsports2</code> $\\rightarrow$ Transmitir Directv Sports 2\n"
            "• <code>/stream dsports</code> $\\rightarrow$ Transmitir Directv Sports 1\n"
            "• <code>/stream &lt;CANAL_O_URL&gt; [STREAM_KEY]</code>\n\n"
            "📋 <b>GUÍA DE PARTIDOS Y CANALES:</b>\n"
            "• <code>/partidos</code> $\\rightarrow$ Ver <b>TODOS los partidos de hoy</b> de rojadirectatv.ec\n"
            "• <code>/top</code> $\\rightarrow$ Lista de canales deportivos principales\n\n"
            "🛑 <b>DETENER TRANSMISIONES:</b>\n"
            "• <code>/stop</code> $\\rightarrow$ Detener la transmisión activa\n"
            "• <code>/stop 1</code> | <code>/stop 2</code> $\\rightarrow$ Detener por número\n"
            "• <code>/stopall</code> $\\rightarrow$ Detener TODAS las transmisiones a la vez\n\n"
            "📊 <b>ESTADO EN VIVO:</b>\n"
            "• <code>/status</code> $\\rightarrow$ Ver qué transmisiones están activas\n\n"
            f"🔑 <b>CLAVE STREAM:</b> <code>/key &lt;NUEVA_KEY&gt;</code>"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/top") or text.startswith("/deportes"):
        msg_txt = "🌟 <b>CANALES DEPORTIVOS PRINCIPALES (DIRECTO HD):</b>\n\n"
        for ch in TOP_SPORTS_CHANNELS:
            msg_txt += f"📺 <b>{ch['name']}:</b>\n<code>/stream {ch['cmd']} {curr_key}</code>\n\n"
        msg_txt += "💡 <i>Toca cualquier comando en gris para copiarlo y enviarlo al instante.</i>"
        send_msg(chat_id, msg_txt)

    elif text.startswith("/partidos") or text.startswith("/hoy") or text.startswith("/agenda"):
        send_msg(chat_id, "⏳ <b>Cargando agenda de partidos y canales de rojadirectatv.ec...</b>")
        agenda_msgs = get_live_agenda_messages(curr_key)
        for m in agenda_msgs:
            send_msg(chat_id, m)

    elif text.startswith("/key") or text.startswith("/setkey"):
        parts = text.split()
        if len(parts) < 2:
            send_msg(chat_id, f"⚠️ <b>Uso:</b> <code>/key NUEVA_STREAM_KEY</code>\nClave actual: <code>{curr_key}</code>")
            return
        new_k = clean_arg(parts[1])
        CONFIG["stream_key"] = new_k
        save_config(CONFIG)
        send_msg(chat_id, f"✅ <b>¡Stream Key por defecto actualizada!</b>\n🔑 Nueva Key: <code>{new_k}</code>")

    elif text.startswith("/stream"):
        parts = text.split()
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL&gt;</code> o <code>/stream &lt;CANAL&gt; &lt;STREAM_KEY&gt;</code>\nEjemplo: <code>/stream dsports2</code>")
            return
        
        raw_url = clean_arg(parts[1])
        stream_key = clean_arg(parts[2]) if len(parts) >= 3 else curr_key
        
        send_msg(chat_id, f"⏳ <b>Iniciando transmisión blindada anti-freeze de {html.escape(raw_url)}...</b>")
        ok, sid, res = start_single_stream(raw_url, stream_key)
        if ok:
            send_msg(chat_id, (
                f"✅ <b>¡Transmisión ACTIVA y PROTEGIDA!</b> 🚀\n\n"
                f"📺 <b>Transmisión #{sid}:</b> <code>{html.escape(raw_url)}</code>\n"
                f"🔑 <b>Key:</b> <code>{stream_key[:8]}...</code>\n"
                f"🛡️ <b>Protección:</b> Anti-Freeze + Watchdog Auto-Reconexión\n"
                f"⚡ <b>Modo:</b> Direct Passthrough (0% CPU / Calidad HD)\n\n"
                f"🛑 <b>Detener esta:</b> <code>/stop {sid}</code> | <b>Detener todas:</b> <code>/stopall</code>"
            ))
        else:
            send_msg(chat_id, f"❌ <b>Error al iniciar:</b>\n{html.escape(res)}")

    elif text.startswith("/stopall") or text == "/stop all":
        count = stop_all_streams()
        if count > 0:
            send_msg(chat_id, f"🛑 <b>Se han detenido todas las transmisiones ({count} partidos cerrados).</b>")
        else:
            send_msg(chat_id, "ℹ️ No había ninguna transmisión activa.")

    elif text.startswith("/stop"):
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            if not active_streams:
                send_msg(chat_id, "ℹ️ No hay ninguna transmisión activa actualmente.")
                return
            if len(active_streams) == 1:
                sid = list(active_streams.keys())[0]
                ok, _, ch_name = stop_single_stream(sid)
                send_msg(chat_id, f"🛑 <b>Transmisión #{sid} ({html.escape(ch_name)}) detenida correctamente.</b>")
                return
            else:
                txt = "⚠️ <b>Hay varias transmisiones activas. Elige cuál detener:</b>\n\n"
                for sid, info in active_streams.items():
                    txt += f"• Transmisión #{sid} (<b>{html.escape(info['raw_name'])}</b>): <code>/stop {sid}</code>\n"
                txt += "\n🛑 <b>O detener todas a la vez:</b> <code>/stopall</code>"
                send_msg(chat_id, txt)
                return
        
        target = parts[1].strip()
        ok, sid, ch_name = stop_single_stream(target)
        if ok:
            send_msg(chat_id, f"🛑 <b>Transmisión #{sid} ({html.escape(ch_name)}) detenida correctamente.</b>")
        else:
            send_msg(chat_id, f"❌ No se encontró ninguna transmisión activa con identificador: <code>{html.escape(target)}</code>.\nUsa <code>/status</code> para ver las transmisiones activas.")

    elif text.startswith("/status"):
        if not active_streams:
            send_msg(chat_id, "🔴 <b>No hay ninguna transmisión activa actualmente.</b>")
            return

        status_text = f"🟢 <b>TRANSMISIONES EN DIRECTO ({len(active_streams)} ACTIVAS):</b>\n\n"
        for sid, info in sorted(active_streams.items()):
            elapsed = int(time.time() - info["start_time"])
            mins = elapsed // 60
            secs = elapsed % 60
            restarts = info.get("restart_count", 0)
            status_text += (
                f"📺 <b>Transmisión #{sid} ({html.escape(info['raw_name'])}):</b>\n"
                f"• ⏱️ Tiempo: <code>{mins}m {secs}s</code>\n"
                f"• 🔄 Auto-Reconexiones: <code>{restarts}</code>\n"
                f"• 📡 Key: <code>{info['key'][:8]}...</code>\n"
                f"• 🛑 <b>Detener esta:</b> <code>/stop {sid}</code>\n\n"
            )
        status_text += "🛑 <b>Detener todas juntas:</b> <code>/stopall</code>"
        send_msg(chat_id, status_text)

def main():
    print("🤖 Iniciando Motor Anti-Freeze y Watchdog de rojadirectatv.ec...")
    
    # Iniciar hilo del Watchdog Auto-Recuperador en segundo plano
    wd_thread = threading.Thread(target=stream_watchdog, daemon=True)
    wd_thread.start()
    
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
