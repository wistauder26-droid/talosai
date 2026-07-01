"""Lokales Dashboard: Chat mit Talos + Live-Blick in Memory, Lektionen, Skills.

Start: `talos-web`, dann http://localhost:7777
Single-User, nur für localhost gedacht. Features: Live-Streaming der
Tool-Aufrufe, Markdown, Dark Mode, Token-Zähler, Voice-Ein-/Ausgabe.
"""

from __future__ import annotations

import json
import queue
import threading

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .agent import Agent
from .learning import reflect

app = FastAPI(title="TalosAI")
_agent = Agent(session_id="web")
_lock = threading.Lock()  # ein Agent, eine Anfrage zur Zeit


class ChatIn(BaseModel):
    message: str


def _usage() -> dict:
    return {
        "input": _agent.llm.total_input_tokens,
        "output": _agent.llm.total_output_tokens,
    }


@app.post("/api/chat/stream")
def chat_stream(body: ChatIn):
    """Streamt Tool-Events live, dann die finale Antwort (SSE-Format)."""
    q: queue.Queue = queue.Queue()

    def worker() -> None:
        with _lock:
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


@app.post("/api/reset")
def reset():
    global _agent
    with _lock:
        lessons = reflect(_agent)
        _agent = Agent(session_id="web")
    return {"lessons": lessons}


@app.get("/api/state")
def state():
    return {
        "memory": _agent.memory.index(),
        "lessons": _agent.memory.lessons(),
        "skills": _agent.skills.index(),
        "model": _agent.cfg.model,
        "usage": _usage(),
    }


PAGE = """<!doctype html>
<html lang="de"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TalosAI</title>
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
<style>
  :root{--bg:#f5f5f7;--card:#fff;--text:#1d1d1f;--muted:#86868b;--accent:#0071e3;
        --border:#e5e5ea;--chip:#f0f0f2;--radius:16px}
  @media(prefers-color-scheme:dark){:root{--bg:#000;--card:#1c1c1e;--text:#f5f5f7;
        --muted:#98989d;--accent:#0a84ff;--border:#2c2c2e;--chip:#2c2c2e}}
  *{box-sizing:border-box;margin:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Helvetica,Arial,sans-serif;
       background:var(--bg);color:var(--text);height:100vh;display:flex}
  main{flex:1;display:flex;flex-direction:column;max-width:820px;margin:0 auto;
       padding:20px 24px;height:100vh}
  header{display:flex;align-items:center;gap:12px;padding-bottom:8px}
  header h1{font-size:20px;font-weight:600;letter-spacing:-.02em}
  .badge{font-size:11px;color:var(--muted);background:var(--chip);padding:3px 10px;
         border-radius:10px}
  #usage{margin-left:auto}
  #chat{flex:1;overflow-y:auto;padding:14px 4px;display:flex;flex-direction:column;gap:10px}
  .msg{max-width:84%;padding:11px 15px;border-radius:var(--radius);line-height:1.55;
       font-size:15px;word-break:break-word}
  .msg p{margin:0 0 8px}.msg p:last-child{margin:0}
  .msg pre{background:rgba(128,128,128,.12);padding:10px;border-radius:8px;overflow-x:auto;
       font-size:13px;margin:8px 0}
  .msg code{font-family:ui-monospace,Menlo,monospace;font-size:13px}
  .msg ul,.msg ol{padding-left:20px;margin:6px 0}
  .user{align-self:flex-end;background:var(--accent);color:#fff;border-bottom-right-radius:5px;
        white-space:pre-wrap}
  .bot{align-self:flex-start;background:var(--card);border-bottom-left-radius:5px;
       box-shadow:0 1px 2px rgba(0,0,0,.08)}
  .tool{align-self:flex-start;font-size:12px;color:var(--muted);padding:2px 8px;
        background:var(--chip);border-radius:10px;max-width:84%;overflow:hidden;
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
        font-size:15px;background:var(--card);color:var(--text);outline:none}
  input[type=text]:focus{border-color:var(--accent)}
  .iconbtn{width:44px;height:44px;border:none;border-radius:50%;background:var(--chip);
        color:var(--text);font-size:18px;cursor:pointer;flex-shrink:0}
  .iconbtn.active{background:#ff3b30;color:#fff}
  .iconbtn.on{background:var(--accent);color:#fff}
  #send{width:auto;padding:0 22px;height:44px;border-radius:24px;background:var(--accent);
        color:#fff;font-size:15px;font-weight:500}
  #send:disabled{opacity:.4}
  aside{width:330px;background:var(--card);border-left:1px solid var(--border);padding:20px;
        overflow-y:auto;display:flex;flex-direction:column;gap:8px}
  details{border-bottom:1px solid var(--border);padding:10px 0}
  summary{font-size:13px;font-weight:600;color:var(--muted);text-transform:uppercase;
        letter-spacing:.05em;cursor:pointer;list-style:none;display:flex;gap:8px}
  summary::before{content:'›';transition:transform .15s}
  details[open] summary::before{transform:rotate(90deg)}
  details pre{font:12px/1.7 ui-monospace,Menlo,monospace;white-space:pre-wrap;
        word-break:break-word;padding-top:8px;color:var(--text)}
  .reset{background:none;border:1px solid var(--border);color:var(--text);border-radius:12px;
        padding:9px;font-size:13px;cursor:pointer;margin-top:12px}
  @media(max-width:920px){aside{display:none}}
</style></head><body>
<main>
  <header>
    <h1>◈ TalosAI</h1>
    <span class="badge" id="model"></span>
    <span class="badge" id="usage">0 Tokens</span>
  </header>
  <div id="chat"></div>
  <div id="suggestions">
    <button>Was weißt du über mich?</button>
    <button>Recherchiere die wichtigsten KI-News von heute</button>
    <button>Welche Skills hast du schon gelernt?</button>
  </div>
  <form id="form">
    <button type="button" class="iconbtn" id="mic" title="Spracheingabe">🎤</button>
    <input type="text" id="inp" placeholder="Nachricht an Talos…" autocomplete="off" autofocus>
    <button type="button" class="iconbtn" id="tts" title="Antworten vorlesen">🔊</button>
    <button id="send" class="iconbtn">Senden</button>
  </form>
</main>
<aside>
  <details open><summary>🧠 Gedächtnis</summary><pre id="memory">–</pre></details>
  <details open><summary>📚 Lektionen</summary><pre id="lessons">–</pre></details>
  <details open><summary>⚡ Skills</summary><pre id="skills">–</pre></details>
  <button class="reset" onclick="resetSession()">Session beenden &amp; reflektieren</button>
</aside>
<script>
const chat=document.getElementById('chat'),inp=document.getElementById('inp'),
      send=document.getElementById('send'),sugg=document.getElementById('suggestions');

function el(cls,html){const d=document.createElement('div');d.className=cls;
  if(html!==undefined)d.innerHTML=html;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d}
function addUser(t){const d=el('msg user');d.textContent=t}
function addBot(t){el('msg bot',marked.parse(t))}
function addTool(t){el('tool','⚙ '+t.name+(t.detail?': '+t.detail:''))}

async function refreshState(){const s=await (await fetch('/api/state')).json();
  document.getElementById('memory').textContent=s.memory||'(leer)';
  document.getElementById('lessons').textContent=s.lessons||'(keine)';
  document.getElementById('skills').textContent=s.skills||'(keine)';
  document.getElementById('model').textContent=s.model;
  updateUsage(s.usage)}
function updateUsage(u){if(!u)return;
  document.getElementById('usage').textContent=
    (u.input+u.output).toLocaleString('de-DE')+' Tokens ('+u.input.toLocaleString('de-DE')+' ein / '
    +u.output.toLocaleString('de-DE')+' aus)'}

// ===== Sprachausgabe (TTS) =====
let ttsOn=false;
const ttsBtn=document.getElementById('tts');
ttsBtn.onclick=()=>{ttsOn=!ttsOn;ttsBtn.classList.toggle('on',ttsOn);
  if(!ttsOn)speechSynthesis.cancel()};
function speak(text){if(!ttsOn)return;
  const plain=text.replace(/```[\\s\\S]*?```/g,' Codeblock. ').replace(/[*_#`>|-]/g,'')
                  .replace(/\\[(.*?)\\]\\(.*?\\)/g,'$1');
  const u=new SpeechSynthesisUtterance(plain);u.lang='de-DE';u.rate=1.05;
  const v=speechSynthesis.getVoices().find(v=>v.lang.startsWith('de'));if(v)u.voice=v;
  speechSynthesis.cancel();speechSynthesis.speak(u)}

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

// ===== Chat mit Live-Streaming =====
async function sendMessage(text){
  addUser(text);sugg.style.display='none';send.disabled=true;
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
        if(ev.type==='tool')addTool(ev);
        else if(ev.type==='reply'){typing.remove();addBot(ev.text);speak(ev.text);
          updateUsage(ev.usage)}}}
  }catch(err){typing.remove();addBot('**Fehler:** '+err)}
  send.disabled=false;inp.focus();refreshState()}

document.getElementById('form').onsubmit=e=>{e.preventDefault();
  const t=inp.value.trim();if(t){inp.value='';sendMessage(t)}};
sugg.querySelectorAll('button').forEach(b=>b.onclick=()=>sendMessage(b.textContent));
async function resetSession(){const r=await (await fetch('/api/reset',{method:'POST'})).json();
  addBot('*Neue Session gestartet.* '+(r.lessons&&r.lessons.length?'**Gelernt:** '+r.lessons.join('; '):''));
  refreshState()}
speechSynthesis.getVoices();  // Voices vorladen
refreshState();
</script></body></html>"""


@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(PAGE)


def main() -> None:
    import uvicorn

    print("TalosAI Dashboard: http://localhost:7777")
    uvicorn.run(app, host="127.0.0.1", port=7777, log_level="warning")


if __name__ == "__main__":
    main()
