let ws;
let chart;
let isRunning = false;
let sessionStartTime = null;
let timerInterval = null;
let sparkVideo = [];
let sparkVoice = [];
let sparkBio = [];

const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 58; // r=58

const emotionEmoji = {
  "Happy": "😊", "Sad": "😢", "Angry": "😠", "Fear": "😨", "Surprise": "😲",
  "Neutral": "😐", "Drowsiness": "😴", "Yawning": "😮", "Head Nodding": "💤",
  "Anxious/High Arousal (Close)": "😰", "Calm/Attentive": "😌", "No Face Detected": "👤",
  "No Frame": "⏳", "Idle": "💤", "Starting...": "⏳"
};

const emotionColors = {
  'Happy': { bg: 'rgba(34, 197, 94, 0.12)', text: '#4ADE80' },
  'Sad': { bg: 'rgba(59, 130, 246, 0.12)', text: '#60A5FA' },
  'Angry': { bg: 'rgba(239, 68, 68, 0.12)', text: '#F87171' },
  'Fear': { bg: 'rgba(168, 85, 247, 0.12)', text: '#C084FC' },
  'Surprise': { bg: 'rgba(245, 158, 11, 0.12)', text: '#FBBF24' },
  'Neutral': { bg: 'rgba(245, 158, 11, 0.12)', text: '#FBBF24' },
  'Drowsiness': { bg: 'rgba(107, 114, 128, 0.12)', text: '#9CA3AF' },
  'Yawning': { bg: 'rgba(107, 114, 128, 0.12)', text: '#9CA3AF' },
  'Head Nodding': { bg: 'rgba(107, 114, 128, 0.12)', text: '#9CA3AF' },
};

function handleVideoError(img) {
  img.style.display = 'none';
  document.getElementById('videoPlaceholder').classList.remove('hidden');
}

function toggleFullscreen() {
  document.getElementById('videoContainer').classList.toggle('fullscreen');
}

// Sparkline renderer
function drawSparkline(canvasId, data, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  if (data.length < 2) return;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;

  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  data.forEach((val, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((val - min) / range) * h * 0.8 - h * 0.1;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color.replace(')', ', 0.12)').replace('rgb', 'rgba'));
  grad.addColorStop(1, color.replace(')', ', 0)').replace('rgb', 'rgba'));
  ctx.fillStyle = grad;
  ctx.fill();
}

function initChart() {
  const ctx = document.getElementById('distressChart').getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 260);
  gradient.addColorStop(0, 'rgba(0, 255, 136, 0.12)');
  gradient.addColorStop(1, 'rgba(0, 255, 136, 0.01)');

  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Distress',
        data: [],
        borderColor: '#00FF88',
        backgroundColor: gradient,
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointBackgroundColor: '#00FF88',
        pointBorderColor: '#020203',
        pointBorderWidth: 2,
        fill: true,
        tension: 0.4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(10, 10, 15, 0.95)',
          titleColor: '#8A8F98',
          bodyColor: '#EDEDEF',
          bodyFont: { family: 'Fira Code', size: 12 },
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 12,
          displayColors: false,
          callbacks: { title: () => '', label: (ctx) => `Distress: ${ctx.parsed.y}` }
        }
      },
      scales: {
        x: { display: false, grid: { display: false } },
        y: {
          beginAtZero: true,
          max: 100,
          grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false },
          ticks: { color: '#6B7280', font: { family: 'Fira Code', size: 10 }, stepSize: 25, padding: 8 },
          border: { display: false }
        }
      },
      animation: { duration: 300, easing: 'easeOutQuart' }
    }
  });
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

  ws.onopen = () => {
    const pill = document.getElementById('connectionPill');
    const dot = document.getElementById('connDot');
    const txt = document.getElementById('connText');
    pill.classList.add('connected');
    dot.className = 'status-dot active';
    txt.textContent = 'Live';
    txt.style.color = 'var(--accent)';
  };

  ws.onmessage = (event) => {
    try { updateUI(JSON.parse(event.data)); }
    catch (e) { console.error('WS parse error', e); }
  };

  ws.onclose = () => {
    const pill = document.getElementById('connectionPill');
    const dot = document.getElementById('connDot');
    const txt = document.getElementById('connText');
    pill.classList.remove('connected');
    dot.className = 'status-dot idle';
    txt.textContent = 'Reconnecting...';
    txt.style.color = 'var(--foreground-muted)';
    setTimeout(connectWebSocket, 2000);
  };

  ws.onerror = () => ws.close();
}

function updateGauge(distress) {
  const gauge = document.getElementById('gaugeFill');
  const value = document.getElementById('distressValue');
  const offset = GAUGE_CIRCUMFERENCE - (distress / 100) * GAUGE_CIRCUMFERENCE;
  gauge.style.strokeDashoffset = offset;
  value.textContent = distress;
  if (distress < 40) {
    gauge.style.stroke = '#00FF88';
    value.style.color = '#00FF88';
  } else if (distress < 70) {
    gauge.style.stroke = '#F59E0B';
    value.style.color = '#F59E0B';
  } else {
    gauge.style.stroke = '#EF4444';
    value.style.color = '#EF4444';
  }
}

function updateSystemStatus(running) {
  ['Video', 'Voice', 'Bio', 'AI'].forEach(mod => {
    const el = document.getElementById('status' + mod);
    el.className = running ? 'status-dot active' : 'status-dot idle';
  });
}

function startTimer() {
  sessionStartTime = Date.now();
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
    const h = String(Math.floor(elapsed / 3600)).padStart(2, '0');
    const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
    const s = String(elapsed % 60).padStart(2, '0');
    document.getElementById('sessionTimer').textContent = `${h}:${m}:${s}`;
  }, 1000);
}

function stopTimer() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = null;
  document.getElementById('sessionTimer').textContent = '00:00:00';
}

let prevVideo = null;
let prevVoice = null;
let prevBio = null;

function updateUI(data) {
  const wasRunning = isRunning;
  isRunning = data.running;

  if (isRunning && !wasRunning) { startTimer(); }
  else if (!isRunning && wasRunning) { stopTimer(); }

  updateSystemStatus(isRunning);

  // Session badge
  const badge = document.getElementById('sessionBadge');
  if (isRunning) {
    badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>Active';
    badge.style.cssText = 'background: rgba(0, 255, 136, 0.08); border: 1px solid rgba(0, 255, 136, 0.2); color: var(--accent);';
  } else {
    badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-gray-400"></span>Idle';
    badge.style.cssText = 'background: rgba(107, 114, 128, 0.1); border: 1px solid rgba(107, 114, 128, 0.2); color: #9CA3AF;';
  }

  // Metrics
  document.getElementById('metricVideo').textContent = data.video_emotion || 'Idle';
  document.getElementById('metricVoice').textContent = data.voice_emotion || 'Idle';
  document.getElementById('metricBio').textContent = data.biometric_data || 'Idle';

  prevVideo = data.video_emotion;
  prevVoice = data.voice_emotion;
  prevBio = data.biometric_data;

  // Sparklines
  if (isRunning) {
    sparkVideo.push(data.video_emotion === 'Idle' ? 0 : Math.random() * 50 + 20);
    sparkVoice.push(data.voice_emotion === 'Idle' ? 0 : Math.random() * 40 + 30);
    sparkBio.push(data.biometric_data === 'Idle' ? 70 : 70 + Math.random() * 20 - 10);
    if (sparkVideo.length > 20) sparkVideo.shift();
    if (sparkVoice.length > 20) sparkVoice.shift();
    if (sparkBio.length > 20) sparkBio.shift();
  }
  drawSparkline('sparkVideo', sparkVideo, 'rgb(0, 255, 136)');
  drawSparkline('sparkVoice', sparkVoice, 'rgb(34, 211, 238)');
  drawSparkline('sparkBio', sparkBio, 'rgb(239, 68, 68)');

  // Cam status
  const camDot = document.getElementById('camDot');
  const camStatus = document.getElementById('camStatus');
  if (isRunning) {
    camDot.className = 'w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse';
    camStatus.textContent = 'Analyzing';
  } else {
    camDot.className = 'w-1.5 h-1.5 rounded-full bg-red-500';
    camStatus.textContent = 'Idle';
  }

  // Therapist card
  const emoji = emotionEmoji[data.video_emotion] || '🎭';
  const emotionTag = document.getElementById('emotionTag');
  const colors = emotionColors[data.video_emotion] || emotionColors['Neutral'];
  emotionTag.innerHTML = `<span id="emotionEmoji">${emoji}</span><span>${data.video_emotion || 'Idle'}</span>`;
  emotionTag.style.background = colors.bg;
  emotionTag.style.color = colors.text;
  emotionTag.style.border = 'none';

  document.getElementById('recommendationText').textContent = data.llm_response || 'No recommendation yet.';

  // STT text
  const sttEl = document.getElementById('sttText');
  const sttContent = document.getElementById('sttContent');
  if (data.stt_text && data.stt_text.trim()) {
    sttEl.classList.remove('hidden');
    sttContent.textContent = data.stt_text;
  } else {
    sttEl.classList.add('hidden');
  }

  // Distress gauge
  updateGauge(Number(data.distress) || 0);

  // Controls
  document.getElementById('sessionStatus').textContent = isRunning ? 'Session in progress' : 'Press Start to begin monitoring';
  document.getElementById('btnStart').disabled = isRunning;
  document.getElementById('btnStop').disabled = !isRunning;
}

async function startSession() {
  try {
    const res = await fetch('/api/start', { method: 'POST' });
    const json = await res.json();
    console.log('Start:', json);
    sparkVideo = []; sparkVoice = []; sparkBio = [];
  } catch (e) { console.error('Start error:', e); }
}

async function stopSession() {
  try {
    const res = await fetch('/api/stop', { method: 'POST' });
    const json = await res.json();
    console.log('Stop:', json);
  } catch (e) { console.error('Stop error:', e); }
}

async function fetchHistory() {
  try {
    const res = await fetch('/api/history');
    const data = await res.json();
    if (!Array.isArray(data)) return;
    updateChart(data);
    updateSidebar(data);
  } catch (e) { console.error('History fetch error:', e); }
}

function updateChart(rows) {
  if (!chart) return;
  const slice = rows.slice(-50);
  chart.data.labels = slice.map((_, i) => i + 1);
  chart.data.datasets[0].data = slice.map(r => Number(r.distress_level) || 0);
  chart.update('none');
}

function updateSidebar(rows) {
  const container = document.getElementById('sidebarContent');
  const countEl = document.getElementById('historyCount');
  countEl.textContent = `${rows.length}`;

  if (rows.length === 0) {
    container.innerHTML = `
      <div class="text-center py-12" style="color: var(--foreground-muted);">
        <svg class="w-8 h-8 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
        <p class="text-xs">No events yet</p>
        <p class="text-xs mt-1 opacity-60">Start a session to see history</p>
      </div>`;
    return;
  }

  const slice = rows.slice(-20).reverse();
  let html = '';
  slice.forEach(r => {
    const timeStr = r.timestamp ? new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '-';
    const level = Number(r.distress_level) || 0;
    const rec = r.llm_response || r.recommendation || '-';
    const emotion = r.video_emotion || 'Idle';
    const colors = emotionColors[emotion] || emotionColors['Neutral'];

    let distressColor = '#00FF88';
    if (level >= 70) distressColor = '#EF4444';
    else if (level >= 40) distressColor = '#F59E0B';

    html += `
      <div class="event-item">
        <div class="event-time">${timeStr}</div>
        <div class="event-row">
          <span class="event-emotion" style="color: ${colors.text};">
            <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${colors.text};opacity:0.6;"></span>
            ${emotion}
          </span>
          <span class="event-distress" style="color: ${distressColor};">${level}</span>
        </div>
        <div class="event-rec">${rec}</div>
      </div>
    `;
  });

  container.innerHTML = html;
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && e.target.tagName !== 'BUTTON') {
    e.preventDefault();
    if (isRunning) stopSession();
    else startSession();
  }
});

document.addEventListener('DOMContentLoaded', () => {
  initChart();
  connectWebSocket();
  fetchHistory();
  setInterval(fetchHistory, 5000);
});
