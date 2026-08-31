import subprocess
import time
import datetime
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

IPTV_USER = "4645904a05"
IPTV_PASS = "5ebc71b005"
IPTV_HOSTS = [
    "http://line.trex4k.top"
]
IPTV_HEADERS = {"User-Agent": "IPTVSmartersPro"}

# Canales principales pre-mapeados (Trex IPTV 53,766 Canales 4K/FHD)
OFFICIAL_CHANNELS = {
    # España
    "1972995": "Movistar LaLiga FHD",
    "2068331": "DAZN LaLiga 1 FHD",
    "2068330": "DAZN LaLiga 2 FHD",
    "2068307": "Movistar Liga de Campeones",
    "2068325": "DAZN F1 España",
    "2137697": "DAZN MotoGP",
    # Argentina & Sudamérica
    "1358601": "ESPN Premium HD",
    "79284": "TyC Sports HD",
    "25595": "TNT Sports HD (Argentina)",
    "25511": "ESPN 1 HD",
    "1358604": "ESPN 2 HD",
    "25512": "ESPN 3 HD",
    "25509": "Fox Sports 2 / ESPN 5 HD",
    "25508": "Fox Sports 3 / ESPN 6 HD",
    "75276": "Fox Sports Premium HD",
    "25510": "Fox Sports 1 HD",
    "75284": "ESPN Deportes USA",
    # Colombia & Sudamérica
    "145416": "Win Sports+ HD (Colombia)",
    "25338": "Win Sports Colombia",
    "656326": "DIRECTV Sports 1 HD (DSports)",
    "656327": "DIRECTV Sports 2 HD (DSports 2)",
    # Venezuela
    "1370773": "Televen",
    "1912051": "IVC Network HD",
    "529670": "Venevisión HD",
    "1838655": "Globovisión",
    # México & USA
    "1930896": "TUDN MX",
    "1143996": "(ViX) TUDN",
    "1052092": "Canal 5 México FHD",
    # Centroamérica
    "558638": "FUTV HD (Costa Rica)",
    "1166517": "Teletica / TD+ (Costa Rica)"
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

    # Reglas específicas por nombre de canal
    if "espn" in clean:
        if "prem" in clean:
            return "4883", "ESPN Premium HD"
        if "extra" in clean:
            return "34051", "ESPN Extra HD"
        if "deportes" in clean or "usa" in clean:
            return "32038", "ESPN Deportes USA"
        if "college" in clean or "plus" in clean:
            if "7" in clean:
                return "32153", "ESPN College Extra 7"
            if "6" in clean:
                return "32152", "ESPN College Extra 6"
            if "5" in clean:
                return "32151", "ESPN College Extra 5"
            if "4" in clean:
                return "32150", "ESPN College Extra 4"
            if "3" in clean:
                return "32149", "ESPN College Extra 3"
            if "2" in clean:
                return "32148", "ESPN College Extra 2"
            return "32147", "ESPN College Extra 1"
        if "7" in clean:
            return "75276", "Fox Sports Premium / ESPN Extra"
        if "6" in clean:
            return "25508", "Fox Sports 3 / ESPN 6 HD"
        if "5" in clean:
            return "25509", "Fox Sports 2 / ESPN 5 HD"
        if "4" in clean:
            return "25511", "ESPN 1 HD"
        if "3" in clean:
            return "25512", "ESPN 3 HD"
        if "2" in clean:
            return "1358604", "ESPN 2 HD"
        return "25511", "ESPN 1 HD"
        
    if "laliga" in clean or "la liga" in clean or "movistar" in clean:
        if "campeones" in clean or "champions" in clean:
            return "2068307", "Movistar Liga de Campeones"
        return "1972995", "Movistar LaLiga FHD"
        
    if "dazn" in clean:
        if "f1" in clean or "formula" in clean:
            return "2068325", "DAZN F1 España"
        if "moto" in clean:
            return "2137697", "DAZN MotoGP"
        if "2" in clean:
            return "2068330", "DAZN LaLiga 2 FHD"
        return "2068331", "DAZN LaLiga 1 FHD"
        
    if "win" in clean:
        if "+" in clean or "plus" in clean:
            return "145416", "Win Sports+ HD (Colombia)"
        return "25338", "Win Sports Colombia"
        
    if "tyc" in clean:
        return "79284", "TyC Sports HD"
    if "tnt" in clean:
        return "25595", "TNT Sports HD (Argentina)"
        
    if "dsport" in clean or "directv" in clean:
        if "2" in clean:
            return "656327", "DIRECTV Sports 2 HD"
        return "656326", "DIRECTV Sports 1 HD"
        
    if "fox" in clean:
        if "prem" in clean:
            return "75276", "Fox Sports Premium HD"
        if "3" in clean:
            return "25508", "Fox Sports 3 HD"
        if "2" in clean:
            return "25509", "Fox Sports 2 HD"
        return "25510", "Fox Sports 1 HD"
        
    if "tudn" in clean:
        return "1930896", "TUDN MX"
    if "vix" in clean:
        return "1143996", "(ViX) TUDN"
    if "canal 5" in clean:
        return "1052092", "Canal 5 México FHD"
        
    if "futv" in clean:
        return "558638", "FUTV HD (Costa Rica)"
    if "teletica" in clean or "td+" in clean:
        return "1166517", "Teletica / TD+ (Costa Rica)"
    if "ivc" in clean:
        return "1912051", "IVC Network HD"
    if "venevision" in clean or "venevisión" in clean:
        return "529670", "Venevisión HD"
    if "televen" in clean:
        return "1370773", "Televen"
    if "globovision" in clean or "globovisión" in clean:
        return "1838655", "Globovisión"

    for k, v in OFFICIAL_CHANNELS.items():
        if clean in v.lower():
            return k, v

    return "25511", "ESPN 1 HD"

def resolve_channel_from_raw(slug, cname):
    txt = f"{slug} {cname}".lower()
    
    # MLB / Béisbol
    if "mlb" in txt or "béisbol" in txt or "beisbol" in txt:
        return "25511", "ESPN 1 HD (MLB Béisbol)"
        
    # US Open / Tenis
    if "us open" in txt or "tenis" in txt:
        return "1358604", "ESPN 2 HD (US Open)"
        
    # Costa Rica
    if "fut" in txt or "futv" in txt:
        return "558638", "FUTV HD (Costa Rica)"
    if "teletica" in txt or "td+" in txt:
        return "1166517", "Teletica / TD+ (Costa Rica)"
        
    # Venezuela
    if "televen" in txt:
        return "1370773", "Televen"
    if "ivc" in txt:
        return "1912051", "IVC Network HD"
    if "venevision" in txt:
        return "529670", "Venevisión HD"
    if "globovision" in txt:
        return "1838655", "Globovisión"
        
    # Movistar LaLiga
    if "movistar" in txt or "la liga tv" in txt or "laliga tv" in txt:
        if "campeones" in txt or "champions" in txt:
            return "2068307", "Movistar Liga de Campeones"
        return "1972995", "Movistar LaLiga FHD"
        
    # DAZN
    if "dazn" in txt:
        if "f1" in txt or "formula" in txt:
            return "2068325", "DAZN F1 España"
        if "moto" in txt:
            return "2137697", "DAZN MotoGP"
        if "la liga 2" in txt or "laliga 2" in txt:
            return "2068330", "DAZN LaLiga 2 FHD"
        return "2068331", "DAZN LaLiga 1 FHD"
        
    # ESPN
    if "espn" in txt:
        if "prem" in txt:
            return "1358601", "ESPN Premium HD"
        if "deportes" in txt:
            return "75284", "ESPN Deportes USA"
        if "extra" in txt or "7" in txt:
            return "75276", "Fox Sports Premium / ESPN Extra"
        if "4" in txt or "sur" in txt:
            return "25511", "ESPN 1 HD"
        if "3" in txt:
            return "25512", "ESPN 3 HD"
        if "2" in txt:
            return "1358604", "ESPN 2 HD"
        return "25511", "ESPN 1 HD"
        
    # DIRECTV / DSports
    if "dsport" in txt or "directv" in txt:
        if "2" in txt:
            return "656327", "DIRECTV Sports 2 HD"
        return "656326", "DIRECTV Sports 1 HD"
        
    # Win Sports
    if "win" in txt:
        if "+" in txt or "plus" in txt or "online" in txt:
            return "145416", "Win Sports+ HD (Colombia)"
        return "25338", "Win Sports Colombia"
        
    # Argentina & Conmebol
    if "tyc" in txt:
        return "79284", "TyC Sports HD"
    if "tnt" in txt:
        return "25595", "TNT Sports HD (Argentina)"
        
    # Mexico
    if "tudn" in txt:
        return "1930896", "TUDN MX"
    if "vix" in txt:
        return "1143996", "(ViX) TUDN"
    if "canal 5" in txt:
        return "1052092", "Canal 5 México FHD"
        
    # Fox Sports
    if "fox" in txt:
        if "prem" in txt:
            return "75276", "Fox Sports Premium HD"
        if "3" in txt:
            return "25508", "Fox Sports 3 HD"
        if "2" in txt:
            return "25509", "Fox Sports 2 HD"
        return "25510", "Fox Sports 1 HD"
        
    return None, None

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
            
    # 2. Asignar los canales exactos según los equipos o liga
    if not matched_channels:
        if "saprissa" in title_lower or "alajuelense" in title_lower or "herediano" in title_lower or "costa rica" in title_lower or "puntarenas" in title_lower or "san carlos" in title_lower:
            matched_channels.append({"id": "558638", "name": "FUTV HD (Costa Rica)"})
        elif "mlb" in title_lower or "béisbol" in title_lower or "beisbol" in title_lower or "cubs" in title_lower or "twins" in title_lower:
            matched_channels.append({"id": "25511", "name": "ESPN 1 HD (MLB Béisbol)"})
        elif "djokovic" in title_lower or "navone" in title_lower or "us open" in title_lower:
            matched_channels.append({"id": "1358604", "name": "ESPN 2 HD (US Open)"})
        elif "laliga" in title_lower or "la liga" in title_lower:
            matched_channels.append({"id": "1972995", "name": "Movistar LaLiga FHD"})
            matched_channels.append({"id": "2068331", "name": "DAZN LaLiga 1 FHD"})
        elif "argentina" in title_lower or "independiente" in title_lower or "boca" in title_lower or "river" in title_lower or "gimnasia" in title_lower or "racing" in title_lower:
            matched_channels.append({"id": "25595", "name": "TNT Sports HD (Argentina)"})
            matched_channels.append({"id": "1358601", "name": "ESPN Premium HD"})
            matched_channels.append({"id": "79284", "name": "TyC Sports HD"})
        elif "colombia" in title_lower or "nacional" in title_lower or "millonarios" in title_lower or "junior" in title_lower:
            matched_channels.append({"id": "145416", "name": "Win Sports+ HD (Colombia)"})
        elif "brasil" in title_lower or "brasileir" in title_lower or "bahia" in title_lower or "internacional" in title_lower:
            matched_channels.append({"id": "145416", "name": "Win Sports+ HD (Transmisión Conmebol)"})
        elif "mexico" in title_lower or "liga mx" in title_lower or "américa" in title_lower or "chivas" in title_lower:
            matched_channels.append({"id": "1930896", "name": "TUDN MX"})
            matched_channels.append({"id": "1143996", "name": "(ViX) TUDN"})

    return matched_channels

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
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_art = now_utc - datetime.timedelta(hours=3) # Hora de referencia agenda
        current_minutes = now_art.hour * 60 + now_art.minute

        r = requests.get("https://tarjetaroja.my/", headers=headers, timeout=6)
        if r.status_code == 200:
            page_html = r.text
            articles = re.findall(r'<article class="tr-event"[^>]*>(.*?)</article>', page_html, re.DOTALL)
            
            live_events = []
            upcoming_events = []
            
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
                
                if not iptv_options:
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
                    "title": title_clean,
                    "status_tag": status_tag,
                    "channels": iptv_options
                }
                
                if is_live:
                    live_events.append(ev_data)
                elif is_upcoming:
                    upcoming_events.append(ev_data)
                    
            if live_events or upcoming_events:
                messages = []
                current_msg = ""
                
                if live_events:
                    current_msg += "🔴 <b>PARTIDOS EN VIVO AHORA MISMO (JUGÁNDOSE EN TV):</b>\n\n"
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
                    up_header = "\n⏰ <b>PRÓXIMOS PARTIDOS DE HOY:</b>\n\n"
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
        "🏆 <b>DIRECTORIO OFICIAL DE CANALES DEPORTIVOS (TREX IPTV 53K CHANNELS)</b>\n\n"
        "🇪🇸 <b>ESPAÑA (LALIGA, DAZN & MOTOR):</b>\n"
        f"• ⚽ <b>Movistar LaLiga FHD:</b> <code>/stream 1972995 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 1 FHD:</b> <code>/stream 2068331 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 2 FHD:</b> <code>/stream 2068330 {curr_key}</code>\n"
        f"• ⚽ <b>Movistar Liga de Campeones:</b> <code>/stream 2068307 {curr_key}</code>\n"
        f"• 🏎️ <b>DAZN F1 España:</b> <code>/stream 2068325 {curr_key}</code>\n"
        f"• 🏍️ <b>DAZN MotoGP:</b> <code>/stream 2137697 {curr_key}</code>\n\n"
        "🇦🇷 <b>ARGENTINA & SUDAMÉRICA (LIGA PROFESIONAL & CONMEBOL):</b>\n"
        f"• ⚽ <b>ESPN Premium HD:</b> <code>/stream 1358601 {curr_key}</code>\n"
        f"• ⚽ <b>TyC Sports HD:</b> <code>/stream 79284 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 1 HD:</b> <code>/stream 1931078 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 2 / ESPN 5 HD:</b> <code>/stream 45570 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 3 / ESPN 6 HD:</b> <code>/stream 1972968 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 1 HD:</b> <code>/stream 45579 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 2 HD:</b> <code>/stream 1358604 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 3 HD:</b> <code>/stream 1358603 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 4 HD:</b> <code>/stream 1870845 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN Extra / ESPN 7 HD:</b> <code>/stream 1358602 {curr_key}</code>\n"
    )
    msg2 = (
        "🇨🇴 <b>COLOMBIA & SUDAMÉRICA (DSPORTS & WIN SPORTS):</b>\n"
        f"• ⚽ <b>Win Sports+ HD (Colombia):</b> <code>/stream 145416 {curr_key}</code>\n"
        f"• ⚽ <b>Win Sports Colombia:</b> <code>/stream 25338 {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports 1 HD (DSports):</b> <code>/stream 656326 {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports 2 HD:</b> <code>/stream 656327 {curr_key}</code>\n\n"
        "🇻🇪 <b>VENEZUELA (CANALES NACIONALES & BEISBOL):</b>\n"
        f"• 📺 <b>Televen:</b> <code>/stream 1370773 {curr_key}</code>\n"
        f"• 📺 <b>IVC Network HD:</b> <code>/stream 1912051 {curr_key}</code>\n"
        f"• 📺 <b>Venevisión HD:</b> <code>/stream 529670 {curr_key}</code>\n"
        f"• 📺 <b>Globovisión:</b> <code>/stream 1838655 {curr_key}</code>\n\n"
        "🌎 <b>CENTROAMÉRICA & MÉXICO:</b>\n"
        f"• 🇨🇷 <b>FUTV HD (Costa Rica):</b> <code>/stream 558638 {curr_key}</code>\n"
        f"• 🇨🇷 <b>Teletica / TD+ (Costa Rica):</b> <code>/stream 1166517 {curr_key}</code>\n"
        f"• 🇲🇽 <b>TUDN MX:</b> <code>/stream 1930896 {curr_key}</code>\n"
        f"• 🇲🇽 <b>(ViX) TUDN:</b> <code>/stream 1143996 {curr_key}</code>\n"
        f"• 🇲🇽 <b>Canal 5 México FHD:</b> <code>/stream 1052092 {curr_key}</code>\n"
        f"• 🇺🇸 <b>ESPN Deportes 60fps USA:</b> <code>/stream 1921358 {curr_key}</code>\n\n"
        "🔍 <i>¿Buscas cualquier otro de los 53,766 canales?</i> Usa <code>/buscar &lt;nombre&gt;</code>"
    )
    return [msg1, msg2]

IPTV_STREAMS_CACHE = {"timestamp": 0, "data": []}

def get_all_iptv_streams():
    global IPTV_STREAMS_CACHE
    now = time.time()
    if now - IPTV_STREAMS_CACHE["timestamp"] < 3600 and IPTV_STREAMS_CACHE["data"]:
        return IPTV_STREAMS_CACHE["data"]
    try:
        url = f"{IPTV_HOSTS[0]}/player_api.php?username={IPTV_USER}&password={IPTV_PASS}&action=get_live_streams"
        r = requests.get(url, headers=IPTV_HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                IPTV_STREAMS_CACHE["data"] = [(str(s.get("stream_id")), s.get("name", "")) for s in data]
                IPTV_STREAMS_CACHE["timestamp"] = now
                return IPTV_STREAMS_CACHE["data"]
    except Exception as e:
        print("Error fetching all iptv streams:", e)
    return list(OFFICIAL_CHANNELS.items())

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

    elif text.startswith("/espn"):
        espn_msg = (
            "📺 <b>DIRECTORIO COMPLETO DE SEÑALES ESPN (100% ONLINE HD):</b>\n\n"
            "🇦🇷 <b>ESPN SUDAMÉRICA / SUR (ARGENTINA, URUGUAY, CHILE):</b>\n"
            f"• ⚽ <b>ESPN 1 HD:</b> <code>/stream 34050 {curr_key}</code>\n"
            f"• ⚽ <b>ESPN 2 HD:</b> <code>/stream 3412 {curr_key}</code>\n"
            f"• ⚽ <b>ESPN 3 HD:</b> <code>/stream 3411 {curr_key}</code>\n"
            f"• ⚽ <b>ESPN 4 SUR HD:</b> <code>/stream 1453275 {curr_key}</code>\n"
            f"• ⚽ <b>ESPN 5 (Fox Sports 2):</b> <code>/stream 4881 {curr_key}</code>\n"
            f"• ⚽ <b>ESPN 6 (Fox Sports 3):</b> <code>/stream 4882 {curr_key}</code>\n"
            f"• ⚽ <b>ESPN 7 / ESPN Extra HD:</b> <code>/stream 34051 {curr_key}</code>\n"
            f"• ⚽ <b>ESPN Premium HD:</b> <code>/stream 4883 {curr_key}</code>\n"
            f"• ⚽ <b>ESPN Deportes USA:</b> <code>/stream 32038 {curr_key}</code>\n\n"
            "🇺🇸 <b>ESPN COLLEGE EXTRA (EVENTOS USA EN VIVO):</b>\n"
            f"• 🏀 <b>ESPN College 1:</b> <code>/stream 32147 {curr_key}</code>\n"
            f"• 🏀 <b>ESPN College 2:</b> <code>/stream 32148 {curr_key}</code>\n"
            f"• 🏀 <b>ESPN College 3:</b> <code>/stream 32149 {curr_key}</code>\n"
            f"• 🏀 <b>ESPN College 4:</b> <code>/stream 32150 {curr_key}</code>\n"
            f"• 🏀 <b>ESPN College 5:</b> <code>/stream 32151 {curr_key}</code>\n"
            f"• 🏀 <b>ESPN College 6:</b> <code>/stream 32152 {curr_key}</code>\n"
            f"• 🏀 <b>ESPN College 7:</b> <code>/stream 32153 {curr_key}</code>"
        )
        send_msg(chat_id, espn_msg)

    elif text.startswith("/partidos") or text.startswith("/agenda") or text.startswith("/hoy"):
        send_msg(chat_id, "⏳ <b>Cargando todos los partidos de hoy con canales listos en 1-click...</b>")
        msgs = get_live_matches_agenda(curr_key)
        for m in msgs:
            send_msg(chat_id, m)

    elif text.startswith("/buscar"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/buscar &lt;nombre_de_canal&gt;</code>\nEjemplo: <code>/buscar espn</code>, <code>/buscar ufc</code> o <code>/buscar fox</code>")
            return
        
        query = parts[1].strip().lower()
        words = query.split()
        all_channels = get_all_iptv_streams()
        
        matches = []
        seen = set()
        for cid, cname in all_channels:
            c_low = cname.lower()
            if all(w in c_low for w in words):
                if cid not in seen:
                    seen.add(cid)
                    matches.append((cid, cname))
                    if len(matches) >= 15:
                        break
        
        if not matches:
            send_msg(chat_id, f"❌ No se encontró ningún canal con: <b>{html.escape(query)}</b>")
            return

        res = f"🔍 <b>CANALES ENCONTRADOS PARA '{html.escape(query)}' ({len(matches)}):</b>\n\n"
        for cid, cname in matches:
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
            send_msg(chat_id, (
                "⚠️ <b>Uso del comando /stream:</b>\n"
                "Puedes escribir directamente el nombre del canal o su ID:\n\n"
                "• <code>/stream espn</code> $\\rightarrow$ ESPN 1 HD\n"
                "• <code>/stream espn 2</code> $\\rightarrow$ ESPN 2 HD\n"
                "• <code>/stream espn 4</code> $\\rightarrow$ ESPN 4 SUR HD\n"
                "• <code>/stream laliga</code> $\\rightarrow$ Movistar LaLiga FHD\n"
                "• <code>/stream dazn</code> $\\rightarrow$ DAZN LaLiga 1 FHD\n"
                "• <code>/stream dsports</code> $\\rightarrow$ DIRECTV Sports HD\n"
                "• <code>/stream win</code> $\\rightarrow$ Win Sports+ HD\n"
                "• <code>/stream tyc</code> $\\rightarrow$ TyC Sports HD\n"
                "• <code>/stream televen</code> $\\rightarrow$ Televen\n"
                "• <code>/stream venevision</code> $\\rightarrow$ Venevisión HD"
            ))
            return
        
        # Detectar si el último argumento es una stream key
        if len(parts) >= 3 and (":" in parts[-1] and len(parts[-1]) > 15):
            stream_key = clean_arg(parts[-1])
            raw_ch = " ".join(parts[1:-1]).strip()
        else:
            stream_key = curr_key
            raw_ch = " ".join(parts[1:]).strip()
        
        send_msg(chat_id, f"⏳ <b>Conectando al canal '{html.escape(raw_ch)}' en servidor Gigabit dedicado...</b>")
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
            {"command": "espn", "description": "📺 Todos los canales ESPN (1,2,3,4 Sur, Extra, etc.)"},
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
