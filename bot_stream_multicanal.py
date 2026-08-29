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
# 1. CONFIGURACIÓN DEL BOT Y CLAVE STREAM (STREAMEAST 100% EXCLUSIVO)
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CONFIG_FILE = "config_stream.json"
STREAMEAST_MAIN = "https://istreameast.cx/"

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

# RESOLUCIÓN DE TRANSMISIONES DE STREAMEAST Y ENLACES DIRECTOS
def resolve_live_stream_url(target):
    target = target.strip()
    
    # 1. Si es un enlace directo .m3u8 o .ts (copiado de Server 2 de StreamEast)
    if ".m3u8" in target or ".ts" in target:
        referer = "https://embed.st/"
        if "embedindia" in target:
            referer = "https://embedindia.st/"
        elif "istreameast" in target:
            referer = "https://istreameast.cx/"
        hdrs = f"Referer: {referer}\r\nOrigin: {referer.rstrip('/')}\r\n"
        return target, hdrs, True

    # 2. Si es una URL de evento de StreamEast (https://istreameast.cx/links/...)
    if "istreameast.cx" in target or "thestreameast" in target or target.startswith("/links/"):
        full_url = target if target.startswith("http") else f"https://istreameast.cx{target}"
        try:
            r = requests.get(full_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://istreameast.cx/"}, timeout=4)
            # Extraer botones de servidor priorizando SERVER 2
            btns = re.findall(r'<button[^>]+class=["\']server-btn[^"\']*["\'][^>]+data-src=["\']([^"\']+)["\'][^>]*>(.*?)</button>', r.text)
            
            selected_embed = None
            for src, name in btns:
                if "2" in name or "Server 2" in name or "server 2" in name:
                    selected_embed = src
                    break
            if not selected_embed and btns:
                selected_embed = btns[0][0]
                
            if selected_embed:
                r_ifr = requests.get(selected_embed, headers={"User-Agent": "Mozilla/5.0", "Referer": full_url}, timeout=4)
                m3u8s = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', r_ifr.text)
                if m3u8s:
                    return m3u8s[0], f"Referer: {selected_embed}\r\nOrigin: {selected_embed.rsplit('/', 1)[0]}\r\n", True
        except Exception:
            pass

    # 3. Canales o nombres directos
    aliases = [target.lower()]
    for al in aliases:
        endpoints = [
            f"https://tvf90.com/hd.php?stream={al}",
            f"https://futbollibre.ch/hd.php?stream={al}",
            f"https://tvf90.com/5.php?stream={al}",
            f"https://futbollibre.ch/5.php?stream={al}",
        ]
        for ep in endpoints:
            try:
                r = requests.get(ep, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://rojadirectatv.ec/"}, timeout=2.0)
                if r.status_code == 200:
                    m3u8s = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', r.text)
                    if m3u8s:
                        return m3u8s[0], f"Referer: {ep}\r\nOrigin: {ep.rsplit('/', 1)[0]}\r\n", True
            except Exception:
                pass

    return None, f"No se pudo resolver el canal '{target}'.", False

# AGENDA OFICIAL COMPLETA DE STREAMEAST
def get_streameast_agenda_messages(curr_key):
    try:
        r = requests.get(STREAMEAST_MAIN, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://istreameast.cx/"}, timeout=6)
        html_txt = r.text
        
        cards = re.findall(r'<div[^>]+class=["\']event-card[^"\']*["\'][^>]+onclick=["\']window\.location\.href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</div>\s*</div>', html_txt, re.DOTALL)
        if not cards:
            return ["🔴 No se encontraron eventos disponibles en StreamEast en este momento."]
            
        events = []
        for link, body in cards:
            title_m = re.findall(r'<div[^>]+class=["\']event-title["\'][^>]*>(.*?)</div>', body)
            title = html.unescape(title_m[0].strip()) if title_m else link.replace("/links/", "").replace("-", " ").title()
            
            time_m = re.findall(r'<div[^>]+class=["\']event-datetime["\'][^>]*>(.*?)</div>', body)
            dt = html.unescape(time_m[0].strip()) if time_m else ""
            
            league_m = re.findall(r'<div[^>]+class=["\']event-league["\'][^>]*>(.*?)</div>', body)
            league_raw = re.sub(r'<[^>]+>', ' ', league_m[0]).strip() if league_m else ""
            is_live = "LIVE" in league_raw.upper()
            
            events.append({
                "title": title,
                "time": dt,
                "live": is_live,
                "url": f"https://istreameast.cx{link}"
            })
            
        messages = []
        current_msg = f"🌐 <b>AGENDA STREAMEAST EN VIVO ({len(events)} EVENTOS DE HOY)</b>\n\n"
        
        for ev in events:
            live_tag = "🔴 <b>[EN VIVO]</b> " if ev["live"] else "⏳ "
            time_str = f" ({html.escape(ev['time'])})" if ev["time"] else ""
            
            item_block = (
                f"{live_tag}<b>{html.escape(ev['title'])}</b>{time_str}\n"
                f"▶ <b>Transmitir (Server 2):</b>\n"
                f"<code>/stream {ev['url']} {curr_key}</code>\n\n"
            )
            
            if len(current_msg) + len(item_block) > 3400:
                messages.append(current_msg)
                current_msg = item_block
            else:
                current_msg += item_block
                
        if current_msg.strip():
            messages.append(current_msg)
            
        return messages
    except Exception as e:
        return [f"⚠️ Error obteniendo agenda de StreamEast: {e}"]

# ==============================================================================
# 2. MOTOR ANTI-CONGELAMIENTO (FFMPEG BLINDADO + WATCHDOG)
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
            "⚽ <b>BOT DE TRANSMISIÓN STREAMEAST OFICIAL</b>\n\n"
            "📋 <b>AGENDA DE PARTIDOS:</b>\n"
            "• <code>/partidos</code> $\\rightarrow$ Ver todos los partidos de <b>StreamEast en vivo</b>\n\n"
            "📺 <b>TRANSMITIR:</b>\n"
            "• <code>/stream &lt;URL_STREAMEAST_O_M3U8&gt; [STREAM_KEY]</code>\n"
            "• <i>(Prioridad automática a Server 2)</i>\n\n"
            "🛑 <b>DETENER TRANSMISIONES:</b>\n"
            "• <code>/stop</code> $\\rightarrow$ Detener la transmisión activa\n"
            "• <code>/stopall</code> $\\rightarrow$ Detener TODAS las transmisiones\n\n"
            "📊 <b>ESTADO EN VIVO:</b>\n"
            "• <code>/status</code> $\\rightarrow$ Ver transmisiones activas\n\n"
            f"🔑 <b>CLAVE STREAM:</b> <code>/key &lt;NUEVA_KEY&gt;</code>"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/partidos") or text.startswith("/hoy") or text.startswith("/agenda") or text.startswith("/streameast"):
        send_msg(chat_id, "⏳ <b>Cargando agenda oficial en vivo de StreamEast...</b>")
        agenda_msgs = get_streameast_agenda_messages(curr_key)
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
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;URL_STREAMEAST_O_M3U8&gt;</code> o <code>/stream &lt;URL&gt; &lt;STREAM_KEY&gt;</code>")
            return
        
        raw_url = clean_arg(parts[1])
        stream_key = clean_arg(parts[2]) if len(parts) >= 3 else curr_key
        
        send_msg(chat_id, f"⏳ <b>Iniciando transmisión blindada anti-freeze de StreamEast (Server 2)...</b>")
        ok, sid, res = start_single_stream(raw_url, stream_key)
        if ok:
            send_msg(chat_id, (
                f"✅ <b>¡Transmisión ACTIVA (StreamEast Server 2)!</b> 🚀\n\n"
                f"📺 <b>Transmisión #{sid}:</b> <code>{html.escape(raw_url[:45])}</code>\n"
                f"🔑 <b>Key:</b> <code>{stream_key[:8]}...</code>\n"
                f"🛡️ <b>Fuente:</b> StreamEast (Server 2 / HD)\n"
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
                send_msg(chat_id, f"🛑 <b>Transmisión #{sid} ({html.escape(ch_name[:30])}) detenida correctamente.</b>")
                return
            else:
                txt = "⚠️ <b>Hay varias transmisiones activas. Elige cuál detener:</b>\n\n"
                for sid, info in active_streams.items():
                    txt += f"• Transmisión #{sid} (<b>{html.escape(info['raw_name'][:30])}</b>): <code>/stop {sid}</code>\n"
                txt += "\n🛑 <b>O detener todas a la vez:</b> <code>/stopall</code>"
                send_msg(chat_id, txt)
                return
        
        target = parts[1].strip()
        ok, sid, ch_name = stop_single_stream(target)
        if ok:
            send_msg(chat_id, f"🛑 <b>Transmisión #{sid} ({html.escape(ch_name[:30])}) detenida correctamente.</b>")
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
                f"📺 <b>Transmisión #{sid} ({html.escape(info['raw_name'][:35])}):</b>\n"
                f"• ⏱️ Tiempo: <code>{mins}m {secs}s</code>\n"
                f"• 🔄 Auto-Reconexiones: <code>{restarts}</code>\n"
                f"• 📡 Key: <code>{info['key'][:8]}...</code>\n"
                f"• 🛑 <b>Detener esta:</b> <code>/stop {sid}</code>\n\n"
            )
        status_text += "🛑 <b>Detener todas juntas:</b> <code>/stopall</code>"
        send_msg(chat_id, status_text)

def main():
    print("🤖 Bot StreamEast Oficial (100% Exclusivo con Server 2) listo...")
    
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
