const $ = id => document.getElementById(id);
/* ── State ─────────────────────────────────────────────────── */
let ws;
let config = { cam:null, canvas:null, stream:null, frameTimer:null, frameBusy:false };
let mic = { recorder:null, stream:null, active:false, mode:'hold' };
let app = { running:false, timer:null, startMs:0, mode:'live' };
let data = { sparkFace:[], sparkVoice:[], lastPlayedB64:null, audio:null, chart:null, sttText:'', lastResponse:'', lastStt:'', lastDistress:0, messages:[], thinking:false, thinkText:'', chatVersion:0, ttsLoading:false, lastThinking:false };
const GAUGE = 2 * Math.PI * 16;

const E = {
  Happy:{e:'😊',c:'#10b981'},Sad:{e:'😢',c:'#3b82f6'},Angry:{e:'😠',c:'#ef4444'},Fear:{e:'😨',c:'#a855f7'},
  Surprise:{e:'😲',c:'#f59e0b'},Neutral:{e:'😐',c:'#71717a'},Calm:{e:'😌',c:'#06b6d4'},Anxious:{e:'😰',c:'#f97316'},
  Drowsiness:{e:'😴',c:'#71717a'},Yawning:{e:'🥱',c:'#71717a'},'Head Nodding':{e:'😪',c:'#71717a'},
  'No Face Detected':{e:'👤',c:'#52525b'},Idle:{e:'💤',c:'#3f3f46'},Starting:{e:'⏳',c:'#f59e0b'},
  Error:{e:'⚠',c:'#ef4444'},
};

/* ── WebSocket ────────────────────────────────────────────── */
function wsConnect(){
  ws=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws`);
  ws.onopen=()=>{$('connDot').className='topbar-dot live'};
  ws.onclose=()=>{$('connDot').className='topbar-dot dead';setTimeout(wsConnect,2000)};
  ws.onmessage=e=>{try{render(JSON.parse(e.data))}catch(ex){}};
  ws.onerror=()=>ws.close();
}

/* ── Timer ────────────────────────────────────────────────── */
function tStart(){app.startMs=Date.now();app.timer=setInterval(()=>{const s=Math.floor((Date.now()-app.startMs)/1000);$('timerDisplay').textContent=`${String(Math.floor(s/3600)).padStart(2,'0')}:${String(Math.floor(s%3600/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`},1000)}
function tStop(){clearInterval(app.timer);app.timer=null;$('timerDisplay').textContent='--:--:--'}

/* ── Camera ───────────────────────────────────────────────── */
async function camStart(){if(config.stream)return true;try{config.stream=await navigator.mediaDevices.getUserMedia({video:true,audio:false});config.canvas=document.createElement('canvas');config.canvas.width=320;config.canvas.height=240;return true}catch(e){$('camStatus').textContent='Denied';return false}}
function camStop(){clearInterval(config.frameTimer);config.frameTimer=null;config.frameBusy=false;if(config.stream){config.stream.getTracks().forEach(t=>t.stop());config.stream=null}config.canvas=null}
function camLoop(){if(config.frameTimer)return;config.frameTimer=setInterval(()=>{if(!app.running||config.frameBusy||!config.canvas)return;config.frameBusy=true;try{const ctx=config.canvas.getContext('2d');ctx.drawImage($('localVideo'),0,0,config.canvas.width,config.canvas.height);config.canvas.toBlob(b=>{if(!b){config.frameBusy=false;return}const fd=new FormData();fd.append('frame',b,'frame.jpg');fetch('/api/browser-frame',{method:'POST',body:fd}).finally(()=>{config.frameBusy=false})},'image/jpeg',0.5)}catch(e){config.frameBusy=false}},200)}

/* ── Mic ───────────────────────────────────────────────────── */
function toggleMicMode(){mic.mode=mic.mode==='hold'?'stream':'hold';$('micModeLabel').textContent=mic.mode==='hold'?'HOLD':'STRM';$('micModeLabel').style.color=mic.mode==='hold'?'var(--accent)':'var(--cyan)';$('micLabel').textContent=mic.mode==='hold'?'Hold to Speak':'Push to Talk';if(mic.active)micStop()}
function micStart(){if(mic.active||!app.running)return;mic.active=true;navigator.mediaDevices.getUserMedia({audio:true}).then(s=>{mic.stream=s;const o={mimeType:'audio/webm;codecs=opus'};if(!MediaRecorder.isTypeSupported(o.mimeType))o.mimeType='audio/webm';if(!MediaRecorder.isTypeSupported(o.mimeType))o.mimeType='';mic.recorder=new MediaRecorder(s,o);
  if(mic.mode==='stream'){mic.recorder.ondataavailable=async e=>{if(e.data&&e.data.size){const f=new FormData();f.append('audio',e.data,'chunk.webm');fetch('/api/browser-audio',{method:'POST',body:f}).catch(()=>{})}};mic.recorder.onstop=()=>{mic.active=false;micUI();if(s){s.getTracks().forEach(t=>t.stop());mic.stream=null}fetch('/api/audio/stop',{method:'POST'}).catch(()=>{})};fetch('/api/audio/start',{method:'POST'}).catch(()=>{});mic.recorder.start(1000)}
  else{let b=null;mic.recorder.ondataavailable=e=>{if(e.data&&e.data.size)b=e.data};mic.recorder.onstop=async()=>{mic.active=false;micUI();if(s){s.getTracks().forEach(t=>t.stop());mic.stream=null}      if(b&&b.size>800){data.thinking=true;data.thinkText='Transcribing...';console.log('[Mic] Sending',b.size,'bytes for STT');const f=new FormData();f.append('audio',b,'audio.webm');const r=await fetch('/api/stt/transcribe',{method:'POST',body:f}).catch(()=>{});if(r){const d=await r.json().catch(()=>({}));console.log('[Mic] STT response:',JSON.stringify(d).slice(0,100));if(d.transcript){data.sttText=d.transcript;data.thinkText='Thinking...'}else{console.warn('[Mic] No transcript in response')}}else{console.error('[Mic] STT API failed');data.thinking=false}}await fetch('/api/audio/stop',{method:'POST'}).catch(()=>{});micUI()};mic.recorder.start()}micUI()}).catch(()=>{mic.active=false;micUI()})}
function micStop(){if(mic.recorder&&mic.recorder.state!=='inactive')mic.recorder.stop();else if(mic.stream){mic.stream.getTracks().forEach(t=>t.stop());mic.stream=null;mic.active=false;micUI()}}
function micUI(){const b=$('btnMic'),l=$('micLabel');if(!b||!l)return;if(mic.active){l.textContent=mic.mode==='hold'?'Recording...':'Recording (click)';b.className='chat-footer mic-btn recording'}else{l.textContent=mic.mode==='hold'?'Hold to Speak':'Push to Talk';b.className='chat-footer mic-btn'}}
document.addEventListener('DOMContentLoaded',()=>{const m=$('btnMic');m.addEventListener('pointerdown',()=>{if(mic.mode==='hold')micStart()});m.addEventListener('pointerup',()=>{if(mic.mode==='hold')micStop()});m.addEventListener('pointerleave',()=>{if(mic.mode==='hold'&&mic.active)micStop()});m.addEventListener('click',()=>{if(mic.mode==='stream'){mic.active?micStop():micStart()}})});

/* ── Session ───────────────────────────────────────────────── */
async function startSession(){switchMode('live');if(!await camStart()){alert('Camera needed');return}const r=await fetch('/api/start',{method:'POST'});await r.json();app.running=true;data.sparkFace=[];data.sparkVoice=[];data.sttText='';data.lastResponse='';data.lastStt='';data.lastDistress=0;data.messages=[];data.thinking=false;data.thinkText='';const v=$('localVideo');v.srcObject=config.stream;v.style.display='';$('videoPlaceholder').style.display='none';$('camDot').className='video-status-dot active';$('camStatus').textContent='Analyzing';camLoop();$('btnStart').disabled=true;$('btnStop').disabled=false;$('btnMic').disabled=false;$('btnClearChat').disabled=false;$('badge').textContent='Active';$('badge').className='topbar-badge live';tStart()}
async function stopSession(){
  micStop();camStop();await fetch('/api/stop',{method:'POST'});
  app.running=false;tStop();
  $('localVideo').style.display='none';$('localVideo').srcObject=null;
  $('videoPlaceholder').style.display='';$('camOverlay').style.display='none';
  $('camDot').className='video-status-dot off';$('camStatus').textContent='Off';
  $('btnStart').disabled=false;$('btnStop').disabled=true;
  $('btnMic').disabled=true;$('btnClearChat').disabled=true;
  $('badge').textContent='Idle';$('badge').className='topbar-badge idle';
  $('emotionTag').innerHTML='💤 Idle';$('emotionTag').style.cssText='';
  data.sttText='';data.lastResponse='';data.lastStt='';data.messages=[];data.thinking=false;data.thinkText='';data.chatVersion=0;data.lastThinking=false;
  $('chatMessages').innerHTML=emptyChatHTML();
  $('chatMessages').innerHTML=emptyChatHTML();
}
async function clearChat(){await fetch('/api/chat/clear',{method:'POST'});$('chatMessages').innerHTML=emptyChatHTML();data.sttText='';data.lastResponse='';data.lastStt='';data.messages=[];data.thinking=false;data.thinkText='';data.chatVersion=0;data.lastThinking=false}

/* ── Mode ──────────────────────────────────────────────────── */
function switchMode(m){app.mode=m;$('liveMode').style.display=m==='live'?'':'none';$('videoSessionMode').style.display=m==='video'?'':'none'}

/* ── Render ────────────────────────────────────────────────── */
function render(d){
  const r=d.running;if(app.mode!=='live')return;
  $('badge').textContent=r?'Active':'Idle';$('badge').className=r?'topbar-badge live':'topbar-badge idle';
  $('btnStart').disabled=r;$('btnStop').disabled=!r;$('btnMic').disabled=!r;$('btnClearChat').disabled=!r;
  if(!r&&mic.active)micStop();if(!r&&app.timer)tStop();

  // Health
  ['face','voice','llm'].forEach(k=>{const e=$('health'+k.charAt(0).toUpperCase()+k.slice(1));if(e)e.className='health-dot '+(d['health_'+k]||'off')});

  // Emotion
  const ve=d.video_emotion||'Idle',eo=E[ve]||E['Idle'];
  $('emotionTag').innerHTML=`${eo.e} ${ve}`;$('emotionTag').style.background=`rgba(${h2r(eo.c)},0.12)`;$('emotionTag').style.color=eo.c;$('emotionTag').style.border='none';
  $('faceMetricValue').textContent=ve;$('voiceMetricValue').textContent=d.voice_emotion||'Idle';

  // Camera overlay
  const ov=$('camOverlay');if(r&&ve&&ve!=='Idle'){ov.style.display='';ov.textContent=`${eo.e} ${ve}`;ov.style.color=eo.c}else ov.style.display='none';

  // Gauge
  const dist=Number(d.distress)||0,gf=$('gaugeFill'),gv=$('gaugeValue'),off=GAUGE-(dist/100)*GAUGE;gf.style.strokeDashoffset=off;gv.textContent=dist;
  let gc='var(--accent)';if(dist>=70)gc='var(--red)';else if(dist>=40)gc='var(--amber)';gf.style.stroke=gc;gv.style.color=gc;

  // Chat messages — only update when something changes
  const sttNow = d.stt_text && d.stt_text.trim();
  let llmNow = d.llm_response && d.llm_response.trim();
  const skipLlm = ['Initializing...','Waiting...','Start a session to begin monitoring.','Start a session to begin.'];
  if (llmNow && skipLlm.includes(llmNow)) llmNow = null;
  let chatDirty = false;

  if (sttNow && sttNow !== data.lastStt) {
    data.messages.push({ type:'user', text:sttNow });
    data.lastStt = sttNow;
    data.thinking = true;
    data.chatVersion++;
    chatDirty = true;
  }
  if (llmNow && llmNow !== data.lastResponse) {
    data.messages.push({ type:'assistant', text:llmNow });
    data.lastResponse = llmNow;
    data.thinking = false;
    data.chatVersion++;
    chatDirty = true;
  }

  // Also rebuild if thinking state changed
  if (data.thinking !== data.lastThinking) {
    chatDirty = true;
    data.lastThinking = data.thinking;
  }

  if (chatDirty) {
    let mhtml = '';
    for (const m of data.messages) {
      mhtml += `<div class="chat-bubble ${m.type}"><div class="bubble-label">${m.type==='user'?'You':'Therapist'}</div>${esc(m.text)}</div>`;
    }
    if (data.thinking) {
      mhtml += `<div class="chat-thinking" id="chatThinking" style="display:flex"><div class="spinner"></div><span id="thinkingText">${data.thinkText||'Processing...'}</span></div>`;
    }
    const cm = $('chatMessages');
    if (cm) cm.innerHTML = mhtml || emptyChatHTML();
  }

  // TTS
  // TTS
  if (d.tts_generating) {
    data.ttsLoading = true;
    $('ttsRow').style.display = 'flex';
    $('ttsStatus').textContent = 'Generating audio...';
    $('ttsPlayBtn').style.display = 'none';
    $('ttsRow').innerHTML = '<div class="spinner" style="width:12px;height:12px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite"></div><span style="font-size:10px;color:var(--muted)">Generating audio...</span>';
  } else if (d.tts_audio_b64 || d.tts_audio_url) {
    data.ttsLoading = false;
    $('ttsRow').style.display = 'flex';
    $('ttsRow').innerHTML = '<button id="ttsPlayBtn" onclick="playTTS()">▶ Play</button><span style="font-size:10px;color:var(--muted)" id="ttsStatus">Ready</span>';
    if (d.tts_audio_b64 && d.tts_audio_b64 !== data.lastPlayedB64) {
      if (data.audio) { data.audio.pause(); data.audio = null; }
      data.audio = new Audio(`data:${d.tts_audio_mime||'audio/wav'};base64,${d.tts_audio_b64}`);
      data.lastPlayedB64 = d.tts_audio_b64;
      data.audio.addEventListener('canplaythrough', () => { data.audio.play().catch(()=>{}); $('ttsStatus').textContent = 'Playing...'; }, {once:true});
      data.audio.addEventListener('ended', () => { $('ttsStatus').textContent = 'Finished'; });
      data.audio.load();
    }
  } else if (!data.ttsLoading) {
    $('ttsRow').style.display = 'none';
  }

  // Sparklines
  if(r){data.sparkFace.push(pVal(ve));data.sparkVoice.push(pVal(d.voice_emotion));if(data.sparkFace.length>20){data.sparkFace.shift();data.sparkVoice.shift()}}
  sLine('sparkFace',data.sparkFace,eo.c);sLine('sparkVoice',data.sparkVoice,'#06b6d4');

  // Chart
  if(!data.chart)cInit();if(data.chart&&r){data.chart.data.labels.push('');data.chart.data.datasets[0].data.push(dist);if(data.chart.data.labels.length>50){data.chart.data.labels.shift();data.chart.data.datasets[0].data.shift()}data.chart.update('none')}
}
function playTTS(){if(data.audio)data.audio.play().catch(()=>{})}

/* ── Helpers ────────────────────────────────────────────────── */
function emptyChatHTML(){return '<div class="empty"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg><span>Press Start, then hold-to-speak</span></div><div class="chat-thinking" id="chatThinking" style="display:none"><div class="spinner"></div><span id="thinkingText">Processing...</span></div>'}
function esc(s){if(!s)return'';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function h2r(h){const r=/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(h);return r?`${parseInt(r[1],16)},${parseInt(r[2],16)},${parseInt(r[3],16)}`:''}
function pVal(e){if(!e||e==='Idle'||e==='Starting'||e==='No Face Detected')return 0;const h=['Happy','Surprise','Calm'],m=['Neutral','Sad'],l=['Angry','Fear','Anxious','Disgust'];if(h.includes(e))return 30+Math.random()*20;if(m.includes(e))return 15+Math.random()*10;if(l.includes(e))return Math.random()*10;return Math.random()*20}
function sLine(id,arr,color){const c=document.getElementById(id);if(!c)return;const w=c.width=c.offsetWidth,h=c.height=24,ctx=c.getContext('2d');ctx.clearRect(0,0,w,h);if(arr.length<2)return;const max=Math.max(...arr,0.1),min=Math.min(...arr,0),r=max-min||1;ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=1.5;arr.forEach((v,i)=>{const x=(i/(arr.length-1))*w,y=h-((v-min)/r)*h*.7-h*.15;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y)});ctx.stroke()}
function cInit(){const ctx=$('distressChartCanvas').getContext('2d');data.chart=new Chart(ctx,{type:'line',data:{labels:[],datasets:[{label:'Distress',data:[],borderColor:'#10b981',borderWidth:2,pointRadius:0,pointHoverRadius:3,tension:.35,fill:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{display:false},y:{beginAtZero:true,max:100,grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#71717a',font:{size:9},stepSize:25}}},animation:{duration:250,easing:'easeOutQuart'}}})}

/* ── History ───────────────────────────────────────────────── */
async function fHistory(){try{const r=await fetch('/api/history');const rows=await r.json();if(!Array.isArray(rows)||!rows.length){$('historyList').innerHTML='<div class="empty"><svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><span>No events</span></div>';$('historyCount').textContent='0';return}$('historyCount').textContent=rows.length;const s=rows.slice(-30).reverse();let h='';s.forEach(r=>{const t=r.timestamp?new Date(r.timestamp).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'}):'-';const ve=r.video_emotion||'Idle',eo=E[ve]||E['Idle'];const lvl=Number(r.distress_level)||0;let dc='var(--accent)';if(lvl>=70)dc='var(--red)';else if(lvl>=40)dc='var(--amber)';const resp=r.llm_response||r.recommendation||'-';h+=`<div class="history-row"><span class="history-time">${t}</span><span class="history-emo" style="color:${eo.c}">${eo.e} ${ve}</span><span class="history-response" title="${esc(resp)}">${resp.slice(0,65)}</span><span class="history-distress" style="color:${dc}">${lvl}</span></div>`});$('historyList').innerHTML=h}catch(e){}}

/* ── Video Session ─────────────────────────────────────────── */
let vsStream=null,vsRec=null,vsChunks=[],vsMs=0,vsTimer=null;
let videoSession={id:null,poll:null};
async function vsStart(){try{vsStream=await navigator.mediaDevices.getUserMedia({video:true,audio:true});const v=$('vsVideo');v.srcObject=vsStream;v.style.display='';$('vsPlaceholder').style.display='none';vsChunks=[];const o={mimeType:'video/webm;codecs=vp8,opus'};if(!MediaRecorder.isTypeSupported(o.mimeType))o.mimeType='video/webm';vsRec=new MediaRecorder(vsStream,o);vsRec.ondataavailable=e=>{if(e.data&&e.data.size)vsChunks.push(e.data)};vsRec.onstop=vsUpload;vsRec.start(1000);vsMs=Date.now();$('vsStartBtn').disabled=true;$('vsStopBtn').disabled=false;$('vsTimer').style.display='';$('vsRecDot').className='vs-rec-dot active';$('vsRecLabel').textContent='Recording...';vsTimer=setInterval(()=>{const e=Date.now()-vsMs,rem=Math.max(0,20*60*1000-e);if(rem<=0){vsStop();return}$('vsTimer').textContent=`${String(Math.floor(e/60000)).padStart(2,'0')}:${String(Math.floor(e%60000/1000)).padStart(2,'0')} / 20:00`},500)}catch(e){alert('Camera/mic needed')}}
function vsStop(){if(vsRec&&vsRec.state!=='inactive')vsRec.stop();clearInterval(vsTimer);vsTimer=null;$('vsStopBtn').disabled=true;$('vsRecDot').className='vs-rec-dot';$('vsRecLabel').textContent=''}
async function vsUpload(){if(vsStream){vsStream.getTracks().forEach(t=>t.stop());vsStream=null}$('vsVideo').style.display='none';if(!vsChunks.length){alert('No data');return}$('vsProcessing').style.display='';$('vsProcStatus').textContent='Uploading...';const b=new Blob(vsChunks,{type:'video/webm'});const f=new FormData();f.append('video',b,'session.webm');try{const r=await fetch('/api/upload-video',{method:'POST',body:f});const d=await r.json();videoSession.id=d.session_id;vsPoll()}catch(e){$('vsProcStatus').textContent='Upload failed'}}
function vsPoll(){if(videoSession.poll)clearInterval(videoSession.poll);videoSession.poll=setInterval(async()=>{if(!videoSession.id)return;const r=await fetch(`/api/video-session/${videoSession.id}`);const d=await r.json();if(d.status==='processed'||d.status==='completed'){clearInterval(videoSession.poll);videoSession.poll=null;$('vsProcessing').style.display='none';$('vsResults').style.display='';$('vsResultFer').textContent=d.fer_emotion||'--';$('vsResultSer').textContent=d.ser_emotion||'--';const dist=d.llm_distress||0;$('vsResultDistress').textContent=dist;$('vsResultStt').textContent=d.stt_text||'(none)';$('vsResultLlm').textContent=d.llm_response||'--';if(d.tts_audio_b64){$('vsResultTts').innerHTML=`<button onclick="vsPlayTTS()" style="padding:5px 12px;border-radius:6px;font-size:11px;font-weight:600;background:var(--accent-dim);border:1px solid rgba(16,185,129,.25);color:var(--accent)">▶ Play Audio</button>`;window._vsB64=d.tts_audio_b64}}else if(d.status&&d.status.startsWith('error')){clearInterval(videoSession.poll);videoSession.poll=null;$('vsProcessing').style.display='none';alert('Error: '+d.error)}},2000)}
function vsPlayTTS(){if(window._vsB64){const a=new Audio(`data:audio/wav;base64,${window._vsB64}`);a.play().catch(()=>{})}}
function vsReset(){$('vsResults').style.display='none';$('vsProcessing').style.display='none';$('vsPlaceholder').style.display='';$('vsStartBtn').disabled=false;$('vsTimer').style.display='none';vsChunks=[];vsRec=null;videoSession.id=null}

/* ── Init ──────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded',()=>{wsConnect();fHistory();cInit();setInterval(fHistory,5000)});
window.addEventListener('beforeunload',()=>{camStop();micStop()});
