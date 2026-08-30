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

# ==============================================================================
# 1. CONFIGURACIÓN DEL BOT (100% NATIVO TARJETAROJA.MY + STREAMXHD EN ESPAÑOL)
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CONFIG_FILE = "config_stream.json"
AGENDA_URL = "https://tarjetaroja.my/"

IPTV_USER = "BE15ERDV"
IPTV_PASS = "PXELERB9"
IPTV_HOSTS = [
    "http://evestv.leptis.live",
    "http://evestv.ptjfj.com"
]

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://tarjetaroja.my/"
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

# CLASIFICACIÓN DE LIGAS CON BANDERAS
LEAGUE_CATEGORIES = [
    (r'juventus|parma|serie a|coppa italia|milan|inter|roma|napoli|lazio', '🇮🇹 <b>SERIE A (ITALIA)</b>', 30),
    (r'laliga smartbank|laliga hypermotion|smartbank|hypermotion', '🇪🇸 <b>LALIGA HYPERMOTION (ESPAÑA)</b>', 10),
    (r'laliga|la liga|copa del rey|supercopa de espa[nñ]a|real madrid|barcelona|atletico|sevilla', '🇪🇸 <b>LALIGA EA SPORTS (ESPAÑA)</b>', 11),
    (r'premier league|premier|liverpool|arsenal|chelsea|manchester|tottenham|newcastle', '🏴󠁧󠁢󠁥󠁮󠁧󠁿 <b>PREMIER LEAGUE (INGLATERRA)</b>', 20),
    (r'championship|efl cup|carabao|fa cup|league one|league two', '🏴󠁧󠁢󠁥󠁮󠁧󠁿 <b>FÚTBOL INGLÉS (CHAMPIONSHIP / COPAS)</b>', 21),
    (r'champions league|uefa|sorteo.*champions|europa league|conference league|supercopa de europa', '🇪🇺 <b>UEFA (CHAMPIONS / EUROPA / CONFERENCE)</b>', 1),
    (r'libertadores|sudamericana|recopa', '🌎 <b>CONMEBOL (LIBERTADORES / SUDAMERICANA)</b>', 2),
    (r'bundesliga 2|2\. bundesliga', '🇩🇪 <b>BUNDESLIGA 2 (ALEMANIA)</b>', 40),
    (r'bundesliga|dfb[ -]pokal|supercopa alemana|bayern|dortmund', '🇩🇪 <b>BUNDESLIGA (ALEMANIA)</b>', 41),
    (r'ligue 1|ligue 2|coupe de france|psg|marseille|monaco|lyon', '🇫🇷 <b>LIGUE 1 (FRANCIA)</b>', 50),
    (r'primeira liga|taca de portugal|liga portugal|benfica|porto|sporting', '🇵🇹 <b>PRIMEIRA LIGA (PORTUGAL)</b>', 60),
    (r'eredivisie|eerste divisie|knvb beker|ajax|psv|feyenoord', '🇳🇱 <b>EREDIVISIE (PAÍSES BAJOS)</b>', 70),
    (r'pro league|saudi pro league|saudi|al fateh|al ittihad|al hilal|al nassr', '🇸🇦 <b>SAUDI PRO LEAGUE (ARABIA SAUDITA)</b>', 75),
    (r'liga profesional|copa de la liga|copa argentina|primera nacional|boca|river|racing', '🇦🇷 <b>FÚTBOL ARGENTINO (LIGA PROFESIONAL)</b>', 80),
    (r'brasileir[aã]o|copa do brasil|paulista|carioca|flamengo|palmeiras', '🇧🇷 <b>BRASILEIRÃO (BRASIL)</b>', 90),
    (r'primera a:\s*(?:junior|santa fe|jaguares|am[eé]rica|alianza|atl[eé]tico nacional|millonarios|medellin|cali|tolima|once caldas|bucaramanga|pereira|pasto|envigado|aguilas|equidad|patriotas|fortaleza)|liga betplay|copa colombia', '🇨🇴 <b>LIGA BETPLAY (COLOMBIA)</b>', 100),
    (r'liga mx|expansi[oó]n mx|liga de expansi[oó]n|copa mx|america|chivas|cruz azul|monterrey|tigres', '🇲🇽 <b>LIGA MX (MÉXICO)</b>', 110),
    (r'liga 1|liga 2|copa bicentenario|alianza lima|universitario|cristal', '🇵🇪 <b>LIGA 1 (PERÚ)</b>', 120),
    (r'moto gp|motogp|f[oó]rmula 1|f1|indycar|nascar|rally|gp arag', '🏎️ <b>MOTORSPORT (MOTO GP / F1 / INDYCAR)</b>', 210),
    (r'ciclismo|la vuelta|tour de francia|giro d.italia|giro de italia|\bgiro\b', '🚴 <b>CICLISMO (LA VUELTA)</b>', 220),
    (r'tenis|tennis|atp|wta|us open|roland garros|wimbledon|australian open', '🎾 <b>TENIS (ATP / WTA)</b>', 230),
    (r'golf|pga|tour championship', '⛳ <b>GOLF (PGA TOUR)</b>', 290),
    (r'rugby|pumas|all blacks|six nations|urba', '🏉 <b>RUGBY</b>', 240),
    (r'boxeo|box|knockout|ufc|mma|peleas|lfa', '🥊 <b>BOXEO / UFC / COMBATE</b>', 250),
    (r'b[eé]isbol|baseball|mlb|little ligue|little league', '⚾ <b>BÉISBOL (MLB)</b>', 260),
    (r'b[aá]squet|basketball|nba|euroliga', '🏀 <b>BÁSQUETBOL (NBA / EUROLIGA)</b>', 270),
    (r'hockey', '🏑 <b>HOCKEY</b>', 280),
]

def classify_event(desc):
    desc_clean = desc.lower()
    for pattern, cat_name, priority in LEAGUE_CATEGORIES:
        if re.search(pattern, desc_clean):
            return cat_name, priority
    return '🏆 <b>MÁS EVENTOS DEPORTIVOS</b>', 999

def channel_stability_score(ch_name, slug):
    n = ch_name.lower()
    s = slug.lower()
    # Prioridad: Disney / Star+ > ESPN > Max > Movistar / DAZN > Fox Sports > TUDN
    if "disney" in n or "disney" in s:
        return 1
    if "espn" in n or "espn" in s:
        return 2
    if "max" in n or "max" in s:
        return 3
    if "movistar" in n or "laliga" in n:
        return 4
    if "dazn" in n:
        return 5
    if "fox" in n:
        return 6
    if "tudn" in n:
        return 7
    return 10

# CANALES DEDICADOS EN ESPAÑOL (LATINOAMÉRICA / ESPAÑA)
TARJETAROJA_FALLBACKS = {
    "espn": "32164", "espn1": "32164", "espn2": "32164", "espn3": "32112", "espn4": "32111", "espn7": "32138",
    "espnextra": "32138", "espnplus1": "32164", "espn-deportes": "32038", "espndeportes": "32038",
    "disney-1": "32164", "disney-2": "32164", "disney-3": "32112", "disney-4": "32111", "disney-5": "32138",
    "foxone": "6873", "foxone3": "6872", "fox1ar": "6873", "foxsports": "6873",
    "tudn_usa": "32040", "tudn": "32040", "max1": "239671", "max": "239671",
    "universo_usa": "32162", "universo": "32162", "canal5": "3987",
    "paramount1": "29016", "paramount2": "29043", "paramount3": "29044", "stp-paramount1": "29016",
    "juventus": "8805", "juve": "8805", "seriea": "8805", "parma": "8805",
    "dsports": "33933", "dsports1": "33933", "directv": "33933", "dsportsar": "33933",
    "dsports2": "33932", "dsportsplus": "33931",
    "winsports": "33945", "win": "33945", "wincolombia": "33944",
    "tyc": "30365", "tycsports": "30365",
    "laliga": "30905", "movistarlaliga": "30905", "m+laliga": "30905", "laligatv": "33866",
    "dazn": "224832", "daznlaliga": "224832",
    "f1": "30907", "daznf1": "30907", "motogp": "1349240"
}

# EXTRACTOR DE M3U8 DE STREAMXHD (DISNEY, STAR, MAX, PEACOCK, ESPN EN ESPAÑOL)
def extract_from_streamxhd(stream_url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://tarjetaroja.my/"
        }
        r = requests.get(stream_url, headers=headers, timeout=3.5)
        html_txt = r.text
        
        m_var = re.search(r'([a-zA-Z0-9_]+)\.forEach\([^}]*playbackURL\+=', html_txt)
        if not m_var:
            return None, None, False
        arr_var = m_var.group(1)
        
        m_k = re.search(rf'{arr_var}\.sort[^;]+;\s*var\s+k\s*=\s*([a-zA-Z0-9_]+)\(\)\s*\+\s*([a-zA-Z0-9_]+)\(\)', html_txt)
        if not m_k:
            return None, None, False
        f1_name, f2_name = m_k.group(1), m_k.group(2)
        
        m_f1 = re.search(rf'function\s+{f1_name}\(\)\s*\{{\s*return\s+(\d+);\s*\}}', html_txt)
        m_f2 = re.search(rf'function\s+{f2_name}\(\)\s*\{{\s*return\s+(\d+);\s*\}}', html_txt)
        if not m_f1 or not m_f2:
            return None, None, False
            
        k = int(m_f1.group(1)) + int(m_f2.group(1))
        
        m_arr = re.search(rf'(?:var\s+|let\s+)?{arr_var}\s*=\s*(\[\[\d+,\s*["\'][^"\']+["\']\].*?\]);', html_txt, re.DOTALL)
        if not m_arr:
            return None, None, False
            
        ho_data = json.loads(m_arr.group(1))
        ho_data.sort(key=lambda x: x[0])
        
        playbackURL = ""
        for idx, v in ho_data:
            decoded_b64 = base64.b64decode(v).decode('utf-8', errors='ignore')
            digits_only = re.sub(r'\D', '', decoded_b64)
            if digits_only:
                char_code = int(digits_only) - k
                playbackURL += chr(char_code)
                
        if playbackURL.startswith("http"):
            hdrs_str = f"Referer: {stream_url}\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
            return playbackURL, hdrs_str, True
    except Exception as e:
        print(f"Error decodificando StreamXHD ({stream_url}): {e}")
    return None, None, False

# RESOLVER DE SEÑAL EXACTA EN ESPAÑOL DE TARJETAROJA.MY
def resolve_tarjetaroja_stream(channel_name):
    ch_raw = str(channel_name).strip().lower().replace("stp-", "")
    ch_nodash = ch_raw.replace("-", "")
    
    # 1. Consultar la página exacta del stream en https://tarjetaroja.my/stream/<ch>
    for test_slug in [ch_raw, ch_nodash]:
        page_url = f"https://tarjetaroja.my/stream/{test_slug}"
        try:
            r_page = requests.get(page_url, headers=HTTP_HEADERS, timeout=3)
            if r_page.status_code == 200:
                iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', r_page.text)
                if iframes:
                    ifr_url = iframes[0]
                    if ifr_url.startswith("//"):
                        ifr_url = "https:" + ifr_url
                    if "streamxhd.com" in ifr_url:
                        m3u8, hdrs, ok = extract_from_streamxhd(ifr_url)
                        if ok:
                            return m3u8, hdrs, True
        except Exception:
            pass

    # 2. Consultar directamente en StreamXHD (donde están los canales latinos)
    for s_name in [ch_nodash, ch_raw]:
        for live_p in ["live1", "live2"]:
            u = f"https://streamxhd.com/{live_p}.php?stream={s_name}"
            m3u8, hdrs, ok = extract_from_streamxhd(u)
            if ok:
                return m3u8, hdrs, True

    # 3. Mapeo de alias a StreamXHD
    aliases = {
        "peacocktv": "peacock1", "peacock": "peacock1",
        "espn1": "espn", "espn": "espn", "espn2": "espn2", "espn3": "espn3", "espn4": "espn4",
        "foxsports1": "foxsports", "fox1ar": "foxsports", "max": "max1"
    }
    if ch_raw in aliases or ch_nodash in aliases:
        target_alias = aliases.get(ch_raw, aliases.get(ch_nodash))
        for live_p in ["live1", "live2"]:
            u = f"https://streamxhd.com/{live_p}.php?stream={target_alias}"
            m3u8, hdrs, ok = extract_from_streamxhd(u)
            if ok:
                return m3u8, hdrs, True

    # 4. Servidor dedicado en español garantizado 24/7
    stream_id = TARJETAROJA_FALLBACKS.get(ch_raw, TARJETAROJA_FALLBACKS.get(ch_nodash, "32164"))
    for host in IPTV_HOSTS:
        try:
            req_url = f"{host}/live/{IPTV_USER}/{IPTV_PASS}/{stream_id}.ts"
            return req_url, "User-Agent: IPTVSmartersPro\r\n", True
        except Exception:
            pass

    return None, None, False

# AGENDA EXTRAÍDA 100% DE HTTPS://TARJETAROJA.MY/ (CON CANAL MÁS ESTABLE PRIMERO)
def get_tarjetaroja_agenda_messages(curr_key):
    try:
        r = requests.get(AGENDA_URL, headers=HTTP_HEADERS, timeout=8)
        if r.status_code != 200:
            return ["🔴 No se pudo conectar a https://tarjetaroja.my/."]
        
        articles = re.findall(r'<article class="tr-event"[^>]*>(.*?)</article>', r.text, re.DOTALL)
        if not articles:
            return ["🔴 No se encontraron partidos en https://tarjetaroja.my/."]

        groups = {}
        for art in articles:
            m_time = re.search(r'<span class="tr-event-time[^"]*">([^<]+)</span>', art)
            event_time = m_time.group(1).strip() if m_time else "00:00"

            m_title = re.search(r'<span class="tr-event-title">(.*?)</span>\s*<span class="tr-event-chevron"', art, re.DOTALL)
            if m_title:
                clean = re.sub(r'<[^>]+>', ' ', m_title.group(1)).strip()
                clean_title = html.escape(" ".join(clean.split()))
            else:
                m_title_fallback = re.search(r'<span class="tr-event-title">(.*?)</span>', art, re.DOTALL)
                if m_title_fallback:
                    clean = re.sub(r'<[^>]+>', ' ', m_title_fallback.group(1)).strip()
                    clean_title = html.escape(" ".join(clean.split()))
                else:
                    clean_title = "Evento Deportivo"

            channels = []
            ch_matches = re.findall(r'<a class="tr-event-channel"\s+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', art)
            for href, ch_name in ch_matches:
                ch_slug = href.split("/stream/")[-1].strip()
                channels.append((html.escape(ch_name.strip()), ch_slug))

            # Ordenar canales para que la opción más estable (Disney / Star+ / ESPN / Max) esté siempre primero
            channels.sort(key=lambda x: channel_stability_score(x[0], x[1]))

            cat_header, prio = classify_event(clean_title)
            if (prio, cat_header) not in groups:
                groups[(prio, cat_header)] = []

            groups[(prio, cat_header)].append((event_time, clean_title, channels))

        messages = []
        header = f"📅 <b>AGENDA DEPORTIVA DE TARJETAROJA.MY ({len(articles)} EVENTOS EN VIVO)</b>\n\n"
        current_msg = header

        for (prio, cat_header), event_list in sorted(groups.items()):
            cat_title = f"━━━━━━━━━━━━━━━━━━━━\n{cat_header}\n━━━━━━━━━━━━━━━━━━━━\n"

            if len(current_msg) + len(cat_title) > 2800:
                messages.append(current_msg)
                current_msg = cat_title
            else:
                current_msg += cat_title

            for event_time, clean_title, channels in event_list:
                partido_block = f"⚽ <b>{clean_title}</b> (<code>{event_time}</code>)\n"
                if not channels:
                    partido_block += f"  ⭐ <b>MÁS ESTABLE (ESPN en Español):</b>\n  <code>/stream espn {curr_key}</code>\n"
                else:
                    # Canal principal recomendado / más estable
                    top_name, top_slug = channels[0]
                    partido_block += f"  ⭐ <b>MÁS ESTABLE ({top_name} en Español):</b>\n  <code>/stream {top_slug} {curr_key}</code>\n"
                    
                    # Canales alternativos
                    if len(channels) > 1:
                        partido_block += "  <i>Alternativas:</i>\n"
                        for alt_name, alt_slug in channels[1:]:
                            partido_block += f"  • ▶ <b>{alt_name}:</b> <code>/stream {alt_slug} {curr_key}</code>\n"
                partido_block += "\n"

                if len(current_msg) + len(partido_block) > 2800:
                    messages.append(current_msg)
                    current_msg = f"{cat_title}{partido_block}"
                else:
                    current_msg += partido_block

        if current_msg.strip():
            messages.append(current_msg)

        return messages
    except Exception as e:
        return [f"⚠️ Error cargando agenda de tarjetaroja.my: {e}"]

# ==============================================================================
# 2. MOTOR ULTRA-SINCRONIZADO (CERO DESFASE DE AUDIO / STREAM-COPY DIRECTO)
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
    # Configuración de Buffer HLS idéntica a los navegadores web (Hls.js / Clappr)
    # -live_start_index -3: Mantiene un colchón de seguridad de 3 segmentos (12s) para absorber cualquier latencia de red
    # -http_persistent 1 + -multiple_requests 1: Mantiene la conexión HTTP viva y estable
    cmd = [
        "ffmpeg",
        "-live_start_index", "-3",
        "-http_persistent", "1",
        "-multiple_requests", "1",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-rw_timeout", "10000000",
        "-fflags", "+genpts+igndts+discardcorrupt",
        "-analyzeduration", "2000000",
        "-probesize", "2000000"
    ]

    if headers:
        cmd.extend(["-headers", headers])

    cmd.extend([
        "-i", source_url,
        "-c", "copy",
        "-bsf:v", "dump_extra=freq=keyframe",
        "-bsf:a", "aac_adtstoasc",
        "-avoid_negative_ts", "make_zero",
        "-max_muxing_queue_size", "8192",
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
        source_url, headers, is_ok = resolve_tarjetaroja_stream(raw_url)

        if not is_ok or not source_url:
            return False, stream_id, f"No se pudo resolver la señal '{raw_url}' de tarjetaroja.my."

        proc, out_f, log_file = launch_ffmpeg_process(source_url, headers, destination, stream_id)
        
        time.sleep(3.5)
        if proc.poll() is not None:
            out_f.close()
            err_snippet = "No se pudo conectar a la fuente."
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    log_text = f.read()
                    if "Error opening output" in log_text or "I/O error" in log_text:
                        err_snippet = "Telegram rechazó la Stream Key. Asegúrate de que el directo esté abierto en Telegram y copia la Stream Key actual."
                    else:
                        lines = [l.strip() for l in log_text.splitlines() if l.strip()]
                        if lines:
                            err_snippet = lines[-1]
            except Exception:
                pass
            return False, stream_id, err_snippet

        now = time.time()
        active_streams[stream_id] = {
            "process": proc,
            "log_file": out_f,
            "log_path": log_file,
            "raw_name": raw_url,
            "url": source_url,
            "headers": headers,
            "destination": destination,
            "key": stream_key,
            "start_time": now,
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
            info["auto_restart"] = False
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
# 3. WATCHDOG LIMPIO (SOLO RECONECTA SI EL PROCESO REALMENTE CAE)
# ==============================================================================
def stream_watchdog():
    while True:
        try:
            time.sleep(2.0)
            with stream_lock:
                for sid, info in list(active_streams.items()):
                    if not info.get("auto_restart", False):
                        continue
                    
                    proc = info.get("process")
                    if proc and proc.poll() is not None:
                        print(f"⚠️ Watchdog: Canal #{sid} ({info['raw_name']}) cayó. Reconectando inmediatamente...")
                        try:
                            if "log_file" in info and not info["log_file"].closed:
                                info["log_file"].close()
                        except Exception:
                            pass
                        
                        new_url, new_hdrs, ok = resolve_tarjetaroja_stream(info["raw_name"])
                        if ok and new_url:
                            new_proc, new_out_f, new_log = launch_ffmpeg_process(
                                new_url, new_hdrs, info["destination"], sid
                            )
                            info["process"] = new_proc
                            info["log_file"] = new_out_f
                            info["log_path"] = new_log
                            info["url"] = new_url
                            info["headers"] = new_hdrs
                            info["restart_count"] = info.get("restart_count", 0) + 1
                            print(f"✅ Watchdog: Canal #{sid} reanudado exitosamente (Reconexión #{info['restart_count']}).")
        except Exception as e:
            print(f"Error en stream watchdog: {e}")

# ==============================================================================
# 4. INTERFAZ DE BOT DE TELEGRAM
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
            "⚽ <b>BOT DE TRANSMISIÓN DEPORTIVA (AUDIO/VIDEO 100% SINCRONIZADOS)</b>\n\n"
            "📋 <b>AGENDA DE PARTIDOS:</b>\n"
            "• <code>/partidos</code> $\\rightarrow$ Ver partidos en vivo con la <b>Opción Más Estable</b> de primero.\n\n"
            "📺 <b>TRANSMITIR CUALQUIER SEÑAL (EN ESPAÑOL):</b>\n"
            "• <code>/stream disney-4</code> | <code>/stream espn</code> | <code>/stream max1</code>\n"
            "• <code>/stream &lt;CANAL_O_SLUG&gt; [STREAM_KEY]</code>\n\n"
            "🛑 <b>DETENER TRANSMISIONES:</b>\n"
            "• <code>/stop</code> $\\rightarrow$ Detener la transmisión activa\n"
            "• <code>/stopall</code> $\\rightarrow$ Detener TODAS las transmisiones\n\n"
            "📊 <b>ESTADO EN VIVO:</b>\n"
            "• <code>/status</code> $\\rightarrow$ Ver transmisiones activas\n\n"
            f"🔑 <b>CLAVE STREAM:</b> <code>/key &lt;NUEVA_KEY&gt;</code>"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/partidos") or text.startswith("/hoy") or text.startswith("/agenda"):
        send_msg(chat_id, "⏳ <b>Cargando agenda en vivo de https://tarjetaroja.my/...</b>")
        agenda_msgs = get_tarjetaroja_agenda_messages(curr_key)
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
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL_O_SLUG&gt;</code> o <code>/stream &lt;CANAL&gt; &lt;STREAM_KEY&gt;</code>\nEjemplo: <code>/stream disney-4</code> o <code>/stream espn</code>")
            return
        
        raw_url = clean_arg(parts[1])
        stream_key = clean_arg(parts[2]) if len(parts) >= 3 else curr_key
        
        send_msg(chat_id, f"⏳ <b>Conectando a la señal en español de {html.escape(raw_url)} en https://tarjetaroja.my/...</b>")
        ok, sid, res = start_single_stream(raw_url, stream_key)
        if ok:
            send_msg(chat_id, (
                f"✅ <b>¡Transmisión ACTIVA y SINCRONIZADA!</b> 🚀\n\n"
                f"📺 <b>Canal #{sid}:</b> <code>{html.escape(raw_url)}</code>\n"
                f"🔑 <b>Key:</b> <code>{stream_key[:8]}...</code>\n"
                f"📡 <b>Fuente:</b> https://tarjetaroja.my/stream/{html.escape(raw_url)}\n"
                f"🎙️ <b>Sincronización:</b> Audio y Video 1:1 Nativo (Cero desfase)\n"
                f"⚡ <b>Modo:</b> Pure Stream Copy (0% CPU / Calidad Original)\n\n"
                f"🛑 <b>Detener esta:</b> <code>/stop {sid}</code> | <b>Detener todas:</b> <code>/stopall</code>"
            ))
        else:
            send_msg(chat_id, f"❌ <b>Error al iniciar:</b>\n{html.escape(res)}")

    elif text.startswith("/stopall") or text == "/stop all":
        count = stop_all_streams()
        if count > 0:
            send_msg(chat_id, f"🛑 <b>Se han detenido todas las transmisiones ({count} canales cerrados).</b>")
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
    print("🤖 Bot 100% TarjetaRoja.my (Audio/Video Pure Copy Sync) listo...")
    
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
