import subprocess
import time
import requests
import json
import os
import sys
import re
import html
import threading
import concurrent.futures

# ==============================================================================
# 1. CONFIGURACIÓN DEL SERVIDOR IPTV DEDICADO (XTREAM CODES)
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

# MAPEO RÁPIDO DE CANALES DEPORTIVOS PRINCIPALES
IPTV_TOP_CHANNELS = {
    "espn": {"id": "32114", "name": "ESPN 1 HD"},
    "espn1": {"id": "32114", "name": "ESPN 1 HD"},
    "espn2": {"id": "32164", "name": "ESPN 2 HD"},
    "dsports": {"id": "33933", "name": "Directv Sports 1 HD"},
    "dsports1": {"id": "33933", "name": "Directv Sports 1 HD"},
    "directv": {"id": "33933", "name": "Directv Sports 1 HD"},
    "dsportsar": {"id": "33933", "name": "Directv Sports 1 HD"},
    "dsports2": {"id": "33932", "name": "Directv Sports 2 HD"},
    "dsportsplus": {"id": "33931", "name": "Directv Sports Plus HD"},
    "dsports3": {"id": "33931", "name": "Directv Sports Plus HD"},
    "winsports": {"id": "33945", "name": "Win Sports+ HD (Colombia)"},
    "win": {"id": "33945", "name": "Win Sports+ HD (Colombia)"},
    "wincolombia": {"id": "33944", "name": "Win Sports Colombia"},
    "tyc": {"id": "30365", "name": "TyC Sports HD (Argentina)"},
    "tycsports": {"id": "30365", "name": "TyC Sports HD (Argentina)"},
    "laliga": {"id": "30905", "name": "Movistar LaLiga FHD"},
    "movistarlaliga": {"id": "30905", "name": "Movistar LaLiga FHD"},
    "laligatv": {"id": "33866", "name": "LaLiga TV FHD"},
    "dazn": {"id": "224832", "name": "DAZN LaLiga 1 FHD"},
    "daznlaliga": {"id": "224832", "name": "DAZN LaLiga 1 FHD"},
    "f1": {"id": "30907", "name": "DAZN F1 España FHD"},
    "daznf1": {"id": "30907", "name": "DAZN F1 España FHD"},
    "motogp": {"id": "1349240", "name": "DAZN MotoGP FHD"},
    "champions": {"id": "239671", "name": "Movistar Champions League"},
    "movistarchampions": {"id": "239671", "name": "Movistar Champions League"},
    "premier": {"id": "29016", "name": "Sky Sports Premier League FHD"},
    "premiersports": {"id": "29043", "name": "Premier Sports 1 FHD"},
    "eurosport": {"id": "30911", "name": "Eurosport 1 FHD"},
    "eurosport1": {"id": "30911", "name": "Eurosport 1 FHD"},
    "eurosport2": {"id": "30912", "name": "Eurosport 2 FHD"},
    "nfl": {"id": "32121", "name": "NFL Redzone HD"},
    "redzone": {"id": "32121", "name": "NFL Redzone HD"},
    "nba": {"id": "32106", "name": "NBA TV FHD"},
}

# RESOLVER DE STREAM IPTV CON RESOLUCIÓN DINÁMICA DE EDGE
def resolve_iptv_stream(stream_id_or_cmd):
    target = str(stream_id_or_cmd).lower().strip()
    stream_id = None

    if target in IPTV_TOP_CHANNELS:
        stream_id = IPTV_TOP_CHANNELS[target]["id"]
    elif target.isdigit():
        stream_id = target
    else:
        # Buscar por coincidencia parcial en el diccionario rápido
        for k, v in IPTV_TOP_CHANNELS.items():
            if k in target or target in k:
                stream_id = v["id"]
                break

    if not stream_id:
        return None, None, f"Canal o ID '{target}' no encontrado. Usa /canales o /buscar <nombre>."

    # Obtener URL del stream desde los hosts activos
    for host in IPTV_HOSTS:
        try:
            req_url = f"{host}/live/{IPTV_USER}/{IPTV_PASS}/{stream_id}.ts"
            r = requests.get(req_url, headers={"User-Agent": "IPTVSmartersPro"}, allow_redirects=False, timeout=4)
            loc = r.headers.get("Location")
            if loc:
                edge_host = loc.split('/')[2]
                edge_ip = "149.57.9.64"
                try:
                    doh = requests.get(f"https://cloudflare-dns.com/dns-query?name={edge_host}&type=A", headers={"accept": "application/dns-json"}, timeout=2).json()
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

    return None, None, f"No se pudo conectar al servidor IPTV para el canal ID: {stream_id}."

# BÚSQUEDA EN TIEMPO REAL DE CANALES IPTV
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

        for sid, name in matches[:60]: # Limitar a los 60 mejores resultados
            item = f"📺 <b>{name}</b> (ID: <code>{sid}</code>)\n<code>/stream {sid} {curr_key}</code>\n\n"
            if len(current_msg) + len(item) > 3400:
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

        if not is_ok:
            return False, stream_id, f"Error: {is_ok}"

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
            "🌟 <b>CANALES PRINCIPALES (DIRECTO HD / 1080P):</b>\n"
            "• <code>/canales</code> o <code>/top</code> $\\rightarrow$ Ver canales deportivos listos\n"
            "• <code>/buscar &lt;nombre&gt;</code> $\\rightarrow$ Buscar entre los 27.000 canales del servidor\n\n"
            "📺 <b>TRANSMITIR:</b>\n"
            "• <code>/stream espn</code> | <code>/stream espn2</code>\n"
            "• <code>/stream dsports</code> | <code>/stream dsports2</code>\n"
            "• <code>/stream laliga</code> | <code>/stream dazn</code> | <code>/stream f1</code>\n"
            "• <code>/stream winsports</code> | <code>/stream tyc</code> | <code>/stream champions</code>\n"
            "• <code>/stream &lt;CANAL_O_ID&gt; [STREAM_KEY]</code>\n\n"
            "🛑 <b>DETENER TRANSMISIONES:</b>\n"
            "• <code>/stop</code> $\\rightarrow$ Detener la transmisión activa\n"
            "• <code>/stopall</code> $\\rightarrow$ Detener TODAS las transmisiones\n\n"
            "📊 <b>ESTADO EN VIVO:</b>\n"
            "• <code>/status</code> $\\rightarrow$ Ver transmisiones activas\n\n"
            f"🔑 <b>CLAVE STREAM:</b> <code>/key &lt;NUEVA_KEY&gt;</code>"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/top") or text.startswith("/canales") or text.startswith("/partidos") or text.startswith("/deportes"):
        msg_txt = "🌟 <b>CANALES DEPORTIVOS DEDICADOS (IPTV 1080P / FLUIDOS):</b>\n\n"
        seen = set()
        for cmd_name, info in IPTV_TOP_CHANNELS.items():
            sid = info["id"]
            if sid in seen:
                continue
            seen.add(sid)
            msg_txt += f"📺 <b>{info['name']}:</b>\n<code>/stream {cmd_name} {curr_key}</code>\n\n"
        msg_txt += "💡 <i>Toca cualquier comando en gris para copiarlo y enviarlo al instante.</i>\n"
        msg_txt += "🔍 <i>¿Buscas otro canal? Usa <code>/buscar &lt;nombre&gt;</code></i>"
        send_msg(chat_id, msg_txt)

    elif text.startswith("/buscar") or text.startswith("/search"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/buscar &lt;nombre_canal&gt;</code>\nEjemplo: <code>/buscar espn</code> o <code>/buscar directv</code> o <code>/buscar movistar</code>")
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
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;CANAL_O_ID&gt;</code> o <code>/stream &lt;CANAL&gt; &lt;STREAM_KEY&gt;</code>\nEjemplo: <code>/stream espn</code> o <code>/stream 30905</code>")
            return
        
        raw_url = clean_arg(parts[1])
        stream_key = clean_arg(parts[2]) if len(parts) >= 3 else curr_key
        
        send_msg(chat_id, f"⏳ <b>Iniciando transmisión IPTV dedicada de {html.escape(raw_url)}...</b>")
        ok, sid, res = start_single_stream(raw_url, stream_key)
        if ok:
            send_msg(chat_id, (
                f"✅ <b>¡Transmisión IPTV ACTIVA y FLUIDA!</b> 🚀\n\n"
                f"📺 <b>Canal #{sid}:</b> <code>{html.escape(raw_url)}</code>\n"
                f"🔑 <b>Key:</b> <code>{stream_key[:8]}...</code>\n"
                f"📡 <b>Servidor:</b> IPTV Dedicado (0% Cortes / 1080p)\n"
                f"⚡ <b>Modo:</b> Direct Passthrough (0% CPU / Calidad Máxima)\n\n"
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
    print("🤖 Bot IPTV Dedicado (Account: BE15ERDV) listo...")
    
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
