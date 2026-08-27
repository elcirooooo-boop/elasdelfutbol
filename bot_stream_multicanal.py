import subprocess
import time
import requests
import json
import os
import sys
import re
import html
import base64
from urllib.parse import urlparse

# ==============================================================================
# 1. CONFIGURACIÓN DEL BOT Y CLAVE STREAM (FUENTE EXCLUSIVA: PIRLOTV.WORLD)
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CONFIG_FILE = "config_stream.json"
PIRLOTV_URL = "https://pirlotv.world/"

IPTV_USER = "BE15ERDV"
IPTV_PASS = "PXELERB9"
IPTV_SERVER = "http://evestv.ptjfj.com"
IPTV_SERVER_ALT = "http://evestv.leptis.live"

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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://pirlotv.world/"
}

# CANALES CON REDUNDANCIA AUTOMÁTICA
CHANNEL_FALLBACKS = {
    "dsports": [
        "https://futbollibre.ch/5.php?stream=dsports",
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33933.ts"
    ],
    "dsports2": [
        "https://futbollibre.ch/5.php?stream=dsports",
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
    "espndeportes": [
        "https://futbollibre.ch/5.php?stream=espndeportes",
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
    "foxsports": [
        "https://futbollibre.ch/5.php?stream=foxsports",
    ],
    "laliga": [
        f"{IPTV_SERVER_ALT}/live/{IPTV_USER}/{IPTV_PASS}/33866.ts",
        "https://futbollibre.ch/5.php?stream=dsports"
    ]
}

# MAPEO EXPLÍCITO DE CANALES PIRLO
PIRLO_CANAL_DIRECT = {
    "65": "dsports",     # Celta vs Osasuna
    "64": "dsports2",
    "145": "espn",
    "6": "espn2",
    "7": "espn2",
    "8": "espn2",
    "9": "espn2",
}

CANAL_KEYWORDS = [
    ("espn2", "espn2"),
    ("espn 2", "espn2"),
    ("espn3", "espn3"),
    ("espn 3", "espn3"),
    ("espn4", "espn4"),
    ("espn 4", "espn4"),
    ("espn5", "espn5"),
    ("espn 5", "espn5"),
    ("espn6", "espn6"),
    ("espn 6", "espn6"),
    ("espn7", "espn7"),
    ("espn 7", "espn7"),
    ("espn", "espn"),
    ("dsports 2", "dsports2"),
    ("dsports2", "dsports2"),
    ("directv 2", "dsports2"),
    ("directv2", "dsports2"),
    ("dsports", "dsports"),
    ("directv", "dsports"),
    ("tyc", "tyc"),
    ("win sports", "winsports"),
    ("winsports", "winsports"),
    ("fox sports", "foxsports"),
    ("foxsports", "foxsports"),
    ("laliga", "laliga"),
]

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

# DECODIFICADOR STREAMXHD
def decode_streamxhd(html_content):
    try:
        arr_match = re.search(r'(\[\[\d+,\s*"[A-Za-z0-9+/=]+"\].*?\]\])', html_content)
        if not arr_match:
            return None
            
        arr_data = json.loads(arr_match.group(1))
        arr_data.sort(key=lambda x: x[0])
        
        fn_returns = re.findall(r'function\s+\w+\(\)\s*\{\s*return\s*(\d+);?\s*\}', html_content)
        if len(fn_returns) < 2:
            return None
            
        k = sum(int(x) for x in fn_returns[:2])
        
        playback_url = ""
        for idx, v in arr_data:
            try:
                b64_dec = base64.b64decode(v).decode('utf-8')
                digits_only = re.sub(r'\D', '', b64_dec)
                if digits_only:
                    char_code = int(digits_only) - k
                    playback_url += chr(char_code)
            except Exception:
                pass
        return playback_url if playback_url.startswith("http") else None
    except Exception:
        return None

# RESOLVEDOR INTELIGENTE DE PIRLOTV.WORLD
def resolve_live_stream_url(target):
    target_clean = target.lower().strip()
    
    # 1. Si es ID tipo pirlo_65 o canal-65 o número
    canal_id = None
    if target_clean.startswith("pirlo_") or target_clean.startswith("click_") or target_clean.startswith("world_"):
        canal_id = target_clean.replace("pirlo_", "").replace("click_", "").replace("world_", "")
    elif target_clean.startswith("canal-"):
        canal_id = target_clean.replace("canal-", "").replace(".php", "")
    elif target_clean.isdigit() and len(target_clean) <= 4:
        canal_id = target_clean

    # Mapeo directo para canales clave de eventos en vivo
    if canal_id and canal_id in PIRLO_CANAL_DIRECT:
        key_direct = PIRLO_CANAL_DIRECT[canal_id]
        url_fb, hdrs_fb, ok_fb = resolve_channel_fallback(key_direct)
        if ok_fb:
            return url_fb, hdrs_fb, True

    # 2. Si es clave directa
    if target_clean in CHANNEL_FALLBACKS:
        url_fb, hdrs_fb, ok_fb = resolve_channel_fallback(target_clean)
        if ok_fb:
            return url_fb, hdrs_fb, True

    if canal_id:
        target_url = f"https://pirlotv.world/canal-{canal_id}.php"
    elif target.startswith("http"):
        target_url = target
    else:
        target_url = f"https://pirlotv.world/{target.lstrip('/')}"

    # 3. Mapeo inteligente y extracción limpia
    try:
        r1 = requests.get(target_url, headers=HEADERS, timeout=6)
        if r1.status_code == 200:
            iframes_1 = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', r1.text)
            player_url = iframes_1[0] if iframes_1 else None

            if player_url:
                r2 = requests.get(player_url, headers={"User-Agent": HEADERS["User-Agent"], "Referer": target_url}, timeout=6)
                if r2.status_code == 200:
                    r2_text = r2.text.lower()
                    
                    for kw, chan_key in CANAL_KEYWORDS:
                        if kw in r2_text:
                            url_fb, hdrs_fb, ok_fb = resolve_channel_fallback(chan_key)
                            if ok_fb:
                                return url_fb, hdrs_fb, True

                    iframes_2 = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', r2.text)
                    final_player = iframes_2[0] if iframes_2 else player_url
                    r3 = requests.get(final_player, headers={"User-Agent": HEADERS["User-Agent"], "Referer": player_url}, timeout=6)
                    
                    # A) Probar decodificador de streamxhd
                    m3u8_streamxhd = decode_streamxhd(r3.text)
                    if m3u8_streamxhd:
                        return m3u8_streamxhd, f"Referer: {final_player}\r\nOrigin: {final_player.rstrip('/')}\r\n", True
                    
                    # B) Probar iframes base64 (atob)
                    atob_matches = re.findall(r"atob\(['\"]([A-Za-z0-9+/=]+)['\"]\)", r3.text)
                    for b in atob_matches:
                        try:
                            dec = base64.b64decode(b).decode('utf-8')
                            if dec.startswith("http"):
                                r4 = requests.get(dec, headers={"User-Agent": HEADERS["User-Agent"], "Referer": final_player}, timeout=6)
                                m3u8_4 = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', r4.text)
                                if m3u8_4:
                                    return m3u8_4[0], f"Referer: {dec}\r\nOrigin: {dec.rstrip('/')}\r\n", True
                        except Exception:
                            pass

                    # C) Buscar m3u8 directo
                    m3u8_direct = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', r3.text)
                    if m3u8_direct:
                        return m3u8_direct[0], f"Referer: {final_player}\r\nOrigin: {final_player.rstrip('/')}\r\n", True
    except Exception as e:
        print(f"Error resolviendo stream {target}: {e}")

    if target.endswith(".m3u8") or ".ts" in target:
        return target, f"Referer: {PIRLOTV_URL}\r\nOrigin: {PIRLOTV_URL.rstrip('/')}\r\n", True

    return None, (
        f"⚠️ La señal '{target}' aún no ha iniciado en la fuente o está programada para más tarde.\n"
        f"💡 Las señales de eventos se activan 5 a 10 minutos antes del inicio del partido."
    ), False

# EXTRACTOR DE LA AGENDA DIRECTA DE PIRLOTV.WORLD
def get_live_agenda_messages(curr_key):
    try:
        r = requests.get(PIRLOTV_URL, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return ["🔴 No se pudo conectar a pirlotv.world en este momento."]

        html_text = r.text
        rows = re.findall(r'<tr[^>]*>.*?<span class="t">(\d{2}:\d{2})</span>.*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>.*?</tr>', html_text, re.DOTALL)

        if not rows:
            return ["🔴 No hay partidos programados en la agenda en este momento."]

        partidos_dict = {}
        for hour, link, title in rows:
            clean_title = re.sub(r'<[^>]+>', ' ', title).strip()
            clean_title = " ".join(clean_title.split())
            key = (hour, clean_title)
            if key not in partidos_dict:
                partidos_dict[key] = []
            partidos_dict[key].append(link)

        messages = []
        header = f"📅 <b>AGENDA EXCLUSIVA PIRLOTV.WORLD ({len(partidos_dict)} EVENTOS DE HOY)</b>\n\n"
        current_msg = header

        for (hour, title), links in partidos_dict.items():
            clean_desc = html.escape(title)
            partido_block = f"⚽ <b>{clean_desc}</b> (<code>{hour}</code>)\n"

            for idx, l in enumerate(links):
                cid = l.replace("/canal-", "").replace(".php", "").replace("/", "")
                cmd = f"/stream pirlo_{cid} {curr_key}"
                partido_block += f"  • ▶ <b>Opción {idx+1}:</b>\n  <code>{cmd}</code>\n"

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
        return [f"⚠️ Error obteniendo la agenda de pirlotv.world: {e}"]

# ==============================================================================
# 2. MOTOR DE TRANSMISIÓN DIRECTA PASSTHROUGH (0% CPU / CERO LATENCIA)
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

def start_single_stream(raw_url, stream_key):
    raw_url = clean_arg(raw_url)
    stream_key = clean_arg(stream_key)
    destination = RTMP_SERVER + stream_key

    for sid, info in list(active_streams.items()):
        if info["key"] == stream_key:
            stop_single_stream(sid)

    stream_id = get_next_stream_id()
    source_url, headers, is_ok = resolve_live_stream_url(raw_url)

    if not is_ok:
        return False, stream_id, headers

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
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
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
        return False, stream_id, f"Error: {err_snippet}"

    active_streams[stream_id] = {
        "process": proc,
        "log_file": out_f,
        "raw_name": raw_url,
        "url": source_url,
        "key": stream_key,
        "start_time": time.time()
    }
    return True, stream_id, raw_url

def stop_single_stream(identifier):
    ident = str(identifier).strip().lower()
    
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
            "⚽ <b>BOT DE TRANSMISIÓN EXCLUSIVO PIRLOTV.WORLD</b>\n\n"
            "📺 <b>TRANSMITIR PARTIDO:</b>\n"
            "• <code>/partidos</code> $\\rightarrow$ Ver todos los partidos de hoy de <b>pirlotv.world</b> con opciones directas\n"
            "• <code>/stream pirlo_65</code> $\\rightarrow$ Transmitir <b>Celta vs Osasuna</b> (LaLiga)\n"
            "• <code>/stream pirlo_6</code> $\\rightarrow$ Transmitir canal de la agenda\n"
            "• <code>/stream &lt;CANAL_O_URL&gt; [STREAM_KEY]</code>\n\n"
            "🛑 <b>DETENER TRANSMISIONES:</b>\n"
            "• <code>/stop</code> $\\rightarrow$ Detener la transmisión activa\n"
            "• <code>/stop 1</code> | <code>/stop 2</code> $\\rightarrow$ Detener por número\n"
            "• <code>/stopall</code> $\\rightarrow$ Detener TODAS las transmisiones\n\n"
            "📊 <b>ESTADO EN VIVO:</b>\n"
            "• <code>/status</code> $\\rightarrow$ Ver qué transmisiones están activas\n\n"
            f"🔑 <b>CLAVE STREAM:</b> <code>/key &lt;NUEVA_KEY&gt;</code>"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/partidos") or text.startswith("/hoy") or text.startswith("/agenda") or text.startswith("/top"):
        send_msg(chat_id, "⏳ <b>Cargando agenda exclusiva de pirlotv.world...</b>")
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
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL_O_URL&gt;</code> o <code>/stream &lt;CANAL&gt; &lt;STREAM_KEY&gt;</code>\nEjemplo: <code>/stream pirlo_65</code>")
            return
        
        raw_url = clean_arg(parts[1])
        stream_key = clean_arg(parts[2]) if len(parts) >= 3 else curr_key
        
        send_msg(chat_id, f"⏳ <b>Iniciando transmisión directa de {html.escape(raw_url)} desde pirlotv.world...</b>")
        ok, sid, res = start_single_stream(raw_url, stream_key)
        if ok:
            send_msg(chat_id, (
                f"✅ <b>¡Transmisión DIRECTA ACTIVA!</b> 🚀\n\n"
                f"📺 <b>Transmisión #{sid}:</b> <code>{html.escape(raw_url)}</code>\n"
                f"🔑 <b>Key:</b> <code>{stream_key[:8]}...</code>\n"
                f"🌐 <b>Fuente:</b> pirlotv.world\n"
                f"⚡ <b>Modo:</b> Direct Passthrough (0% CPU / Calidad Original)\n\n"
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
            status_text += (
                f"📺 <b>Transmisión #{sid} ({html.escape(info['raw_name'])}):</b>\n"
                f"• ⏱️ Tiempo: <code>{mins}m {secs}s</code>\n"
                f"• 📡 Key: <code>{info['key'][:8]}...</code>\n"
                f"• 🛑 <b>Detener esta:</b> <code>/stop {sid}</code>\n\n"
            )
        status_text += "🛑 <b>Detener todas juntas:</b> <code>/stopall</code>"
        send_msg(chat_id, status_text)

def main():
    print("🤖 Bot Conectado Exclusivamente a pirlotv.world con Mapeo Directo listo...")
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
