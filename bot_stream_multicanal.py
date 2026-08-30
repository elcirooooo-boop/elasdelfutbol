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
# 1. CONFIGURACIÓN DEDICADA 100% IPTV (ALTA VELOCIDAD GIGABIT / CERO CONGELAMIENTOS)
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

# MAPA DE CANALES POPULARES EN ESPAÑOL Y DEPORTES
DIRECT_MAP = {
    # 🇪🇸 España (LaLiga & DAZN & Movistar)
    "movistar": "30905", "movistarlaliga": "30905", "m+laliga": "30905", "laliga": "30905", "laligatv": "33866",
    "laliga1": "30905", "laliga2": "33672", "laliga3": "33673", "laliga4": "33674",
    "daznlaliga": "224832", "daznlaliga1": "224832", "daznlaliga2": "224831",
    "dazn1": "91781", "dazn2": "91782", "dazn3": "97617", "dazn4": "97618", "dazn": "91781",
    "f1": "30907", "daznf1": "30907", "motogp": "1349240", "daznmotogp": "1349240",
    "hypermotion": "6560", "segunda": "6560", "vamos": "6559",
    "copadelrey": "1036611",

    # 🇦🇷 Argentina & Conmebol
    "espnpremium": "4883", "premium": "4883", "tyc": "30365", "tycsports": "30365",
    "espn": "30326", "espn1": "30326", "espn2": "30327", "espn3": "30328", "espnextra": "30329",
    "espn4": "1453275", "espndeportes": "32038",
    "foxsports": "4880", "foxsports1": "4880", "foxsports2": "4881", "foxsports3": "4882", "fox1": "4880", "fox2": "4881", "fox3": "4882",
    "disney1": "30326", "disney2": "30327", "disney3": "30328", "disney4": "30329",

    # 🇨🇴 Colombia & Sudamérica
    "win": "33945", "winsports": "33945", "win+": "33945", "winsports+": "33945", "wincolombia": "33944",
    "dsports": "33933", "dsports1": "33933", "directv": "33933", "directvsports": "33933",
    "dsports2": "33932", "dsportsplus": "33931", "dsports+": "33931",

    # 🇲🇽 México (Liga MX & TUDN)
    "tudn": "985726", "tudnmx": "1288338", "canal5": "3987", "canal5mx": "3987",
    "foxsportsmx": "34041", "foxsports2mx": "34042", "foxsports3mx": "34043", "foxpremiummx": "1024956",

    # 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League (Inglaterra)
    "premier": "29016", "skysports": "29016", "skypremier": "29016", "skymain": "1256711",
    
    # 🇮🇹 Serie A (Italia)
    "juventus": "8805", "inter": "8804", "milan": "8803", "napoli": "8802", "roma": "8801", "lazio": "8800", "parma": "8784",

    # 🥊 Deportes de Combate
    "ufc": "32169", "ufchd": "32169", "ufcfightpass": "35452"
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

# Cargar caché de canales IPTV
IPTV_CHANNELS_CACHE = []
if os.path.exists("canales_iptv_raw.json"):
    try:
        with open("canales_iptv_raw.json", "r", encoding="utf-8") as f:
            IPTV_CHANNELS_CACHE = json.load(f)
    except Exception:
        pass

def resolve_channel_input(query):
    q = str(query).strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    
    # 1. Si es ID numérico directo
    if q.isdigit():
        return q, f"Canal ID #{q}"
        
    # 2. Si coincide en el mapa directo
    if q in DIRECT_MAP:
        return DIRECT_MAP[q], f"Canal {query.upper()}"
        
    # 3. Búsqueda inteligente en la base de datos de canales
    q_words = [w for w in re.split(r'[\s\-_]+', str(query).lower()) if w]
    if q_words and IPTV_CHANNELS_CACHE:
        for s in IPTV_CHANNELS_CACHE:
            name_l = s.get("name", "").lower()
            if all(w in name_l for w in q_words):
                return str(s.get("stream_id")), s.get("name")
            
    return "30905", "Movistar LaLiga (Por Defecto)"

def get_iptv_stream_url(stream_id):
    # Probar el host activo y obtener la URL directa
    for host in IPTV_HOSTS:
        try:
            url = f"{host}/live/{IPTV_USER}/{IPTV_PASS}/{stream_id}.ts"
            return url, "User-Agent: IPTVSmartersPro\r\n", True
        except Exception:
            pass
    return None, None, False

# ==============================================================================
# 2. MOTOR DIRECTO GIGABIT (0% FREEZE / AUDIO PERFECTO)
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
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-rw_timeout", "10000000",
        "-fflags", "+genpts+igndts+discardcorrupt",
        "-analyzeduration", "3000000",
        "-probesize", "3000000"
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

def start_single_stream(raw_channel, stream_key):
    raw_channel = clean_arg(raw_channel)
    stream_key = clean_arg(stream_key)
    destination = RTMP_SERVER + stream_key

    with stream_lock:
        for sid, info in list(active_streams.items()):
            if info["key"] == stream_key:
                stop_single_stream(sid)

        stream_id = get_next_stream_id()
        channel_id, channel_display = resolve_channel_input(raw_channel)
        source_url, headers, is_ok = get_iptv_stream_url(channel_id)

        if not is_ok or not source_url:
            return False, stream_id, f"No se pudo conectar al canal '{raw_channel}' en el servidor IPTV."

        proc, out_f, log_file = launch_ffmpeg_process(source_url, headers, destination, stream_id)
        
        time.sleep(3.0)
        if proc.poll() is not None:
            out_f.close()
            err_snippet = "No se pudo conectar a la transmisión de Telegram."
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    log_text = f.read()
                    if "I/O error" in log_text or "Error opening output" in log_text:
                        err_snippet = "Telegram rechazó la Stream Key. Asegúrate de tener abierta la ventana del directo en Telegram y copiar la Stream Key actual."
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
            "raw_name": channel_display,
            "channel_id": channel_id,
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
# 3. WATCHDOG DE RECONEXIÓN AUTOMÁTICA EN CASO DE CAÍDA
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
                        print(f"⚠️ Watchdog: Canal #{sid} ({info['raw_name']}) cayó. Reconectando...")
                        try:
                            if "log_file" in info and not info["log_file"].closed:
                                info["log_file"].close()
                        except Exception:
                            pass
                        
                        new_url, new_hdrs, ok = get_iptv_stream_url(info["channel_id"])
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
                            print(f"✅ Watchdog: Canal #{sid} reanudado exitosamente.")
        except Exception as e:
            print(f"Error en watchdog: {e}")

# ==============================================================================
# 4. INTERFAZ Y COMANDOS DE TELEGRAM
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

def get_sports_menu_messages(curr_key):
    msg1 = (
        "🏆 <b>CANALES DEPORTIVOS OFICIALES DISPONIBLES (100% DIRECTO GIGABIT)</b>\n\n"
        "🇪🇸 <b>ESPAÑA (LALIGA & DAZN):</b>\n"
        f"• ⚽ <b>Movistar LaLiga FHD:</b> <code>/stream 30905 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN LaLiga 1 FHD:</b> <code>/stream 224832 {curr_key}</code>\n"
        f"• ⚽ <b>LaLiga Hypermotion (2da):</b> <code>/stream 6560 {curr_key}</code>\n"
        f"• ⚽ <b>DAZN 1 España:</b> <code>/stream 91781 {curr_key}</code>\n"
        f"• 🏎️ <b>DAZN F1 España:</b> <code>/stream 30907 {curr_key}</code>\n"
        f"• 🏍️ <b>DAZN MotoGP:</b> <code>/stream 1349240 {curr_key}</code>\n\n"
        "🇦🇷 <b>ARGENTINA (LIGA PROFESIONAL):</b>\n"
        f"• ⚽ <b>ESPN Premium HD:</b> <code>/stream 4883 {curr_key}</code>\n"
        f"• ⚽ <b>TyC Sports HD:</b> <code>/stream 30365 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 1 Argentina:</b> <code>/stream 4880 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 1 HD:</b> <code>/stream 30326 {curr_key}</code>\n"
        f"• ⚽ <b>ESPN 2 HD:</b> <code>/stream 30327 {curr_key}</code>\n\n"
        "🇨🇴 <b>COLOMBIA & SUDAMÉRICA:</b>\n"
        f"• ⚽ <b>Win Sports+ HD (Colombia):</b> <code>/stream 33945 {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports 1 HD (DSports):</b> <code>/stream 33933 {curr_key}</code>\n"
        f"• ⚽ <b>DIRECTV Sports 2 HD:</b> <code>/stream 33932 {curr_key}</code>\n"
    )
    msg2 = (
        "🇲🇽 <b>MÉXICO (LIGA MX):</b>\n"
        f"• ⚽ <b>TUDN MX:</b> <code>/stream 1288338 {curr_key}</code>\n"
        f"• ⚽ <b>Canal 5 México FHD:</b> <code>/stream 3987 {curr_key}</code>\n"
        f"• ⚽ <b>Fox Sports 1 México:</b> <code>/stream 34041 {curr_key}</code>\n\n"
        "🏴󠁧󠁢󠁥󠁮󠁧󠁿 <b>PREMIER LEAGUE:</b>\n"
        f"• ⚽ <b>Sky Sports Premier League:</b> <code>/stream 29016 {curr_key}</code>\n"
        f"• ⚽ <b>Sky Sports Main Events:</b> <code>/stream 1256711 {curr_key}</code>\n\n"
        "🇮🇹 <b>SERIE A (ITALIA - CANALES DEDICADOS):</b>\n"
        f"• ⚽ <b>Juventus:</b> <code>/stream 8805 {curr_key}</code>\n"
        f"• ⚽ <b>Inter:</b> <code>/stream 8804 {curr_key}</code>\n"
        f"• ⚽ <b>Milan:</b> <code>/stream 8803 {curr_key}</code>\n"
        f"• ⚽ <b>Napoli:</b> <code>/stream 8802 {curr_key}</code>\n\n"
        "🔍 <i>¿Buscas otro canal específico?</i> Usa <code>/buscar &lt;nombre&gt;</code>"
    )
    return [msg1, msg2]

def search_channels(query):
    q_words = [w for w in re.split(r'[\s\-_]+', str(query).lower()) if w]
    if not q_words or not IPTV_CHANNELS_CACHE:
        return "⚠️ No se encontraron resultados."
    
    matches = []
    for s in IPTV_CHANNELS_CACHE:
        name = s.get("name", "")
        if all(w in name.lower() for w in q_words):
            matches.append((s.get("stream_id"), name))
            if len(matches) >= 15:
                break
                
    if not matches:
        return f"❌ No se encontró ningún canal con: <b>{html.escape(query)}</b>"
        
    res = f"🔍 <b>RESULTADOS PARA '{html.escape(query)}':</b>\n\n"
    for sid, name in matches:
        res += f"• 📺 <b>{html.escape(name)}:</b>\n  <code>/stream {sid}</code>\n\n"
    return res

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
            "⚽ <b>BOT DE TRANSMISIÓN DEPORTIVA 100% DIRECTA (ALTA VELOCIDAD GIGABIT)</b>\n\n"
            "📋 <b>MENÚ DE CANALES DEPORTIVOS:</b>\n"
            "• <code>/partidos</code> o <code>/canales</code> $\\rightarrow$ Ver canales principales con ID directo\n\n"
            "🔍 <b>BUSCAR CUALQUIER CANAL:</b>\n"
            "• <code>/buscar barcelona</code> | <code>/buscar espn</code> | <code>/buscar laliga</code>\n\n"
            "📺 <b>TRANSMITIR POR NOMBRE O POR ID:</b>\n"
            "• <code>/stream 30905</code> $\\rightarrow$ Movistar LaLiga FHD\n"
            "• <code>/stream 4883</code> $\\rightarrow$ ESPN Premium HD\n"
            "• <code>/stream espn</code> | <code>/stream win</code> | <code>/stream dsports</code>\n"
            "• <code>/stream &lt;CANAL_O_ID&gt; [STREAM_KEY]</code>\n\n"
            "🛑 <b>DETENER:</b> <code>/stop</code> | <code>/stopall</code>\n"
            "📊 <b>ESTADO:</b> <code>/status</code>\n"
            f"🔑 <b>CLAVE STREAM:</b> <code>/key &lt;NUEVA_KEY&gt;</code>"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/partidos") or text.startswith("/canales") or text.startswith("/agenda"):
        msgs = get_sports_menu_messages(curr_key)
        for m in msgs:
            send_msg(chat_id, m)

    elif text.startswith("/buscar"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/buscar &lt;nombre_o_equipo&gt;</code>\nEjemplo: <code>/buscar espn</code> o <code>/buscar madrid</code>")
            return
        res = search_channels(parts[1])
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
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL_O_ID&gt;</code> o <code>/stream &lt;ID&gt; &lt;STREAM_KEY&gt;</code>\nEjemplo: <code>/stream 30905</code> o <code>/stream espn</code>")
            return
        
        raw_ch = clean_arg(parts[1])
        stream_key = clean_arg(parts[2]) if len(parts) >= 3 else curr_key
        
        send_msg(chat_id, f"⏳ <b>Conectando al canal {html.escape(raw_ch)} en servidor Gigabit dedicado...</b>")
        ok, sid, res = start_single_stream(raw_ch, stream_key)
        if ok:
            send_msg(chat_id, (
                f"✅ <b>¡Transmisión ACTIVA y 100% DIRECTA!</b> 🚀\n\n"
                f"📺 <b>Canal #{sid}:</b> <code>{html.escape(res)}</code>\n"
                f"🔑 <b>Key:</b> <code>{stream_key[:8]}...</code>\n"
                f"📡 <b>Servidor:</b> IPTV Gigabit Dedicado (0% Lags / 0% Freezing)\n"
                f"🎙️ <b>Sincronización:</b> Audio y Video 1:1 Nativo Directo\n"
                f"⚡ <b>Modo:</b> Pure Passthrough (0% CPU / Calidad Original 60fps)\n\n"
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
    print("🤖 Bot 100% IPTV Directo Gigabit (0% Freeze / Audio Sincronizado) listo...")
    
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
