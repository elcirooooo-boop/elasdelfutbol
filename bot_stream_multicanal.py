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
# CONFIGURACIÓN DEDICADA 100% STREAMEAST (https://istreameast.cx/)
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CONFIG_FILE = "config_stream.json"

STREAMEAST_BASE = "https://istreameast.cx"
STREAMEAST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://istreameast.cx/"
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

# Caché de eventos de StreamEast
STREAMEAST_CACHE = {"timestamp": 0, "events": []}

def fetch_streameast_events():
    global STREAMEAST_CACHE
    now = time.time()
    if now - STREAMEAST_CACHE.get("timestamp", 0) < 180 and STREAMEAST_CACHE.get("events"):
        return STREAMEAST_CACHE["events"]

    schedule_urls = [
        ("Fútbol", f"{STREAMEAST_BASE}/schedule/soccer"),
        ("UFC / MMA", f"{STREAMEAST_BASE}/schedule/ufc"),
        ("Motorsport / F1", f"{STREAMEAST_BASE}/schedule/f1"),
        ("Boxeo", f"{STREAMEAST_BASE}/schedule/boxing"),
        ("NBA / Baloncesto", f"{STREAMEAST_BASE}/schedule/nba"),
        ("NFL", f"{STREAMEAST_BASE}/schedule/nfl"),
        ("MLB", f"{STREAMEAST_BASE}/schedule/mlb"),
        ("En Vivo", f"{STREAMEAST_BASE}/")
    ]

    all_events = []
    seen_slugs = set()

    for cat_name, url in schedule_urls:
        try:
            r = requests.get(url, headers=STREAMEAST_HEADERS, timeout=6)
            if r.status_code == 200:
                cards = re.findall(r'<div class="event-card"[^>]*onclick="window\.location\.href=[\'"]/links/([^\'"]+)[\'"][^>]*>(.*?)</div>\s*</div>\s*</div>', r.text, re.DOTALL)
                for slug, inner in cards:
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)
                    
                    title_m = re.search(r'<div class="event-title">([^<]+)</div>', inner)
                    time_m = re.search(r'<div class="event-datetime">([^<]+)</div>', inner)
                    league_m = re.search(r'<div class="event-league">\s*([A-Za-z0-9\s]+)', inner)
                    status_m = re.search(r'class="event-status[^"]*">([^<]+)<', inner)
                    
                    title = title_m.group(1).strip() if title_m else slug.replace("-", " ").title()
                    time_str = time_m.group(1).strip() if time_m else ""
                    league = league_m.group(1).strip() if league_m else cat_name
                    status = status_m.group(1).strip() if status_m else "Programado"
                    
                    all_events.append({
                        "slug": slug,
                        "title": title,
                        "time": time_str,
                        "league": league,
                        "sport_cat": cat_name,
                        "status": status,
                        "url": f"{STREAMEAST_BASE}/links/{slug}"
                    })
        except Exception:
            pass

    if all_events:
        STREAMEAST_CACHE["timestamp"] = now
        STREAMEAST_CACHE["events"] = all_events
        return all_events
    return STREAMEAST_CACHE.get("events", [])

def resolve_streameast_stream(query):
    q = query.strip()
    
    # 1. Si el usuario pasa directamente un link m3u8 o http/https
    if q.startswith("http://") or q.startswith("https://"):
        if ".m3u8" in q or "workers.dev" in q or "stream" in q:
            return q, "Enlace Directo StreamEast (.m3u8)", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\nReferer: https://istreameast.cx/\r\n", True
        
        # Si es una URL de página de StreamEast: https://istreameast.cx/links/<slug>
        slug_m = re.search(r'/links/([^\s/?#]+)', q)
        if slug_m:
            q = slug_m.group(1)

    # 2. Buscar en los eventos de StreamEast por slug o por nombre
    events = fetch_streameast_events()
    target_event = None
    
    # Coincidencia exacta de slug
    for ev in events:
        if ev["slug"].lower() == q.lower() or q.lower() in ev["slug"].lower():
            target_event = ev
            break
            
    # Coincidencia por palabras del título
    if not target_event:
        q_words = [w for w in re.split(r'[\s\-_]+', q.lower()) if len(w) > 2]
        for ev in events:
            if all(w in ev["title"].lower() or w in ev["slug"].lower() for w in q_words):
                target_event = ev
                break

    if not target_event and events:
        target_event = events[0] # Por defecto primer partido en vivo

    if target_event:
        match_url = target_event["url"]
        try:
            r = requests.get(match_url, headers=STREAMEAST_HEADERS, timeout=10)
            if r.status_code == 200:
                # Buscar embeds de reproducción
                iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text)
                server_btns = re.findall(r'class="server-btn[^"]*"[^>]+data-src=["\']([^"\']+)["\']', r.text)
                
                embed_urls = iframes + server_btns
                for eu in embed_urls:
                    if "embed" in eu:
                        # Intentar extraer m3u8 del embed
                        try:
                            r_emb = requests.get(eu, headers=STREAMEAST_HEADERS, timeout=8)
                            m3u8_m = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', r_emb.text)
                            if m3u8_m:
                                return m3u8_m[0], f"{target_event['title']} (StreamEast)", f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\nReferer: {eu}\r\n", True
                        except Exception:
                            pass

                # Si no se pudo resolver el embed automáticamente, devolver instrucciones
                return None, target_event['title'], match_url, False
        except Exception as e:
            print(f"Error resolviendo match {match_url}: {e}")

    return None, q, None, False

# ==============================================================================
# MOTOR DE TRANSMISIÓN TELEGRAM (ULTRA-BAJA LATENCIA / 50-60 FPS SUAVE)
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

def start_single_stream(raw_channel, stream_key):
    raw_channel = clean_arg(raw_channel)
    stream_key = clean_arg(stream_key)
    destination = RTMP_SERVER + stream_key

    with stream_lock:
        for sid in list(active_streams.keys()):
            stop_single_stream(sid)
        time.sleep(0.5)

        stream_id = "1"
        source_url, title_display, hdrs_or_link, is_ok = resolve_streameast_stream(raw_channel)

        if not is_ok or not source_url:
            err_msg = (
                f"ℹ️ <b>Partido:</b> {html.escape(title_display)}\n\n"
                f"Para emitir este partido directo desde StreamEast sin límites:\n"
                f"1. Abre en tu navegador: <code>{html.escape(str(hdrs_or_link))}</code>\n"
                f"2. En DevTools (F12 $\\rightarrow$ Network) copia el enlace <b>mono.ts.m3u8</b>.\n"
                f"3. Envía: <code>/stream &lt;URL_M3U8&gt; {stream_key}</code>"
            )
            return False, stream_id, err_msg

        proc, out_f, log_file = launch_ffmpeg_process(source_url, hdrs_or_link, destination, stream_id)
        
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
            "raw_name": title_display,
            "url": source_url,
            "headers": hdrs_or_link,
            "destination": destination,
            "key": stream_key,
            "start_time": now,
            "auto_restart": True,
            "restart_count": 0
        }
        return True, stream_id, title_display

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
# COMANDOS Y MENÚS DE TELEGRAM (STREAMEAST)
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

def get_streameast_agenda_messages(curr_key):
    events = fetch_streameast_events()
    if not events:
        return ["⚠️ No se pudieron cargar los eventos de StreamEast en este momento. Intenta de nuevo en unos segundos."]

    messages = []
    
    # 1. Separar los eventos en vivo
    live_events = [e for e in events if "LIVE" in e.get("status", "").upper()]
    upcoming_events = [e for e in events if "LIVE" not in e.get("status", "").upper()]

    current_msg = "🔥 <b>AGENDA COMPLETA STREAMEAST (https://istreameast.cx/)</b>\n\n"

    if live_events:
        current_msg += "🔴 <b>PARTIDOS EN DIRECTO AHORA MISMO (LIVE NOW):</b>\n"
        for ev in live_events:
            current_msg += (
                f"• ⚽ <b>{html.escape(ev['title'])}</b> ({html.escape(ev['league'])})\n"
                f"  <code>/stream {ev['slug']} {curr_key}</code>\n"
            )
        current_msg += "\n"

    # Agrupar por deporte / liga los demás partidos
    by_league = {}
    for ev in upcoming_events:
        lg = ev.get("league", "Otros Deportes")
        if lg not in by_league:
            by_league[lg] = []
        by_league[lg].append(ev)

    for lg, ev_list in by_league.items():
        block = f"🏆 <b>{html.escape(lg).upper()} ({len(ev_list)} Partidos):</b>\n"
        for ev in ev_list:
            st = ev.get("status", "")
            block += (
                f"• ⏰ <b>{html.escape(ev['title'])}</b>\n"
                f"  ⏱️ <i>{html.escape(ev['time'])}</i>\n"
                f"  <code>/stream {ev['slug']} {curr_key}</code>\n"
            )
        block += "\n"

        if len(current_msg) + len(block) > 3500:
            messages.append(current_msg)
            current_msg = block
        else:
            current_msg += block

    if current_msg:
        messages.append(current_msg)

    return messages

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
            "🔥 <b>BOT DE TRANSMISIÓN DEDICADO 100% A STREAMEAST</b>\n"
            "🌐 Fuente Oficial: <code>https://istreameast.cx/</code>\n\n"
            "📋 <b>COMANDOS DISPONIBLES:</b>\n"
            "• <code>/partidos</code> o <code>/agenda</code> $\\rightarrow$ Ver todos los partidos de StreamEast en vivo\n"
            "• <code>/stream &lt;SLUG_O_M3U8&gt; [STREAM_KEY]</code> $\\rightarrow$ Iniciar transmisión\n"
            "• <code>/buscar &lt;equipo&gt;</code> $\\rightarrow$ Buscar partido en StreamEast\n"
            "• <code>/stop</code> o <code>/stopall</code> $\\rightarrow$ Detener transmisión\n"
            "• <code>/status</code> $\\rightarrow$ Ver estado de emisión\n"
            f"• <code>/key &lt;NUEVA_KEY&gt;</code> $\\rightarrow$ Cambiar clave por defecto"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/partidos") or text.startswith("/agenda") or text.startswith("/hoy") or text.startswith("/canales"):
        send_msg(chat_id, "⏳ <b>Cargando todos los partidos y directos de StreamEast...</b>")
        msgs = get_streameast_agenda_messages(curr_key)
        for m in msgs:
            send_msg(chat_id, m)

    elif text.startswith("/buscar"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/buscar &lt;nombre_o_equipo&gt;</code>\nEjemplo: <code>/buscar chelsea</code> o <code>/buscar madrid</code>")
            return
        
        query = parts[1].strip().lower()
        events = fetch_streameast_events()
        matches = [e for e in events if query in e["title"].lower() or query in e["slug"].lower()]
        
        if not matches:
            send_msg(chat_id, f"❌ No se encontró ningún partido en StreamEast con: <b>{html.escape(query)}</b>")
            return

        res = f"🔍 <b>RESULTADOS EN STREAMEAST PARA '{html.escape(query)}':</b>\n\n"
        for ev in matches[:10]:
            st = ev.get("status", "")
            res += (
                f"• ⚽ <b>{html.escape(ev['title'])}</b> ({html.escape(ev['league'])})\n"
                f"  ⏱️ {html.escape(st)}\n"
                f"  <code>/stream {ev['slug']} {curr_key}</code>\n\n"
            )
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
            send_msg(chat_id, "⚠️ <b>Uso:</b> <code>/stream &lt;SLUG_O_M3U8&gt; [STREAM_KEY]</code>\nEjemplo: <code>/stream chelsea-vs-brighton-and-hove-albion-2494014</code>")
            return
        
        raw_ch = clean_arg(parts[1])
        stream_key = clean_arg(parts[2]) if len(parts) >= 3 else curr_key
        
        send_msg(chat_id, f"⏳ <b>Conectando a la señal de StreamEast ({html.escape(raw_ch[:35])})...</b>")
        ok, sid, res = start_single_stream(raw_ch, stream_key)
        if ok:
            send_msg(chat_id, (
                f"✅ <b>¡Transmisión ACTIVA desde StreamEast!</b> 🚀\n\n"
                f"📺 <b>Partido:</b> <code>{html.escape(res)}</code>\n"
                f"🔑 <b>Key:</b> <code>{stream_key[:8]}...</code>\n"
                f"📡 <b>Fuente:</b> https://istreameast.cx/\n"
                f"⚡ <b>Formato:</b> 50 FPS Sedoso / Baja Latencia en Vivo\n\n"
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

    elif text.startswith("/status"):
        if not active_streams:
            send_msg(chat_id, "🔴 <b>No hay ninguna transmisión activa actualmente.</b>")
            return

        status_text = f"🟢 <b>TRANSMISIÓN EN DIRECTO ACTIVA:</b>\n\n"
        for sid, info in sorted(active_streams.items()):
            elapsed = int(time.time() - info["start_time"])
            mins = elapsed // 60
            secs = elapsed % 60
            status_text += (
                f"📺 <b>Partido:</b> <code>{html.escape(info['raw_name'])}</code>\n"
                f"• ⏱️ Tiempo: <code>{mins}m {secs}s</code>\n"
                f"• 📡 Key: <code>{info['key'][:8]}...</code>\n"
                f"• 🛑 <b>Detener:</b> <code>/stop</code>\n"
            )
        send_msg(chat_id, status_text)

def main():
    print("🤖 Bot 100% StreamEast (https://istreameast.cx/) listo...")
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
