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
    "30328": "ESPN 3 HD",
    "1453275": "ESPN 4 HD",
    "30329": "ESPN Extra HD",
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
        "espn3": ("30328", "ESPN 3 HD"),
        "espn4": ("1453275", "ESPN 4 HD"),
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

def resolve_to_iptv(slug, cname):
    txt = f"{slug} {cname}".lower()
    
    if "movistar" in txt or "la liga" in txt or "laliga" in txt:
        if "hyper" in txt or "2" in txt or "segunda" in txt:
            return "6560", "LaLiga Hypermotion"
        return "30905", "Movistar LaLiga FHD"
    if "dazn" in txt:
        if "f1" in txt or "formula" in txt:
            return "30907", "DAZN F1"
        if "moto" in txt:
            return "1349240", "DAZN MotoGP"
        return "224832", "DAZN LaLiga 1 FHD"
    if "win" in txt:
        return "33945", "Win Sports+ HD"
    if "espn" in txt:
        if "prem" in txt:
            return "4883", "ESPN Premium HD"
        if "4" in txt:
            return "1453275", "ESPN 4 HD"
        if "2" in txt:
            return "30327", "ESPN 2 HD"
        if "3" in txt:
            return "30328", "ESPN 3 HD"
        return "30326", "ESPN 1 HD"
    if "tyc" in txt or "tnt" in txt:
        return "30365", "TyC/TNT Sports HD"
    if "dsports" in txt or "directv" in txt:
        return "33933", "DSports 1 HD"
    if "tudn" in txt or "vix" in txt:
        return "1288338", "TUDN MX"
    if "fox" in txt:
        return "4880", "Fox Sports 1"
    if "sky" in txt or "premier" in txt:
        return "29016", "Sky Sports Premier"
        
    return "30905", "Movistar LaLiga FHD"

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
        # Reemplazar únicamente la transmisión que use la MISMA stream_key
        for sid, info in list(active_streams.items()):
            if info.get("key") == stream_key:
                stop_single_stream(sid)

        stream_id = get_next_stream_id()
        chosen_acc = None

        if raw_channel.startswith("http://") or raw_channel.startswith("https://"):
            source_url = raw_channel
            headers = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n"
            channel_display = "Enlace Directo Stream"
            channel_id = "direct"
            is_ok = True
        else:
            chosen_acc = get_free_iptv_account()
            if not chosen_acc and active_streams:
                # Si todas las cuentas IPTV están ocupadas, liberar la más antigua
                oldest_sid = list(active_streams.keys())[0]
                stop_single_stream(oldest_sid)
                time.sleep(0.5)
                chosen_acc = get_free_iptv_account()

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
                
                iptv_options = []
                seen_ids = set()
                for slug, cname in channels_raw:
                    iptv_id, iptv_display = resolve_to_iptv(slug, cname)
                    if iptv_id not in seen_ids:
                        seen_ids.add(iptv_id)
                        iptv_options.append({"id": iptv_id, "name": iptv_display})
                        
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
        "🏆 <b>CANALES DEPORTIVOS OFICIALES (100% DIRECTO GIGABIT)</b>\n\n"
        "🇪🇸 <b>ESPAÑA (LALIGA & DAZN):</b>\n"
        f"• ⚽ <b>Movistar LaLiga FHD:</b> <code>/stream 30905 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 1 FHD:</b> <code>/stream 224832 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 2 FHD:</b> <code>/stream 224831 {curr_key}</code>\n"
        f"• ⚽ <b>LaLiga Hypermotion (2da):</b> <code>/stream 6560 {curr_key}</code>\n"
        f"• 🏎️ <b>DAZN F1 España:</b> <code>/stream 30907 {curr_key}</code>\n"
        f"• 🏍️ <b>DAZN MotoGP:</b> <code>/stream 1349240 {curr_key}</code>\n\n"
        "🇦🇷 <b>ARGENTINA (LIGA PROFESIONAL & CONMEBOL):</b>\n"
        f"• ⚽ <b>ESPN Premium HD:</b> <code>/stream 4883 {curr_key}</code>\n"
        f"• ⚽ <b>TyC Sports HD:</b> <code>/stream 30365 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 1 HD:</b> <code>/stream 30326 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 2 HD:</b> <code>/stream 30327 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 3 HD:</b> <code>/stream 30328 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 4 HD:</b> <code>/stream 1453275 {curr_key}</code>\n"
    )
    msg2 = (
        "🇨🇴 <b>COLOMBIA & SUDAMÉRICA:</b>\n"
        f"• ⚽ <b>Win Sports+ HD (Colombia):</b> <code>/stream 33945 {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports 1 HD (DSports):</b> <code>/stream 33933 {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports 2 HD:</b> <code>/stream 33932 {curr_key}</code>\n\n"
        "🇲🇽 <b>MÉXICO (LIGA MX & TUDN):</b>\n"
        f"• ⚽ <b>TUDN MX:</b> <code>/stream 1288338 {curr_key}</code>\n"
        f"• ⚽ <b>Canal 5 México FHD:</b> <code>/stream 3987 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 1 México:</b> <code>/stream 34041 {curr_key}</code>\n\n"
        "🏴󠁧󠁢󠁥󠁮󠁧󠁿 <b>PREMIER LEAGUE:</b>\n"
        f"• ⚽ <b>Sky Sports Premier League:</b> <code>/stream 29016 {curr_key}</code>\n"
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
            "• <code>/partidos</code> o <code>/agenda</code> $\\rightarrow$ Ver todos los partidos de hoy con su canal listo\n"
            "• <code>/stream &lt;CANAL&gt; [STREAM_KEY]</code> $\\rightarrow$ Iniciar transmisión directa\n"
            "• <code>/buscar &lt;nombre&gt;</code> $\\rightarrow$ Buscar un canal deportivo\n"
            "• <code>/stop</code> $\\rightarrow$ Detener transmisión\n"
            "• <code>/status</code> $\\rightarrow$ Ver estado de emisión\n"
            f"• <code>/key &lt;NUEVA_KEY&gt;</code> $\\rightarrow$ Cambiar clave por defecto"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/partidos") or text.startswith("/agenda") or text.startswith("/hoy") or text.startswith("/canales"):
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

def main():
    print("🤖 Bot Deportivo 100% Automatizado listo...")
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
