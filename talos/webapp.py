"""Lokales Dashboard: Chat mit Talos + Live-Blick in Memory, Lektionen, Skills.

Start: `talos-web`, dann http://localhost:7777
Single-User, nur für localhost gedacht. Features: Verlauf (Sessions),
Chat-/Coding-Modus, Live-Aktivitätsgraph, Token/Kosten-Anzeige,
Voice-Ein-/Ausgabe, Markdown, Dark Mode.
"""

from __future__ import annotations

import base64
import json
import os
import queue
import secrets
import threading
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from .agent import Agent
from .config import Config
from .learning import reflect

MODES = {
    "chat": "",
    "coden": (
        "CODING-MODUS: Du arbeitest als Programmier-Agent. Liefere lauffähigen, "
        "getesteten Code. Nutze das shell-Tool, um Code auszuführen und zu prüfen, "
        "bevor du Erfolg meldest. Lege Projekte unter ~/TalosProjekte/ an. "
        "Erkläre knapp, Code spricht für sich."
    ),
}

app = FastAPI(title="TalosAI")

# Passwortschutz: wenn TALOS_WEB_PASSWORD gesetzt ist, verlangt das Dashboard
# HTTP-Basic-Auth (beliebiger Nutzername, dieses Passwort). Pflicht, sobald der
# Server öffentlich erreichbar ist — der Agent hat ein Shell-Tool.
_WEB_PASSWORD = os.getenv("TALOS_WEB_PASSWORD", "")


@app.middleware("http")
async def _auth(request: Request, call_next):
    if _WEB_PASSWORD:
        header = request.headers.get("authorization", "")
        ok = False
        if header.startswith("Basic "):
            try:
                _, pw = base64.b64decode(header[6:]).decode().split(":", 1)
                ok = secrets.compare_digest(pw, _WEB_PASSWORD)
            except (ValueError, UnicodeDecodeError):
                ok = False
        if not ok:
            return Response(
                "Anmeldung erforderlich", status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="TalosAI"'},
            )
    return await call_next(request)


_cfg = Config()
_sessions_dir = _cfg.data_dir / "sessions"
_sessions_dir.mkdir(exist_ok=True)
_lock = threading.Lock()  # ein Agent, eine Anfrage zur Zeit


def _new_agent(mode: str = "chat") -> Agent:
    agent = Agent(_cfg, session_id=uuid.uuid4().hex[:12])
    agent.mode_prompt = MODES.get(mode, "")
    agent.mode = mode
    agent.title = ""
    return agent


_agent = _new_agent()


def _save_session() -> None:
    if not _agent.messages:
        return
    path = _sessions_dir / f"{_agent.session_id}.json"
    path.write_text(json.dumps({
        "id": _agent.session_id,
        "title": _agent.title,
        "mode": getattr(_agent, "mode", "chat"),
        "updated": time.time(),
        "messages": _agent.messages,
    }, ensure_ascii=False))


def _usage() -> dict:
    return {
        "input": _agent.llm.total_input_tokens,
        "output": _agent.llm.total_output_tokens,
        "cost": round(_agent.llm.total_cost_usd, 4),
        "context": _agent.llm.last_input_tokens,
        "window": 200_000,
    }


class ChatIn(BaseModel):
    message: str


class SessionIn(BaseModel):
    id: str = ""
    mode: str = "chat"


@app.post("/api/chat/stream")
def chat_stream(body: ChatIn):
    """Streamt Tool-Events live, dann die finale Antwort (SSE-Format)."""
    q: queue.Queue = queue.Queue()

    def worker() -> None:
        with _lock:
            if not _agent.title:
                _agent.title = body.message[:60]
            _agent.on_tool = lambda name, args: q.put({
                "type": "tool",
                "name": name,
                "detail": str(
                    args.get("command") or args.get("query") or args.get("url")
                    or args.get("task") or args.get("name") or ""
                )[:120],
            })
            try:
                reply = _agent.run(body.message)
            except Exception as e:
                reply = f"Fehler: {type(e).__name__}: {e}"
            _save_session()
            q.put({"type": "reply", "text": reply, "usage": _usage()})
        q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def gen():
        while True:
            item = q.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/sessions")
def sessions():
    out = []
    for path in _sessions_dir.glob("*.json"):
        try:
            d = json.loads(path.read_text())
            out.append({"id": d["id"], "title": d.get("title") or "(ohne Titel)",
                        "mode": d.get("mode", "chat"), "updated": d.get("updated", 0)})
        except (json.JSONDecodeError, KeyError):
            continue
    out.sort(key=lambda s: -s["updated"])
    return {"sessions": out[:50], "current": _agent.session_id}


@app.post("/api/session/new")
def session_new(body: SessionIn):
    global _agent
    with _lock:
        if _agent.messages:
            reflect(_agent)
            _save_session()
        _agent = _new_agent(body.mode)
    return {"id": _agent.session_id}


@app.post("/api/session/load")
def session_load(body: SessionIn):
    global _agent
    path = _sessions_dir / f"{body.id}.json"
    if not path.exists():
        return {"error": "nicht gefunden"}
    d = json.loads(path.read_text())
    with _lock:
        _agent = _new_agent(d.get("mode", "chat"))
        _agent.session_id = d["id"]
        _agent.title = d.get("title", "")
        _agent.messages = d["messages"]
    # nur User/Assistent-Textnachrichten fürs UI
    history = [
        {"role": m["role"], "text": m["content"]}
        for m in _agent.messages
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
        and m.get("content")
    ]
    return {"id": d["id"], "history": history}


@app.get("/api/graph")
def graph():
    """Wissens-Graph im Obsidian-Stil: Memory, Skills, Lektionen + Links."""
    import re as _re

    nodes = [
        {"id": "talos", "label": "Talos", "type": "hub", "content": ""},
        {"id": "hub-mem", "label": "Gedächtnis", "type": "hub", "content": ""},
        {"id": "hub-skill", "label": "Skills", "type": "hub", "content": ""},
        {"id": "hub-lesson", "label": "Lektionen", "type": "hub", "content": ""},
    ]
    links = [{"a": "talos", "b": "hub-mem"}, {"a": "talos", "b": "hub-skill"},
             {"a": "talos", "b": "hub-lesson"}]
    mem_ids = set()
    for p in sorted(_agent.memory.dir.glob("*.md")):
        if p.name == "MEMORY.md" or p.name == "lessons.md":
            continue
        nid = f"mem-{p.stem}"
        mem_ids.add(p.stem)
        nodes.append({"id": nid, "label": p.stem, "type": "memory",
                      "content": p.read_text()[:2000]})
        links.append({"a": "hub-mem", "b": nid})
    # [[wiki-links]] zwischen Memory-Einträgen
    for p in _agent.memory.dir.glob("*.md"):
        if p.stem in mem_ids:
            for target in _re.findall(r"\[\[([\w-]+)\]\]", p.read_text()):
                if target in mem_ids and target != p.stem:
                    links.append({"a": f"mem-{p.stem}", "b": f"mem-{target}"})
    for p in sorted(_agent.skills.dir.glob("*.md")):
        nid = f"skill-{p.stem}"
        nodes.append({"id": nid, "label": p.stem, "type": "skill",
                      "content": p.read_text()[:2000]})
        links.append({"a": "hub-skill", "b": nid})
    for i, line in enumerate(_agent.memory.lessons().splitlines()):
        line = line.lstrip("- ").strip()
        if line:
            nodes.append({"id": f"lesson-{i}", "label": line[:32] + ("…" if len(line) > 32 else ""),
                          "type": "lesson", "content": line})
            links.append({"a": "hub-lesson", "b": f"lesson-{i}"})
    return {"nodes": nodes, "links": links}


class TTSIn(BaseModel):
    text: str


@app.post("/api/tts")
def tts(body: TTSIn):
    """Sprachausgabe über ElevenLabs (Fallback im Frontend: Browser-Stimme)."""
    if not _cfg.eleven_key:
        return {"error": "kein ElevenLabs-Key konfiguriert"}
    import httpx
    from fastapi.responses import Response

    resp = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{_cfg.eleven_voice}",
        headers={"xi-api-key": _cfg.eleven_key},
        json={
            "text": body.text[:900],
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=60,
    )
    if resp.status_code != 200:
        return {"error": f"ElevenLabs: HTTP {resp.status_code}"}
    return Response(content=resp.content, media_type="audio/mpeg")


DEFAULT_SETTINGS = {
    "active_provider": "Anthropic",
    "providers": [],
    "eleven_key": "", "eleven_voice": "", "verify": True,
    "mcp_servers": [],
}


@app.get("/api/settings")
def get_settings():
    s = dict(DEFAULT_SETTINGS)
    if _cfg.settings_file.exists():
        try:
            s.update(json.loads(_cfg.settings_file.read_text()))
        except json.JSONDecodeError:
            pass
    if not s["providers"]:
        # Initialbestand aus der .env ableiten
        s["providers"] = [{"name": "Anthropic", "base_url": _cfg.base_url,
                           "api_key": _cfg.api_key, "model": _cfg.model,
                           "small_model": _cfg.small_model}]
        s["active_provider"] = "Anthropic"
    if not s["eleven_key"]:
        s["eleven_key"] = _cfg.eleven_key
    if not s["eleven_voice"]:
        s["eleven_voice"] = _cfg.eleven_voice
    mcp_status = _agent.mcp.status() if _agent.mcp else None
    return {**s, "mcp_status": mcp_status}


@app.post("/api/settings")
def save_settings(body: dict):
    global _cfg, _agent
    body.pop("mcp_status", None)
    _cfg.settings_file.write_text(json.dumps(body, ensure_ascii=False, indent=2))
    with _lock:
        _cfg = Config()
        _agent = _new_agent(getattr(_agent, "mode", "chat"))
    status = _agent.mcp.status() if _agent.mcp else None
    return {"ok": True, "model": _cfg.model, "mcp_status": status}


@app.get("/api/state")
def state():
    return {
        "memory": _agent.memory.index(),
        "lessons": _agent.memory.lessons(),
        "skills": _agent.skills.index(),
        "model": _agent.cfg.model,
        "mode": getattr(_agent, "mode", "chat"),
        "usage": _usage(),
    }


PAGE = """<!doctype html>
<html lang="de"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TalosAI</title>
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
<style>
  :root{--bg:#f5f5f7;--card:#fff;--text:#1d1d1f;--muted:#86868b;--accent:#0071e3;
        --border:#e5e5ea;--chip:#f0f0f2;--nav:#ececf0;--radius:16px}
  @media(prefers-color-scheme:dark){:root{--bg:#000;--card:#1c1c1e;--text:#f5f5f7;
        --muted:#98989d;--accent:#0a84ff;--border:#2c2c2e;--chip:#2c2c2e;--nav:#141416}}
  *{box-sizing:border-box;margin:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Helvetica,Arial,sans-serif;
       background:var(--bg);color:var(--text);height:100vh;display:flex;overflow:hidden}

  /* ===== linke Navigation ===== */
  nav{width:230px;background:var(--nav);border-right:1px solid var(--border);padding:16px 12px;
      display:flex;flex-direction:column;gap:4px;flex-shrink:0}
  nav .logo{font-size:17px;font-weight:700;letter-spacing:-.02em;padding:4px 10px 14px}
  nav button{display:flex;align-items:center;gap:9px;width:100%;text-align:left;background:none;
      border:none;color:var(--text);padding:9px 10px;border-radius:10px;font-size:14px;cursor:pointer}
  nav button:hover{background:var(--chip)}
  nav button.active{background:var(--accent);color:#fff}
  nav .sect{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;
      letter-spacing:.05em;padding:16px 10px 6px}
  #history{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:2px}
  #history button{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;
      text-overflow:ellipsis;display:block}
  #history button.active{background:var(--chip);color:var(--text)}

  /* ===== Mitte: Chat ===== */
  main{flex:1;display:flex;flex-direction:column;max-width:800px;margin:0 auto;
       padding:18px 24px;height:100vh;min-width:0}
  header{display:flex;align-items:center;gap:10px;padding-bottom:6px}
  header h1{font-size:18px;font-weight:600}
  .badge{font-size:11px;color:var(--muted);background:var(--chip);padding:3px 10px;border-radius:10px}
  #chat{flex:1;overflow-y:auto;padding:12px 4px;display:flex;flex-direction:column;gap:10px}
  .msg{max-width:86%;padding:11px 15px;border-radius:var(--radius);line-height:1.55;
       font-size:15px;word-break:break-word;position:relative}
  .msg p{margin:0 0 8px}.msg p:last-child{margin:0}
  .msg pre{background:rgba(128,128,128,.12);padding:10px;border-radius:8px;overflow-x:auto;
       font-size:13px;margin:8px 0}
  .msg code{font-family:ui-monospace,Menlo,monospace;font-size:13px}
  .msg ul,.msg ol{padding-left:20px;margin:6px 0}
  .user{align-self:flex-end;background:var(--accent);color:#fff;border-bottom-right-radius:5px;
        white-space:pre-wrap}
  .bot{align-self:flex-start;background:var(--card);border-bottom-left-radius:5px;
       box-shadow:0 1px 2px rgba(0,0,0,.08)}
  .speakbtn{position:absolute;bottom:-22px;left:6px;background:none;border:none;cursor:pointer;
       font-size:13px;color:var(--muted);padding:2px}
  .tool{align-self:flex-start;font-size:12px;color:var(--muted);padding:2px 10px;
        background:var(--chip);border-radius:10px;max-width:86%;overflow:hidden;
        text-overflow:ellipsis;white-space:nowrap;animation:pop .2s ease}
  @keyframes pop{from{opacity:0;transform:translateY(4px)}to{opacity:1}}
  .typing{align-self:flex-start;color:var(--muted);font-size:14px;padding:4px 8px}
  .typing::after{content:'●●●';letter-spacing:3px;animation:blink 1.2s infinite}
  @keyframes blink{50%{opacity:.3}}
  #suggestions{display:flex;gap:8px;flex-wrap:wrap;padding:8px 0}
  #suggestions button{background:var(--chip);border:none;color:var(--text);padding:8px 14px;
        border-radius:16px;font-size:13px;cursor:pointer}
  form{display:flex;gap:8px;padding-top:10px;align-items:center}
  input[type=text]{flex:1;padding:13px 18px;border-radius:24px;border:1px solid var(--border);
        font-size:15px;background:var(--card);color:var(--text);outline:none;min-width:0}
  input[type=text]:focus{border-color:var(--accent)}
  .iconbtn{width:44px;height:44px;border:none;border-radius:50%;background:var(--chip);
        color:var(--text);font-size:18px;cursor:pointer;flex-shrink:0}
  .iconbtn.active{background:#ff3b30;color:#fff}
  .iconbtn.on{background:var(--accent);color:#fff}
  #send{width:auto;padding:0 20px;height:44px;border-radius:24px;background:var(--accent);
        color:#fff;font-size:15px;font-weight:500}
  #send:disabled{opacity:.4}

  /* ===== rechte Seite: Graph + Wissen + Verbrauch ===== */
  aside{width:340px;background:var(--card);border-left:1px solid var(--border);
        overflow-y:auto;display:flex;flex-direction:column;flex-shrink:0}
  #graphwrap{position:relative;background:#0d1526;height:240px;flex-shrink:0}
  #graph{width:100%;height:100%;display:block}
  #graphlabel{position:absolute;bottom:8px;left:12px;color:#4a5a78;font-size:11px}
  .asidebody{padding:16px 20px;display:flex;flex-direction:column;gap:6px}
  details{border-bottom:1px solid var(--border);padding:9px 0}
  summary{font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;
        letter-spacing:.05em;cursor:pointer;list-style:none;display:flex;gap:8px}
  summary::before{content:'›';transition:transform .15s}
  details[open] summary::before{transform:rotate(90deg)}
  details pre{font:12px/1.7 ui-monospace,Menlo,monospace;white-space:pre-wrap;
        word-break:break-word;padding-top:8px;color:var(--text)}

  /* Verbrauch im Claude-Code-Stil */
  #usagebox{background:var(--chip);border-radius:12px;padding:12px 14px;margin-top:10px;
        font:12px/1.8 ui-monospace,Menlo,monospace}
  #usagebox .row{display:flex;justify-content:space-between}
  #usagebox .row span:last-child{font-weight:600}
  #ctxbar{height:6px;background:rgba(128,128,128,.25);border-radius:3px;margin-top:6px;overflow:hidden}
  #ctxfill{height:100%;width:0%;background:#30d158;border-radius:3px;transition:width .4s}
  #ctxfill.warn{background:#ffd60a}#ctxfill.crit{background:#ff453a}
  /* ===== Obsidian-Wissensgraph (Vollbild-View) ===== */
  #knowview{display:none;flex:1;position:relative;background:#0d1526;border-radius:var(--radius);
        overflow:hidden;margin:8px 0}
  #knowview.show{display:block}
  #kcanvas{width:100%;height:100%;display:block;cursor:grab}
  #kdetail{position:absolute;top:14px;right:14px;width:280px;max-height:70%;overflow-y:auto;
        background:rgba(20,28,48,.92);border:1px solid #2a3a5c;border-radius:12px;padding:14px;
        color:#dce4f5;font-size:12.5px;line-height:1.6;display:none;backdrop-filter:blur(8px)}
  #kdetail h3{font-size:13px;margin-bottom:6px;color:#fff}
  #kdetail pre{white-space:pre-wrap;word-break:break-word;font:11.5px/1.6 ui-monospace,Menlo,monospace}
  #khint{position:absolute;bottom:10px;left:14px;color:#4a5a78;font-size:11px}
  body.knowledge #chat,body.knowledge #suggestions,body.knowledge #form{display:none}

  /* ===== Einstellungen ===== */
  #setview{display:none;flex:1;overflow-y:auto;padding:10px 4px}
  #setview.show{display:block}
  body.settings #chat,body.settings #suggestions,body.settings #form{display:none}
  .card{background:var(--card);border:1px solid var(--border);border-radius:14px;
        padding:18px;margin-bottom:14px}
  .card h2{font-size:15px;margin-bottom:12px}
  .card label{display:block;font-size:12px;color:var(--muted);margin:10px 0 4px}
  .card input[type=text],.card input[type=password],.card select,.card textarea{
        width:100%;padding:9px 12px;border-radius:9px;border:1px solid var(--border);
        background:var(--bg);color:var(--text);font-size:13px;outline:none;
        font-family:inherit}
  .card textarea{font-family:ui-monospace,Menlo,monospace;font-size:12px;min-height:110px}
  .row2{display:flex;gap:10px}.row2>div{flex:1}
  .btnrow{display:flex;gap:10px;margin-top:14px;align-items:center}
  .btn{background:var(--accent);color:#fff;border:none;border-radius:10px;
        padding:9px 18px;font-size:13px;font-weight:500;cursor:pointer}
  .btn.sec{background:var(--chip);color:var(--text)}
  .hint{font-size:11.5px;color:var(--muted);margin-top:6px;line-height:1.5}
  #savemsg{font-size:12.5px;color:#30d158}
  @media(max-width:1100px){aside{display:none}}
  @media(max-width:800px){nav{display:none}}
</style></head><body>

<nav>
  <div class="logo">◈ TalosAI</div>
  <button onclick="newSession()">＋ Neuer Chat</button>
  <div class="sect">Modus</div>
  <button id="mode-chat" onclick="setMode('chat')">💬 Chat</button>
  <button id="mode-coden" onclick="setMode('coden')">⌨️ Coden</button>
  <button id="mode-wissen" onclick="showKnowledge()">🕸 Wissen</button>
  <button id="mode-settings" onclick="showSettings()">⚙️ Einstellungen</button>
  <div class="sect">Verlauf</div>
  <div id="history"></div>
</nav>

<main>
  <header>
    <h1 id="modetitle">Chat</h1>
    <span class="badge" id="model"></span>
  </header>
  <div id="knowview">
    <canvas id="kcanvas"></canvas>
    <div id="kdetail"></div>
    <span id="khint">Ziehen: Knoten bewegen · Scrollen: Zoom · Klick: Details</span>
  </div>
  <div id="setview">
    <div class="card">
      <h2>🤖 LLM-Provider</h2>
      <div class="row2">
        <div><label>Aktiver Provider</label><select id="s-active"></select></div>
        <div><label>Neu anlegen aus Vorlage</label><select id="s-preset">
          <option value="">– Vorlage wählen –</option></select></div>
      </div>
      <div class="row2">
        <div><label>Name</label><input type="text" id="s-name"></div>
        <div><label>Base-URL (OpenAI-kompatibel)</label><input type="text" id="s-url"></div>
      </div>
      <label>API-Key</label><input type="password" id="s-key">
      <div class="row2">
        <div><label>Modell</label><input type="text" id="s-model"></div>
        <div><label>Kleines Modell (Reflexion/Verifier)</label><input type="text" id="s-small"></div>
      </div>
      <div class="btnrow"><button class="btn sec" onclick="saveProvider()">Provider speichern</button>
        <button class="btn sec" onclick="deleteProvider()">Löschen</button></div>
      <div class="hint">Funktioniert mit jeder OpenAI-kompatiblen API: Anthropic, OpenAI,
        OpenRouter, Groq, BytePlus ModelArk — oder 100&nbsp;% lokal mit Ollama/vLLM.</div>
    </div>
    <div class="card">
      <h2>🗣 Sprachausgabe (ElevenLabs)</h2>
      <div class="row2">
        <div><label>API-Key</label><input type="password" id="s-elkey"></div>
        <div><label>Voice-ID</label><input type="text" id="s-elvoice"></div>
      </div>
      <div class="hint">Leer lassen = Browser-Stimme. Key: elevenlabs.io → Profil → API Keys.</div>
    </div>
    <div class="card">
      <h2>✅ Ehrlichkeits-Verifier</h2>
      <label><input type="checkbox" id="s-verify"> Antworten nach Tool-Nutzung gegen
        die Tool-Ergebnisse prüfen (empfohlen)</label>
    </div>
    <div class="card">
      <h2>🔌 MCP-Server</h2>
      <label>Konfiguration (JSON-Liste)</label>
      <textarea id="s-mcp" placeholder='[{"name":"files","command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","/Users/du/Dokumente"]}]'></textarea>
      <div class="hint" id="s-mcpstatus">Beispiele: Dateisystem (npx @modelcontextprotocol/server-filesystem),
        Web (uvx mcp-server-fetch), oder jede URL eines Remote-MCP-Servers via {"name":"x","url":"https://…"}.</div>
    </div>
    <div class="btnrow"><button class="btn" onclick="saveSettings()">Alles speichern &amp; neu laden</button>
      <span id="savemsg"></span></div>
  </div>
  <div id="chat"></div>
  <div id="suggestions">
    <button>Was weißt du über mich?</button>
    <button>Recherchiere die wichtigsten KI-News von heute</button>
    <button>Welche Skills hast du schon gelernt?</button>
  </div>
  <form id="form">
    <button type="button" class="iconbtn" id="mic" title="Spracheingabe">🎤</button>
    <input type="text" id="inp" placeholder="Nachricht an Talos…" autocomplete="off" autofocus>
    <button type="button" class="iconbtn" id="tts" title="Antworten automatisch vorlesen">🔊</button>
    <button id="send" class="iconbtn">Senden</button>
  </form>
</main>

<aside>
  <div id="graphwrap"><canvas id="graph"></canvas><span id="graphlabel">Agenten-Aktivität</span></div>
  <div class="asidebody">
    <details open><summary>🧠 Gedächtnis</summary><pre id="memory">–</pre></details>
    <details><summary>📚 Lektionen</summary><pre id="lessons">–</pre></details>
    <details><summary>⚡ Skills</summary><pre id="skills">–</pre></details>
    <div id="usagebox">
      <div class="row"><span>Session-Kosten</span><span id="u-cost">$0.0000</span></div>
      <div class="row"><span>Tokens ein</span><span id="u-in">0</span></div>
      <div class="row"><span>Tokens aus</span><span id="u-out">0</span></div>
      <div class="row"><span>Kontext</span><span id="u-ctx">0%</span></div>
      <div id="ctxbar"><div id="ctxfill"></div></div>
    </div>
  </div>
</aside>

<script>
const chat=document.getElementById('chat'),inp=document.getElementById('inp'),
      send=document.getElementById('send'),sugg=document.getElementById('suggestions');
let mode='chat';

function el(cls,html){const d=document.createElement('div');d.className=cls;
  if(html!==undefined)d.innerHTML=html;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d}
function addUser(t){const d=el('msg user');d.textContent=t}
function addBot(t){const d=el('msg bot',marked.parse(t));
  const b=document.createElement('button');b.className='speakbtn';b.textContent='🔊';
  b.title='Vorlesen';b.onclick=()=>speak(t,true);d.appendChild(b)}
function addTool(t){el('tool','⚙ '+t.name+(t.detail?': '+t.detail:''))}

// ===== Verbrauch (Claude-Code-Stil) =====
function updateUsage(u){if(!u)return;
  document.getElementById('u-cost').textContent='$'+u.cost.toFixed(4);
  document.getElementById('u-in').textContent=u.input.toLocaleString('de-DE');
  document.getElementById('u-out').textContent=u.output.toLocaleString('de-DE');
  const pct=Math.min(100,Math.round(u.context/u.window*100));
  document.getElementById('u-ctx').textContent=
    pct+'% ('+(u.context/1000).toFixed(1)+'k / '+(u.window/1000)+'k)';
  const f=document.getElementById('ctxfill');f.style.width=pct+'%';
  f.className=pct>80?'crit':pct>50?'warn':''}

// ===== Sprachausgabe: ElevenLabs, Fallback Browser-Stimme =====
let ttsOn=false,voices=[],audioEl=null;
function loadVoices(){voices=speechSynthesis.getVoices()}
loadVoices();speechSynthesis.onvoiceschanged=loadVoices;
const ttsBtn=document.getElementById('tts');
ttsBtn.onclick=()=>{ttsOn=!ttsOn;ttsBtn.classList.toggle('on',ttsOn);
  if(ttsOn){speak('Sprachausgabe aktiviert.',true)}else{stopSpeaking()}};
function stopSpeaking(){speechSynthesis.cancel();
  if(audioEl){audioEl.pause();audioEl=null}}
function plainText(text){return text.replace(/```[\\s\\S]*?```/g,' Codeblock. ')
  .replace(/`[^`]*`/g,'').replace(/\\[(.*?)\\]\\([^)]*\\)/g,'$1')
  .replace(/[*_#>|]/g,'').replace(/\\s+/g,' ').trim()}
async function speak(text,force){
  if(!ttsOn&&!force)return;
  stopSpeaking();
  const plain=plainText(text);if(!plain)return;
  // 1. Versuch: ElevenLabs über den Server
  try{
    const r=await fetch('/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text:plain})});
    if(r.ok&&(r.headers.get('content-type')||'').includes('audio')){
      audioEl=new Audio(URL.createObjectURL(await r.blob()));audioEl.play();return}
  }catch(e){}
  // 2. Fallback: Browser-Stimme (in Sätzen — lange Utterances brechen ab)
  const voice=voices.find(v=>v.lang==='de-DE')||voices.find(v=>v.lang.startsWith('de'));
  const parts=plain.match(/[^.!?]+[.!?]*/g)||[plain];
  for(const p of parts){const u=new SpeechSynthesisUtterance(p.trim());
    u.lang='de-DE';u.rate=1.05;if(voice)u.voice=voice;speechSynthesis.speak(u)}
  clearInterval(window._ttsKick);
  window._ttsKick=setInterval(()=>{if(!speechSynthesis.speaking)clearInterval(window._ttsKick);
    else{speechSynthesis.pause();speechSynthesis.resume()}},10000)}

// ===== Spracheingabe (Mikrofon) =====
const micBtn=document.getElementById('mic');
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
if(!SR){micBtn.style.display='none'}
else{const rec=new SR();rec.lang='de-DE';rec.interimResults=true;let listening=false;
  micBtn.onclick=()=>{if(listening){rec.stop();return}
    rec.start();listening=true;micBtn.classList.add('active');micBtn.textContent='⏹'};
  rec.onresult=e=>{inp.value=Array.from(e.results).map(r=>r[0].transcript).join('')};
  rec.onend=()=>{listening=false;micBtn.classList.remove('active');micBtn.textContent='🎤';
    if(inp.value.trim())document.getElementById('form').requestSubmit()};
  rec.onerror=()=>{listening=false;micBtn.classList.remove('active');micBtn.textContent='🎤'}}

// ===== Live-Aktivitätsgraph (rechte Seite) =====
const cv=document.getElementById('graph'),gctx=cv.getContext('2d');
function gsize(){cv.width=cv.clientWidth*devicePixelRatio;cv.height=cv.clientHeight*devicePixelRatio;
  gctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0)}
addEventListener('resize',gsize);
const COLORS={talos:'#ffffff',delegate:'#7aa2ff',web_search:'#5ac8fa',web_fetch:'#5ac8fa',
  shell:'#ffd60a',memory_save:'#bf5af2',memory_read:'#bf5af2',skill_save:'#30d158',
  skill_read:'#30d158',default:'#98989d'};
let gnodes=[],gedges=[],ambient=[],hub=null,busy=false;
function initGraph(){const W=cv.clientWidth,H=cv.clientHeight;
  ambient=Array.from({length:50},()=>({x:Math.random()*W,y:Math.random()*H,
    r:.8+Math.random()*1.3,tw:Math.random()*6.28}));
  gnodes=[{id:'talos',label:'Talos',x:W/2,y:H/2,tx:W/2,ty:H/2,r:7,color:COLORS.talos,
    born:0,perm:true}];gedges=[];hub=gnodes[0]}
function addGraphNode(name){const W=cv.clientWidth,H=cv.clientHeight,now=performance.now();
  const parent=(name==='delegate')?gnodes[0]:hub;
  const ang=Math.random()*6.28,dist=38+Math.random()*36;
  const n={id:name+now,label:name,x:parent.x,y:parent.y,
    tx:Math.min(W-16,Math.max(16,parent.x+Math.cos(ang)*dist)),
    ty:Math.min(H-14,Math.max(14,parent.y+Math.sin(ang)*dist)),
    r:name==='delegate'?5.5:3.5,color:COLORS[name]||COLORS.default,born:now,perm:false};
  gnodes.push(n);gedges.push({a:parent,b:n,born:now});
  if(name==='delegate')hub=n;
  if(gnodes.length>50){gnodes.splice(1,1);gedges.splice(0,1)}}
function drawGraph(t){const W=cv.clientWidth,H=cv.clientHeight;
  gctx.clearRect(0,0,W,H);
  for(const a of ambient){const tw=.25+.2*Math.sin(t/900+a.tw);
    gctx.fillStyle='rgba(180,195,225,'+tw+')';
    gctx.beginPath();gctx.arc(a.x,a.y,a.r,0,6.28);gctx.fill()}
  for(const e of gedges){const age=(t-e.born)/1000,alpha=Math.min(.5,age*2)*(busy?1:.55);
    gctx.strokeStyle='rgba(120,150,210,'+alpha+')';gctx.lineWidth=.7;
    gctx.beginPath();gctx.moveTo(e.a.x,e.a.y);gctx.lineTo(e.b.x,e.b.y);gctx.stroke()}
  for(const n of gnodes){n.x+=(n.tx-n.x)*.08;n.y+=(n.ty-n.y)*.08;
    const age=(t-n.born)/1000;let r=n.r;
    if(n.perm&&busy)r=n.r+1.6*Math.sin(t/280);else if(age<.5)r=n.r*(age*2);
    gctx.fillStyle=n.color;gctx.shadowColor=n.color;gctx.shadowBlur=n.perm||age<2?10:4;
    gctx.beginPath();gctx.arc(n.x,n.y,Math.max(r,0),0,6.28);gctx.fill();gctx.shadowBlur=0;
    if(n.perm||age<6){gctx.fillStyle='rgba(160,180,215,'+(n.perm?.9:Math.max(0,1-age/6))+')';
      gctx.font='10px -apple-system';gctx.fillText(n.label,n.x+8,n.y+3)}}
  requestAnimationFrame(drawGraph)}
gsize();initGraph();requestAnimationFrame(drawGraph);

// ===== Obsidian-Wissensgraph =====
const kview=document.getElementById('knowview'),kcv=document.getElementById('kcanvas'),
      kctx=kcv.getContext('2d'),kdetail=document.getElementById('kdetail');
const KCOLORS={hub:'#ffffff',memory:'#bf5af2',skill:'#30d158',lesson:'#ff9f0a'};
let knodes=[],klinks=[],kcam={x:0,y:0,z:1},kdrag=null,kpan=null,kactive=false;
function ksize(){kcv.width=kcv.clientWidth*devicePixelRatio;kcv.height=kcv.clientHeight*devicePixelRatio}
async function loadKnowledge(){
  const d=await (await fetch('/api/graph')).json();
  const W=kcv.clientWidth,H=kcv.clientHeight;
  knodes=d.nodes.map(n=>({...n,
    x:W/2+(Math.random()-.5)*W*.6,y:H/2+(Math.random()-.5)*H*.6,vx:0,vy:0,
    r:n.type==='hub'?(n.id==='talos'?10:7):5,color:KCOLORS[n.type]||'#98989d'}));
  const byId=Object.fromEntries(knodes.map(n=>[n.id,n]));
  klinks=d.links.map(l=>({a:byId[l.a],b:byId[l.b]})).filter(l=>l.a&&l.b);
  const t=byId['talos'];if(t){t.x=W/2;t.y=H/2}}
function kstep(){
  // Abstoßung zwischen allen Knoten
  for(let i=0;i<knodes.length;i++)for(let j=i+1;j<knodes.length;j++){
    const a=knodes[i],b=knodes[j];let dx=b.x-a.x,dy=b.y-a.y;
    let d2=dx*dx+dy*dy;if(d2<1)d2=1;const d=Math.sqrt(d2);
    const f=Math.min(1200/d2,4);dx/=d;dy/=d;
    a.vx-=dx*f;a.vy-=dy*f;b.vx+=dx*f;b.vy+=dy*f}
  // Federn entlang der Kanten
  for(const l of klinks){let dx=l.b.x-l.a.x,dy=l.b.y-l.a.y;
    const d=Math.sqrt(dx*dx+dy*dy)||1,f=(d-70)*.01;dx/=d;dy/=d;
    l.a.vx+=dx*f*d*.02;l.a.vy+=dy*f*d*.02;l.b.vx-=dx*f*d*.02;l.b.vy-=dy*f*d*.02}
  // leichte Zentrierung + Dämpfung
  const W=kcv.clientWidth,H=kcv.clientHeight;
  for(const n of knodes){
    n.vx+=(W/2-n.x)*.0006;n.vy+=(H/2-n.y)*.0006;
    if(kdrag!==n){n.x+=n.vx*=.85;n.y+=n.vy*=.85}}}
function kdraw(){
  if(!kactive)return;
  kstep();
  const dpr=devicePixelRatio,W=kcv.clientWidth,H=kcv.clientHeight;
  kctx.setTransform(dpr,0,0,dpr,0,0);kctx.clearRect(0,0,W,H);
  kctx.setTransform(dpr*kcam.z,0,0,dpr*kcam.z,dpr*kcam.x,dpr*kcam.y);
  for(const l of klinks){kctx.strokeStyle='rgba(120,150,210,.35)';kctx.lineWidth=.8/kcam.z;
    kctx.beginPath();kctx.moveTo(l.a.x,l.a.y);kctx.lineTo(l.b.x,l.b.y);kctx.stroke()}
  for(const n of knodes){
    kctx.fillStyle=n.color;kctx.shadowColor=n.color;kctx.shadowBlur=n.type==='hub'?12:5;
    kctx.beginPath();kctx.arc(n.x,n.y,n.r,0,6.28);kctx.fill();kctx.shadowBlur=0;
    if(kcam.z>0.55||n.type==='hub'){
      kctx.fillStyle='rgba(190,205,235,.85)';kctx.font=(n.type==='hub'?11:9.5)+'px -apple-system';
      kctx.fillText(n.label,n.x+n.r+3,n.y+3)}}
  requestAnimationFrame(kdraw)}
function kpos(e){const rect=kcv.getBoundingClientRect();
  return {x:(e.clientX-rect.left-kcam.x)/kcam.z,y:(e.clientY-rect.top-kcam.y)/kcam.z}}
function kfind(p){return knodes.find(n=>{const dx=n.x-p.x,dy=n.y-p.y;
  return dx*dx+dy*dy<(n.r+6)*(n.r+6)})}
kcv.addEventListener('mousedown',e=>{const p=kpos(e),n=kfind(p);
  if(n){kdrag=n;kdrag._moved=false}else{kpan={x:e.clientX-kcam.x,y:e.clientY-kcam.y}}});
addEventListener('mousemove',e=>{
  if(kdrag){const p=kpos(e);kdrag.x=p.x;kdrag.y=p.y;kdrag.vx=kdrag.vy=0;kdrag._moved=true}
  else if(kpan){kcam.x=e.clientX-kpan.x;kcam.y=e.clientY-kpan.y}});
addEventListener('mouseup',e=>{
  if(kdrag&&!kdrag._moved){
    kdetail.style.display='block';
    kdetail.innerHTML='<h3>'+kdrag.label+'</h3><pre>'+
      (kdrag.content||'('+kdrag.type+')').replace(/</g,'&lt;')+'</pre>'}
  kdrag=null;kpan=null});
kcv.addEventListener('wheel',e=>{e.preventDefault();
  const f=e.deltaY<0?1.1:0.9,rect=kcv.getBoundingClientRect(),
        mx=e.clientX-rect.left,my=e.clientY-rect.top;
  kcam.x=mx-(mx-kcam.x)*f;kcam.y=my-(my-kcam.y)*f;kcam.z*=f},{passive:false});
async function showKnowledge(){
  hideSettings();
  document.body.classList.add('knowledge');kview.classList.add('show');
  document.getElementById('modetitle').textContent='Wissen';
  document.getElementById('mode-wissen').classList.add('active');
  document.getElementById('mode-chat').classList.remove('active');
  document.getElementById('mode-coden').classList.remove('active');
  ksize();kcam={x:0,y:0,z:1};kdetail.style.display='none';
  await loadKnowledge();
  if(!kactive){kactive=true;requestAnimationFrame(kdraw)}}
function hideKnowledge(){document.body.classList.remove('knowledge');
  kview.classList.remove('show');kactive=false;
  document.getElementById('mode-wissen').classList.remove('active')}
addEventListener('resize',()=>{if(kactive)ksize()});

// ===== Einstellungen =====
const setview=document.getElementById('setview');
const PRESETS={
 'Anthropic':{base_url:'https://api.anthropic.com/v1/',model:'claude-opus-4-8',small_model:'claude-haiku-4-5'},
 'OpenAI':{base_url:'https://api.openai.com/v1',model:'gpt-4o',small_model:'gpt-4o-mini'},
 'OpenRouter':{base_url:'https://openrouter.ai/api/v1',model:'anthropic/claude-sonnet-4.6',small_model:'meta-llama/llama-3.3-70b-instruct'},
 'Groq':{base_url:'https://api.groq.com/openai/v1',model:'llama-3.3-70b-versatile',small_model:'llama-3.1-8b-instant'},
 'BytePlus ModelArk':{base_url:'https://ark.ap-southeast.bytepluses.com/api/v3',model:'kimi-k2-250905',small_model:''},
 'Ollama (lokal)':{base_url:'http://localhost:11434/v1',model:'qwen3:14b',small_model:'qwen3:4b',api_key:'none'},
 'vLLM (lokal)':{base_url:'http://localhost:8000/v1',model:'',small_model:'',api_key:'none'}};
let SETTINGS=null;
const $=id=>document.getElementById(id);
function fillProviderForm(name){
  const p=SETTINGS.providers.find(x=>x.name===name);if(!p)return;
  $('s-name').value=p.name;$('s-url').value=p.base_url||'';
  $('s-key').value=p.api_key||'';$('s-model').value=p.model||'';
  $('s-small').value=p.small_model||''}
function renderProviders(){
  const sel=$('s-active');sel.innerHTML='';
  for(const p of SETTINGS.providers){const o=document.createElement('option');
    o.value=p.name;o.textContent=p.name;sel.appendChild(o)}
  sel.value=SETTINGS.active_provider;fillProviderForm(sel.value)}
async function showSettings(){
  hideKnowledge();document.body.classList.add('settings');setview.classList.add('show');
  $('modetitle').textContent='Einstellungen';
  $('mode-settings').classList.add('active');
  $('mode-chat').classList.remove('active');$('mode-coden').classList.remove('active');
  SETTINGS=await (await fetch('/api/settings')).json();
  const ps=$('s-preset');ps.innerHTML='<option value="">– Vorlage wählen –</option>';
  for(const k of Object.keys(PRESETS)){const o=document.createElement('option');
    o.value=k;o.textContent=k;ps.appendChild(o)}
  renderProviders();
  $('s-elkey').value=SETTINGS.eleven_key||'';$('s-elvoice').value=SETTINGS.eleven_voice||'';
  $('s-verify').checked=!!SETTINGS.verify;
  $('s-mcp').value=SETTINGS.mcp_servers.length?JSON.stringify(SETTINGS.mcp_servers,null,1):'';
  if(SETTINGS.mcp_status){const st=SETTINGS.mcp_status;
    $('s-mcpstatus').textContent='Verbunden: '+st.servers.join(', ')+' ('+st.tools+' Tools)'+
      (Object.keys(st.errors).length?' — Fehler: '+JSON.stringify(st.errors):'')}}
function hideSettings(){document.body.classList.remove('settings');
  setview.classList.remove('show');$('mode-settings').classList.remove('active')}
$('s-active').addEventListener('change',e=>{SETTINGS.active_provider=e.target.value;
  fillProviderForm(e.target.value)});
$('s-preset').addEventListener('change',e=>{const p=PRESETS[e.target.value];if(!p)return;
  $('s-name').value=e.target.value;$('s-url').value=p.base_url;
  $('s-key').value=p.api_key||'';$('s-model').value=p.model;$('s-small').value=p.small_model||''});
function saveProvider(){
  const p={name:$('s-name').value.trim(),base_url:$('s-url').value.trim(),
    api_key:$('s-key').value.trim(),model:$('s-model').value.trim(),
    small_model:$('s-small').value.trim()};
  if(!p.name||!p.base_url)return;
  const i=SETTINGS.providers.findIndex(x=>x.name===p.name);
  if(i>=0)SETTINGS.providers[i]=p;else SETTINGS.providers.push(p);
  SETTINGS.active_provider=p.name;renderProviders();
  $('savemsg').textContent='Provider gemerkt — unten "Alles speichern" klicken.'}
function deleteProvider(){
  SETTINGS.providers=SETTINGS.providers.filter(x=>x.name!==$('s-name').value.trim());
  if(SETTINGS.providers.length)SETTINGS.active_provider=SETTINGS.providers[0].name;
  renderProviders()}
async function saveSettings(){
  let mcp=[];const raw=$('s-mcp').value.trim();
  if(raw){try{mcp=JSON.parse(raw)}catch(e){$('savemsg').textContent='MCP-JSON ungültig: '+e;return}}
  SETTINGS.eleven_key=$('s-elkey').value.trim();
  SETTINGS.eleven_voice=$('s-elvoice').value.trim();
  SETTINGS.verify=$('s-verify').checked;SETTINGS.mcp_servers=mcp;
  const r=await (await fetch('/api/settings',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(SETTINGS)})).json();
  $('savemsg').textContent='Gespeichert ✓ Modell: '+r.model+
    (r.mcp_status?' · MCP: '+r.mcp_status.tools+' Tools':'');
  refreshState()}

// ===== Sessions / Verlauf / Modus =====
async function refreshSessions(){const s=await (await fetch('/api/sessions')).json();
  const h=document.getElementById('history');h.innerHTML='';
  for(const sess of s.sessions){const b=document.createElement('button');
    b.textContent=(sess.mode==='coden'?'⌨️ ':'')+sess.title;
    if(sess.id===s.current)b.className='active';
    b.onclick=()=>loadSession(sess.id);h.appendChild(b)}}
function setModeUI(){document.getElementById('mode-chat').classList.toggle('active',mode==='chat');
  document.getElementById('mode-coden').classList.toggle('active',mode==='coden');
  document.getElementById('modetitle').textContent=mode==='coden'?'Coden':'Chat';
  inp.placeholder=mode==='coden'?'Was soll ich bauen?':'Nachricht an Talos…'}
async function setMode(m){hideKnowledge();hideSettings();mode=m;await newSession()}
async function newSession(){hideKnowledge();hideSettings();await fetch('/api/session/new',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});
  chat.innerHTML='';sugg.style.display='flex';initGraph();setModeUI();
  refreshSessions();refreshState()}
async function loadSession(id){hideKnowledge();hideSettings();const r=await (await fetch('/api/session/load',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({id,mode})})).json();
  if(r.error)return;chat.innerHTML='';sugg.style.display='none';initGraph();
  for(const m of r.history){m.role==='user'?addUser(m.text):addBot(m.text)}
  refreshSessions();refreshState()}

async function refreshState(){const s=await (await fetch('/api/state')).json();
  document.getElementById('memory').textContent=s.memory||'(leer)';
  document.getElementById('lessons').textContent=s.lessons||'(keine)';
  document.getElementById('skills').textContent=s.skills||'(keine)';
  document.getElementById('model').textContent=s.model;
  mode=s.mode||'chat';setModeUI();updateUsage(s.usage)}

// ===== Chat mit Live-Streaming =====
async function sendMessage(text){
  addUser(text);sugg.style.display='none';send.disabled=true;
  busy=true;hub=gnodes[0];
  const typing=el('typing');
  try{
    const resp=await fetch('/api/chat/stream',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
    const reader=resp.body.getReader(),dec=new TextDecoder();let buf='';
    while(true){const {done,value}=await reader.read();if(done)break;
      buf+=dec.decode(value,{stream:true});
      let idx;while((idx=buf.indexOf('\\n\\n'))>=0){
        const line=buf.slice(0,idx).trim();buf=buf.slice(idx+2);
        if(!line.startsWith('data: '))continue;
        const ev=JSON.parse(line.slice(6));
        if(ev.type==='tool'){addTool(ev);addGraphNode(ev.name)}
        else if(ev.type==='reply'){typing.remove();addBot(ev.text);speak(ev.text);
          updateUsage(ev.usage)}}}
  }catch(err){typing.remove();addBot('**Fehler:** '+err)}
  busy=false;hub=gnodes[0];
  send.disabled=false;inp.focus();refreshSessions()}

document.getElementById('form').onsubmit=e=>{e.preventDefault();
  const t=inp.value.trim();if(t){inp.value='';sendMessage(t)}};
sugg.querySelectorAll('button').forEach(b=>b.onclick=()=>sendMessage(b.textContent));
refreshState();refreshSessions();
</script></body></html>"""


@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(PAGE)


def main() -> None:
    import uvicorn

    host = os.getenv("TALOS_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("TALOS_WEB_PORT", "7777"))
    if host != "127.0.0.1" and not _WEB_PASSWORD:
        raise SystemExit(
            "SICHERHEIT: Öffentlicher Host ohne TALOS_WEB_PASSWORD verweigert. "
            "Setze TALOS_WEB_PASSWORD, bevor du das Dashboard nach außen öffnest."
        )
    where = f"http://{host}:{port}" if host != "127.0.0.1" else f"http://localhost:{port}"
    print(f"TalosAI Dashboard: {where}" + ("  (passwortgeschützt)" if _WEB_PASSWORD else ""))
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
