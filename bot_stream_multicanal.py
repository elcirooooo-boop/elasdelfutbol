import subprocess
import time
import requests
import json
import os
import sys
import re
from urllib.parse import urlparse

# ==============================================================================
# 1. CONFIGURACIÓN DEL BOT Y CUENTA IPTV
# ==============================================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8720125234:AAGB4vCTAehurwPhxCvAsWsNaqM_mvyZ_xs")
RTMP_SERVER = "rtmps://dc4-1.rtmp.t.me/s/"
CHANNELS_FILE = "channels.json"

IPTV_USER = "BE15ERDV"
IPTV_PASS = "PXELERB9"
IPTV_SERVER = "http://evestv.leptis.live"

def load_channels():
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "1": os.environ.get("STREAM_KEY_1", "4394528713:myDTS60UhFs8Q1cpXDDyaQ"),
        "2": os.environ.get("STREAM_KEY_2", "4400198885:PcUiiv-__sV28_Hnyq83Ew"),
        "3": os.environ.get("STREAM_KEY_3", "3936015063:nG8N_no46UfNuA6jXewiag")
    }

def save_channels(channels_dict):
    try:
        with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump(channels_dict, f, indent=2)
    except Exception:
        pass

CHANNELS = load_channels()
ADMIN_USER_ID = None
active_streams = {}

TOP_SPORTS_CHANNELS = [
    {"name": "ESPN 1 HD", "id": "32114", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/32114.ts"},
    {"name": "ESPN 2 HD", "id": "32164", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/32164.ts"},
    {"name": "ESPN 2 HD (Respaldo)", "id": "239665", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/239665.ts"},
    {"name": "ESPN HD (Latam)", "id": "34050", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/34050.ts"},
    {"name": "ESPN 3 HD", "id": "34049", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/34049.ts"},
    {"name": "ESPN 4 HD", "id": "1201550", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/1201550.ts"},
    {"name": "TyC Sports HD", "id": "30365", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/30365.ts"},
    {"name": "Directv Sports 1 (DSPORTS)", "id": "33933", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/33933.ts"},
    {"name": "Directv Sports 2 (DSPORTS 2)", "id": "33932", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/33932.ts"},
    {"name": "LaLiga TV (FHD)", "id": "33866", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/33866.ts"},
    {"name": "LaLiga TV (HD)", "id": "34105", "url": f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/34105.ts"},
]

cached_streams = []

def get_iptv_streams():
    global cached_streams
    if cached_streams:
        return cached_streams
    try:
        api_url = f"{IPTV_SERVER}/player_api.php?username={IPTV_USER}&password={IPTV_PASS}&action=get_live_streams"
        r = requests.get(api_url, timeout=15, headers={"User-Agent": "IPTVSmartersPro"})
        if r.status_code == 200:
            cached_streams = r.json()
            return cached_streams
    except Exception as e:
        print(f"Error cargando canales IPTV: {e}")
    return []

def search_iptv_channels(query, max_results=8):
    streams = get_iptv_streams()
    results = []
    query_clean = query.lower().strip()
    for ch in streams:
        name = ch.get("name", "")
        sid = ch.get("stream_id")
        clean_name = re.sub(r'[^\x00-\x7F]+', ' ', name).strip()
        if query_clean in clean_name.lower():
            link = f"{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/{sid}.ts"
            results.append((clean_name, sid, link))
            if len(results) >= max_results:
                break
    return results

# ==============================================================================
# 2. GESTOR DE MULTI-TRANSMISIÓN DEFINITIVO (SIN -RE / 100% FLUIDO EN VIVO)
# ==============================================================================
def clean_arg(val):
    if not val:
        return ""
    return val.strip().strip("<>").strip('"').strip("'").strip()

def start_single_stream(stream_id, raw_url, stream_key, label=None):
    if stream_id in active_streams:
        stop_single_stream(stream_id)

    source_url = clean_arg(raw_url)
    stream_key = clean_arg(stream_key)
    destination = RTMP_SERVER + stream_key

    # PERFIL ULTRA-LIVIANO ANTI-LAG (Sin -re para no frenar la señal en vivo)
    cmd = [
        "ffmpeg",
        "-user_agent", "IPTVSmartersPro",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "2",
        "-fflags", "+nobuffer+genpts+igndts+discardcorrupt",
        "-avoid_negative_ts", "make_zero",
        "-i", source_url,
        "-max_muxing_queue_size", "4096",
        "-vf", "scale=960:540",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-threads", "0",
        "-b:v", "1000k",
        "-maxrate", "1200k",
        "-bufsize", "2000k",
        "-pix_fmt", "yuv420p",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", "96k",
        "-ar", "44100",
        "-bsf:a", "aac_adtstoasc",
        "-max_interleave_delta", "0",
        "-flvflags", "no_duration_filesize",
        "-f", "flv",
        destination
    ]

    log_file = f"/tmp/stream_{stream_id}.log" if os.name != 'nt' else f"stream_{stream_id}.log"
    out_f = open(log_file, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(cmd, stdout=out_f, stderr=out_f)
    
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
        return False, f"Error: {err_snippet}"

    active_streams[stream_id] = {
        "process": proc,
        "log_file": out_f,
        "url": source_url,
        "key": stream_key,
        "name": label if label else f"Canal {stream_id}",
        "start_time": time.time()
    }
    return True, source_url

def stop_single_stream(stream_id):
    if stream_id in active_streams:
        info = active_streams[stream_id]
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
        del active_streams[stream_id]
        return True
    return False

def stop_all_streams():
    ids = list(active_streams.keys())
    for sid in ids:
        stop_single_stream(sid)
    return len(ids)

# ==============================================================================
# 3. INTERFAZ DE BOT DE TELEGRAM
# ==============================================================================
def send_msg(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

def handle_message(msg):
    global CHANNELS
    chat_id = msg.get("chat", {}).get("id")
    user_id = msg.get("from", {}).get("id")
    text = msg.get("text", "").strip()

    if ADMIN_USER_ID and user_id != ADMIN_USER_ID:
        send_msg(chat_id, "⛔ No tienes permisos para usar este bot.")
        return

    if text.startswith("/start") or text.startswith("/ayuda"):
        help_text = (
            "⚽ *BOT DE TRANSMISIÓN DEPORTIVA MULTI-CANAL*\n\n"
            "📋 *GUÍA DE CANALES Y PARTIDOS:*\n"
            "• `/top` $\\rightarrow$ Ver todos los canales deportivos top con sus URLs\n"
            "• `/buscar <nombre>` $\\rightarrow$ Buscar cualquier canal en tu IPTV (ej. `/buscar dazn`)\n"
            "• `/partidos` $\\rightarrow$ Cartelera y enlaces de los partidos de hoy\n\n"
            "📺 *TRANSMITIR EN CANALES:*\n"
            "• `/c1 <URL>` $\\rightarrow$ Transmitir en Canal 1\n"
            "• `/c2 <URL>` $\\rightarrow$ Transmitir en Canal 2\n"
            "• `/c3 <URL>` $\\rightarrow$ Transmitir en Canal 3\n"
            "• `/stream <URL> <STREAM_KEY>` $\\rightarrow$ Personalizado\n\n"
            "🔑 *GESTIÓN DE CLAVES:*\n"
            "• `/set1 <KEY>` | `/set2 <KEY>` | `/set3 <KEY>`\n"
            "• `/canales` $\\rightarrow$ Ver claves guardadas\n\n"
            "🛑 *DETENER:*\n"
            "• `/stop1` | `/stop2` | `/stop3` | `/stopall`\n\n"
            "📊 *ESTADO:*\n"
            "• `/status` $\\rightarrow$ Ver qué partidos están emitiéndose"
        )
        send_msg(chat_id, help_text)

    elif text.startswith("/top") or text.startswith("/deportes"):
        msg_txt = "🌟 *CANALES DEPORTIVOS PRINCIPALES (100% ACTIVOS):*\n\n"
        for ch in TOP_SPORTS_CHANNELS:
            msg_txt += f"📺 *{ch['name']}*\n🔗 `{ch['url']}`\n\n"
        msg_txt += "💡 _Toca cualquier enlace para copiarlo y envíalo con `/c1 <enlace>`_"
        send_msg(chat_id, msg_txt)

    elif text.startswith("/buscar"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_msg(chat_id, "⚠️ *Uso:* `/buscar <palabra>` (ejemplo: `/buscar espn`, `/buscar tyc`, `/buscar fox`)")
            return
        query = parts[1].strip()
        send_msg(chat_id, f"🔍 *Buscando canales con:* `{query}`...")
        results = search_iptv_channels(query)
        if not results:
            send_msg(chat_id, f"❌ No se encontraron canales con `{query}`.")
            return

        resp_txt = f"🎯 *RESULTADOS PARA:* `{query}`\n\n"
        for name, sid, link in results:
            resp_txt += f"• *{name}* (ID `{sid}`):\n🔗 `{link}`\n\n"
        resp_txt += "💡 _Toca el enlace para copiarlo y envíalo con `/c1 <enlace>`_"
        send_msg(chat_id, resp_txt)

    elif text.startswith("/partidos") or text.startswith("/hoy"):
        partidos_txt = (
            "⚽ *CARTELERA DE PARTIDOS TOP DE HOY:*\n\n"
            "🏴󠁧󠁢󠁥󠁮󠁧󠁿 *Premier League: Fulham vs. Chelsea*\n"
            "• 📺 Canal: ESPN 1 HD\n"
            f"• 🔗 `{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/32114.ts`\n\n"
            "🇪🇸 *LaLiga: Osasuna vs. Levante*\n"
            "• 📺 Canal: ESPN 4 HD\n"
            f"• 🔗 `{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/1201550.ts`\n\n"
            "🇪🇸 *LaLiga: Málaga vs. Deportivo La Coruña*\n"
            "• 📺 Canal: Directv Sports 1 (DSPORTS)\n"
            f"• 🔗 `{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/33933.ts`\n\n"
            "🇮🇹 *Serie A: Bologna vs. Lazio*\n"
            "• 📺 Canal: ESPN 2 HD\n"
            f"• 🔗 `{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/32164.ts`\n\n"
            "🇮🇹 *Serie A: AS Roma vs. Fiorentina*\n"
            "• 📺 Canal: ESPN 2 HD\n"
            f"• 🔗 `{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/32164.ts`\n\n"
            "🇦🇷 *Liga Argentina: Tigre vs. Central Córdoba*\n"
            "• 📺 Canal: TyC Sports HD\n"
            f"• 🔗 `{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/30365.ts`\n\n"
            "🇦🇷 *Liga Argentina: Talleres vs. Rosario Central*\n"
            "• 📺 Canal: ESPN 1 HD\n"
            f"• 🔗 `{IPTV_SERVER}/live/{IPTV_USER}/{IPTV_PASS}/32114.ts`\n\n"
            "💡 _Toca cualquier enlace para copiarlo y transmitir con `/c1 <enlace>`_"
        )
        send_msg(chat_id, partidos_txt)

    elif text.startswith("/canales"):
        txt = "📋 *CANALES CONFIGURADOS ACTUALMENTE:*\n\n"
        for cid, k in sorted(CHANNELS.items()):
            txt += f"• *Canal {cid}:* `{k}`\n"
        txt += "\n💡 Para cambiar una clave escribe: `/set1 <nueva_clave>`"
        send_msg(chat_id, txt)

    elif text.startswith("/set"):
        parts = text.split()
        if text.startswith("/set1") or text.startswith("/set2") or text.startswith("/set3"):
            cid = text[4:5]
            if len(parts) < 2:
                send_msg(chat_id, f"⚠️ *Uso:* `/set{cid} NUEVA_STREAM_KEY`")
                return
            new_key = clean_arg(parts[1])
        else:
            if len(parts) < 3:
                send_msg(chat_id, "⚠️ *Uso:* `/set NUMERO_CANAL STREAM_KEY`")
                return
            cid = clean_arg(parts[1])
            new_key = clean_arg(parts[2])

        CHANNELS[cid] = new_key
        save_channels(CHANNELS)
        send_msg(chat_id, f"✅ *¡Clave del Canal {cid} actualizada con éxito!*\n🔑 Nueva Stream Key: `{new_key}`")

    elif text.startswith("/c"):
        parts = text.split()
        cid = parts[0][2:]
        if not cid.isalnum():
            return
        if len(parts) < 2:
            send_msg(chat_id, f"⚠️ *Uso:* `/c{cid} <URL>`")
            return
        
        raw_url = clean_arg(parts[1])
        stream_key = clean_arg(CHANNELS.get(cid))
        if not stream_key:
            send_msg(chat_id, f"❌ El Canal {cid} no tiene ninguna clave configurada.\nConfigúrala primero con: `/set{cid} <STREAM_KEY>`")
            return

        send_msg(chat_id, f"⏳ *Iniciando transmisión blindada en Canal {cid}...*")
        ok, res = start_single_stream(cid, raw_url, stream_key, f"Canal {cid}")
        if ok:
            send_msg(chat_id, f"✅ *¡Transmisión ACTIVA en Canal {cid}!* 🚀\n📡 Key: `{stream_key[:8]}...`\n⚡ Perfil: Ultra-Fluido 0% Lag")
        else:
            send_msg(chat_id, f"❌ *Error al iniciar:* {res}")

    elif text.startswith("/stream"):
        parts = text.split()
        if len(parts) < 3:
            send_msg(chat_id, "⚠️ *Uso:* `/stream <URL> <STREAM_KEY>`")
            return
        raw_url = clean_arg(parts[1])
        custom_key = clean_arg(parts[2])
        custom_id = f"custom_{len(active_streams) + 1}"
        send_msg(chat_id, "⏳ *Iniciando transmisión ultra-fluida...*")
        ok, res = start_single_stream(custom_id, raw_url, custom_key, f"Personalizado ({custom_id})")
        if ok:
            send_msg(chat_id, f"✅ *¡Transmisión ACTIVA!* 🚀\nID: `{custom_id}`\n📡 Key: `{custom_key[:8]}...`\n⚡ Perfil: Ultra-Fluido 0% Lag")
        else:
            send_msg(chat_id, f"❌ *Error al iniciar:* {res}")

    elif text.startswith("/stop") and text != "/stopall":
        cid = clean_arg(text[5:])
        if not cid:
            send_msg(chat_id, "⚠️ *Uso:* `/stop1`, `/stop2` o `/stopall`")
            return
        if stop_single_stream(cid):
            send_msg(chat_id, f"🛑 *Canal {cid} detenido correctamente.*")
        else:
            send_msg(chat_id, f"ℹ️ El Canal {cid} no estaba transmitiendo.")

    elif text.startswith("/stopall"):
        count = stop_all_streams()
        send_msg(chat_id, f"🛑 *Se han detenido todas las transmisiones ({count} partidos cerrados).*")

    elif text.startswith("/status"):
        if not active_streams:
            send_msg(chat_id, "🔴 *No hay ninguna transmisión activa actualmente.*")
            return

        status_text = "🟢 *CANALES EN DIRECTO:*\n\n"
        for sid, info in active_streams.items():
            elapsed = int(time.time() - info["start_time"])
            mins = elapsed // 60
            secs = elapsed % 60
            status_text += f"📺 *{info['name']}:*\n• ⏱️ Tiempo: `{mins}m {secs}s`\n• 📡 Key: `{info['key'][:8]}...`\n• 🔗 URL: `{info['url'][:35]}...`\n\n"
        send_msg(chat_id, status_text)

def main():
    print("🤖 Bot Multi-Canal Blindado listo...")
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
