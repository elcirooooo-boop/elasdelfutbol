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
from urllib.parse import urlparse

# ==============================================================================
# 1. CONFIGURACIÓN DEL BOT (SERVIDOR IPTV DEDICADO + AGENDA MUNDIAL)
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CONFIG_FILE = "config_stream.json"
AGENDA_API = "https://futbollibretv.org.pe/diaries.json?v=2.2"

IPTV_USER = "BE15ERDV"
IPTV_PASS = "PXELERB9"
IPTV_HOSTS = [
    "http://evestv.leptis.live",
    "http://evestv.ptjfj.com",
    "http://tv.rmhat.com"
]

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
    (r'juventus|parma|serie a|coppa italia|milan|inter|roma|napoli|lazio', '🇮🇹 <b>SERIE A (ITALIA)</b>', 30),
    (r'laliga smartbank|laliga hypermotion|smartbank|hypermotion', '🇪🇸 <b>LALIGA HYPERMOTION (ESPAÑA)</b>', 10),
    (r'laliga|la liga|copa del rey|supercopa de espa[nñ]a|real madrid|barcelona|atletico|sevilla', '🇪🇸 <b>LALIGA EA SPORTS (ESPAÑA)</b>', 11),
    (r'premier league|premier|liverpool|arsenal|chelsea|manchester|tottenham|newcastle', '🏴󠁧󠁢󠁥󠁮󠁧󠁿 <b>PREMIER LEAGUE (INGLATERRA)</b>', 20),
    (r'championship|efl cup|carabao|fa cup|league one|league two', '🏴󠁧󠁢󠁥󠁮󠁧󠁿 <b>FÚTBOL INGLÉS (CHAMPIONSHIP / COPAS)</b>', 21),
    (r'champions league|uefa|sorteo.*champions|europa league|conference league|supercopa de europa', '🇪🇺 <b>UEFA (CHAMPIONS / EUROPA / CONFERENCE)</b>', 1),
    (r'libertadores|sudamericana|recopa', '🌎 <b>CONMEBOL (LIBERTADORES / SUDAMERICANA)</b>', 2),
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
    (r'moto gp|motogp|f[oó]rmula 1|f1|indycar|nascar|rally', '🏎️ <b>MOTORSPORT (MOTO GP / F1 / INDYCAR)</b>', 210),
    (r'ciclismo|la vuelta|tour de francia|giro d.italia|giro de italia|\bgiro\b', '🚴 <b>CICLISMO</b>', 220),
    (r'tenis|tennis|atp|wta|us open|roland garros|wimbledon|australian open', '🎾 <b>TENIS (ATP / WTA)</b>', 230),
    (r'golf|pga|tour championship', '⛳ <b>GOLF (PGA TOUR)</b>', 290),
    (r'rugby|pumas|all blacks|six nations|urba', '🏉 <b>RUGBY</b>', 240),
    (r'boxeo|box|knockout|ufc|mma|peleas', '🥊 <b>BOXEO / UFC / COMBATE</b>', 250),
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

# DICCIONARIO GLOBAL DE CANALES IPTV
IPTV_CHANNELS_MAP = {
    # Juventus / Serie A
    "juventus": "8805",
    "juve": "8805",
    "seriea": "8805",
    "parma": "8805",
    "cbssports": "32109",
    "golazo": "3959",
    
    # ESPN / Disney
    "espn": "32114",
    "espn1": "32114",
    "espn2": "32164",
    "espn3": "32112",
    "espn4": "32111",
    "espnextra": "32138",
    "espnpremium": "32114",
    "espndeportes": "32038",
    "disney1": "32114",
    "disney2": "32164",
    "disney3": "32112",
    "disney4": "32111",
    "disney5": "32138",
    "disney6": "32114",
    "disney7": "32164",
    
    # Directv Sports (DSPORTS)
    "dsports": "33933",
    "dsports1": "33933",
    "directv": "33933",
    "dsportsar": "33933",
    "dsports2": "33932",
    "dsportsplus": "33931",
    "dsports3": "33931",
    
    # LaLiga / España
    "laliga": "30905",
    "movistarlaliga": "30905",
    "m+laliga": "30905",
    "laligatv": "33866",
    "hypermotion": "1219972",
    "hypermotion1": "1219972",
    "hypermotion2": "1219971",
    "dazn": "224832",
    "daznlaliga": "224832",
    "dazn1": "1459675",
    "golplay": "30905",
    "gol": "30905",
    
    # Champions / Premier / UK / USA
    "champions": "239671",
    "movistarchampions": "239671",
    "premier": "29016",
    "skysports": "29016",
    "premiersports": "29043",
    "premiersports1": "29043",
    "premiersports2": "29044",
    "tudn": "32040",
    "tudn_usa": "32040",
    "telemundo": "32162",
    "universo_usa": "32162",
    "max1": "239671",
    "paramount1": "29016",
    "paramount2": "29043",
    "paramount3": "29044",
    
    # Deportes Regionales
    "winsports": "33945",
    "win": "33945",
    "wincolombia": "33944",
    "tyc": "30365",
    "tycsports": "30365",
    "foxsports": "6873",
    "fox1ar": "6873",
    "foxone": "6873",
    
    # Moto / Motorsport / Otros
    "f1": "30907",
    "daznf1": "30907",
    "motogp": "1349240",
    "eurosport": "30911",
    "eurosport1": "30911",
    "eurosport2": "30912",
    "nfl": "32121",
    "redzone": "32121",
    "nba": "32106",
}

def clean_channel_code(raw_code):
    if not raw_code:
        return "espn"
    
    c = raw_code.strip()
    
    # Si viene con r= o base64
    if "r=" in c:
        try:
            b64 = c.split("r=")[1].split("&")[0]
            c = base64.b64decode(b64 + "==").decode('utf-8')
        except Exception:
            pass
            
    # Si es base64 puro
    if len(c) > 10 and not "/" in c and not "." in c and not " " in c:
        try:
            dec = base64.b64decode(c + "==").decode('utf-8')
            if "stream=" in dec:
                c = dec
        except Exception:
            pass

    if "stream=" in c:
        c = c.split("stream=")[1].split("&")[0].strip()
    elif "/" in c:
        c = c.split("/")[-1].replace(".php", "").replace(".html", "").strip()

    c_clean = re.sub(r'[^a-zA-Z0-9_]', '', c).lower()
    return c_clean or "espn"

# RESOLVER DE CANAL IPTV (DIRECTO A SERVIDOR DEDICADO)
def resolve_iptv_stream(stream_id_or_cmd):
    target_raw = str(stream_id_or_cmd).strip()
    target = clean_channel_code(target_raw)
    stream_id = None

    if target in IPTV_CHANNELS_MAP:
        stream_id = IPTV_CHANNELS_MAP[target]
    elif target.isdigit():
        stream_id = target
    else:
        for k, sid in IPTV_CHANNELS_MAP.items():
            if k in target or target in k:
                stream_id = sid
                break

    if not stream_id:
        stream_id = "32114"

    for host in IPTV_HOSTS:
        try:
            req_url = f"{host}/live/{IPTV_USER}/{IPTV_PASS}/{stream_id}.ts"
            r = requests.get(req_url, headers={"User-Agent": "IPTVSmartersPro"}, allow_redirects=False, timeout=3.5)
            loc = r.headers.get("Location")
            if loc:
                edge_host = loc.split('/')[2]
                edge_ip = "154.6.144.120"
                try:
                    doh = requests.get(f"https://cloudflare-dns.com/dns-query?name={edge_host}&type=A", headers={"accept": "application/dns-json"}, timeout=2).json()
                    if "Answer" in doh and doh["Answer"]:
                        edge_ip = doh["Answer"][0]["data"]
                except Exception:
                    pass
                
                final_stream_url = loc.replace(edge_host, edge_ip)
                headers_str = f"User-Agent: IPTVSmartersPro\r\nHost: {edge_host}\r\n"
                return final_stream_url, headers_str, True
            elif r.status_code == 200:
                return req_url, "User-Agent: IPTVSmartersPro\r\n", True
        except Exception:
            pass

    return None, None, False

# AGENDA MUNDIAL DE PARTIDOS CON CÓDIGOS LIMPIOS Y SEGUROS
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
        header = f"📅 <b>AGENDA DEPORTIVA DE HOY ({len(data)} EVENTOS CON CANALES IPTV 1080P)</b>\n\n"
        current_msg = header

        for (prio, cat_header), event_list in sorted(groups.items()):
            cat_title = f"━━━━━━━━━━━━━━━━━━━━\n{cat_header}\n━━━━━━━━━━━━━━━━━━━━\n"
            
            if len(current_msg) + len(cat_title) > 3000:
                messages.append(current_msg)
                current_msg = cat_title
            else:
                current_msg += cat_title

            for hour, clean_desc, embeds in event_list:
                partido_block = f"⚽ <b>{clean_desc}</b> (<code>{hour}</code>)\n"
                if not embeds:
                    partido_block += "  • 📺 <i>Canales:</i> <code>/stream espn</code> | <code>/stream laliga</code>\n"
                else:
                    for em in embeds:
                        em_attrs = em.get("attributes", {})
                        em_name = html.escape(em_attrs.get("embed_name", "").strip())
                        em_ifr = em_attrs.get("embed_iframe", "")
                        
                        clean_cmd = clean_channel_code(em_ifr)
                        partido_block += f"  • ▶ <b>{em_name}:</b>\n  <code>/stream {clean_cmd} {curr_key}</code>\n"
                partido_block += "\n"
                
                if len(current_msg) + len(partido_block) > 3000:
                    messages.append(current_msg)
                    current_msg = f"{cat_title}{partido_block}"
                else:
                    current_msg += partido_block

        if current_msg.strip():
            messages.append(current_msg)

        return messages
    except Exception as e:
        return [f"⚠️ Error obteniendo la agenda de partidos: {e}"]

# BÚSQUEDA DE CANALES IPTV EN EL SERVIDOR DEDICADO
def search_iptv_channels(query, curr_key):
    q = query.upper().strip()
    try:
        url = f"{IPTV_HOSTS[0]}/player_api.php?username={IPTV_USER}&password={IPTV_PASS}&action=get_live_streams"
        r = requests.get(url, timeout=10, headers={"User-Agent": "IPTVSmartersPro"}).json()
        
        matches = []
        for s in r:
            name = s.get("name", "").upper()
            if q in name:
                sid = s.get("stream_id")
                clean_name = html.escape(s.get("name").strip())
                matches.append((sid, clean_name))

        if not matches:
            return [f"🔍 No se encontraron canales con la búsqueda: <b>{html.escape(query)}</b>"]

        messages = []
        header = f"🔍 <b>RESULTADOS PARA '{html.escape(query)}' ({len(matches)} CANALES ENCONTRADOS):</b>\n\n"
        current_msg = header

        for sid, name in matches[:60]:
            item = f"📺 <b>{name}</b> (ID: <code>{sid}</code>)\n<code>/stream {sid} {curr_key}</code>\n\n"
            if len(current_msg) + len(item) > 3000:
                messages.append(current_msg)
                current_msg = item
            else:
                current_msg += item

        if current_msg.strip():
            messages.append(current_msg)

        return messages
    except Exception as e:
        return [f"⚠️ Error buscando canales en el servidor IPTV: {e}"]

# ==============================================================================
# 2. MOTOR ANTI-CONGELAMIENTO (FFMPEG ULTRA-ESTABLE PARA IPTV TS)
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
        source_url, headers, is_ok = resolve_iptv_stream(raw_url)

        if not is_ok or not source_url:
            return False, stream_id, f"No se pudo resolver el canal '{raw_url}'. Usa /top o /buscar."

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
                        
                        new_url, new_hdrs, ok = resolve_iptv_stream(info["raw_name"])
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
            "⚽ <b>BOT DE TRANSMISIÓN DEPORTIVA (SERVIDOR IPTV DEDICADO)</b>\n\n"
            "📋 <b>AGENDA DE PARTIDOS:</b>\n"
            "• <code>/partidos</code> $\\rightarrow$ Ver todos los partidos de hoy con sus canales limpios\n"
            "• <code>/top</code> $\\rightarrow$ Canales deportivos principales 24/7\n"
            "• <code>/buscar &lt;nombre&gt;</code> $\\rightarrow$ Buscar entre los 27.000 canales del servidor\n\n"
            "📺 <b>TRANSMITIR:</b>\n"
            "• <code>/stream juventus</code> | <code>/stream seriea</code>\n"
            "• <code>/stream espn</code> | <code>/stream espn2</code> | <code>/stream espn4</code>\n"
            "• <code>/stream dsports</code> | <code>/stream laliga</code> | <code>/stream dazn</code>\n"
            "• <code>/stream &lt;CANAL_O_ID&gt; [STREAM_KEY]</code>\n\n"
            "🛑 <b>DETENER TRANSMISIONES:</b>\n"
            "• <code>/stop</code> $\\rightarrow$ Detener la transmisión activa\n"
            "• <code>/stopall</code> $\\rightarrow$ Detener TODAS las transmisiones\n\n"
            "📊 <b>ESTADO EN VIVO:</b>\n"
            "• <code>/status</code> $\\rightarrow$ Ver transmisiones activas\n\n"
            f"🔑 <b>CLAVE STREAM:</b> <code>/key &lt;NUEVA_KEY&gt;</code>"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/partidos") or text.startswith("/hoy") or text.startswith("/agenda"):
        send_msg(chat_id, "⏳ <b>Cargando agenda limpia de hoy con todos los canales IPTV...</b>")
        agenda_msgs = get_live_agenda_messages(curr_key)
        for m in agenda_msgs:
            send_msg(chat_id, m)

    elif text.startswith("/top") or text.startswith("/canales") or text.startswith("/deportes"):
        msg_txt = "🌟 <b>CANALES DEPORTIVOS PRINCIPALES (SERVIDOR IPTV DEDICADO 1080P):</b>\n\n"
        seen = set()
        for cmd_name, sid in IPTV_CHANNELS_MAP.items():
            if sid in seen:
                continue
            seen.add(sid)
            msg_txt += f"📺 <b>{cmd_name.upper()}:</b>\n<code>/stream {cmd_name} {curr_key}</code>\n\n"
        msg_txt += "💡 <i>Toca cualquier comando en gris para copiarlo y enviarlo al instante.</i>\n"
        msg_txt += "🔍 <i>¿Buscas otro canal? Usa <code>/buscar &lt;nombre&gt;</code></i>"
        send_msg(chat_id, msg_txt)

    elif text.startswith("/buscar") or text.startswith("/search"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/buscar &lt;nombre_canal&gt;</code>\nEjemplo: <code>/buscar juventus</code> o <code>/buscar espn</code> o <code>/buscar directv</code>")
            return
        query = parts[1].strip()
        send_msg(chat_id, f"🔍 <b>Buscando '{html.escape(query)}' en los 27.000 canales del servidor IPTV...</b>")
        results_msgs = search_iptv_channels(query, curr_key)
        for m in results_msgs:
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
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL_O_ID&gt;</code> o <code>/stream &lt;CANAL&gt; &lt;STREAM_KEY&gt;</code>\nEjemplo: <code>/stream juventus</code> o <code>/stream espn</code>")
            return
        
        raw_url = clean_arg(parts[1])
        stream_key = clean_arg(parts[2]) if len(parts) >= 3 else curr_key
        
        send_msg(chat_id, f"⏳ <b>Iniciando transmisión IPTV de {html.escape(raw_url)}...</b>")
        ok, sid, res = start_single_stream(raw_url, stream_key)
        if ok:
            send_msg(chat_id, (
                f"✅ <b>¡Transmisión IPTV ACTIVA y FLUIDA!</b> 🚀\n\n"
                f"📺 <b>Canal #{sid}:</b> <code>{html.escape(raw_url)}</code>\n"
                f"🔑 <b>Key:</b> <code>{stream_key[:8]}...</code>\n"
                f"📡 <b>Servidor:</b> IPTV Dedicado (0% Cortes / Calidad Máxima 1080p)\n"
                f"⚡ <b>Modo:</b> Direct Passthrough (0% CPU / Ultra Estable)\n\n"
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
    print("🤖 Bot IPTV Dedicado (Auto-Decoder & Juventus Stream) listo...")
    
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
