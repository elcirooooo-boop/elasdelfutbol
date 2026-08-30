import subprocess
import time
import requests
import json
import os
import sys
import re
import html
import threading

# ==============================================================================
# CONFIGURACIÓN GENERAL DEL BOT Y SERVIDOR IPTV
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CONFIG_FILE = "config_stream.json"

IPTV_USER = "BE15ERDV"
IPTV_PASS = "PXELERB9"
IPTV_HOSTS = [
    "http://evestv.leptis.live",
    "http://evestv.ptjfj.com",
    "http://tv.rmhat.com"
]
IPTV_HEADERS = {"User-Agent": "IPTVSmartersPro"}

# Canales principales pre-mapeados
OFFICIAL_CHANNELS = {
    # España
    "30905": "Movistar LaLiga FHD",
    "224832": "DAZN LaLiga 1 FHD",
    "224831": "DAZN LaLiga 2 FHD",
    "6560": "LaLiga Hypermotion HD (2da División)",
    "91781": "DAZN 1 España",
    "91782": "DAZN 2 España",
    "30907": "DAZN F1 España",
    "1349240": "DAZN MotoGP",
    # Argentina / Sudamérica
    "4883": "ESPN Premium HD (Argentina)",
    "30365": "TyC Sports HD",
    "4880": "Fox Sports 1 Argentina",
    "4881": "Fox Sports 2 Argentina",
    "4882": "Fox Sports 3 Argentina",
    "30326": "ESPN 1 HD",
    "30327": "ESPN 2 HD",
    "3411": "ESPN 3 HD",
    "1453275": "ESPN 4 HD",
    "34051": "ESPN Extra HD",
    # Colombia
    "33945": "Win Sports+ HD (Colombia)",
    "33944": "Win Sports Colombia",
    "33933": "DIRECTV Sports 1 HD (DSports)",
    "33932": "DIRECTV Sports 2 HD (DSports 2)",
    "33931": "DIRECTV Sports Plus HD (DSports+)",
    # México
    "1288338": "TUDN MX",
    "985726": "(ViX) TUDN",
    "3987": "Canal 5 México FHD",
    "34041": "Fox Sports 1 México",
    # Inglaterra / Internacional
    "29016": "Sky Sports Premier League",
    "1256711": "Sky Sports Main Events",
    "8805": "DAZN Juventus",
    "8804": "DAZN Inter",
    "8803": "DAZN AC Milan",
    "8802": "DAZN Napoli"
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

def get_free_iptv_account():
    accounts = CONFIG.get("iptv_accounts", [{"user": "BE15ERDV", "pass": "PXELERB9"}])
    used_users = set()
    for sid, info in active_streams.items():
        if "account_user" in info:
            used_users.add(info["account_user"])
            
    for acc in accounts:
        if acc["user"] not in used_users:
            return acc
    return None

def get_iptv_stream_url(stream_id, account=None):
    clean_id = str(stream_id).strip()
    headers_str = "User-Agent: IPTVSmartersPro\r\n"
    acc = account or CONFIG.get("iptv_accounts", [{"user": "BE15ERDV", "pass": "PXELERB9"}])[0]
    user = acc["user"]
    passwd = acc["pass"]
    for host in IPTV_HOSTS:
        url = f"{host}/live/{user}/{passwd}/{clean_id}.ts"
        return url, headers_str, True
    return None, None, False

def resolve_channel_input(raw_input):
    clean = str(raw_input).strip().lower()
    
    if clean.isdigit() and clean in OFFICIAL_CHANNELS:
        return clean, OFFICIAL_CHANNELS[clean]
    if clean.isdigit():
        return clean, f"Canal ID #{clean}"

    aliases = {
        "laliga": ("30905", "Movistar LaLiga FHD"),
        "movistar": ("30905", "Movistar LaLiga FHD"),
        "dazn": ("224832", "DAZN LaLiga 1 FHD"),
        "dazn1": ("224832", "DAZN LaLiga 1 FHD"),
        "dazn2": ("224831", "DAZN LaLiga 2 FHD"),
        "daznf1": ("30907", "DAZN F1 España"),
        "f1": ("30907", "DAZN F1 España"),
        "motogp": ("1349240", "DAZN MotoGP"),
        "win": ("33945", "Win Sports+ HD (Colombia)"),
        "win+": ("33945", "Win Sports+ HD (Colombia)"),
        "winsports": ("33945", "Win Sports+ HD (Colombia)"),
        "espn": ("4883", "ESPN Premium HD"),
        "espnpremium": ("4883", "ESPN Premium HD"),
        "espn1": ("30326", "ESPN 1 HD"),
        "espn2": ("30327", "ESPN 2 HD"),
        "espn3": ("3411", "ESPN 3 HD"),
        "espn4": ("1453275", "ESPN 4 HD"),
        "espnextra": ("34051", "ESPN Extra HD"),
        "tyc": ("30365", "TyC Sports HD"),
        "dsports": ("33933", "DIRECTV Sports 1 HD (DSports)"),
        "directv": ("33933", "DIRECTV Sports 1 HD (DSports)"),
        "tudn": ("1288338", "TUDN MX"),
        "fox": ("4880", "Fox Sports 1 Argentina"),
        "premier": ("29016", "Sky Sports Premier League")
    }
    
    if clean in aliases:
        return aliases[clean]
        
    for k, v in OFFICIAL_CHANNELS.items():
        if clean in v.lower():
            return k, v

    return "30905", "Movistar LaLiga FHD"

def smart_match_channel_resolver(title, channels_raw):
    title_lower = title.lower()
    matched_channels = []
    
    # 1. Si los canales vienen especificados en el scraper
    for slug, cname in channels_raw:
        c_low = f"{slug} {cname}".lower()
        if "movistar" in c_low or "la liga" in c_low or "laliga" in c_low:
            if "hyper" in c_low or "2" in c_low:
                matched_channels.append(("6560", "LaLiga Hypermotion HD"))
            else:
                matched_channels.append(("30905", "Movistar LaLiga FHD"))
        elif "dazn la liga" in c_low or "dazn laliga" in c_low:
            matched_channels.append(("224832", "DAZN LaLiga 1 FHD"))
        elif "dazn f1" in c_low or "formula" in c_low:
            matched_channels.append(("30907", "DAZN F1 España"))
        elif "moto" in c_low:
            matched_channels.append(("1349240", "DAZN MotoGP"))
        elif "win" in c_low:
            matched_channels.append(("33945", "Win Sports+ HD"))
        elif "espn premium" in c_low:
            matched_channels.append(("4883", "ESPN Premium HD"))
        elif "tyc" in c_low or "tnt" in c_low:
            matched_channels.append(("30365", "TyC Sports HD"))
        elif "dsports" in c_low or "directv" in c_low:
            matched_channels.append(("33933", "DSports 1 HD"))
        elif "tudn" in c_low:
            matched_channels.append(("1288338", "TUDN MX"))
        elif "sky" in c_low or "premier" in c_low:
            matched_channels.append(("29016", "Sky Sports Premier League"))

    # 2. Si no hubo coincidencia o el scraper no tenía canales específicos, asignar por LIGA / EQUIPOS:
    if not matched_channels:
        if "serie a" in title_lower or "italia" in title_lower:
            if "inter" in title_lower:
                matched_channels.append(("8804", "DAZN Inter"))
            elif "milan" in title_lower:
                matched_channels.append(("8803", "DAZN AC Milan"))
            elif "juventus" in title_lower or "juve" in title_lower:
                matched_channels.append(("8805", "DAZN Juventus"))
            elif "napoli" in title_lower:
                matched_channels.append(("8802", "DAZN Napoli"))
            matched_channels.append(("30327", "ESPN 2 HD (Serie A)"))
            matched_channels.append(("3411", "ESPN 3 HD"))
            
        elif "premier" in title_lower or "inglaterra" in title_lower:
            matched_channels.append(("29016", "Sky Sports Premier League"))
            matched_channels.append(("30326", "ESPN 1 HD (Premier)"))
            matched_channels.append(("1256711", "Sky Sports Main Events"))
            
        elif "ligue 1" in title_lower or "francia" in title_lower:
            matched_channels.append(("30327", "ESPN 2 HD (Ligue 1)"))
            matched_channels.append(("3411", "ESPN 3 HD"))
            
        elif "bundesliga" in title_lower or "alemania" in title_lower:
            matched_channels.append(("30327", "ESPN 2 HD (Bundesliga)"))
            matched_channels.append(("1256711", "Sky Sports Main Events"))
            
        elif "laliga" in title_lower or "la liga" in title_lower or "espana" in title_lower or "españa" in title_lower:
            matched_channels.append(("30905", "Movistar LaLiga FHD"))
            matched_channels.append(("224832", "DAZN LaLiga 1 FHD"))
            
        elif "colombia" in title_lower:
            matched_channels.append(("33945", "Win Sports+ HD (Colombia)"))
            matched_channels.append(("33944", "Win Sports Colombia"))
            
        elif "argentina" in title_lower or "copa de la liga" in title_lower or "profesional" in title_lower:
            matched_channels.append(("4883", "ESPN Premium HD (Argentina)"))
            matched_channels.append(("30365", "TyC Sports HD"))
            matched_channels.append(("4880", "Fox Sports 1 Argentina"))
            
        elif "mexico" in title_lower or "liga mx" in title_lower:
            matched_channels.append(("1288338", "TUDN MX"))
            matched_channels.append(("3987", "Canal 5 México FHD"))
            matched_channels.append(("34041", "Fox Sports 1 México"))
            
        elif "uruguay" in title_lower or "paraguay" in title_lower or "chile" in title_lower or "peru" in title_lower or "sudameric" in title_lower:
            matched_channels.append(("1453275", "ESPN 4 HD"))
            matched_channels.append(("33933", "DIRECTV Sports (DSports)"))
            matched_channels.append(("3411", "ESPN 3 HD"))
            
        elif "f1" in title_lower or "formula" in title_lower:
            matched_channels.append(("30907", "DAZN F1 España"))
            
        elif "moto" in title_lower:
            matched_channels.append(("1349240", "DAZN MotoGP"))
            
        else:
            matched_channels.append(("30326", "ESPN 1 HD"))
            matched_channels.append(("30327", "ESPN 2 HD"))
            matched_channels.append(("30905", "Movistar LaLiga FHD"))

    # Eliminar duplicados manteniendo orden
    seen = set()
    unique = []
    for cid, cname in matched_channels:
        if cid not in seen:
            seen.add(cid)
            unique.append({"id": cid, "name": cname})
    return unique

def resolve_to_iptv(slug, cname):
    txt = f"{slug} {cname}".lower()
    if "hyper" in txt or "2" in txt:
        return "6560", "LaLiga Hypermotion"
    if "movistar" in txt:
        return "30905", "Movistar LaLiga FHD"
    if "dazn" in txt:
        return "224832", "DAZN LaLiga 1 FHD"
    if "win" in txt:
        return "33945", "Win Sports+ HD"
    if "tyc" in txt or "tnt" in txt:
        return "30365", "TyC Sports HD"
    return "30326", "ESPN 1 HD"

# ==============================================================================
# MOTOR DE TRANSMISIÓN EN DIRECTO (0% LAG / ULTRA BAJA LATENCIA)
# ==============================================================================
def clean_arg(val):
    if not val:
        return ""
    return val.strip().strip("<>").strip('"').strip("'").strip()

def launch_ffmpeg_process(source_url, headers, destination, stream_id):
    cmd = [
        "ffmpeg",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-rw_timeout", "10000000",
        "-flags", "low_delay",
        "-fflags", "+nobuffer+genpts+igndts+discardcorrupt",
        "-analyzeduration", "1000000",
        "-probesize", "1000000"
    ]

    if headers:
        cmd.extend(["-headers", headers])

    cmd.extend([
        "-i", source_url,
        "-vf", "bwdif=mode=send_field:parity=auto:deint=all,fps=50,scale=1280:720",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-b:v", "3000k",
        "-maxrate", "3500k",
        "-bufsize", "6000k",
        "-g", "50",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-avoid_negative_ts", "make_zero",
        "-flush_packets", "1",
        "-max_interleave_delta", "50000",
        "-max_muxing_queue_size", "8192",
        "-flvflags", "no_duration_filesize",
        "-f", "flv",
        destination
    ])

    log_file = f"/tmp/stream_{stream_id}.log" if os.name != 'nt' else f"stream_{stream_id}.log"
    out_f = open(log_file, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(cmd, stdout=out_f, stderr=out_f)
    return proc, out_f, log_file

def get_next_stream_id():
    for i in range(1, 100):
        sid = str(i)
        if sid not in active_streams:
            return sid
    return str(len(active_streams) + 1)

def start_single_stream(raw_channel, stream_key):
    raw_channel = clean_arg(raw_channel)
    stream_key = clean_arg(stream_key)
    destination = RTMP_SERVER + stream_key

    with stream_lock:
        chosen_acc = get_free_iptv_account()
        # Si la cuenta IPTV ya está ocupada por otra transmisión, detenerla para liberar la conexión
        if not chosen_acc and active_streams:
            for sid in list(active_streams.keys()):
                stop_single_stream(sid)
            time.sleep(1.0)
            chosen_acc = get_free_iptv_account()

        # Si ya hay una transmisión activa usando la MISMA stream_key, la reemplazamos
        for sid, info in list(active_streams.items()):
            if info.get("key") == stream_key:
                stop_single_stream(sid)

        stream_id = get_next_stream_id()

        if raw_channel.startswith("http://") or raw_channel.startswith("https://"):
            source_url = raw_channel
            headers = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n"
            channel_display = "Enlace Directo Stream"
            channel_id = "direct"
            is_ok = True
            chosen_acc = None
        else:
            if not chosen_acc:
                chosen_acc = CONFIG.get("iptv_accounts", [{"user": "BE15ERDV", "pass": "PXELERB9"}])[0]
            channel_id, channel_display = resolve_channel_input(raw_channel)
            source_url, headers, is_ok = get_iptv_stream_url(channel_id, chosen_acc)

        if not is_ok or not source_url:
            return False, stream_id, f"No se pudo conectar al canal '{raw_channel}'."

        proc, out_f, log_file = launch_ffmpeg_process(source_url, headers, destination, stream_id)
        
        time.sleep(3.0)
        if proc.poll() is not None:
            out_f.close()
            err_snippet = "Telegram rechazó la Stream Key. Asegúrate de tener abierta la ventana del directo en Telegram y copiar la Stream Key actual."
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    log_text = f.read()
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
            "raw_name": channel_display,
            "channel_id": channel_id,
            "account_user": chosen_acc.get("user") if chosen_acc else "direct",
            "url": source_url,
            "headers": headers,
            "destination": destination,
            "key": stream_key,
            "start_time": now,
            "auto_restart": True,
            "restart_count": 0
        }
        return True, stream_id, channel_display

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
# AGENDA DINÁMICA DE PARTIDOS 100% AUTOMATIZADA
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

MATCHES_AGENDA_CACHE = {"timestamp": 0, "messages": []}

def get_live_matches_agenda(curr_key):
    global MATCHES_AGENDA_CACHE
    now = time.time()
    
    if now - MATCHES_AGENDA_CACHE.get("timestamp", 0) < 180 and MATCHES_AGENDA_CACHE.get("messages"):
        cached_msgs = []
        for m in MATCHES_AGENDA_CACHE["messages"]:
            cached_msgs.append(re.sub(r'(/stream \w+) [\w\-_:]+', rf'\1 {curr_key}', m))
        return cached_msgs

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get("https://tarjetaroja.my/", headers=headers, timeout=6)
        if r.status_code == 200:
            page_html = r.text
            articles = re.findall(r'<article class="tr-event"[^>]*>(.*?)</article>', page_html, re.DOTALL)
            parsed_events = []
            for art in articles:
                time_m = re.search(r'<span class="tr-event-time[^"]*">([^<]+)</span>', art)
                time_str = time_m.group(1).strip() if time_m else ""
                
                title_m = re.search(r'<span class="tr-event-title">(.*?)</span>\s*<span class="tr-event-chevron"', art, re.DOTALL)
                if title_m:
                    title_raw = title_m.group(1)
                    title_clean = re.sub(r'<[^>]+>', ' ', title_raw).strip()
                    title_clean = re.sub(r'\s+', ' ', title_clean)
                else:
                    ds_m = re.search(r'data-search="([^"]+)"', art)
                    title_clean = ds_m.group(1) if ds_m else "Evento Deportivo"
                    
                channels_raw = re.findall(r'<a class="tr-event-channel"[^>]*href="[^"]*stream/([^"]+)"[^>]*>([^<]+)</a>', art)
                iptv_options = smart_match_channel_resolver(title_clean, channels_raw)
                        
                if iptv_options:
                    parsed_events.append({
                        "time": time_str,
                        "title": title_clean,
                        "channels": iptv_options
                    })
                    
            if parsed_events:
                messages = []
                current_msg = "⚽ <b>AGENDA DE PARTIDOS DE HOY (CON CANAL DIRECTO 1-CLICK)</b>\n\n"
                for ev in parsed_events:
                    block = f"🏆 <b>[{html.escape(ev['time'])}] {html.escape(ev['title'])}</b>\n"
                    for ch in ev["channels"][:3]:
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
        "🏆 <b>DIRECTORIO OFICIAL DE CANALES DEPORTIVOS (GIGABIT DIRECTO)</b>\n\n"
        "🇪🇸 <b>ESPAÑA (LALIGA, DAZN & MOTOR):</b>\n"
        f"• ⚽ <b>Movistar LaLiga FHD:</b> <code>/stream 30905 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 1 FHD:</b> <code>/stream 224832 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 2 FHD:</b> <code>/stream 224831 {curr_key}</code>\n"
        f"• ⚽ <b>LaLiga Hypermotion (2da):</b> <code>/stream 6560 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN 1 España:</b> <code>/stream 91781 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN 2 España:</b> <code>/stream 91782 {curr_key}</code>\n"
        f"• 🏎️ <b>DAZN F1 España:</b> <code>/stream 30907 {curr_key}</code>\n"
        f"• 🏍️ <b>DAZN MotoGP:</b> <code>/stream 1349240 {curr_key}</code>\n\n"
        "🇦🇷 <b>ARGENTINA & CONMEBOL (LIGA PROFESIONAL & LIBERTADORES):</b>\n"
        f"• ⚽ <b>ESPN Premium HD:</b> <code>/stream 4883 {curr_key}</code>\n"
        f"• ⚽ <b>TyC Sports HD:</b> <code>/stream 30365 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 1 Argentina:</b> <code>/stream 4880 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 2 Argentina:</b> <code>/stream 4881 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 3 Argentina:</b> <code>/stream 4882 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 1 HD:</b> <code>/stream 30326 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 2 HD:</b> <code>/stream 30327 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 3 HD:</b> <code>/stream 3411 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 4 HD:</b> <code>/stream 1453275 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN Extra HD:</b> <code>/stream 34051 {curr_key}</code>\n"
    )
    msg2 = (
        "🇨🇴 <b>COLOMBIA & SUDAMÉRICA (DSPORTS & WIN SPORTS):</b>\n"
        f"• ⚽ <b>Win Sports+ HD (Colombia):</b> <code>/stream 33945 {curr_key}</code>\n"
        f"• ⚽ <b>Win Sports Colombia:</b> <code>/stream 33944 {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports 1 HD (DSports):</b> <code>/stream 33933 {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports 2 HD:</b> <code>/stream 33932 {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports Plus HD:</b> <code>/stream 33931 {curr_key}</code>\n\n"
        "🇲🇽 <b>MÉXICO (LIGA MX & TUDN):</b>\n"
        f"• ⚽ <b>TUDN MX:</b> <code>/stream 1288338 {curr_key}</code>\n"
        f"• ⚽ <b>(ViX) TUDN:</b> <code>/stream 985726 {curr_key}</code>\n"
        f"• ⚽ <b>Canal 5 México FHD:</b> <code>/stream 3987 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 1 México:</b> <code>/stream 34041 {curr_key}</code>\n\n"
        "🏴󠁧󠁢󠁥󠁮󠁧󠁿 <b>PREMIER LEAGUE (INGLATERRA):</b>\n"
        f"• ⚽ <b>Sky Sports Premier League:</b> <code>/stream 29016 {curr_key}</code>\n"
        f"• ⚽ <b>Sky Sports Main Events:</b> <code>/stream 1256711 {curr_key}</code>\n\n"
        "🇮🇹 <b>SERIE A (ITALIA):</b>\n"
        f"• ⚽ <b>DAZN Juventus:</b> <code>/stream 8805 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN Inter:</b> <code>/stream 8804 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN AC Milan:</b> <code>/stream 8803 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN Napoli:</b> <code>/stream 8802 {curr_key}</code>\n\n"
        "🔍 <i>¿Buscas otro canal específico?</i> Usa <code>/buscar &lt;nombre&gt;</code>"
    )
    return [msg1, msg2]

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
            "⚽ <b>BOT DE TRANSMISIÓN DE FÚTBOL Y DEPORTES 100% AUTOMÁTICO</b>\n\n"
            "📋 <b>COMANDOS DISPONIBLES:</b>\n"
            "• <code>/canales</code> o <code>/deportes</code> $\\rightarrow$ Ver todos los canales deportivos oficiales\n"
            "• <code>/partidos</code> o <code>/agenda</code> $\\rightarrow$ Ver los partidos de hoy con canales listos\n"
            "• <code>/stream &lt;CANAL_O_ID&gt; [STREAM_KEY]</code> $\\rightarrow$ Iniciar transmisión directa\n"
            "• <code>/buscar &lt;nombre&gt;</code> $\\rightarrow$ Buscar canal por nombre\n"
            "• <code>/stop</code> $\\rightarrow$ Detener transmisión\n"
            "• <code>/status</code> $\\rightarrow$ Ver estado de transmisión activa\n"
            "• <code>/cuentas</code> $\\rightarrow$ Ver cuentas IPTV registradas\n"
            f"• <code>/key &lt;NUEVA_KEY&gt;</code> $\\rightarrow$ Cambiar clave por defecto"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/canales") or text.startswith("/deportes") or text.startswith("/menu"):
        msgs = get_sports_menu_messages(curr_key)
        for m in msgs:
            send_msg(chat_id, m)

    elif text.startswith("/partidos") or text.startswith("/agenda") or text.startswith("/hoy"):
        send_msg(chat_id, "⏳ <b>Cargando todos los partidos de hoy con canales listos en 1-click...</b>")
        msgs = get_live_matches_agenda(curr_key)
        for m in msgs:
            send_msg(chat_id, m)

    elif text.startswith("/buscar"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/buscar &lt;nombre_de_canal&gt;</code>\nEjemplo: <code>/buscar laliga</code> o <code>/buscar espn</code>")
            return
        
        query = parts[1].strip().lower()
        matches = [(k, v) for k, v in OFFICIAL_CHANNELS.items() if query in v.lower()]
        
        if not matches:
            send_msg(chat_id, f"❌ No se encontró ningún canal con: <b>{html.escape(query)}</b>")
            return

        res = f"🔍 <b>CANALES ENCONTRADOS PARA '{html.escape(query)}':</b>\n\n"
        for cid, cname in matches[:10]:
            res += f"• 📺 <b>{html.escape(cname)}:</b>\n  <code>/stream {cid} {curr_key}</code>\n\n"
        send_msg(chat_id, res)

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
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL_O_ID&gt; [STREAM_KEY]</code>\nEjemplo: <code>/stream 30905</code> o <code>/stream laliga</code>")
            return
        
        raw_ch = clean_arg(parts[1])
        stream_key = clean_arg(parts[2]) if len(parts) >= 3 else curr_key
        
        send_msg(chat_id, f"⏳ <b>Conectando al canal {html.escape(raw_ch)} en servidor Gigabit dedicado...</b>")
        ok, sid, res = start_single_stream(raw_ch, stream_key)
        if ok:
            send_msg(chat_id, (
                f"✅ <b>¡Transmisión ACTIVA y 100% DIRECTA!</b> 🚀\n\n"
                f"📺 <b>Canal:</b> <code>{html.escape(res)}</code>\n"
                f"🔑 <b>Key:</b> <code>{stream_key[:8]}...</code>\n"
                f"⚡ <b>Formato:</b> 50 FPS Suave Progresivo / Cero Lag\n"
                f"🔊 <b>Audio:</b> AAC Estéreo 100% Sincronizado\n\n"
                f"🛑 <b>Detener:</b> <code>/stop</code>"
            ))
        else:
            send_msg(chat_id, f"❌ <b>Error al iniciar:</b>\n{res}")

    elif text.startswith("/stopall") or text == "/stop all" or text.startswith("/stop"):
        count = stop_all_streams()
        if count > 0:
            send_msg(chat_id, f"🛑 <b>Transmisión detenida correctamente.</b>")
        else:
            send_msg(chat_id, "ℹ️ No había ninguna transmisión activa.")

    elif text.startswith("/cuentas") or text.startswith("/accounts"):
        accs = CONFIG.get("iptv_accounts", [{"user": "BE15ERDV", "pass": "PXELERB9"}])
        res = "📋 <b>CUENTAS IPTV REGISTRADAS:</b>\n\n"
        for i, a in enumerate(accs, 1):
            res += f"• <b>Cuenta #{i}:</b> <code>{a['user']}</code>\n"
        res += f"\n💡 <i>Puedes transmitir tantos canales simultáneos como cuentas IPTV tengas registradas.</i>\nPara agregar otra cuenta: <code>/addcuenta &lt;USER&gt; &lt;PASS&gt;</code>"
        send_msg(chat_id, res)

    elif text.startswith("/addcuenta"):
        parts = text.split()
        if len(parts) < 3:
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/addcuenta &lt;USUARIO&gt; &lt;PASSWORD&gt;</code>\nEjemplo: <code>/addcuenta MI_USER MI_PASS</code>")
            return
        u = clean_arg(parts[1])
        p = clean_arg(parts[2])
        accs = CONFIG.get("iptv_accounts", [{"user": "BE15ERDV", "pass": "PXELERB9"}])
        # Verificar si ya existe
        if any(a["user"] == u for a in accs):
            send_msg(chat_id, f"ℹ️ La cuenta <code>{u}</code> ya está registrada.")
            return
        accs.append({"user": u, "pass": p})
        CONFIG["iptv_accounts"] = accs
        save_config(CONFIG)
        send_msg(chat_id, f"✅ <b>¡Nueva cuenta IPTV agregada con éxito!</b>\n👤 Usuario: <code>{u}</code>\nTotal cuentas disponibles: <b>{len(accs)}</b>")

    elif text.startswith("/status"):
        if not active_streams:
            send_msg(chat_id, "🔴 <b>No hay ninguna transmisión activa actualmente.</b>")
            return

        status_text = f"🟢 <b>TRANSMISIONES EN DIRECTO ACTIVAS ({len(active_streams)}):</b>\n\n"
        for sid, info in sorted(active_streams.items()):
            elapsed = int(time.time() - info["start_time"])
            mins = elapsed // 60
            secs = elapsed % 60
            status_text += (
                f"📺 <b>Canal #{sid}:</b> <code>{html.escape(info['raw_name'])}</code>\n"
                f"• ⏱️ Tiempo: <code>{mins}m {secs}s</code>\n"
                f"• 📡 Key: <code>{info['key'][:8]}...</code>\n"
                f"• 🛑 <b>Detener esta:</b> <code>/stop {sid}</code>\n\n"
            )
        status_text += "🛑 <b>Detener todas:</b> <code>/stopall</code>"
        send_msg(chat_id, status_text)

def set_telegram_commands():
    try:
        commands = [
            {"command": "canales", "description": "🏆 Directorio de todos los canales deportivos"},
            {"command": "partidos", "description": "⚽ Partidos de hoy con canal listo"},
            {"command": "stream", "description": "▶️ Iniciar transmisión (/stream CANAL KEY)"},
            {"command": "buscar", "description": "🔍 Buscar canal deportivo (/buscar nombre)"},
            {"command": "status", "description": "🟢 Ver estado de transmisiones en vivo"},
            {"command": "stop", "description": "🛑 Detener transmisión"},
            {"command": "stopall", "description": "🛑 Detener todas las transmisiones"},
            {"command": "cuentas", "description": "👥 Ver cuentas IPTV registradas"}
        ]
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/setMyCommands", json={"commands": commands}, timeout=10)
    except Exception:
        pass

def main():
    print("🤖 Bot Deportivo 100% Automatizado listo (Multi-Thread)...")
    set_telegram_commands()
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            resp = requests.get(url, timeout=35).json()
            if resp.get("ok"):
                for update in resp.get("result", []):
                    offset = update["update_id"] + 1
                    if "message" in update:
                        # Procesar en hilo independiente para no bloquear el bot
                        threading.Thread(target=handle_message, args=(update["message"],), daemon=True).start()
        except Exception as e:
            time.sleep(1)

if __name__ == "__main__":
    main()
