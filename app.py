# -*- coding: utf-8 -*-
"""
Created on Mon Oct 27 20:40:13 2025

@author: yuril
"""

# -*- coding: utf-8 -*-
"""
Created on Sun Oct 26 17:10:56 2025

@author: yuril
"""
# app.py — Chat protocolli reparto con bottoni rapidi, QR code, dark mode e layout migliorato

from openai import OpenAI
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from jinja2 import Template
import qrcode
from io import BytesIO
import time
import traceback

# ====== CONFIG ======
import os
API_KEY = os.getenv("API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
TITLE = "Mar-IA"  # <-- titolo principale, ora lo rendiamo molto più grande
PRIMARY = "#1F4E79"     # blu sobrio
RATE_LIMIT_SECONDS = 8   # minimo secondi tra due domande dalla stessa IP
# ====================

client = OpenAI(api_key=API_KEY)
threads = getattr(client, "threads", None) or client.beta.threads  # compat con versioni "beta"

# Rate limiting naive in-memory
_last_call_by_ip = {}

HTML = r"""
<!doctype html>
<html lang="it">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{{title}}</title>
<style>
:root {
  --primary: {{primary}};
  --bg: #ffffff;
  --fg: #111111;
  --muted: #666;
  --card: #fff;
  --border: #e5e7eb;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0b0d10;
    --fg: #e8eaed;
    --muted: #a3a3a3;
    --card: #111418;
    --border: #1f232a;
  }
}
* { box-sizing: border-box; }
body {
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
  margin: 0; padding: 0; background: var(--bg); color: var(--fg);
}
.header {
  position: sticky; top: 0; z-index: 10;
  background: linear-gradient(90deg, var(--primary), #264c72 60%, #2b587a);
  color: #fff; padding: 16px 18px; display: flex; align-items: center; gap: 14px;
  box-shadow: 0 2px 10px rgba(0,0,0,.2);
}
.title-logo {
  height: 52px;   /* dimensione del logo */
  width: auto;
  margin-right: 6px;
}
.container { max-width: 900px; margin: 16px auto; padding: 0 12px 20px; }
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 14px; padding: 14px; box-shadow: 0 2px 10px rgba(0,0,0,.06);
}
h1 {
  font-size: clamp(28px, 4.2vw, 48px);
  line-height: 1.1;
  margin: 0;
}
h2 { font-size: 16px; margin: 16px 0 8px; }
.subtitle { color: #e5effa; opacity: .95; font-size: 14px; margin-top: 6px; }
.subtitle-2 { color: #e5effa; opacity: .9; font-size: 13px; margin-top: 4px; }
.label { color: var(--muted); font-size: 13px; margin-bottom: 6px; }
textarea {
  width: 100%; height: 120px; resize: vertical; padding: 10px 12px;
  border-radius: 10px; border: 1px solid var(--border); background: var(--bg); color: var(--fg);
}
.btn {
  display: inline-block; padding: 10px 14px; border-radius: 10px; border: 1px solid var(--border);
  background: var(--card); color: var(--fg); text-decoration: none; cursor: pointer; font-weight: 600;
}
.btn-primary {
  background: var(--primary); color: #fff; border: 0; box-shadow: 0 3px 10px rgba(31,78,121,.25);
}
.btn-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 2px; }
.response {
  white-space: pre-wrap; border: 1px solid var(--border); padding: 12px; border-radius: 12px; background: var(--bg);
}
.grid {
  display: grid; grid-template-columns: 1fr; gap: 12px;
}
@media (min-width: 900px) {
  .grid { grid-template-columns: 2fr 1fr; }
}
.small { font-size: 12px; color: var(--muted); }
.qrbox { display: grid; place-items: center; padding: 8px; }
.error { color: #ff6b6b; white-space: pre-wrap; }
.badge { font-size: 11px; color: #fff; background: rgba(255,255,255,.15); padding: 2px 8px; border-radius: 999px; }
.notice { background: rgba(31,78,121,.08); border: 1px dashed var(--primary); color: var(--fg);
  padding: 8px 10px; border-radius: 10px; }

.disclaimer-box {
  max-width: 900px;
  margin: 20px auto;
  padding: 16px;
  background: rgba(255, 230, 150, 0.15);
  border: 2px solid #f4c542;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  color: #664d00;
  text-align: center;
  font-weight: 600;
}
</style>
</head>
<body>

<div class="header">
  <img src="/static/logo.png" alt="Logo Mar-IA" class="title-logo" />
  <div>
    <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
      <h1>{{title}}</h1>
      <span class="badge">Prototipo</span>
    </div>
    <div class="subtitle">Il tuo assistente AI di Reparto – USARE CON CAUTELA!</div>
    <div class="subtitle-2">Reparto di Chirurgia Epatobiliare e Generale – Fondazione Policlinico Universitario &quot;A. Gemelli&quot; IRCCS</div>
  </div>
</div>

<div class="container grid">

  <div class="card">
    <div class="label">Domanda</div>
    <form method="post" action="/ask">
      <textarea name="q" placeholder="Es.: Quando devo rimuovere i drenaggi?">{{prefill or ""}}</textarea>
      <div class="btn-row">
        <button class="btn btn-primary" type="submit">Chiedi</button>
        <button class="btn" name="preset" value="Sepsi: cosa fare adesso? ..." formmethod="post" formaction="/preset">Sepsi</button>
        <button class="btn" name="preset" value="Profilassi antibiotica pre-ERCP..." formmethod="post" formaction="/preset">ERCP (profilassi)</button>
        <button class="btn" name="preset" value="Dimissione paziente: criteri, farmaci..." formmethod="post" formaction="/preset">Dimissione DS</button>
        <button class="btn" name="preset" value="Gestione dolore post-operatorio..." formmethod="post" formaction="/preset">Dolore post-op</button>
        <button class="btn" name="preset" value="Shock Emorragico: cosa fare..." formmethod="post" formaction="/preset">Shock Emorragico</button>
      </div>
      <div class="small">Suggerimento: sii specifico (es. include allergie se previste dal protocollo).</div>
    </form>

    {% if answer %}
      <h2>Risposta</h2>
      <div class="response">{{answer}}</div>
    {% endif %}

    {% if error %}
      <h2>Errore</h2>
      <div class="error">{{error}}</div>
    {% endif %}
  </div>

  <div class="card">
    <h2>Condividi</h2>
    <div class="notice small">Scansiona il QR per aprire questa chat su smartphone.</div>
    <div class="qrbox">
      <img alt="QR code" src="/qr" />
    </div>
    <div class="small">Se il QR non si apre dal telefono, verifica l’indirizzo usato in fase di avvio del server.</div>

    <h2 style="margin-top:16px;">Stato</h2>
    <div class="small">Health: <a class="btn" href="/health">/health</a></div>
  </div>

</div>

<!-- Disclaimer separato in basso -->
<div class="disclaimer-box">
  Supporto operativo basato sui protocolli interni.<br/>
  <b>LA DECISIONE FINALE VIENE PRESA DAL MEDICO;</b> QUESTO PROGRAMMA PUÒ SBAGLIARE.<br/>
  <span style="color:#a00;">NON CARICARE dati personali del paziente.</span>
</div>

</body>
</html>
"""


from fastapi import Depends

app = FastAPI()

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")


def _rate_limit(request: Request):
    """Blocco antispam per IP (naive)."""
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    last = _last_call_by_ip.get(ip, 0)
    if now - last < RATE_LIMIT_SECONDS:
        raise RuntimeError(f"Rallenta: attendi {RATE_LIMIT_SECONDS - int(now - last)}s prima della prossima domanda.")
    _last_call_by_ip[ip] = now

@app.get("/", response_class=HTMLResponse)
def index():
    return Template(HTML).render(title=TITLE, primary=PRIMARY, answer=None, error=None, prefill=None)

@app.post("/preset", response_class=HTMLResponse)
def preset(request: Request, preset: str = Form(...)):
    # precompila la textarea con il testo del bottone
    return Template(HTML).render(title=TITLE, primary=PRIMARY, answer=None, error=None, prefill=preset)

@app.post("/ask", response_class=HTMLResponse)
def ask(request: Request, q: str = Form(...), guard=Depends(_rate_limit)):
    try:
        if not API_KEY or API_KEY.startswith("sk-INSERISCI"):
            raise RuntimeError("API_KEY mancante o non impostata.")
        if not ASSISTANT_ID or not ASSISTANT_ID.startswith("asst_"):
            raise RuntimeError("ASSISTANT_ID mancante o non valido.")

        # 1) crea thread con la domanda
        t = threads.create(messages=[{"role": "user", "content": q}])

        # 2) avvia il run
        run = threads.runs.create_and_poll(thread_id=t.id, assistant_id=ASSISTANT_ID)

        # 3) recupera risposta (primo messaggio role=assistant)
        msgs = threads.messages.list(thread_id=t.id)

        answer_text = None
        for m in msgs.data:
            if getattr(m, "role", "") == "assistant":
                for p in m.content:
                    if hasattr(p, "text") and hasattr(p.text, "value"):
                        answer_text = p.text.value
                        break
                if answer_text:
                    break

        if not answer_text:
            answer_text = "Nessuna risposta testuale trovata."

        return Template(HTML).render(title=TITLE, primary=PRIMARY, answer=answer_text, error=None, prefill=q)

    except Exception as e:
        err = f"{str(e)}\n\nTRACEBACK:\n{traceback.format_exc()}"
        return Template(HTML).render(title=TITLE, primary=PRIMARY, answer=None, error=err, prefill=q)

@app.get("/qr")
def qr(request: Request):
    """
    Genera un QR code che punta alla pagina principale dell'app.
    Se pubblichi l'app su un dominio, il QR si adatterà automaticamente.
    """
    base_url = str(request.base_url).rstrip("/")
    url = f"{base_url}/"
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")

@app.get("/health", response_class=PlainTextResponse)
def health():
    return "ok"

