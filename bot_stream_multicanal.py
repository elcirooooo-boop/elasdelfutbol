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

# LIGAS Y COMPETICIONES CON SUS BANDERAS Y PRIORIDADES
LEAGUE_CATEGORIES = [
    # Deportes específicos
    (r'moto gp|motogp|f[oó]rmula 1|f1|indycar|nascar|rally', '🏎️ <b>MOTORSPORT (MOTO GP / F1 / INDYCAR)</b>', 210),
    (r'ciclismo|la vuelta|tour de francia|giro d.italia|giro de italia|\bgiro\b', '🚴 <b>CICLISMO</b>', 220),
    (r'tenis|tennis|atp|wta|us open|roland garros|wimbledon|australian open', '🎾 <b>TENIS (ATP / WTA)</b>', 230),
    (r'golf|pga|tour championship', '⛳ <b>GOLF (PGA TOUR)</b>', 290),
    (r'rugby|pumas|all blacks|six nations|urba', '🏉 <b>RUGBY</b>', 240),
    (r'boxeo|box|knockout|ufc|mma|peleas', '🥊 <b>BOXEO / UFC / COMBATE</b>', 250),
    (r'b[eé]isbol|baseball|mlb|little ligue|little league', '⚾ <b>BÉISBOL (MLB)</b>', 260),
    (r'b[aá]squet|basketball|nba|euroliga', '🏀 <b>BÁSQUETBOL (NBA / EUROLIGA)</b>', 270),
    (r'hockey', '🏑 <b>HOCKEY</b>', 280),

    # Conmebol / UEFA / Internacionales
    (r'champions league|uefa|sorteo.*champions|europa league|conference league|supercopa de europa', '🇪🇺 <b>UEFA (CHAMPIONS / EUROPA / CONFERENCE)</b>', 1),
    (r'libertadores|sudamericana|recopa', '🌎 <b>CONMEBOL (LIBERTADORES / SUDAMERICANA)</b>', 2),

    # Ligas Top de Europa
    (r'laliga smartbank|laliga hypermotion|smartbank|hypermotion', '🇪🇸 <b>LALIGA HYPERMOTION (ESPAÑA)</b>', 10),
    (r'laliga|la liga|copa del rey|supercopa de espa[nñ]a', '🇪🇸 <b>LALIGA EA SPORTS (ESPAÑA)</b>', 11),
    (r'premier league|premier', '🏴󠁧󠁢󠁥󠁮󠁧󠁿 <b>PREMIER LEAGUE (INGLATERRA)</b>', 20),
    (r'championship|efl cup|carabao|fa cup|league one|league two', '🏴󠁧󠁢󠁥󠁮󠁧󠁿 <b>FÚTBOL INGLÉS (CHAMPIONSHIP / COPAS)</b>', 21),
    
    # Ecuador (antes de Serie A Italia)
    (r'independiente del valle|guayaquil city|manta vs|barcelona.*sc|ldu quito|aucas|emelec|delfin|el nacional|cat[oó]lica.*ecuador|orense|cumbay|macar[aá]|mushuc', '🇪🇨 <b>LIGA PRO (ECUADOR)</b>', 160),
    
    # Italia
    (r'serie a|coppa italia', '🇮🇹 <b>SERIE A (ITALIA)</b>', 30),
    
    # Alemania
    (r'2\.\s*bundesliga', '🇩🇪 <b>2. BUNDESLIGA (ALEMANIA)</b>', 40),
    (r'bundesliga|dfb[ -]pokal|supercopa alemana', '🇩🇪 <b>BUNDESLIGA (ALEMANIA)</b>', 41),
    
    # Francia
    (r'ligue 1|ligue 2|coupe de france', '🇫🇷 <b>LIGUE 1 (FRANCIA)</b>', 50),
    
    # Portugal
    (r'primeira liga|taca de portugal|liga portugal', '🇵🇹 <b>PRIMEIRA LIGA (PORTUGAL)</b>', 60),
    
    # Países Bajos
    (r'eredivisie|eerste divisie|knvb beker', '🇳🇱 <b>EREDIVISIE (PAÍSES BAJOS)</b>', 70),
    
    # Arabia Saudita
    (r'pro league|saudi pro league|saudi|al fateh|al ittihad|al hilal|al nassr', '🇸🇦 <b>SAUDI PRO LEAGUE (ARABIA SAUDITA)</b>', 75),
    
    # Argentina
    (r'liga profesional|copa de la liga|copa argentina|primera nacional|torneo de reserva', '🇦🇷 <b>FÚTBOL ARGENTINO (LIGA PROFESIONAL)</b>', 80),
    
    # Brasil
    (r'brasileir[aã]o|copa do brasil|paulista|carioca|brasileiro', '🇧🇷 <b>BRASILEIRÃO (BRASIL)</b>', 90),
    
    # Colombia
    (r'primera a:\s*(?:junior|santa fe|jaguares|am[eé]rica|alianza|atl[eé]tico nacional|millonarios|medellin|cali|tolima|once caldas|bucaramanga|pereira|pasto|envigado|aguilas|equidad|patriotas|fortaleza)|liga betplay|copa colombia', '🇨🇴 <b>LIGA BETPLAY (COLOMBIA)</b>', 100),
    
    # México
    (r'liga mx|expansi[oó]n mx|liga de expansi[oó]n|copa mx', '🇲🇽 <b>LIGA MX (MÉXICO)</b>', 110),
    
    # Perú
    (r'liga 1|liga 2|copa bicentenario', '🇵🇪 <b>LIGA 1 (PERÚ)</b>', 120),
    
    # Chile
    (r'limache|concepci[oó]n|nublense|san felipe|magallanes|iquique|san luis|santa cruz|rangers|colo|u[.]\s*de chile|u[.]\s*cat[oó]lica|huachipato|audax|cobresal|cobreloa|coquimbo|palestino|uni[oó]n espa[nñ]ola|everton', '🇨🇱 <b>FÚTBOL CHILENO (CHILE)</b>', 130),
    
    # Uruguay
    (r'progreso|danubio|deportivo colonia|tacuaremb|cerrito|montevideo|la luz|paysandu|atenas|torque|boston river|defensor|juventud|deportivo maldonado|pe[nñ]arol|nacional', '🇺🇾 <b>FÚTBOL URUGUAYO (URUGUAY)</b>', 140),
    
    # Paraguay
    (r'trinidense|2 de mayo|recoleta|olimpia|sportivo luq|sportivo sa|cerro porte[nñ]o|libertad|guaran[ií]|nacional.*py|tacuary|general caballero|amelliano', '🇵🇾 <b>PRIMERA DIVISIÓN (PARAGUAY)</b>', 150),
    
    # Bolivia
    (r'bolivia|gualberto|real oruro|potos[ií]|always ready|the strongest|bolivar|wilstermann|oriente petrolero|blooming|aurora|universitario de vinto|guabir[aá]|independiente petrolero|san antonio bulo', '🇧🇴 <b>DIVISIÓN PROFESIONAL (BOLIVIA)</b>', 170),
    
    # Centroamérica / CONCACAF
    (r'costa rica|alajuelense|saprissa|herediano|zeled[oó]n|concacaf|centroamericana|comunicaciones|municipal|motagua|olimpia.*hn|alianza.*pan|mixco', '🌎 <b>CENTROAMÉRICA / CONCACAF</b>', 180),
]

def classify_event(desc):
    desc_clean = desc.lower()
    for pattern, cat_name, priority in LEAGUE_CATEGORIES:
        if re.search(pattern, desc_clean):
            return cat_name, priority
    return '🏆 <b>MÁS EVENTOS DEPORTIVOS</b>', 999

def extract_stream_code(embed_iframe):
    if not embed_iframe:
        return None
    
    clean_ifr = embed_iframe
    if "r=" in clean_ifr:
        try:
            b64 = clean_ifr.split("r=")[1].split("&")[0]
            clean_ifr = base64.b64decode(b64).decode('utf-8')
        except Exception:
            pass
            
    if "stream=" in clean_ifr:
        st = clean_ifr.split("stream=")[1].split("&")[0]
        return st.strip()
        
    if "tv-90.com/" in clean_ifr or "tvf90.com/" in clean_ifr:
        part = clean_ifr.split(".com/")[1].replace(".php", "").split("&")[0]
        if not (part.startswith("1") or part.startswith("hd") or part.startswith("3") or part.startswith("5")):
            return part.strip()
            
    return embed_iframe

# DETECTOR DINÁMICO DE SUBDOMINIO CDN ACTIVO
def find_working_m3u8(raw_m3u8, referer_url):
    for i in range(1, 16):
        vh = f"{i}.01-f.com"
        t_url = re.sub(r'[\w\.-]+\.01-f\.com', vh, raw_m3u8)
        try:
            r = requests.get(t_url, headers={"User-Agent": "Mozilla/5.0", "Referer": referer_url}, timeout=1.5)
            if r.status_code == 200 and ("#EXTM3U" in r.text or len(r.content) > 50):
                return t_url
        except Exception:
            pass
    return None

# RESOLVEDOR UNIVERSAL DINÁMICO CON FALLBACK AUTOMÁTICO
def resolve_live_stream_url(target):
    target_clean = target.lower().strip()
    
    url_to_fetch = target
    if "r=" in target:
        try:
            b64_part = target.split("r=")[1].split("&")[0]
            url_to_fetch = base64.b64decode(b64_part).decode('utf-8')
        except Exception:
            pass

    aliases = [target_clean]
    if target_clean == "dsportsar":
        aliases.extend(["dsports", "dsports2"])
    elif target_clean == "dsports2":
        aliases.extend(["dsports"])
    elif target_clean == "dsports_eventos":
        aliases.extend(["dsports", "dsportsar"])
    elif target_clean == "espnpremium":
        aliases.extend(["espn", "espn2"])

    for alias in aliases:
        endpoints = []
        if url_to_fetch.startswith("http") and alias == target_clean:
            endpoints.append(url_to_fetch)
        
        endpoints.extend([
            f"https://futbollibre.ch/5.php?stream={alias}",
            f"https://tvf90.com/5.php?stream={alias}",
            f"https://futbollibre.ch/hd.php?stream={alias}",
            f"https://tvf90.com/hd.php?stream={alias}",
            f"https://futbollibre.ch/1.php?stream={alias}",
            f"https://tvf90.com/1.php?stream={alias}",
            f"https://futbollibre.ch/3.php?stream={alias}",
            f"https://tvf90.com/3.php?stream={alias}",
        ])

        for ep in endpoints:
            try:
                r = requests.get(ep, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://rojadirectatv.ec/"}, timeout=3.0)
                if r.status_code == 200:
                    m3u8 = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', r.text)
                    if m3u8:
                        working_url = find_working_m3u8(m3u8[0], ep)
                        if working_url:
                            return working_url, f"Referer: {ep}\r\nOrigin: {ep.rsplit('/', 1)[0]}\r\n", True
                    
                    iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text)
                    for ifr in iframes:
                        ifr_url = ifr if ifr.startswith("http") else f"https://futbollibre.ch/{ifr.lstrip('/')}"
                        r2 = requests.get(ifr_url, headers={"User-Agent": "Mozilla/5.0", "Referer": ep}, timeout=3.0)
                        m3u8_2 = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', r2.text)
                        if m3u8_2:
                            working_url2 = find_working_m3u8(m3u8_2[0], ifr_url)
                            if working_url2:
                                return working_url2, f"Referer: {ifr_url}\r\nOrigin: {ifr_url.rsplit('/', 1)[0]}\r\n", True
            except Exception:
                pass

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
    {"name": "Directv Sports Argentina (DSPORTS AR)", "cmd": "dsportsar"},
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

        groups = {}
        for item in data:
            attrs = item.get("attributes", {})
            raw_desc = attrs.get("diary_description", "").strip().replace("\n", " ")
            clean_desc = html.escape(" ".join(raw_desc.split()))
            hour = attrs.get("diary_hour", "")[:5]
            embeds = attrs.get("embeds", {}).get("data", [])
            
            cat_header, prio = classify_event(raw_desc)
            if (prio, cat_header) not in groups:
                groups[(prio, cat_header)] = []
            
            groups[(prio, cat_header)].append((hour, clean_desc, embeds))

        messages = []
        header = f"📅 <b>AGENDA DEPORTIVA ORGANIZADA POR LIGAS ({len(data)} EVENTOS DE HOY)</b>\n\n"
        current_msg = header

        for (prio, cat_header), event_list in sorted(groups.items()):
            cat_block = f"━━━━━━━━━━━━━━━━━━━━\n{cat_header}\n━━━━━━━━━━━━━━━━━━━━\n"
            
            for hour, clean_desc, embeds in event_list:
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
                cat_block += partido_block
            
            if len(current_msg) + len(cat_block) > 3400:
                messages.append(current_msg)
                current_msg = cat_block
            else:
                current_msg += cat_block

        if current_msg.strip():
            messages.append(current_msg)

        return messages
    except Exception as e:
        return [f"⚠️ Error obteniendo la agenda de rojadirectatv.ec: {e}"]

# ==============================================================================
# 2. MOTOR ANTI-CONGELAMIENTO (FFMPEG BLINDADO + WATCHDOG ULTRA-RÁPIDO)
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
        "-reconnect_delay_max", "1",
        "-rw_timeout", "5000000",
        "-fflags", "+nobuffer+genpts+igndts+discardcorrupt",
        "-avoid_negative_ts", "make_zero",
        "-max_interleave_delta", "0"
    ]

    if not source_url.endswith(".m3u8"):
        cmd.extend(["-re"])

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
        source_url, headers, is_ok = resolve_live_stream_url(raw_url)

        if not is_ok:
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

# WATCHDOG EN SEGUNDO PLANO (AUTO-RECUPERADOR INSTANTÁNEO)
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
            "⚽ <b>BOT DE TRANSMISIÓN DEPORTIVA (ROJADIRECTATV.EC)</b>\n\n"
            "📋 <b>AGENDA ORGANIZADA:</b>\n"
            "• <code>/partidos</code> $\\rightarrow$ Ver todos los partidos <b>organizados por ligas y países</b>\n"
            "• <code>/top</code> $\\rightarrow$ Canales deportivos principales 24/7\n\n"
            "📺 <b>TRANSMITIR:</b>\n"
            "• <code>/stream espn</code> | <code>/stream espn2</code> | <code>/stream espn4</code>\n"
            "• <code>/stream dsports</code> | <code>/stream dsports2</code> | <code>/stream dsportsar</code>\n"
            "• <code>/stream winsports</code> | <code>/stream hypermotion1</code> | <code>/stream telemundo</code>\n"
            "• <code>/stream &lt;CANAL&gt; [STREAM_KEY]</code>\n\n"
            "🛑 <b>DETENER TRANSMISIONES:</b>\n"
            "• <code>/stop</code> $\\rightarrow$ Detener la transmisión activa\n"
            "• <code>/stop 1</code> | <code>/stop 2</code> $\\rightarrow$ Detener por número\n"
            "• <code>/stopall</code> $\\rightarrow$ Detener TODAS las transmisiones\n\n"
            "📊 <b>ESTADO EN VIVO:</b>\n"
            "• <code>/status</code> $\\rightarrow$ Ver transmisiones activas\n\n"
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
        send_msg(chat_id, "⏳ <b>Cargando agenda organizada por ligas y banderas...</b>")
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
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL&gt;</code> o <code>/stream &lt;CANAL&gt; &lt;STREAM_KEY&gt;</code>\nEjemplo: <code>/stream espn</code>")
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
                f"🛡️ <b>Protección:</b> Anti-Freeze + Auto-Scan CDN\n"
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
    print("🤖 Bot de Transmisión con Auto-Scan CDN listo...")
    
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
