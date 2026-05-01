let ws;
let chart;
let isRunning = false;
let sessionStartTime = null;
let timerInterval = null;
let sparkVideo = [];
let sparkVoice = [];
let sparkBio = [];
let browserVideo = null;
let browserCanvas = null;
let browserStream = null;
let frameUploadTimer = null;
let frameUploadInFlight = false;
let audioContext = null;
let audioStream = null;
let audioProcessor = null;
let audioUploadTimer = null;
let audioChunkBuffer = [];

let currentMode = 'live';
let mediaRecorder = null;
let recordedChunks = [];
let recordingStartTime = null;
let recordingTimerInterval = null;
let MAX_RECORDING_MS = 20 * 60 * 1000;
let videoSessionId = null;
let videoPollInterval = null;
let lastPlayedAudioB64 = null;  // prevent replaying same audio
let currentAudio = null;        // reference to currently playing Audio object

const GAUGE_CIRCUMFERENCE = 2 * Math.PI * 58;

const emotionEmoji = {
  "Happy": "\u{1F60A}", "Sad": "\u{1F622}", "Angry": "\u{1F620}", "Fear": "\u{1F628}", "Surprise": "\u{1F632}",
  "Neutral": "\u{1F610}", "Disgust": "\u{1F922}", "Drowsiness": "\u{1F634}", "Yawning": "\u{1F62E}", "Head Nodding": "\u{1F4A4}",
  "Anxious": "\u{1F630}", "Calm": "\u{1F60C}", "No Face Detected": "\u{1F464}",
  "No Frame": "\u23F3", "Idle": "\u{1F4A4}", "Starting...": "\u23F3",
  "No Camera": "\u{1F3A5}", "No Camera Found": "\u{1F3A5}", "Unavailable": "\u{2753}", "Error": "\u{26A0}"
};

const emotionColors = {
  'Happy': { bg: 'rgba(34, 197, 94, 0.12)', text: '#4ADE80' },
  'Sad': { bg: 'rgba(59, 130, 246, 0.12)', text: '#60A5FA' },
  'Angry': { bg: 'rgba(239, 68, 68, 0.12)', text: '#F87171' },
  'Fear': { bg: 'rgba(168, 85, 247, 0.12)', text: '#C084FC' },
  'Surprise': { bg: 'rgba(245, 158, 11, 0.12)', text: '#FBBF24' },
  'Neutral': { bg: 'rgba(245, 158, 11, 0.12)', text: '#FBBF24' },
  'Disgust': { bg: 'rgba(34, 197, 94, 0.12)', text: '#86EFAC' },
  'Drowsiness': { bg: 'rgba(107, 114, 128, 0.12)', text: '#9CA3AF' },
  'Yawning': { bg: 'rgba(107, 114, 128, 0.12)', text: '#9CA3AF' },
  'Head Nodding': { bg: 'rgba(107, 114, 128, 0.12)', text: '#9CA3AF' },
  'Anxious': { bg: 'rgba(239, 68, 68, 0.12)', text: '#FCA5A5' },
  'Calm': { bg: 'rgba(34, 211, 238, 0.12)', text: '#22D3EE' },
  'No Face Detected': { bg: 'rgba(107, 114, 128, 0.12)', text: '#9CA3AF' },
  'No Camera': { bg: 'rgba(107, 114, 128, 0.12)', text: '#9CA3AF' },
  'Unavailable': { bg: 'rgba(107, 114, 128, 0.12)', text: '#9CA3AF' },
  'Error': { bg: 'rgba(239, 68, 68, 0.12)', text: '#F87171' },
};

function toggleFullscreen() {
  document.getElementById('videoContainer').classList.toggle('fullscreen');
}

async function initBrowserCamera() {
  if (browserStream) return true;
  try {
    browserStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    browserVideo = document.createElement('video');
    browserVideo.autoplay = true;
    browserVideo.muted = true;
    browserVideo.playsInline = true;
    browserVideo.srcObject = browserStream;
    browserCanvas = document.createElement('canvas');
    browserCanvas.width = 480;
    browserCanvas.height = 360;
    await browserVideo.play();
    return true;
  } catch (err) {
    console.error('Browser camera permission/capture failed:', err);
    return false;
  }
}

function stopBrowserCamera() {
  if (frameUploadTimer) { clearInterval(frameUploadTimer); frameUploadTimer = null; }
  if (browserStream) { browserStream.getTracks().forEach((t) => t.stop()); browserStream = null; }
  browserVideo = null;
  browserCanvas = null;
  frameUploadInFlight = false;
}

function startFrameUploadLoop() {
  if (frameUploadTimer) return;
  frameUploadTimer = setInterval(captureAndSendFrame, 66);
}

async function captureAndSendFrame() {
  if (frameUploadInFlight) return;
  if (!isRunning || !browserVideo || !browserCanvas) return;
  if (browserVideo.readyState < 2) return;
  frameUploadInFlight = true;
  try {
    const ctx = browserCanvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(browserVideo, 0, 0, browserCanvas.width, browserCanvas.height);
    const blob = await new Promise((resolve) => browserCanvas.toBlob(resolve, 'image/jpeg', 0.75));
    if (!blob) return;
    const formData = new FormData();
    formData.append('frame', blob, 'frame.jpg');
    await fetch('/api/browser-frame', { method: 'POST', body: formData });
  } catch (err) { console.error('Frame upload failed:', err); }
  finally { frameUploadInFlight = false; }
}

async function initBrowserAudio() {
  if (audioStream) return true;
  try {
    audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(audioStream);
    audioProcessor = audioContext.createScriptProcessor(4096, 1, 1);
    audioChunkBuffer = [];
    audioProcessor.onaudioprocess = (e) => {
      if (!isRunning) return;
      const inputData = e.inputBuffer.getChannelData(0);
      audioChunkBuffer.push(new Float32Array(inputData));
    };
    source.connect(audioProcessor);
    audioProcessor.connect(audioContext.destination);
    console.log('[Audio] Browser audio capture initialized');
    return true;
  } catch (err) {
    console.error('[Audio] Browser audio permission/capture failed:', err);
    return false;
  }
}

function startAudioUploadLoop() {
  if (audioUploadTimer) return;
  audioUploadTimer = setInterval(uploadAudioChunk, 2000);
}

function stopBrowserAudio() {
  if (audioUploadTimer) { clearInterval(audioUploadTimer); audioUploadTimer = null; }
  if (audioProcessor) { audioProcessor.disconnect(); audioProcessor = null; }
  if (audioContext) { audioContext.close(); audioContext = null; }
  if (audioStream) { audioStream.getTracks().forEach((t) => t.stop()); audioStream = null; }
  audioChunkBuffer = [];
}

async function uploadAudioChunk() {
  if (!isRunning || audioChunkBuffer.length === 0) return;
  const totalLength = audioChunkBuffer.reduce((acc, arr) => acc + arr.length, 0);
  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of audioChunkBuffer) { merged.set(chunk, offset); offset += chunk.length; }
  audioChunkBuffer = [];
  const int16 = new Int16Array(merged.length);
  for (let i = 0; i < merged.length; i++) {
    const s = Math.max(-1, Math.min(1, merged[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  try {
    const blob = new Blob([int16.buffer], { type: 'application/octet-stream' });
    const formData = new FormData();
    formData.append('audio', blob, 'audio.raw');
    await fetch('/api/browser-audio', { method: 'POST', body: formData });
  } catch (err) { console.error('[Audio] Upload failed:', err); }
}

function drawSparkline(canvasId, data, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  if (data.length < 2) return;
  const max = Math.max(...data, 1), min = Math.min(...data, 0), range = max - min || 1;
  ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  data.forEach((val, i) => {
    const x = (i / (data.length - 1)) * w, y = h - ((val - min) / range) * h * 0.8 - h * 0.1;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color.replace(')', ', 0.12)').replace('rgb', 'rgba'));
  grad.addColorStop(1, color.replace(')', ', 0)').replace('rgb', 'rgba'));
  ctx.fillStyle = grad; ctx.fill();
}

function initChart() {
  const ctx = document.getElementById('distressChart').getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 260);
  gradient.addColorStop(0, 'rgba(0, 255, 136, 0.12)'); gradient.addColorStop(1, 'rgba(0, 255, 136, 0.01)');
  chart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'Distress', data: [], borderColor: '#00FF88', backgroundColor: gradient, borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 5, pointBackgroundColor: '#00FF88', pointBorderColor: '#020203', pointBorderWidth: 2, fill: true, tension: 0.4 }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(10, 10, 15, 0.95)', titleColor: '#8A8F98', bodyColor: '#EDEDEF', bodyFont: { family: 'Fira Code', size: 12 }, borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1, padding: 12, displayColors: false, callbacks: { title: () => '', label: (ctx) => `Distress: ${ctx.parsed.y}` } } }, scales: { x: { display: false, grid: { display: false } }, y: { beginAtZero: true, max: 100, grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false }, ticks: { color: '#6B7280', font: { family: 'Fira Code', size: 10 }, stepSize: 25, padding: 8 }, border: { display: false } } }, animation: { duration: 300, easing: 'easeOutQuart' } }
  });
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
  ws.onopen = () => {
    const pill = document.getElementById('connectionPill'), dot = document.getElementById('connDot'), txt = document.getElementById('connText');
    pill.classList.add('connected'); dot.className = 'status-dot active'; txt.textContent = 'Live'; txt.style.color = 'var(--accent)';
  };
  ws.onmessage = (event) => { try { updateUI(JSON.parse(event.data)); } catch (e) { console.error('WS parse error', e); } };
  ws.onclose = () => {
    const pill = document.getElementById('connectionPill'), dot = document.getElementById('connDot'), txt = document.getElementById('connText');
    pill.classList.remove('connected'); dot.className = 'status-dot idle'; txt.textContent = 'Reconnecting...'; txt.style.color = 'var(--foreground-muted)';
    setTimeout(connectWebSocket, 2000);
  };
  ws.onerror = () => ws.close();
}

function updateGauge(distress) {
  const gauge = document.getElementById('gaugeFill'), value = document.getElementById('distressValue');
  const offset = GAUGE_CIRCUMFERENCE - (distress / 100) * GAUGE_CIRCUMFERENCE;
  gauge.style.strokeDashoffset = offset; value.textContent = distress;
  if (distress < 40) { gauge.style.stroke = '#00FF88'; value.style.color = '#00FF88'; }
  else if (distress < 70) { gauge.style.stroke = '#F59E0B'; value.style.color = '#F59E0B'; }
  else { gauge.style.stroke = '#EF4444'; value.style.color = '#EF4444'; }
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
    const h = String(Math.floor(elapsed / 3600)).padStart(2, '0'), m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0'), s = String(elapsed % 60).padStart(2, '0');
    document.getElementById('sessionTimer').textContent = `${h}:${m}:${s}`;
  }, 1000);
}

function stopTimer() { if (timerInterval) clearInterval(timerInterval); timerInterval = null; document.getElementById('sessionTimer').textContent = '00:00:00'; }

function playTTS(data) {
  console.log('[TTS] playTTS called with keys:', Object.keys(data));
  const b64 = data.tts_audio_b64;
  const url = data.tts_audio_url;
  const mime = data.tts_audio_mime || 'audio/wav';

  console.log('[TTS] b64 present:', !!b64, 'url present:', !!url, 'mime:', mime);

  if (!b64 && !url) {
    console.log('[TTS] EARLY RETURN: no b64 and no url');
    return;
  }
  if (b64 && b64 === lastPlayedAudioB64) {
    console.log('[TTS] EARLY RETURN: already played this b64');
    return;
  }

  try {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }

    if (b64) {
      const dataUrl = `data:${mime};base64,${b64}`;
      console.log('[TTS] Creating Audio from data URL, length:', dataUrl.length);
      currentAudio = new Audio(dataUrl);
      lastPlayedAudioB64 = b64;
    } else if (url) {
      console.log('[TTS] Creating Audio from URL:', url);
      currentAudio = new Audio(url);
    }

    if (currentAudio) {
      console.log('[TTS] Setting up audio events...');
      currentAudio.addEventListener('canplaythrough', () => {
        console.log('[TTS] Audio can play, calling .play()...');
        const playPromise = currentAudio.play();
        if (playPromise !== undefined) {
          playPromise.then(() => {
            console.log('[TTS] Playback STARTED successfully');
            updateTTSStatus('Playing...', true);
          }).catch(err => {
            console.warn('[TTS] Playback FAILED:', err.name, err.message);
            updateTTSStatus('Click 🔊 to play', true);
          });
        }
      }, { once: true });

      currentAudio.addEventListener('ended', () => {
        updateTTSStatus('Finished', true);
      });

      currentAudio.addEventListener('error', (e) => {
        console.error('[TTS] Audio load error:', e);
        updateTTSStatus('Error loading audio', true);
      });

      currentAudio.load();
    }
  } catch (err) {
    console.error('[TTS] Playback exception:', err);
  }
}

function updateTTSStatus(text, showControls) {
  const ctrl = document.getElementById('ttsControls');
  const status = document.getElementById('ttsStatus');
  if (ctrl && status) {
    status.textContent = text;
    if (showControls) ctrl.classList.remove('hidden');
  }
}

window.playCurrentTTS = function() {
  console.log('[TTS] Manual play clicked');
  if (currentAudio) {
    currentAudio.play().then(() => {
      console.log('[TTS] Manual play SUCCESS');
      updateTTSStatus('Playing...', true);
    }).catch(err => {
      console.warn('[TTS] Manual play failed:', err);
      updateTTSStatus('Playback blocked by browser', true);
    });
  } else {
    console.warn('[TTS] No currentAudio available');
  }
};

window.playVideoTTS = function() {
  console.log('[TTS] Video manual play clicked');
  if (currentAudio) {
    currentAudio.play().then(() => {
      console.log('[TTS] Video manual play SUCCESS');
    }).catch(err => {
      console.warn('[TTS] Video manual play failed:', err);
    });
  }
};

function updateUI(data) {
  const wasRunning = isRunning;
  isRunning = data.running;
  if (currentMode !== 'live') return;
  if (isRunning && !wasRunning) startTimer();
  else if (!isRunning && wasRunning) stopTimer();
  updateSystemStatus(isRunning);
  const badge = document.getElementById('sessionBadge');
  if (isRunning) { badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>Active'; badge.style.cssText = 'background: rgba(0, 255, 136, 0.08); border: 1px solid rgba(0, 255, 136, 0.2); color: var(--accent);'; }
  else { badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-gray-400"></span>Idle'; badge.style.cssText = 'background: rgba(107, 114, 128, 0.1); border: 1px solid rgba(107, 114, 128, 0.2); color: #9CA3AF;'; }
  document.getElementById('metricVideo').textContent = data.video_emotion || 'Idle';
  document.getElementById('metricVoice').textContent = data.voice_emotion || 'Idle';
  document.getElementById('metricBio').textContent = data.biometric_data || 'Idle';
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
  const camDot = document.getElementById('camDot'), camStatus = document.getElementById('camStatus');
  if (isRunning) { camDot.className = 'w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse'; camStatus.textContent = 'Analyzing'; }
  else { camDot.className = 'w-1.5 h-1.5 rounded-full bg-red-500'; camStatus.textContent = 'Idle'; }
  const emoji = emotionEmoji[data.video_emotion] || '\u{1F3AD}';
  const emotionTag = document.getElementById('emotionTag');
  const colors = emotionColors[data.video_emotion] || emotionColors['Neutral'];
  emotionTag.innerHTML = `<span id="emotionEmoji">${emoji}</span><span>${data.video_emotion || 'Idle'}</span>`;
  emotionTag.style.background = colors.bg; emotionTag.style.color = colors.text; emotionTag.style.border = 'none';
  document.getElementById('recommendationText').textContent = data.llm_response || 'No recommendation yet.';
  const sttEl = document.getElementById('sttText'), sttContent = document.getElementById('sttContent');
  if (data.stt_text && data.stt_text.trim()) { sttEl.classList.remove('hidden'); sttContent.textContent = data.stt_text; }
  else { sttEl.classList.add('hidden'); }
  updateGauge(Number(data.distress) || 0);
  document.getElementById('sessionStatus').textContent = isRunning ? 'Session in progress' : 'Press Start to begin monitoring';
  document.getElementById('btnStart').disabled = isRunning;
  document.getElementById('btnStop').disabled = !isRunning;

  // Auto-play TTS audio when available
  playTTS(data);

  // Show TTS controls if audio is available
  const ttsCtrl = document.getElementById('ttsControls');
  if (ttsCtrl) {
    if (data.tts_audio_b64 || data.tts_audio_url) {
      ttsCtrl.classList.remove('hidden');
      if (!currentAudio || currentAudio.paused) {
        updateTTSStatus('Click to play', true);
      }
    } else {
      ttsCtrl.classList.add('hidden');
    }
  }

  // Update avatar tab
  if (currentMode === 'avatar') {
    const emotion = data.video_emotion || 'Neutral';
    const distress = Number(data.distress) || 0;
    updateAvatarMood(emotion, distress);
    const avEmoji = emotionEmoji[emotion] || '\u{1F3AD}';
    document.getElementById('avatarEmoji').textContent = avEmoji;
    document.getElementById('avatarEmotionTag').querySelector('span:last-child').textContent = emotion;
    document.getElementById('avatarResponse').textContent = data.llm_response || 'Waiting...';
    const avGauge = document.getElementById('avatarGaugeFill');
    if (avGauge) { avGauge.style.strokeDashoffset = GAUGE_CIRCUMFERENCE - (distress / 100) * GAUGE_CIRCUMFERENCE; }
    const avDist = document.getElementById('avatarDistress');
    if (avDist) { avDist.textContent = distress; }
  }
}

// ========== LIVE MODE ==========

async function startSession() {
  if (currentMode !== 'live') { switchMode('live'); }
  try {
    const cameraReady = await initBrowserCamera();
    if (!cameraReady) { document.getElementById('sessionStatus').textContent = 'Browser camera permission denied or unavailable'; return; }
    await initBrowserAudio();
    const res = await fetch('/api/start', { method: 'POST' });
    const json = await res.json();
    console.log('Start:', json);
    sparkVideo = []; sparkVoice = []; sparkBio = [];
    document.getElementById('videoPlaceholder').classList.add('hidden');
    document.getElementById('videoFeed').style.display = '';
    document.getElementById('videoFeed').src = '/video_feed?' + Date.now();
    startFrameUploadLoop();
    startAudioUploadLoop();
  } catch (e) { console.error('Start error:', e); }
}

async function stopSession() {
  try {
    const res = await fetch('/api/stop', { method: 'POST' });
    const json = await res.json();
    console.log('Stop:', json);
    stopBrowserCamera();
    stopBrowserAudio();
  } catch (e) { console.error('Stop error:', e); }
}

// ========== VIDEO SESSION MODE ==========

function switchMode(mode) {
  currentMode = mode;
  document.getElementById('liveMode').style.display = mode === 'live' ? '' : 'none';
  document.getElementById('videoMode').style.display = mode === 'video' ? '' : 'none';
  document.getElementById('avatarMode').style.display = mode === 'avatar' ? '' : 'none';
  document.getElementById('modeLiveBtn').classList.toggle('active', mode === 'live');
  document.getElementById('modeVideoBtn').classList.toggle('active', mode === 'video');
  document.getElementById('modeAvatarBtn').classList.toggle('active', mode === 'avatar');
  if (mode === 'avatar') { initAvatar(); }
}

async function requestVideoPermissions() {
  const btn = document.getElementById('videoPermBtn');
  btn.textContent = 'Requesting...';
  btn.disabled = true;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    stream.getTracks().forEach(t => t.stop());
    document.getElementById('videoStartBtn').disabled = false;
    btn.textContent = 'Permissions Granted';
    btn.style.background = 'linear-gradient(135deg, #059669, #00FF88)';
    showVideoPreview();
  } catch (err) {
    console.error('Permission denied:', err);
    btn.textContent = 'Permission Denied';
    btn.disabled = false;
  }
}

async function showVideoPreview() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    const previewEl = document.getElementById('videoPreviewEl');
    previewEl.srcObject = stream;
    document.getElementById('videoPreviewWrap').style.display = '';
    document.getElementById('videoPlaceholderArea').style.display = 'none';
    // Store stream reference for recording
    window._videoPreviewStream = stream;
  } catch (err) {
    console.error('Preview failed:', err);
  }
}

async function startVideoRecording() {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  } catch (err) {
    console.error('Could not get media:', err);
    alert('Camera/microphone permission required.');
    return;
  }

  // Show preview
  const previewEl = document.getElementById('videoPreviewEl');
  previewEl.srcObject = stream;
  document.getElementById('videoPreviewWrap').style.display = '';
  document.getElementById('videoPlaceholderArea').style.display = 'none';

  recordedChunks = [];
  const options = { mimeType: 'video/webm;codecs=vp8,opus' };
  if (!MediaRecorder.isTypeSupported(options.mimeType)) {
    options.mimeType = 'video/webm';
  }
  mediaRecorder = new MediaRecorder(stream, options);

  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) recordedChunks.push(e.data);
  };

  mediaRecorder.onstop = () => {
    stream.getTracks().forEach(t => t.stop());
    previewEl.srcObject = null;
    uploadVideoSession();
  };

  mediaRecorder.start(1000);
  recordingStartTime = Date.now();

  document.getElementById('videoStartBtn').disabled = true;
  document.getElementById('videoStopBtn').disabled = false;
  document.getElementById('videoPermBtn').disabled = true;
  document.getElementById('videoTimerWrap').style.display = 'flex';
  document.getElementById('videoRecIndicator').className = 'rec-indicator active';

  recordingTimerInterval = setInterval(() => {
    const elapsed = Date.now() - recordingStartTime;
    const remaining = Math.max(0, MAX_RECORDING_MS - elapsed);
    if (remaining <= 0) { stopVideoRecording(); return; }
    const mins = Math.floor(elapsed / 60000), secs = Math.floor((elapsed % 60000) / 1000);
    const maxMins = Math.floor(MAX_RECORDING_MS / 60000);
    document.getElementById('videoTimer').textContent =
      `${String(mins).padStart(2,'0')}:${String(secs).padStart(2,'0')} / ${maxMins}:00`;
  }, 1000);
}

function stopVideoRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  if (recordingTimerInterval) { clearInterval(recordingTimerInterval); recordingTimerInterval = null; }
  document.getElementById('videoRecIndicator').className = 'rec-indicator idle';
  document.getElementById('videoStopBtn').disabled = true;
  document.getElementById('videoTimerWrap').style.display = 'none';
}

async function uploadVideoSession() {
  if (recordedChunks.length === 0) { alert('No video data recorded.'); return; }
  const blob = new Blob(recordedChunks, { type: 'video/webm' });
  const formData = new FormData();
  formData.append('video', blob, 'session.webm');

  document.getElementById('videoProcessing').style.display = '';
  document.getElementById('videoProcessing').scrollIntoView({ behavior: 'smooth' });
  document.getElementById('videoProcessingStep').textContent = 'Uploading video...';

  try {
    const res = await fetch('/api/upload-video', { method: 'POST', body: formData });
    const json = await res.json();
    videoSessionId = json.session_id;
    pollVideoResults();
  } catch (err) {
    console.error('Upload failed:', err);
    document.getElementById('videoProcessingStep').textContent = 'Upload failed. Please try again.';
  }
}

function pollVideoResults() {
  if (videoPollInterval) clearInterval(videoPollInterval);
  const steps = ['Extracting frames & running FER...', 'Extracting audio & running SER...', 'Transcribing speech...', 'Generating AI response...'];
  let stepIdx = 0;
  videoPollInterval = setInterval(async () => {
    if (!videoSessionId) return;
    try {
      const res = await fetch(`/api/video-session/${videoSessionId}`);
      const data = await res.json();
      if (data.status === 'processing') {
        stepIdx = Math.min(stepIdx + 1, steps.length - 1);
        document.getElementById('videoProcessingStep').textContent = steps[stepIdx];
      } else if (data.status === 'completed') {
        clearInterval(videoPollInterval);
        videoPollInterval = null;
        displayVideoResults(data);
      } else if (data.status && data.status.startsWith('error')) {
        clearInterval(videoPollInterval);
        videoPollInterval = null;
        document.getElementById('videoProcessing').style.display = 'none';
        alert('Processing error: ' + (data.error || data.status));
      }
    } catch (err) {
      console.error('Poll error:', err);
    }
  }, 3000);
}

function displayVideoResults(data) {
  console.log('[VideoResults] displayVideoResults called with keys:', Object.keys(data));
  console.log('[VideoResults] tts_audio_b64 present:', !!data.tts_audio_b64, 'len:', data.tts_audio_b64 ? data.tts_audio_b64.length : 0);
  console.log('[VideoResults] tts_audio_url:', data.tts_audio_url);
  document.getElementById('videoProcessing').style.display = 'none';
  document.getElementById('videoResults').style.display = '';

  document.getElementById('resultFer').textContent = data.fer_emotion || 'N/A';
  const ferCounts = data.fer_emotion_counts || {};
  const ferTotal = Object.values(ferCounts).reduce((a, b) => a + b, 0) || 1;
  const ferDetails = Object.entries(ferCounts).map(([k, v]) => `${k}: ${(v / ferTotal * 100).toFixed(0)}%`).join(', ');
  document.getElementById('resultFerDetails').textContent = ferDetails;

  document.getElementById('resultSer').textContent = data.ser_emotion || 'N/A';
  const serCounts = data.ser_emotion_counts || {};
  const serDetails = Object.entries(serCounts).map(([k, v]) => `${k}: ${v}`).join(', ');
  document.getElementById('resultSerDetails').textContent = serDetails;

  const distress = data.llm_distress || 0;
  document.getElementById('resultDistress').textContent = distress;
  let dColor = '#00FF88';
  if (distress >= 70) dColor = '#EF4444';
  else if (distress >= 40) dColor = '#F59E0B';
  document.getElementById('resultDistress').style.color = dColor;

  document.getElementById('resultStt').textContent = data.stt_text || '(No speech detected)';
  document.getElementById('resultLlm').textContent = data.llm_response || 'No response generated.';

  // Auto-play TTS audio for video session results
  playTTS(data);

  // Show video TTS controls if audio is available
  const videoTtsCtrl = document.getElementById('videoTtsControls');
  if (videoTtsCtrl) {
    if (data.tts_audio_b64 || data.tts_audio_url) {
      videoTtsCtrl.classList.remove('hidden');
    } else {
      videoTtsCtrl.classList.add('hidden');
    }
  }

  document.getElementById('videoResults').scrollIntoView({ behavior: 'smooth' });
}

function resetVideoSession() {
  document.getElementById('videoResults').style.display = 'none';
  document.getElementById('videoProcessing').style.display = 'none';
  document.getElementById('videoPreviewWrap').style.display = 'none';
  document.getElementById('videoPlaceholderArea').style.display = '';
  document.getElementById('videoStartBtn').disabled = false;
  document.getElementById('videoStopBtn').disabled = true;
  document.getElementById('videoPermBtn').disabled = false;
  document.getElementById('videoPermBtn').textContent = 'Check Permissions';
  document.getElementById('videoPermBtn').style.background = '';
  recordedChunks = [];
  videoSessionId = null;
  mediaRecorder = null;
  if (window._videoPreviewStream) {
    window._videoPreviewStream.getTracks().forEach(t => t.stop());
    window._videoPreviewStream = null;
  }
}

// ========== HISTORY ==========

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
    container.innerHTML = `<div class="text-center py-12" style="color: var(--foreground-muted);"><svg class="w-8 h-8 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><p class="text-xs">No events yet</p><p class="text-xs mt-1 opacity-60">Start a session to see history</p></div>`;
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
    if (level >= 70) distressColor = '#EF4444'; else if (level >= 40) distressColor = '#F59E0B';
    html += `<div class="event-item"><div class="event-time">${timeStr}</div><div class="event-row"><span class="event-emotion" style="color: ${colors.text};"><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${colors.text};opacity:0.6;"></span>${emotion}</span><span class="event-distress" style="color: ${distressColor};">${level}</span></div><div class="event-rec">${rec}</div></div>`;
  });
  container.innerHTML = html;
}

// ========== AVATAR (Three.js Cube Head) ==========

let avatarScene, avatarCamera, avatarRenderer, avatarCube, avatarLeftEye, avatarRightEye;
let avatarLeftPupil, avatarRightPupil, avatarLeftBrow, avatarRightBrow;
let avatarInit = false, avatarLoading = false;
let avatarRotY = 0, avatarRotX = 0.3;
let avatarTargetRotY = 0;
let avatarMood = { happy: 0, sad: 0, angry: 0, surprised: 0 };

function loadThreeJS() {
  return new Promise((resolve, reject) => {
    if (window.THREE) { resolve(); return; }
    const script = document.createElement('script');
    script.src = '/static/js/three.min.js';
    script.onload = resolve;
    script.onerror = () => reject(new Error('Three.js failed to load'));
    document.head.appendChild(script);
  });
}

async function initAvatar() {
  if (avatarInit || avatarLoading) return;
  avatarLoading = true;
  try {
    await loadThreeJS();
  } catch (e) {
    console.warn('Three.js CDN unavailable, avatar disabled');
    avatarLoading = false;
    return;
  }
  avatarLoading = false;
  const THREE = window.THREE;
  const container = document.getElementById('avatarContainer');
  if (!container || container.clientWidth === 0) return;

  const w = container.clientWidth, h = container.clientHeight || 400;

  avatarScene = new THREE.Scene();
  avatarScene.background = new THREE.Color(0x050506);

  avatarCamera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100);
  avatarCamera.position.set(0, 0.2, 6);
  avatarCamera.lookAt(0, 0, 0);

  avatarRenderer = new THREE.WebGLRenderer({ antialias: true });
  avatarRenderer.setSize(w, h);
  avatarRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(avatarRenderer.domElement);

  const ambientLight = new THREE.AmbientLight(0x404060, 1.2);
  avatarScene.add(ambientLight);
  const keyLight = new THREE.DirectionalLight(0xffffff, 0.8);
  keyLight.position.set(2, 2, 3);
  avatarScene.add(keyLight);
  const rimLight = new THREE.DirectionalLight(0x00ff88, 0.4);
  rimLight.position.set(-2, -1, -2);
  avatarScene.add(rimLight);

  // Head cube
  const headGeo = new THREE.BoxGeometry(2.2, 2.5, 1.8, 2, 2, 2);
  const headMat = new THREE.MeshPhongMaterial({ color: 0x2a2a3a, specular: 0x111122, shininess: 30 });
  avatarCube = new THREE.Mesh(headGeo, headMat);
  avatarCube.position.y = 0.2;
  avatarScene.add(avatarCube);

  // Eyes
  const eyeGeo = new THREE.SphereGeometry(0.22, 16, 16);
  const eyeMat = new THREE.MeshPhongMaterial({ color: 0xffffff });
  avatarLeftEye = new THREE.Mesh(eyeGeo, eyeMat);
  avatarLeftEye.position.set(-0.5, 0.35, 0.92);
  avatarScene.add(avatarLeftEye);
  avatarRightEye = new THREE.Mesh(eyeGeo, eyeMat);
  avatarRightEye.position.set(0.5, 0.35, 0.92);
  avatarScene.add(avatarRightEye);

  // Pupils
  const pupilGeo = new THREE.SphereGeometry(0.1, 8, 8);
  const pupilMat = new THREE.MeshPhongMaterial({ color: 0x000000 });
  avatarLeftPupil = new THREE.Mesh(pupilGeo, pupilMat);
  avatarLeftPupil.position.set(-0.5, 0.35, 1.08);
  avatarScene.add(avatarLeftPupil);
  avatarRightPupil = new THREE.Mesh(pupilGeo, pupilMat);
  avatarRightPupil.position.set(0.5, 0.35, 1.08);
  avatarScene.add(avatarRightPupil);

  // Eyebrows
  const browGeo = new THREE.BoxGeometry(0.5, 0.08, 0.08);
  const browMat = new THREE.MeshPhongMaterial({ color: 0x111122 });
  avatarLeftBrow = new THREE.Mesh(browGeo, browMat);
  avatarLeftBrow.position.set(-0.5, 0.65, 0.95);
  avatarScene.add(avatarLeftBrow);
  avatarRightBrow = new THREE.Mesh(browGeo, browMat);
  avatarRightBrow.position.set(0.5, 0.65, 0.95);
  avatarScene.add(avatarRightBrow);

  avatarInit = true;
  animateAvatar();

  window.addEventListener('resize', () => {
    if (!avatarRenderer || currentMode !== 'avatar') return;
    const c = document.getElementById('avatarContainer');
    if (c) { avatarRenderer.setSize(c.clientWidth, c.clientHeight || 400); avatarCamera.aspect = c.clientWidth / (c.clientHeight || 400); avatarCamera.updateProjectionMatrix(); }
  });
}

function animateAvatar() {
  if (!avatarInit || currentMode !== 'avatar') { requestAnimationFrame(animateAvatar); return; }

  // Smooth rotation
  avatarRotY += (avatarTargetRotY - avatarRotY) * 0.05;
  avatarCube.rotation.y = avatarRotY;
  avatarCube.rotation.x = avatarRotX;

  // Move eyes with cube
  avatarLeftEye.rotation.y = avatarRotY;
  avatarRightEye.rotation.y = avatarRotY;
  avatarLeftEye.position.set(-0.5, 0.35, 0.92);
  avatarRightEye.position.set(0.5, 0.35, 0.92);

  // Pupils follow rotation + mood offset
  const px = avatarMood.happy * 0.04 - avatarMood.sad * 0.02;
  const py = avatarMood.happy * 0.03 + avatarMood.surprised * 0.05;
  avatarLeftPupil.position.set(-0.5 + px, 0.35 + py, 1.08);
  avatarRightPupil.position.set(0.5 + px, 0.35 + py, 1.08);

  // Eyebrows react to mood
  const browY = 0.65 - avatarMood.angry * 0.15 + avatarMood.sad * 0.1 + avatarMood.surprised * 0.2;
  const browAngle = avatarMood.angry * 0.3 - avatarMood.sad * 0.2;
  avatarLeftBrow.position.set(-0.5, browY, 0.95);
  avatarLeftBrow.rotation.z = browAngle;
  avatarRightBrow.position.set(0.5, browY, 0.95);
  avatarRightBrow.rotation.z = -browAngle;

  // Head color reflects distress
  const distress = avatarMood._distress || 0;
  const headColor = new THREE.Color();
  if (distress < 40) headColor.setHSL(0.55, 0.4, 0.2 + distress * 0.002);
  else if (distress < 70) headColor.setHSL(0.12, 0.6, 0.18);
  else headColor.setHSL(0.0, 0.8, 0.15);
  avatarCube.material.color = headColor;

  renderAvatar();
  requestAnimationFrame(animateAvatar);
}

function renderAvatar() {
  if (!avatarRenderer || !avatarScene || !avatarCamera) return;
  // Eyes follow cube
  avatarLeftEye.matrixAutoUpdate = false;
  avatarRightEye.matrixAutoUpdate = false;
  avatarLeftPupil.matrixAutoUpdate = false;
  avatarRightPupil.matrixAutoUpdate = false;
  avatarLeftEye.position.applyMatrix4(avatarCube.matrixWorld);
  avatarRightEye.position.applyMatrix4(avatarCube.matrixWorld);
  avatarLeftPupil.position.applyMatrix4(avatarCube.matrixWorld);
  avatarRightPupil.position.applyMatrix4(avatarCube.matrixWorld);
  avatarRenderer.render(avatarScene, avatarCamera);
}

function rotateAvatar(dir) { avatarTargetRotY += dir === 'left' ? -0.8 : 0.8; }
function resetAvatarView() { avatarTargetRotY = 0; avatarRotX = 0.3; }

function updateAvatarMood(emotion, distress) {
  avatarMood.happy = emotion === 'Happy' ? 1 : avatarMood.happy * 0.85;
  avatarMood.sad = emotion === 'Sad' ? 1 : avatarMood.sad * 0.85;
  avatarMood.angry = emotion === 'Angry' ? 1 : avatarMood.angry * 0.85;
  avatarMood.surprised = emotion === 'Surprise' ? 1 : avatarMood.surprised * 0.85;
  if (emotion === 'Fear') { avatarMood.surprised = 0.7; avatarMood.sad = 0.5; }
  avatarMood._distress = distress || 0;
}

// ========== KEYBOARD & INIT ==========

document.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && e.target.tagName !== 'BUTTON') {
    e.preventDefault();
    if (currentMode === 'live') { if (isRunning) stopSession(); else startSession(); }
  }
});

document.addEventListener('DOMContentLoaded', () => {
  initChart();
  connectWebSocket();
  fetchHistory();
  setInterval(fetchHistory, 5000);
});

window.addEventListener('beforeunload', () => {
  stopBrowserCamera();
  stopBrowserAudio();
  if (window._videoPreviewStream) { window._videoPreviewStream.getTracks().forEach(t => t.stop()); }
});