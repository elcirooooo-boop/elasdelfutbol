import os
import sys
import time
import json
import re
import html
import subprocess
import threading
import requests
import datetime

# ==============================================================================
# CONFIGURACIÓN GENERAL DEL BOT Y SERVIDORES WEB (ROJADIRECTA.CEO / STREAMTP)
# ==============================================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
CONFIG_FILE = "stream_config.json"

HEADERS_WEB = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://rojadirecta.ceo/"
}

STREAMTP_SERVERS = [
    "https://streamtp-golden1.click/global1.php?stream=",
    "https://streamtp2.com/global1.php?stream=",
    "https://tpplayer.xyz/global1.php?stream="
]

STREAMXHD_SERVERS = [
    "https://streamxhd.com/live1.php?stream=",
    "https://streamxhd.com/live2.php?stream="
]

# Canales principales pre-mapeados con servidores CDN de alta velocidad
OFFICIAL_CHANNELS = {
    # España & Motor
    "movistarlaliga": "Movistar LaLiga FHD",
    "daznlaliga": "DAZN LaLiga 1 FHD",
    "daznlaliga2": "DAZN LaLiga 2 FHD",
    "hypermotion1": "LaLiga Hypermotion",
    "daznf1": "DAZN F1 España",
    "daznmotogp": "DAZN MotoGP",
    # Argentina & Conmebol
    "espnpremium": "ESPN Premium HD (Argentina)",
    "tntsports": "TNT Sports HD (Argentina)",
    "tycsports": "TyC Sports HD",
    "tntsportschile": "TNT Sports Chile",
    # Suite ESPN & Fox Sports
    "espn": "ESPN 1 HD",
    "espn2": "ESPN 2 HD",
    "espn3": "ESPN 3 HD",
    "espn4": "ESPN 4 HD",
    "espn5": "ESPN 5 HD",
    "espn6": "ESPN 6 HD",
    "espn7": "ESPN 7 HD",
    "espn-deportes": "ESPN Deportes USA",
    "foxsports": "Fox Sports 1 HD",
    "foxsports2": "Fox Sports 2 HD",
    "foxsports3": "Fox Sports 3 HD",
    # Colombia & DIRECTV
    "winplus": "Win Sports+ HD (Colombia)",
    "winsports": "Win Sports Colombia",
    "dsports": "DIRECTV Sports 1 HD (DSports)",
    "dsports2": "DIRECTV Sports 2 HD (DSports 2)",
    "dsportsplus": "DIRECTV Sports+ HD",
    "liga1max": "Liga 1 MAX (Perú)",
    # México & Centroamérica
    "tudn_usa": "TUDN USA",
    "vix1": "(ViX) TUDN Deportes 1",
    "vix2": "(ViX) TUDN Deportes 2",
    "fut": "FUTV HD (Costa Rica)"
}

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

# ==============================================================================
# EXTRACTOR UNIVERSAL DE M3U8 (ROJADIRECTA.CEO / STREAMTP / STREAMXHD)
# ==============================================================================
def extract_web_m3u8(channel_slug):
    slug = str(channel_slug).strip().lower()
    
    # 1. Intentar extracción directa desde rojadirecta.ceo
    try:
        ceo_url = f"https://rojadirecta.ceo/stream/{slug}"
        r = requests.get(ceo_url, headers=HEADERS_WEB, timeout=3.5)
        if r.status_code == 200:
            iframes = re.findall(r'<iframe[^>]*src="([^"]+)"', r.text)
            for ifr in iframes:
                ifr_url = ifr if ifr.startswith("http") else f"https://rojadirecta.ceo{ifr}"
                ifr_r = requests.get(ifr_url, headers=HEADERS_WEB, timeout=3.5)
                m = re.search(r'var playbackURL\s*=\s*"([^"]+)"', ifr_r.text)
                if m:
                    m3u8_url = m.group(1).replace(r'\/', '/')
                    headers_str = f"Referer: {ifr_url}\r\nUser-Agent: {HEADERS_WEB['User-Agent']}\r\n"
                    return m3u8_url, headers_str, True
    except Exception:
        pass

    # 2. Intentar servidores dedicados de StreamTP
    for base in STREAMTP_SERVERS:
        player_url = f"{base}{slug}"
        try:
            r = requests.get(player_url, headers=HEADERS_WEB, timeout=3.5)
            if r.status_code == 200:
                m = re.search(r'var playbackURL\s*=\s*"([^"]+)"', r.text)
                if m:
                    m3u8_url = m.group(1).replace(r'\/', '/')
                    headers_str = f"Referer: {base}\r\nUser-Agent: {HEADERS_WEB['User-Agent']}\r\n"
                    return m3u8_url, headers_str, True
        except Exception:
            pass

    # 3. Intentar servidores de StreamXHD
    for base in STREAMXHD_SERVERS:
        xhd_url = f"{base}{slug}"
        try:
            r = requests.get(xhd_url, headers=HEADERS_WEB, timeout=3.5)
            if r.status_code == 200:
                m = re.search(r'var playbackURL\s*=\s*"([^"]+)"', r.text)
                if m:
                    m3u8_url = m.group(1).replace(r'\/', '/')
                    headers_str = f"Referer: {base}\r\nUser-Agent: {HEADERS_WEB['User-Agent']}\r\n"
                    return m3u8_url, headers_str, True
        except Exception:
            pass

    return None, None, False

def resolve_channel_input(raw_input):
    clean = str(raw_input).strip().lower()
    
    if clean in OFFICIAL_CHANNELS:
        return clean, OFFICIAL_CHANNELS[clean]

    # Reglas por alias de nombre
    if "espn" in clean or "disney" in clean:
        if "prem" in clean:
            return "espnpremium", "ESPN Premium HD (Argentina)"
        if "deportes" in clean or "usa" in clean:
            return "espn-deportes", "ESPN Deportes USA"
        if "7" in clean:
            return "espn7", "ESPN 7 HD"
        if "6" in clean:
            return "espn6", "ESPN 6 HD"
        if "5" in clean:
            return "espn5", "ESPN 5 HD"
        if "4" in clean:
            return "espn4", "ESPN 4 HD"
        if "3" in clean:
            return "espn3", "ESPN 3 HD"
        if "2" in clean:
            return "espn2", "ESPN 2 HD"
        return "espn", "ESPN 1 HD"

    if "fox" in clean:
        if "3" in clean:
            return "foxsports3", "Fox Sports 3 HD"
        if "2" in clean:
            return "foxsports2", "Fox Sports 2 HD"
        return "foxsports", "Fox Sports 1 HD"
        
    if "laliga" in clean or "la liga" in clean or "movistar" in clean:
        if "2" in clean or "hyper" in clean:
            return "hypermotion1", "LaLiga Hypermotion"
        return "movistarlaliga", "Movistar LaLiga FHD"
        
    if "dazn" in clean:
        if "f1" in clean or "formula" in clean:
            return "daznf1", "DAZN F1 España"
        if "moto" in clean:
            return "daznmotogp", "DAZN MotoGP"
        if "2" in clean:
            return "daznlaliga2", "DAZN LaLiga 2 FHD"
        return "daznlaliga", "DAZN LaLiga 1 FHD"
        
    if "win" in clean:
        if "+" in clean or "plus" in clean:
            return "winplus", "Win Sports+ HD (Colombia)"
        return "winsports", "Win Sports Colombia"
        
    if "tyc" in clean:
        return "tycsports", "TyC Sports HD"
    if "tnt" in clean:
        if "chile" in clean:
            return "tntsportschile", "TNT Sports Chile"
        return "tntsports", "TNT Sports HD (Argentina)"
        
    if "dsport" in clean or "directv" in clean:
        if "plus" in clean or "+" in clean:
            return "dsportsplus", "DIRECTV Sports+ HD"
        if "2" in clean:
            return "dsports2", "DIRECTV Sports 2 HD"
        return "dsports", "DIRECTV Sports 1 HD"
        
    if "vix" in clean:
        if "2" in clean:
            return "vix2", "(ViX) TUDN Deportes 2"
        return "vix1", "(ViX) TUDN Deportes 1"
        
    if "tudn" in clean:
        return "tudn_usa", "TUDN USA"
        
    if "fut" in clean or "futv" in clean:
        return "fut", "FUTV HD (Costa Rica)"

    if "liga 1" in clean or "liga1" in clean:
        return "liga1max", "Liga 1 MAX (Perú)"

    return clean, f"Canal Web [{clean}]"

def resolve_channel_from_raw(slug, cname=""):
    slug_clean = str(slug).strip().lower()
    
    # 1. Mapeo explícito de canales conocidos
    EXACT_MAP = {
        "espn": ("espn", "ESPN 1 HD"),
        "espn2": ("espn2", "ESPN 2 HD"),
        "espn3": ("espn3", "ESPN 3 HD"),
        "espn4": ("espn4", "ESPN 4 HD"),
        "espn5": ("espn5", "ESPN 5 HD"),
        "espn6": ("espn6", "ESPN 6 HD"),
        "espn7": ("espn7", "ESPN 7 HD"),
        "espnpremium": ("espnpremium", "ESPN Premium HD"),
        "espn-deportes": ("espn-deportes", "ESPN Deportes USA"),
        "espnplus1": ("espnplus1", "ESPN+ USA 1"),
        "espnplus2": ("espnplus2", "ESPN+ USA 2"),
        "foxsports": ("foxsports", "Fox Sports 1 HD"),
        "foxsports2": ("foxsports2", "Fox Sports 2 HD"),
        "foxsports3": ("foxsports3", "Fox Sports 3 HD"),
        "foxone": ("foxone", "Fox One HD"),
        "winplus": ("winplus", "Win Sports+ HD (Colombia)"),
        "winsports": ("winsports", "Win Sports Colombia"),
        "tntsports": ("tntsports", "TNT Sports HD (Argentina)"),
        "tntsportschile": ("tntsportschile", "TNT Sports Chile"),
        "tycsports": ("tycsports", "TyC Sports HD"),
        "dsports": ("dsports", "DIRECTV Sports 1 HD (DSports)"),
        "dsports2": ("dsports2", "DIRECTV Sports 2 HD (DSports 2)"),
        "dsportsplus": ("dsportsplus", "DIRECTV Sports+ HD"),
        "liga1max": ("liga1max", "Liga 1 MAX (Perú)"),
        "movistarper": ("movistarper", "Movistar Deportes (Perú)"),
        "fut": ("fut", "FUTV HD (Costa Rica)"),
        "futv": ("fut", "FUTV HD (Costa Rica)"),
        "vix1": ("vix1", "(ViX) TUDN Deportes 1"),
        "vix2": ("vix2", "(ViX) TUDN Deportes 2"),
        "tudn_usa": ("tudn_usa", "TUDN USA"),
        "universo_usa": ("universo_usa", "Universo USA"),
        "tvc-deportes": ("tvc-deportes", "TVC Deportes"),
        "max1": ("max1", "TNT Sports / MAX 1"),
        "max2": ("max2", "TNT Sports / MAX 2"),
        "hypermotion1": ("hypermotion1", "LaLiga Hypermotion"),
        "movistarlaliga": ("movistarlaliga", "Movistar LaLiga FHD"),
        "daznlaliga": ("daznlaliga", "DAZN LaLiga 1 FHD"),
        "daznlaliga2": ("daznlaliga2", "DAZN LaLiga 2 FHD"),
        "daznf1": ("daznf1", "DAZN F1 España"),
        "daznmotogp": ("daznmotogp", "DAZN MotoGP"),
        "premiersports1uk": ("premiersports1uk", "Premier Sports 1 UK"),
        "premiere1": ("premiere1", "Premiere Clubes 1 (Brasil)"),
        "peacocktv": ("peacocktv", "Peacock TV USA")
    }

    if slug_clean in EXACT_MAP:
        return EXACT_MAP[slug_clean]

    # 2. Señales Disney / Star / Fanatiz / Eventos
    if slug_clean.startswith("disney"):
        num = slug_clean.replace("disney", "").replace("-", "").strip()
        return slug_clean, f"Disney+ / Star+ (Señal {num})" if num else "Disney+ / Star+"
    if slug_clean.startswith("fanatiz"):
        num = slug_clean.replace("fanatiz", "").replace("-", "").strip()
        return slug_clean, f"Fanatiz HD (Opción {num})" if num else "Fanatiz HD"
    if slug_clean.startswith("evento"):
        num = slug_clean.replace("evento", "").replace("-", "").strip()
        return slug_clean, f"Señal Evento {num}" if num else "Señal Evento HD"
    if slug_clean.startswith("canal-"):
        num = slug_clean.replace("canal-", "").strip()
        return slug_clean, f"Canal Alternativo {num}"

    return slug_clean, f"Canal [{slug_clean}]"

def smart_match_channel_resolver(title, channels_raw):
    matched_channels = []
    seen = set()
    title_lower = title.lower()
    
    # 1. Resolver todos los canales especificados en la web
    for slug, cname in channels_raw:
        cid, cdisplay = resolve_channel_from_raw(slug, cname)
        if cid and cid not in seen:
            seen.add(cid)
            matched_channels.append({"id": cid, "name": cdisplay})
            
    # 2. Respaldo inteligente si no viniera canal en el artículo
    if not matched_channels:
        if "costa rica" in title_lower or "saprissa" in title_lower:
            matched_channels.append({"id": "fut", "name": "FUTV HD (Costa Rica)"})
        elif "argentina" in title_lower or "profesional" in title_lower:
            matched_channels.append({"id": "tntsports", "name": "TNT Sports HD"})
            matched_channels.append({"id": "espnpremium", "name": "ESPN Premium HD"})
        elif "colombia" in title_lower or "millonarios" in title_lower or "cali" in title_lower:
            matched_channels.append({"id": "winplus", "name": "Win Sports+ HD (Colombia)"})
        elif "laliga" in title_lower or "barcelona" in title_lower:
            matched_channels.append({"id": "movistarlaliga", "name": "Movistar LaLiga FHD"})
            matched_channels.append({"id": "daznlaliga", "name": "DAZN LaLiga 1 FHD"})
        elif "premier" in title_lower:
            matched_channels.append({"id": "espn", "name": "ESPN 1 HD"})
        elif "open" in title_lower or "tenis" in title_lower:
            matched_channels.append({"id": "espn2", "name": "ESPN 2 HD (US Open)"})
            matched_channels.append({"id": "espn3", "name": "ESPN 3 HD (US Open)"})
        elif "mexico" in title_lower or "liga mx" in title_lower:
            matched_channels.append({"id": "tudn_usa", "name": "TUDN USA"})
            matched_channels.append({"id": "vix1", "name": "(ViX) TUDN Deportes"})
        else:
            matched_channels.append({"id": "espn", "name": "ESPN 1 HD"})
            matched_channels.append({"id": "espn2", "name": "ESPN 2 HD"})

    return matched_channels

# ==============================================================================
# MOTOR DE TRANSMISIÓN EN DIRECTO (0% LAG / ULTRA BAJA LATENCIA Y AV SYNC)
# ==============================================================================
def clean_arg(val):
    if not val:
        return ""
    return val.strip().strip("<>").strip('"').strip("'").strip()

def launch_ffmpeg_process(source_url, headers, destination, stream_id):
    cmd = [
        "ffmpeg",
        "-thread_queue_size", "2048",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-rw_timeout", "10000000",
        "-fflags", "+genpts+igndts+discardcorrupt",
        "-analyzeduration", "800000",
        "-probesize", "800000"
    ]

    if headers:
        cmd.extend(["-headers", headers])

    cmd.extend([
        "-i", source_url,
        "-vf", "fps=30,scale=1280:720,setpts=PTS-STARTPTS",
        "-c:v", "libx264",
        "-preset", "superfast",
        "-tune", "zerolatency",
        "-profile:v", "main",
        "-level", "3.1",
        "-b:v", "2000k",
        "-maxrate", "2200k",
        "-bufsize", "4000k",
        "-g", "60",
        "-keyint_min", "30",
        "-sc_threshold", "0",
        "-pix_fmt", "yuv420p",
        "-af", "aresample=async=1000:min_hard_comp=0.100000:first_pts=0",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-avoid_negative_ts", "make_zero",
        "-flush_packets", "1",
        "-max_muxing_queue_size", "4096",
        "-flvflags", "no_duration_filesize",
        "-f", "flv",
        destination
    ])

    log_file = f"/tmp/stream_{stream_id}.log" if os.name != 'nt' else f"stream_{stream_id}.log"
    out_f = open(log_file, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(cmd, stdout=out_f, stderr=out_f)
    return proc, out_f, log_file

def start_single_stream(channel_input, stream_key, chat_id):
    clean_channel_input = clean_arg(channel_input)
    clean_key = clean_arg(stream_key)

    resolved_slug, channel_name = resolve_channel_input(clean_channel_input)
    destination = f"rtmps://dc4-1.rtmp.t.me/s/{clean_key}"

    with stream_lock:
        for sid, info in active_streams.items():
            if info["key"] == clean_key:
                try:
                    info["process"].terminate()
                    info["process"].wait(timeout=2)
                except Exception:
                    try:
                        info["process"].kill()
                    except Exception:
                        pass
                try:
                    if info.get("log_handle"):
                        info["log_handle"].close()
                except Exception:
                    pass
                del active_streams[sid]
                break

    # 1. Extraer stream HLS directo (.m3u8) desde servidores StreamTP / RojaDirecta
    m3u8_url, headers_str, ok = extract_web_m3u8(resolved_slug)
    if not ok or not m3u8_url:
        return False, f"❌ No se pudo conectar al stream en vivo de <b>{html.escape(channel_name)}</b>. Intenta nuevamente o usa <code>/canales</code>."

    with stream_lock:
        stream_id = str(len(active_streams) + 1)
        while stream_id in active_streams:
            stream_id = str(int(stream_id) + 1)

    proc, out_f, log_file = launch_ffmpeg_process(m3u8_url, headers_str, destination, stream_id)

    time.sleep(3.5)
    poll_res = proc.poll()
    if poll_res is not None:
        try:
            out_f.close()
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                logs = f.read()[-500:]
        except Exception:
            logs = "Sin logs"

        if "Connection to tcp://live.telegram.org:1935" in logs or "Error number -138" in logs:
            return False, (
                "⚠️ <b>Telegram no está recibiendo la señal de transmisión.</b>\n\n"
                "👉 <b>Pasos obligatorios para transmitir en Telegram:</b>\n"
                "1. Abre tu canal o grupo de Telegram.\n"
                "2. Toca en el menú de arriba (los 3 puntos <code>...</code>) $\rightarrow$ <b>\"Iniciar transmisión en vivo\"</b> o <b>\"Transmitir con...\"</b>.\n"
                "3. Verifica que la ventana diga <i>\"Esperando señal...\"</i>.\n"
                "4. Vuelve a enviar el comando: <code>/stream " + resolved_slug + " " + clean_key + "</code>"
            )

        return False, f"❌ <b>Error al conectar con Telegram RTMP</b> (Código: {poll_res})\n\n<code>{html.escape(logs)}</code>"

    with stream_lock:
        active_streams[stream_id] = {
            "channel_input": clean_channel_input,
            "resolved_slug": resolved_slug,
            "channel_name": channel_name,
            "key": clean_key,
            "process": proc,
            "log_handle": out_f,
            "log_file": log_file,
            "chat_id": chat_id,
            "start_time": time.time(),
            "auto_restart": True,
            "restarts": 0
        }

    return True, (
        f"✅ <b>TRANSMISIÓN EN VIVO INICIADA (#{stream_id})</b>\n\n"
        f"📺 <b>Canal:</b> {html.escape(channel_name)} [<code>{html.escape(resolved_slug)}</code>]\n"
        f"🌐 <b>Servidor CDN:</b> StreamTP / RojaDirecta HLS (0% Lag)\n"
        f"🔑 <b>Stream Key:</b> <code>{clean_key[:12]}...</code>\n"
        f"⚙️ <b>Audio/Video:</b> 720p @ 30fps (Sincronización AV Bloqueada)\n\n"
        f"🛑 <i>Para detener usa:</i> <code>/stop {stream_id}</code> o <code>/stopall</code>"
    )

def stop_single_stream(stream_id_or_key=None):
    with stream_lock:
        if not active_streams:
            return False, "⚠️ No hay ninguna transmisión activa en este momento."

        target_sid = None
        if stream_id_or_key:
            clean_val = clean_arg(stream_id_or_key)
            if clean_val in active_streams:
                target_sid = clean_val
            else:
                for sid, info in active_streams.items():
                    if info["key"] == clean_val:
                        target_sid = sid
                        break
        else:
            target_sid = list(active_streams.keys())[0]

        if not target_sid or target_sid not in active_streams:
            return False, f"⚠️ No se encontró ninguna transmisión con el ID o Key especificado."

        info = active_streams[target_sid]
        info["auto_restart"] = False
        try:
            info["process"].terminate()
            info["process"].wait(timeout=2)
        except Exception:
            try:
                info["process"].kill()
            except Exception:
                pass

        try:
            if info.get("log_handle"):
                info["log_handle"].close()
        except Exception:
            pass

        ch_name = info["channel_name"]
        del active_streams[target_sid]
        return True, f"🛑 <b>Transmisión #{target_sid} ({html.escape(ch_name)}) detenida con éxito.</b>"

def stop_all_streams():
    with stream_lock:
        if not active_streams:
            return False, "⚠️ No hay transmisiones activas para detener."

        count = len(active_streams)
        for sid, info in list(active_streams.items()):
            info["auto_restart"] = False
            try:
                info["process"].terminate()
                info["process"].wait(timeout=2)
            except Exception:
                try:
                    info["process"].kill()
                except Exception:
                    pass
            try:
                if info.get("log_handle"):
                    info["log_handle"].close()
            except Exception:
                pass
            del active_streams[sid]

        return True, f"🛑 <b>Se han detenido las {count} transmisiones activas.</b>"

# ==============================================================================
# SUPERVISOR AUTOMÁTICO DE RECONEXIÓN
# ==============================================================================
def supervisor_thread():
    while True:
        time.sleep(4)
        with stream_lock:
            for sid, info in list(active_streams.items()):
                proc = info.get("process")
                if proc and proc.poll() is not None:
                    if not info.get("auto_restart", False):
                        continue

                    if info.get("restarts", 0) >= 15:
                        continue

                    info["restarts"] = info.get("restarts", 0) + 1
                    slug = info["resolved_slug"]
                    dest = f"rtmps://dc4-1.rtmp.t.me/s/{info['key']}"

                    m3u8_url, headers_str, ok = extract_web_m3u8(slug)
                    if ok and m3u8_url:
                        try:
                            if info.get("log_handle"):
                                info["log_handle"].close()
                        except Exception:
                            pass

                        new_proc, new_out_f, log_file = launch_ffmpeg_process(m3u8_url, headers_str, dest, sid)
                        info["process"] = new_proc
                        info["log_handle"] = new_out_f
                        info["log_file"] = log_file

# Iniciar hilo supervisor
t_super = threading.Thread(target=supervisor_thread, daemon=True)
t_super.start()

# ==============================================================================
# AGENDA DINÁMICA DE PARTIDOS (ROJADIRECTA.CEO)
# ==============================================================================
MATCHES_AGENDA_CACHE = {"timestamp": 0, "messages": []}

def get_live_matches_agenda(curr_key):
    global MATCHES_AGENDA_CACHE
    now = time.time()
    if now - MATCHES_AGENDA_CACHE["timestamp"] < 90 and MATCHES_AGENDA_CACHE["messages"]:
        return MATCHES_AGENDA_CACHE["messages"]

    try:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_art = now_utc - datetime.timedelta(hours=3) # Referencia horaria
        current_minutes = now_art.hour * 60 + now_art.minute

        r = requests.get("https://rojadirecta.ceo/", headers=HEADERS_WEB, timeout=6)
        if r.status_code == 200:
            page_html = r.text
            rows = re.findall(r'<tr>(.*?)</tr>', page_html, re.DOTALL)
            
            events_dict = {}
            for row in rows:
                m = re.search(r'<td>(.*?):<a\s+href="[^"]*stream/([^"]+)"[^>]*><b>(.*?)</b></a></td>.*?<span\s+class="t">([^<]+)</span>', row, re.DOTALL)
                if m:
                    league = html.unescape(m.group(1).strip())
                    slug = m.group(2).strip()
                    match_title = html.unescape(m.group(3).strip())
                    time_str = m.group(4).strip()
                    
                    full_title = f"{league}: {match_title}"
                    if full_title not in events_dict:
                        events_dict[full_title] = {
                            "time": time_str,
                            "league": league,
                            "title": match_title,
                            "full_title": full_title,
                            "channels_raw": []
                        }
                    events_dict[full_title]["channels_raw"].append((slug, slug))

            live_events = []
            upcoming_events = []
            
            for full_title, ev_info in events_dict.items():
                time_str = ev_info["time"]
                web_options = smart_match_channel_resolver(full_title, ev_info["channels_raw"])
                if not web_options:
                    continue

                status_tag = ""
                is_live = False
                is_upcoming = False
                
                if ":" in time_str:
                    try:
                        h, m = map(int, time_str.split(":"))
                        ev_minutes = h * 60 + m
                        diff = current_minutes - ev_minutes
                        if 0 <= diff <= 125:
                            status_tag = f"🔴 EN VIVO"
                            is_live = True
                        elif diff < 0:
                            status_tag = f"⏰ En {abs(diff)}m"
                            is_upcoming = True
                    except Exception:
                        is_upcoming = True
                else:
                    is_upcoming = True
                    
                ev_data = {
                    "time": time_str,
                    "title": full_title,
                    "status_tag": status_tag,
                    "channels": web_options
                }
                
                if is_live:
                    live_events.append(ev_data)
                elif is_upcoming:
                    upcoming_events.append(ev_data)
                    
            if live_events or upcoming_events:
                messages = []
                current_msg = ""
                
                if live_events:
                    current_msg += "🔴 <b>PARTIDOS EN VIVO AHORA MISMO (ROJADIRECTA.CEO):</b>\n\n"
                    for ev in live_events:
                        block = f"🏆 <b>[{html.escape(ev['time'])}] {html.escape(ev['title'])}</b> {ev['status_tag']}\n"
                        for ch in ev["channels"]:
                            block += f"• 📺 <i>{html.escape(ch['name'])}:</i>\n  <code>/stream {ch['id']} {curr_key}</code>\n"
                        block += "\n"
                        
                        if len(current_msg) + len(block) > 3500:
                            messages.append(current_msg)
                            current_msg = block
                        else:
                            current_msg += block
                            
                if upcoming_events:
                    up_header = "\n⏰ <b>PRÓXIMOS PARTIDOS DE HOY (ROJADIRECTA.CEO):</b>\n\n"
                    if len(current_msg) + len(up_header) > 3500:
                        messages.append(current_msg)
                        current_msg = up_header
                    else:
                        current_msg += up_header
                        
                    for ev in upcoming_events:
                        block = f"🏆 <b>[{html.escape(ev['time'])}] {html.escape(ev['title'])}</b> ({ev['status_tag']})\n"
                        for ch in ev["channels"]:
                            block += f"• 📺 <i>{html.escape(ch['name'])}:</i>\n  <code>/stream {ch['id']} {curr_key}</code>\n"
                        block += "\n"
                        
                        if len(current_msg) + len(block) > 3500:
                            messages.append(current_msg)
                            current_msg = block
                        else:
                            current_msg += block
                            
                if current_msg:
                    messages.append(current_msg)
                    
                MATCHES_AGENDA_CACHE["timestamp"] = now
                MATCHES_AGENDA_CACHE["messages"] = messages
                return messages
    except Exception as e:
        print("Error obteniendo agenda dinámica:", e)

    return get_sports_menu_messages(curr_key)

def get_sports_menu_messages(curr_key):
    msg1 = (
        "🏆 <b>DIRECTORIO DE CANALES DEPORTIVOS (ROJADIRECTA.CEO / STREAMTP)</b>\n\n"
        "🇪🇸 <b>ESPAÑA & MOTOR (LALIGA, F1 & MOTOGP):</b>\n"
        f"• ⚽ <b>Movistar LaLiga FHD:</b> <code>/stream movistarlaliga {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 1 FHD:</b> <code>/stream daznlaliga {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 2 FHD:</b> <code>/stream daznlaliga2 {curr_key}</code>\n"
        f"• ⚽ <b>LaLiga Hypermotion:</b> <code>/stream hypermotion1 {curr_key}</code>\n"
        f"• 🏎️ <b>DAZN F1 España:</b> <code>/stream daznf1 {curr_key}</code>\n"
        f"• 🏍️ <b>DAZN MotoGP:</b> <code>/stream daznmotogp {curr_key}</code>\n\n"
        "🇦🇷 <b>ARGENTINA & CONMEBOL (FÚTBOL PROFESIONAL):</b>\n"
        f"• ⚽ <b>ESPN Premium HD:</b> <code>/stream espnpremium {curr_key}</code>\n"
        f"• ⚽ <b>TNT Sports HD:</b> <code>/stream tntsports {curr_key}</code>\n"
        f"• ⚽ <b>TyC Sports HD:</b> <code>/stream tycsports {curr_key}</code>\n"
        f"• ⚽ <b>TNT Sports Chile:</b> <code>/stream tntsportschile {curr_key}</code>\n\n"
        "🦊 <b>SUITE FOX SPORTS (HD EN VIVO):</b>\n"
        f"• ⚽ <b>Fox Sports 1 HD:</b> <code>/stream foxsports {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 2 HD:</b> <code>/stream foxsports2 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 3 HD:</b> <code>/stream foxsports3 {curr_key}</code>\n"
    )
    msg2 = (
        "🌎 <b>SUITE COMPLETA ESPN (SEÑALES 1 AL 7):</b>\n"
        f"• ⚽ <b>ESPN 1 HD:</b> <code>/stream espn {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 2 HD:</b> <code>/stream espn2 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 3 HD:</b> <code>/stream espn3 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 4 HD:</b> <code>/stream espn4 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 5 HD:</b> <code>/stream espn5 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 6 HD:</b> <code>/stream espn6 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 7 HD:</b> <code>/stream espn7 {curr_key}</code>\n"
        f"• 🇺🇸 <b>ESPN Deportes USA:</b> <code>/stream espn-deportes {curr_key}</code>\n\n"
        "🇨🇴 <b>COLOMBIA & DIRECTV (WIN SPORTS & DSPORTS):</b>\n"
        f"• ⚽ <b>Win Sports+ HD:</b> <code>/stream winplus {curr_key}</code>\n"
        f"• ⚽ <b>Win Sports Colombia:</b> <code>/stream winsports {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports 1 HD (DSports):</b> <code>/stream dsports {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports 2 HD (DSports 2):</b> <code>/stream dsports2 {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports+ HD:</b> <code>/stream dsportsplus {curr_key}</code>\n"
        f"• ⚽ <b>Liga 1 MAX (Perú):</b> <code>/stream liga1max {curr_key}</code>\n\n"
        "🇲🇽 <b>MÉXICO & CENTROAMÉRICA:</b>\n"
        f"• 🇲🇽 <b>TUDN USA:</b> <code>/stream tudn_usa {curr_key}</code>\n"
        f"• 🇲🇽 <b>(ViX) TUDN Deportes 1:</b> <code>/stream vix1 {curr_key}</code>\n"
        f"• 🇲🇽 <b>(ViX) TUDN Deportes 2:</b> <code>/stream vix2 {curr_key}</code>\n"
        f"• 🇨🇷 <b>FUTV HD (Costa Rica):</b> <code>/stream fut {curr_key}</code>\n\n"
        "🔍 <i>Para transmitir cualquier evento usa:</i> <code>/stream &lt;canal&gt;</code>"
    )
    return [msg1, msg2]

def send_msg(chat_id, text, parse_mode="HTML"):
    try:
        url = f"{API_URL}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        print("Error sending msg to telegram:", e)

def handle_message(msg):
    global CONFIG
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = msg.get("text", "").strip()

    if not chat_id or not text:
        return

    if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
        send_msg(chat_id, "⛔ No tienes permisos para usar este bot.")
        return

    try:
        curr_key = CONFIG.get("stream_key", "3936015063:nG8N_no46UfNuA6jXewiag")

        if text.startswith("/start") or text.startswith("/ayuda"):
            help_text = (
                "⚽ <b>BOT DE TRANSMISIÓN DE FÚTBOL Y DEPORTES 100% WEB HLS</b>\n\n"
                "📋 <b>COMANDOS DISPONIBLES:</b>\n"
                "• <code>/partidos</code> o <code>/agenda</code> $\\rightarrow$ Ver partidos de hoy con canales listos en 1-click\n"
                "• <code>/canales</code> o <code>/deportes</code> $\\rightarrow$ Directorio oficial de canales deportivos\n"
                "• <code>/espn</code> $\\rightarrow$ Ver señales de ESPN (1 al 7)\n"
                "• <code>/stream &lt;CANAL&gt; [STREAM_KEY]</code> $\\rightarrow$ Iniciar transmisión en directo\n"
                "• <code>/status</code> $\\rightarrow$ Ver transmisiones activas simultáneas\n"
                "• <code>/stop [ID]</code> $\\rightarrow$ Detener transmisión por ID o primera activa\n"
                "• <code>/stopall</code> $\\rightarrow$ Detener todas las transmisiones activas\n"
                f"• <code>/key &lt;NUEVA_KEY&gt;</code> $\\rightarrow$ Cambiar Stream Key por defecto\n\n"
                "🌐 <b>Servidor CDN:</b> StreamTP / RojaDirecta HLS (0% Lag / 100% AV Sync)"
            )
            send_msg(chat_id, help_text)

        elif text.startswith("/canales") or text.startswith("/deportes") or text.startswith("/menu"):
            msgs = get_sports_menu_messages(curr_key)
            for m in msgs:
                send_msg(chat_id, m)

        elif text.startswith("/espn"):
            espn_msg = (
                "📺 <b>DIRECTORIO COMPLETO DE SEÑALES ESPN (STREAMTP HLS):</b>\n\n"
                "🇦🇷 <b>SEÑALES ESPN (1 AL 7 & PREMIUM):</b>\n"
                f"• ⚽ <b>ESPN 1 HD:</b> <code>/stream espn {curr_key}</code>\n"
                f"• ⚽ <b>ESPN 2 HD:</b> <code>/stream espn2 {curr_key}</code>\n"
                f"• ⚽ <b>ESPN 3 HD:</b> <code>/stream espn3 {curr_key}</code>\n"
                f"• ⚽ <b>ESPN 4 HD:</b> <code>/stream espn4 {curr_key}</code>\n"
                f"• ⚽ <b>ESPN 5 HD:</b> <code>/stream espn5 {curr_key}</code>\n"
                f"• ⚽ <b>ESPN 6 HD:</b> <code>/stream espn6 {curr_key}</code>\n"
                f"• ⚽ <b>ESPN 7 HD:</b> <code>/stream espn7 {curr_key}</code>\n"
                f"• ⚽ <b>ESPN Premium HD:</b> <code>/stream espnpremium {curr_key}</code>\n"
                f"• 🇺🇸 <b>ESPN Deportes USA:</b> <code>/stream espn-deportes {curr_key}</code>\n"
            )
            send_msg(chat_id, espn_msg)

        elif text.startswith("/partidos") or text.startswith("/agenda") or text.startswith("/hoy"):
            send_msg(chat_id, "⏳ <b>Cargando partidos de hoy desde RojaDirecta / Pelota Libre...</b>")
            msgs = get_live_matches_agenda(curr_key)
            for m in msgs:
                send_msg(chat_id, m)

        elif text.startswith("/stream"):
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL&gt; [STREAM_KEY]</code>\nEjemplo: <code>/stream espn2</code> o <code>/stream winplus</code>")
                return

            ch_input = parts[1].strip()
            s_key = parts[2].strip() if len(parts) >= 3 else curr_key

            send_msg(chat_id, f"🔄 <b>Conectando al servidor CDN para {ch_input}...</b>")
            ok, response_msg = start_single_stream(ch_input, s_key, chat_id)
            send_msg(chat_id, response_msg)

        elif text.startswith("/status") or text.startswith("/logs"):
            with stream_lock:
                if not active_streams:
                    send_msg(chat_id, "ℹ️ No hay ninguna transmisión activa actualmente.")
                    return

                msg_status = f"📊 <b>ESTADO DE TRANSMISIONES EN VIVO ({len(active_streams)} activas):</b>\n\n"
                for sid, info in active_streams.items():
                    elapsed = int(time.time() - info["start_time"])
                    mins = elapsed // 60
                    secs = elapsed % 60
                    proc_state = "🟢 EN EJECUCIÓN (EMITIENDO)" if info["process"].poll() is None else "🔴 DETENIDO"
                    
                    last_log = ""
                    try:
                        log_file = info.get("log_file")
                        if log_file and os.path.exists(log_file):
                            with open(log_file, "r", encoding="utf-8", errors="ignore") as lf:
                                last_log = lf.read()[-300:]
                    except Exception:
                        pass

                    msg_status += (
                        f"🔹 <b>Stream #{sid}:</b> {html.escape(info['channel_name'])}\n"
                        f"• 🌐 <b>Estado:</b> {proc_state}\n"
                        f"• ⏱️ <b>Tiempo activo:</b> {mins}m {secs}s\n"
                        f"• 🔑 <b>Key:</b> <code>{info['key'][:12]}...</code>\n"
                        f"• 🛑 <b>Detener:</b> <code>/stop {sid}</code>\n"
                    )
                    if last_log:
                        msg_status += f"• 📋 <b>Último log FFmpeg:</b>\n<code>{html.escape(last_log)}</code>\n\n"
                    else:
                        msg_status += "\n"

                msg_status += "🛑 <i>Para detener todas las transmisiones:</i> <code>/stopall</code>"
                send_msg(chat_id, msg_status)

        elif text.startswith("/stopall"):
            ok, response_msg = stop_all_streams()
            send_msg(chat_id, response_msg)

        elif text.startswith("/stop"):
            parts = text.split(maxsplit=1)
            arg = parts[1].strip() if len(parts) > 1 else None
            ok, response_msg = stop_single_stream(arg)
            send_msg(chat_id, response_msg)

        elif text.startswith("/key"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                send_msg(chat_id, f"🔑 <b>Stream Key actual:</b> <code>{curr_key}</code>\n\nPara cambiarla usa: <code>/key NUEVA_KEY</code>")
                return

            new_key = clean_arg(parts[1])
            CONFIG["stream_key"] = new_key
            save_config(CONFIG)
            send_msg(chat_id, f"✅ <b>Stream Key actualizada correctamente:</b>\n<code>{new_key}</code>")

        elif text.startswith("/"):
            send_msg(chat_id, "❓ <b>Comando no reconocido.</b>\nUsa <code>/partidos</code>, <code>/canales</code> o <code>/ayuda</code> para ver los comandos.")

    except Exception as e:
        print("Error procesando mensaje:", e)
        send_msg(chat_id, f"⚠️ Ocurrió un error temporal al procesar la solicitud: <code>{html.escape(str(e))}</code>")

def main():
    print("=" * 65)
    print("🤖 BOT DE TRANSMISIÓN DE FÚTBOL (STREAMTP / ROJADIRECTA HLS ENGINE)")
    print("=" * 65)
    print("Iniciando polling de Telegram...")
    offset = 0

    while True:
        try:
            url = f"{API_URL}/getUpdates?offset={offset}&timeout=25"
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok"):
                    for result in data.get("result", []):
                        offset = result["update_id"] + 1
                        if "message" in result:
                            t = threading.Thread(target=handle_message, args=(result["message"],), daemon=True)
                            t.start()
            elif r.status_code in [401, 404]:
                print(f"Error fatal Telegram: {r.status_code}. Revisa el TELEGRAM_BOT_TOKEN.")
                time.sleep(10)
            else:
                time.sleep(2)
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    main()
