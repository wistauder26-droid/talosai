"""Lokales Dashboard: Chat mit Talos + Live-Blick in Memory, Lektionen, Skills.

Start: `talos-web`, dann http://localhost:7777
Single-User, nur für localhost gedacht.
"""

from __future__ import annotations

import threading

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .agent import Agent
from .learning import reflect

app = FastAPI(title="TalosAI")
_agent = Agent(session_id="web")
_lock = threading.Lock()  # ein Agent, eine Anfrage zur Zeit


class ChatIn(BaseModel):
    message: str


@app.post("/api/chat")
def chat(body: ChatIn):
    tools: list[dict] = []
    with _lock:
        _agent.on_tool = lambda name, args: tools.append(
            {"name": name, "detail": str(
                args.get("command") or args.get("query") or args.get("url")
                or args.get("task") or args.get("name") or ""
            )[:120]}
        )
        reply = _agent.run(body.message)
    return {"reply": reply, "tools": tools}


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
    }


PAGE = """<!doctype html>
<html lang="de"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TalosAI</title>
<style>
  :root{--bg:#f5f5f7;--card:#fff;--text:#1d1d1f;--muted:#86868b;--accent:#0071e3;--radius:16px}
  *{box-sizing:border-box;margin:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Helvetica,Arial,sans-serif;
       background:var(--bg);color:var(--text);height:100vh;display:flex}
  main{flex:1;display:flex;flex-direction:column;max-width:760px;margin:0 auto;padding:24px;height:100vh}
  h1{font-size:21px;font-weight:600;letter-spacing:-.02em;display:flex;align-items:center;gap:10px}
  h1 .model{font-size:12px;color:var(--muted);font-weight:400}
  #chat{flex:1;overflow-y:auto;padding:18px 4px;display:flex;flex-direction:column;gap:12px}
  .msg{max-width:82%;padding:11px 15px;border-radius:var(--radius);line-height:1.5;font-size:15px;
       white-space:pre-wrap;word-break:break-word}
  .user{align-self:flex-end;background:var(--accent);color:#fff;border-bottom-right-radius:5px}
  .bot{align-self:flex-start;background:var(--card);border-bottom-left-radius:5px;
       box-shadow:0 1px 2px rgba(0,0,0,.06)}
  .tool{align-self:flex-start;font-size:12px;color:var(--muted);padding:0 8px}
  form{display:flex;gap:10px;padding-top:12px}
  input{flex:1;padding:13px 18px;border-radius:24px;border:1px solid #d2d2d7;font-size:15px;
        background:var(--card);outline:none}
  input:focus{border-color:var(--accent)}
  button{padding:0 22px;border:none;border-radius:24px;background:var(--accent);color:#fff;
         font-size:15px;font-weight:500;cursor:pointer}
  button:disabled{opacity:.4}
  aside{width:320px;background:var(--card);border-left:1px solid #e5e5ea;padding:24px;
        overflow-y:auto;display:flex;flex-direction:column;gap:20px}
  aside h2{font-size:13px;font-weight:600;color:var(--muted);text-transform:uppercase;
           letter-spacing:.05em;margin-bottom:8px}
  aside pre{font:12px/1.6 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word;
            color:var(--text)}
  .reset{background:none;border:1px solid #d2d2d7;color:var(--text);border-radius:12px;
         padding:8px;font-size:13px}
  @media(max-width:900px){aside{display:none}}
</style></head><body>
<main>
  <h1>TalosAI <span class="model" id="model"></span></h1>
  <div id="chat"></div>
  <form id="form">
    <input id="inp" placeholder="Nachricht an Talos…" autocomplete="off" autofocus>
    <button id="send">Senden</button>
  </form>
</main>
<aside>
  <div><h2>🧠 Gedächtnis</h2><pre id="memory">–</pre></div>
  <div><h2>📚 Lektionen</h2><pre id="lessons">–</pre></div>
  <div><h2>⚡ Skills</h2><pre id="skills">–</pre></div>
  <button class="reset" onclick="resetSession()">Session beenden &amp; reflektieren</button>
</aside>
<script>
const chat=document.getElementById('chat'),inp=document.getElementById('inp'),
      send=document.getElementById('send');
function add(cls,text){const d=document.createElement('div');d.className='msg '+cls;
  d.textContent=text;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d}
function addTool(t){const d=document.createElement('div');d.className='tool';
  d.textContent='⚙ '+t.name+(t.detail?': '+t.detail:'');chat.appendChild(d);chat.scrollTop=chat.scrollHeight}
async function refreshState(){const s=await (await fetch('/api/state')).json();
  document.getElementById('memory').textContent=s.memory||'(leer)';
  document.getElementById('lessons').textContent=s.lessons||'(keine)';
  document.getElementById('skills').textContent=s.skills||'(keine)';
  document.getElementById('model').textContent=s.model}
document.getElementById('form').onsubmit=async e=>{
  e.preventDefault();const text=inp.value.trim();if(!text)return;
  add('user',text);inp.value='';send.disabled=true;
  const thinking=add('bot','…');
  try{const r=await (await fetch('/api/chat',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})})).json();
    thinking.remove();r.tools.forEach(addTool);add('bot',r.reply)}
  catch(err){thinking.textContent='Fehler: '+err}
  send.disabled=false;inp.focus();refreshState()};
async function resetSession(){const r=await (await fetch('/api/reset',{method:'POST'})).json();
  add('tool'in r?'bot':'bot','Neue Session. '+(r.lessons&&r.lessons.length?'Gelernt: '+r.lessons.join('; '):''));
  refreshState()}
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
