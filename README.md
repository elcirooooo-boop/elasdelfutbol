# ⚽ Bot de Transmisión Multi-Canal para Telegram (Cloud / Railway / VPS)

Sistema autónomo en la nube para retransmitir partidos y eventos en directo hacia múltiples canales de Telegram simultáneamente sin cortes ni congelamientos.

---

## 🚀 Despliegue en Railway (1 Clic)

1. En [Railway.app](https://railway.app/), crea un nuevo proyecto e importa este repositorio de GitHub.
2. En la pestaña **Variables** de tu servicio en Railway, agrega:
   * `BOT_TOKEN`: El token que te da [@BotFather](https://t.me/BotFather) en Telegram.
3. ¡Listo! Railway construirá el contenedor Docker con FFmpeg y encenderá tu bot 24/7 automáticamente.

---

## 📱 Comandos del Bot en Telegram

### Transmitir en Canales:
* `/c1 <URL_M3U8>` — Inicia la transmisión en el Canal 1.
* `/c2 <URL_M3U8>` — Inicia la transmisión en el Canal 2.
* `/c3 <URL_M3U8>` — Inicia la transmisión en el Canal 3.
* `/stream <URL_M3U8> <STREAM_KEY>` — Transmite al instante a cualquier canal temporal.

### Cambiar Claves de Canales desde el Chat:
* `/set1 <NUEVA_STREAM_KEY>` — Actualiza la clave de transmisión del Canal 1.
* `/set2 <NUEVA_STREAM_KEY>` — Actualiza la clave de transmisión del Canal 2.
* `/set3 <NUEVA_STREAM_KEY>` — Actualiza la clave de transmisión del Canal 3.
* `/canales` — Muestra la lista de canales y claves guardadas.

### Control y Monitoreo:
* `/status` — Muestra todos los partidos que se están transmitiendo en vivo con su tiempo de emisión.
* `/stop1` — Detiene la transmisión del Canal 1.
* `/stop2` — Detiene la transmisión del Canal 2.
* `/stopall` — Detiene todas las transmisiones activas.
