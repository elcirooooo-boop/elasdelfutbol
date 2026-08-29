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
import concurrent.futures

# ==============================================================================
# 1. CONFIGURACIÓN DEL BOT (100% NATIVO TARJETAROJA.MY + STREAMXHD + STREAMTP)
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CONFIG_FILE = "config_stream.json"
AGENDA_URL = "https://tarjetaroja.my/"

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

# EXTRACTOR DE M3U8 DE STREAMXHD (DISNEY, STAR, DAZN, ESPN)
def extract_from_streamxhd(stream_url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://tarjetaroja.my/"
        }
        r = requests.get(stream_url, headers=headers, timeout=5)
        html_txt = r.text
        
        func_returns = re.findall(r'function\s+[a-zA-Z0-9_]+\s*\(\)\s*\{\s*return\s+(\d+)\s*;\s*\}', html_txt)
        if not func_returns:
            return None, None, False
        k = sum(int(x) for x in func_returns)
        
        arr_match = re.search(r'(\[\[\d+,\s*["\'][^"\']+["\']\].*?\]);', html_txt, re.DOTALL)
        if not arr_match:
            return None, None, False
            
        ho_data = json.loads(arr_match.group(1))
        ho_data.sort(key=lambda x: x[0])
        
        playbackURL = ""
        for idx, v in ho_data:
            decoded_b64 = base64.b64decode(v).decode('utf-8', errors='ignore')
            digits_only = re.sub(r'\D', '', decoded_b64)
            if digits_only:
                char_code = int(digits_only) - k
                playbackURL += chr(char_code)
                
        if playbackURL.startswith("http"):
            return playbackURL, f"Referer: {stream_url}\r\nUser-Agent: Mozilla/5.0\r\n", True
    except Exception as e:
        print(f"Error decodificando StreamXHD: {e}")
    return None, None, False

# RESOLVER DIRECTO DE SEÑAL EXACTA DE TARJETAROJA.MY
def resolve_tarjetaroja_stream(channel_name):
    ch_raw = str(channel_name).strip().lower()
    ch_slug = ch_raw.replace("stp-", "").strip()
    
    # 1. Consultar la página exacta del stream en https://tarjetaroja.my/stream/<ch>
    page_url = f"https://tarjetaroja.my/stream/{ch_raw}"
    try:
        r_page = requests.get(page_url, headers=HTTP_HEADERS, timeout=5)
        if r_page.status_code == 200:
            iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', r_page.text)
            if iframes:
                ifr_url = iframes[0]
                if ifr_url.startswith("//"):
                    ifr_url = "https:" + ifr_url
                print(f"Iframe detectado para '{ch_raw}': {ifr_url}")
                
                # Caso A: StreamXHD (ej. disney21, disney2, espnplus, etc.)
                if "streamxhd.com" in ifr_url:
                    m3u8, hdrs, ok = extract_from_streamxhd(ifr_url)
                    if ok:
                        return m3u8, hdrs, True
                
                # Caso B: TVF90 / FutbolLibre / StreamTP
                if any(w in ifr_url for w in ["tvf90.com", "futbollibre.ch", "streamtp"]):
                    stream_param = ch_slug
                    if "stream=" in ifr_url:
                        stream_param = ifr_url.split("stream=")[1].split("&")[0].strip()
                    
                    for ep in [
                        f"https://tvf90.com/5.php?stream={stream_param}",
                        f"https://futbollibre.ch/5.php?stream={stream_param}",
                        f"https://tvf90.com/hd.php?stream={stream_param}",
                        f"https://futbollibre.ch/hd.php?stream={stream_param}"
                    ]:
                        try:
                            r_ep = requests.get(ep, headers={"User-Agent": "Mozilla/5.0", "Referer": ifr_url}, timeout=3.5)
                            m = re.search(r'playbackURL\s*=\s*["\']([^"\']+)["\']', r_ep.text)
                            if m and m.group(1).startswith("http"):
                                return m.group(1), f"Referer: {ifr_url}\r\nUser-Agent: Mozilla/5.0\r\n", True
                        except Exception:
                            pass
    except Exception as e:
        print(f"Error consultando {page_url}: {e}")

    # Fallback general para canales conocidos de tarjetaroja
    for ep in [
        f"https://tvf90.com/5.php?stream={ch_slug}",
        f"https://futbollibre.ch/5.php?stream={ch_slug}"
    ]:
        try:
            r_ep = requests.get(ep, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://tvf90.com/"}, timeout=3.5)
            m = re.search(r'playbackURL\s*=\s*["\']([^"\']+)["\']', r_ep.text)
            if m and m.group(1).startswith("http"):
                return m.group(1), "Referer: https://tvf90.com/\r\nUser-Agent: Mozilla/5.0\r\n", True
        except Exception:
            pass

    return None, None, False

# AGENDA EXTRAÍDA 100% DE HTTPS://TARJETAROJA.MY/
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
                    partido_block += f"  • ▶ <b>ESPN:</b>\n  <code>/stream espn {curr_key}</code>\n"
                else:
                    for ch_name, ch_slug in channels:
                        partido_block += f"  • ▶ <b>{ch_name}:</b>\n  <code>/stream {ch_slug} {curr_key}</code>\n"
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
# 2. MOTOR ANTI-CONGELAMIENTO (FFMPEG ULTRA-ESTABLE)
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
        "-reconnect", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "1",
        "-rw_timeout", "5000000",
        "-fflags", "+nobuffer+genpts+igndts+discardcorrupt",
        "-avoid_negative_ts", "make_zero",
        "-max_interleave_delta", "0"
    ]

    if headers:
        cmd.extend(["-headers", headers])

    cmd.extend([
        "-i", source_url,
        "-max_muxing_queue_size", "16384",
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
        source_url, headers, is_ok = resolve_tarjetaroja_stream(raw_url)

        if not is_ok or not source_url:
            return False, stream_id, f"No se pudo resolver la señal '{raw_url}' de tarjetaroja.my."

        proc, out_f, log_file = launch_ffmpeg_process(source_url, headers, destination, stream_id)
        
        time.sleep(2.0)
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

# WATCHDOG EN SEGUNDO PLANO
def stream_watchdog():
    while True:
        try:
            time.sleep(2)
            with stream_lock:
                for sid, info in list(active_streams.items()):
                    if not info.get("auto_restart", False):
                        continue
                    
                    proc = info.get("process")
                    if proc and proc.poll() is not None:
                        print(f"⚠️ Watchdog: Canal #{sid} ({info['raw_name']}) cayó. Re-conectando en 1s...")
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
                            info["url"] = new_url
                            info["headers"] = new_hdrs
                            info["restart_count"] = info.get("restart_count", 0) + 1
                            print(f"✅ Watchdog: Canal #{sid} reanudado exitosamente (Reconexión #{info['restart_count']}).")
        except Exception as e:
            print(f"Error en stream watchdog: {e}")

# ==============================================================================
# 3. INTERFAZ DE BOT DE TELEGRAM
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
            "⚽ <b>BOT DE TRANSMISIÓN DEPORTIVA (FUENTE: TARJETAROJA.MY)</b>\n\n"
            "📋 <b>AGENDA DE PARTIDOS:</b>\n"
            "• <code>/partidos</code> $\\rightarrow$ Ver todos los partidos en vivo de <b>https://tarjetaroja.my/</b>\n\n"
            "📺 <b>TRANSMITIR CUALQUIER SEÑAL:</b>\n"
            "• <code>/stream disney21</code> | <code>/stream disney-2</code>\n"
            "• <code>/stream espn</code> | <code>/stream espn2</code> | <code>/stream espn4</code>\n"
            "• <code>/stream foxone</code> | <code>/stream tudn_usa</code> | <code>/stream max1</code>\n"
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
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL_O_SLUG&gt;</code> o <code>/stream &lt;CANAL&gt; &lt;STREAM_KEY&gt;</code>\nEjemplo: <code>/stream disney21</code> o <code>/stream espn</code>")
            return
        
        raw_url = clean_arg(parts[1])
        stream_key = clean_arg(parts[2]) if len(parts) >= 3 else curr_key
        
        send_msg(chat_id, f"⏳ <b>Conectando a la señal exacta de {html.escape(raw_url)} en https://tarjetaroja.my/...</b>")
        ok, sid, res = start_single_stream(raw_url, stream_key)
        if ok:
            send_msg(chat_id, (
                f"✅ <b>¡Transmisión ACTIVA y 100% IDÉNTICA a la Web!</b> 🚀\n\n"
                f"📺 <b>Canal #{sid}:</b> <code>{html.escape(raw_url)}</code>\n"
                f"🔑 <b>Key:</b> <code>{stream_key[:8]}...</code>\n"
                f"📡 <b>Fuente:</b> https://tarjetaroja.my/stream/{html.escape(raw_url)}\n"
                f"⚡ <b>Modo:</b> Stream Passthrough (0% CPU / Calidad Original)\n\n"
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
    print("🤖 Bot 100% TarjetaRoja.my (StreamXHD & StreamTP Direct Resolver) listo...")
    
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
