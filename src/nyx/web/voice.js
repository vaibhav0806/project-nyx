"use strict";

// Microphone samples go only to this localhost app. OpenRouter is called after local activation.
const voice = {
  token: null, epoch: 0, mic: null, context: null, outputContext: null, node: null, timer: null,
  working: false, playing: false, player: null, url: null, activation: null,
  parts: [], length: 0, quiet: 0, pre: [], preLength: 0, speaking: false,
  noise: 0.001, voiced: 0, lastSpeech: 0, probePromise: null, lastProbe: 0, wakeUntil: 0, pending: null,

  state(text) { $("voice-state").textContent = text; window.dispatchEvent(new CustomEvent("nyx-voice-state", { detail: text })); },
  headers() { return { "x-nyx-voice": this.token, "x-nyx-timezone": Intl.DateTimeFormat().resolvedOptions().timeZone }; },
  reset() { this.parts = []; this.length = 0; this.quiet = 0; this.pre = []; this.preLength = 0; this.speaking = false; this.voiced = 0; },

  async start() {
    if (this.mic || this.starting) return;
    this.starting = true;
    const epoch = ++this.epoch;
    this.state("Requesting microphone access…");
    $("voice-mute").hidden = false;
    try {
      const session = await api("/api/voice/session", { method: "POST" });
      if (epoch !== this.epoch) {
        await api("/api/voice/session", { method: "DELETE", headers: { "x-nyx-voice": session.token } });
        return;
      }
      this.token = session.token;
      this.timer = setInterval(() => api("/api/voice/heartbeat", { method: "POST", headers: this.headers() }).catch(() => this.stop("Voice connection lost. Enable listening again.")), 10000);
      const mic = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false });
      if (epoch !== this.epoch) { mic.getTracks().forEach((track) => track.stop()); return; }
      this.mic = mic;
      mic.getAudioTracks()[0].onended = () => this.stop("Microphone disconnected. Enable listening again.");
      this.context = new AudioContext({ sampleRate: 16000 });
      this.context.onstatechange = () => {
        if (this.context?.state === "suspended") {
          $("voice-enable").hidden = false;
          this.reset();
          this.state("Browser audio paused. Click Enable listening.");
        }
      };
      if (this.context.sampleRate !== 16000) throw new Error("Use Chrome with 16 kHz microphone processing support.");
      await this.context.audioWorklet.addModule("/audio-worklet.js");
      if (epoch !== this.epoch) return;
      this.node = new AudioWorkletNode(this.context, "nyx-audio");
      this.node.port.onmessage = (event) => this.samples(event.data);
      this.context.createMediaStreamSource(mic).connect(this.node);
      this.node.connect(this.context.destination);
      await this.context.resume();
      if (epoch !== this.epoch) return;
      $("voice-enable").hidden = this.context.state === "running";
      $("voice-mute").hidden = false;
      this.reset();
      this.state(this.context.state === "running" ? 'Listening locally · say “Hey Nyx”' : "Microphone ready. Click Enable listening to unlock browser audio.");
    } catch (error) {
      if (epoch === this.epoch) await this.stop(`Listening unavailable: ${error.message}`);
    } finally { this.starting = false; }
  },

  async enable() {
    if (this.context?.state === "suspended") {
      await this.context.resume();
      if (this.context.state !== "running") { this.state("Browser audio is still blocked. Check site permissions."); return; }
      $("voice-enable").hidden = true;
      this.state('Listening locally · say “Hey Nyx”');
    } else await this.start();
    if (!enabled && !requestingCamera && !remoteSession && !paused) startCapture();
  },

  async stop(text = "Microphone muted. Camera recording has separate controls.") {
    this.epoch++;
    clearTimeout(this.activation);
    clearInterval(this.timer);
    this.stopPlayback();
    this.pending = null;
    this.wakeUntil = 0;
    this.reset();
    this.mic?.getTracks().forEach((track) => track.stop());
    this.mic = null;
    this.node?.disconnect();
    this.node = null;
    this.context?.close().catch(() => {});
    this.context = null;
    this.outputContext?.close().catch(() => {});
    this.outputContext = null;
    const token = this.token;
    this.token = null;
    const reason = text === "Page closed." ? "page_closed" : text.startsWith("Camera stopped") ? "camera_stopped" : text.startsWith("Voice connection lost") ? "heartbeat_failed" : "session_stopped";
    if (token) api("/api/voice/session", { method: "DELETE", headers: { "x-nyx-voice": token, "x-nyx-stop-reason": reason }, keepalive: true }).catch(() => {});
    $("voice-enable").hidden = false;
    $("voice-mute").hidden = true;
    $("voice-cancel").hidden = true;
    this.state(text);
  },

  stopPlayback() {
    this.replyAbort?.abort();
    this.replyAbort = null;
    for (const source of this.pcmSources || []) { source.onended = null; source.stop(); }
    this.pcmSources = new Set();
    this.pcmEnd = 0;
    if (this.player) { this.player.onended = null; this.player.onerror = null; this.player.pause(); this.player.removeAttribute("src"); this.player = null; }
    if (this.url) URL.revokeObjectURL(this.url);
    this.url = null;
    this.playing = false;
  },

  async cancel(reason = "user_stop") {
    this.epoch++;
    if (typeof companion !== "undefined" && companion.working) await companion.cancel();
    this.stopPlayback();
    this.pending = null;
    this.wakeUntil = 0;
    this.reset();
    clearTimeout(this.activation);
    if (this.token) await api("/api/voice/cancel", { method: "POST", headers: { ...this.headers(), "x-nyx-cancel-reason": reason } }).catch(() => {});
    $("voice-cancel").hidden = true;
    this.state('Response stopped · say “Hey Nyx” when ready');
  },

  acknowledge() {
    if (!this.context || this.context.state !== "running") return;
    const tone = this.context.createOscillator();
    const volume = this.context.createGain();
    volume.gain.value = 0.025;
    tone.frequency.value = 660;
    tone.connect(volume).connect(this.context.destination);
    tone.start();
    tone.stop(this.context.currentTime + 0.08);
  },

  async listen(turnId) {
    const epoch = this.epoch;
    const result = await api("/api/voice/listen", { ...json({ turn_id: turnId }), headers: { ...this.headers(), "content-type": "application/json" } });
    if (epoch !== this.epoch || !this.token) return;
    this.wakeUntil = performance.now() + result.seconds * 1000;
    this.state("Listening · you can ask a follow-up");
    clearTimeout(this.activation);
    this.activation = setTimeout(() => {
      if (epoch === this.epoch && !this.working && !this.playing) this.state('Listening locally · say “Hey Nyx”');
    }, result.seconds * 1000);
  },

  maybeProbe() {
    const now = performance.now();
    if ((this.working && !this.playing) || this.probePromise || now < this.wakeUntil || this.length < 0.6 * 16000 || now - this.lastProbe < 750) return;
    const size = Math.min(this.length, 40000);
    const pcm = new Int16Array(size);
    let remaining = size;
    for (let i = this.parts.length - 1; i >= 0 && remaining; i--) {
      const part = this.parts[i];
      const take = Math.min(part.length, remaining);
      pcm.set(part.subarray(part.length - take), remaining - take);
      remaining -= take;
    }
    this.lastProbe = now;
    const epoch = this.epoch;
    this.probePromise = api("/api/voice/probe", { method: "POST", headers: this.headers(), body: pcm.buffer, signal: AbortSignal.timeout(5000) })
      .then((reply) => {
        if (epoch !== this.epoch || !this.token || reply.state !== "activated") return;
        if (typeof companion !== "undefined") companion.interruptDelivery();
        if (this.playing) { this.stopPlayback(); this.epoch++; }
        this.wakeUntil = performance.now() + 10000;
        this.state("I'm listening…");
        this.acknowledge();
      }).catch(() => {}).finally(() => { this.probePromise = null; });
  },

  samples(samples) {
    if (!this.token) { this.reset(); return; }
    if (this.pending && !this.working && !busy && !this.playing) { const next = this.pending; this.pending = null; this.hear(next.pcm, next.endedAt); }
    let energy = 0;
    const pcm = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      energy += samples[i] * samples[i];
      pcm[i] = Math.max(-32768, Math.min(32767, Math.round(samples[i] * 32768)));
    }
    const rms = Math.sqrt(energy / samples.length);
    $("voice-level").value = Math.min(1, rms * 12);
    const threshold = Math.max(0.0035, Math.min(0.018, this.noise * 2.8));
    const loud = rms > threshold;
    if (!this.speaking) {
      if (!loud) this.noise = this.noise * 0.98 + rms * 0.02;
      this.pre.push(pcm);
      this.preLength += pcm.length;
      while (this.preLength > 5600) this.preLength -= this.pre.shift().length;
      if (!loud) return;
      this.speaking = true;
      this.parts = this.pre;
      this.length = this.preLength;
      this.pre = [];
      this.preLength = 0;
    } else { this.parts.push(pcm); this.length += pcm.length; }
    if (loud) { this.voiced += pcm.length; this.lastSpeech = performance.now(); }
    this.quiet = loud ? 0 : this.quiet + pcm.length;
    if (this.length >= 24 * 16000) {
      this.reset();
      this.state('Question too long. Say “Hey Nyx” and ask in under 24 seconds.');
      return;
    }
    this.maybeProbe();
    if (this.quiet >= 0.55 * 16000 && this.length >= 0.35 * 16000) {
      if (this.voiced < 1600) { this.reset(); return; }
      const utterance = new Int16Array(this.length);
      let offset = 0;
      for (const part of this.parts) { utterance.set(part, offset); offset += part.length; }
      this.reset();
      if (this.working || busy) this.pending ||= { pcm: utterance, endedAt: this.lastSpeech };
      else this.hear(utterance, this.lastSpeech);
    }
  },

  diagnostic(event, attemptId, stage) {
    if (!this.token) return;
    api("/api/voice/diagnostics", {
      ...json({ event, attempt_id: attemptId, stage }),
      headers: { ...this.headers(), "content-type": "application/json" },
      signal: AbortSignal.timeout(3000),
    }).catch(() => {});
  },

  async playbackContext() {
    if (!this.outputContext || this.outputContext.state === "closed") this.outputContext = new AudioContext({ sampleRate: 24000 });
    const output = this.outputContext;
    if (output.state === "suspended") await output.resume();
    if (output.state !== "running") throw new Error("Audio is paused. Enable listening and try again.");
    return output;
  },

  async streamReply(turn, jobId, active, attemptId, endedAt) {
    const controller = new AbortController();
    this.replyAbort = controller;
    const response = await fetch("/api/voice/reply", { ...json({ turn_id: turn.id, job_id: jobId, stream: true }), headers: { ...this.headers(), "content-type": "application/json" }, signal: controller.signal });
    if (!response.ok) throw new Error((await response.json()).detail || "Speech request failed");
    if (!response.headers.get("content-type")?.includes("application/x-ndjson")) return response.json();
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = "", text = "", result = null, firstAudio = true, firstPlayedMs = null;
    this.pcmSources = new Set();
    this.pcmEnd = 0;
    try {
      while (active()) {
        const { value, done } = await reader.read();
        if (done) break;
        pending += decoder.decode(value, { stream: true });
        let newline;
        while ((newline = pending.indexOf("\n")) >= 0) {
          const line = pending.slice(0, newline);
          pending = pending.slice(newline + 1);
          if (!line.trim() || !active()) continue;
          const event = JSON.parse(line);
          if (event.type === "error") throw new Error(event.message);
          if (event.type === "text") {
            text += event.text;
            $("voice-answer").textContent = `Nyx: ${text}`;
            $("conversation-answer").textContent = text;
          }
          if (event.type === "audio") {
            if (!this.context || this.context.state !== "running") throw new Error("Audio is paused. Enable listening and try again.");
            const output = await this.playbackContext();
            if (!active()) break;
            // Bound queued playback as well as the server's text/audio queues.
            while (active() && this.pcmEnd - output.currentTime > 3) await new Promise(resolve => setTimeout(resolve, 30));
            if (!active()) break;
            const bytes = Uint8Array.from(atob(event.pcm), c => c.charCodeAt(0));
            if (event.sample_rate !== 24000 || bytes.length % 2) throw new Error("Invalid speech audio");
            const view = new DataView(bytes.buffer);
            const buffer = output.createBuffer(1, bytes.length / 2, 24000);
            const channel = buffer.getChannelData(0);
            for (let i = 0; i < channel.length; i++) channel[i] = view.getInt16(i * 2, true) / 32768;
            const source = output.createBufferSource();
            source.buffer = buffer;
            source.connect(output.destination);
            const at = Math.max(output.currentTime + 0.015, this.pcmEnd);
            this.pcmEnd = at + buffer.duration;
            this.pcmSources.add(source);
            source.onended = () => { this.pcmSources.delete(source); source.disconnect(); };
            source.start(at);
            this.playing = true;
            this.state('Speaking · say “Hey Nyx” to interrupt');
            if (firstAudio) {
              firstAudio = false;
              firstPlayedMs = Math.round(performance.now() - endedAt);
              this.diagnostic("playback_started", attemptId, "playback");
              $("voice-timing").textContent = `First audio: ${((performance.now() - endedAt) / 1000).toFixed(2)}s`;
            }
          }
          if (event.type === "done") result = { answer: event.answer, timings: event.timings, audio: null };
        }
      }
      if (!active()) throw new Error("Response stopped");
      if (!result) throw new Error("The response stream ended early. Please try again.");
      while (active() && this.pcmSources.size) await new Promise(resolve => setTimeout(resolve, 30));
      if (!active()) throw new Error("Response stopped");
      this.playing = false;
      if (firstPlayedMs !== null) result.timings.end_of_speech_to_playback_ms = firstPlayedMs;
      return result;
    } finally {
      await reader.cancel().catch(() => {});
      if (this.replyAbort === controller) this.replyAbort = null;
    }
  },

  async sayChecking(turn, active) {
    try {
      const reply = await api("/api/voice/acknowledgement", { ...json({ turn_id: turn.id }), headers: { ...this.headers(), "content-type": "application/json" }, signal: AbortSignal.timeout(15000) });
      if (!active() || !reply.audio) return;
      const bytes = Uint8Array.from(atob(reply.audio), (c) => c.charCodeAt(0));
      this.stopPlayback();
      this.url = URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
      const player = new Audio(this.url);
      this.player = player;
      this.playing = true;
      player.onended = player.onerror = () => { if (this.player === player) this.stopPlayback(); };
      try { await player.play(); } catch { if (this.player === player) this.stopPlayback(); }
    } catch { /* The answer can still finish if the brief acknowledgement fails. */ }
  },

  async hear(pcm, endedAt = performance.now()) {
    if (this.working || !this.token) return;
    this.working = true;
    if (this.probePromise) await this.probePromise;
    if (!this.token) { this.working = false; return; }
    const epoch = this.epoch;
    $("voice-play").hidden = true;
    const active = () => this.token && epoch === this.epoch;
    const attemptId = crypto.randomUUID();
    let stage = "transcription";
    try {
      const began = performance.now();
      if (!this.playing && performance.now() < this.wakeUntil) this.state("Listening…");
      const turn = await api("/api/voice/utterance", { method: "POST", headers: { ...this.headers(), "x-nyx-attempt": attemptId }, body: pcm.buffer, signal: AbortSignal.timeout(100000) });
      if (!active()) return;
      if (turn.state === "listening") { if (!this.playing) this.state('Ready when you are · say “Hey Nyx”'); return; }
      if (turn.state === "activated") {
        if (this.playing) this.stopPlayback();
        this.state("Yes? Ask your question…");
        this.wakeUntil = performance.now() + 10000;
        this.acknowledge();
        clearTimeout(this.activation);
        this.activation = setTimeout(() => { if (active() && !this.working) this.state('Listening locally · say “Hey Nyx”'); }, 10000);
        return;
      }
      this.stopPlayback();
      this.wakeUntil = 0;
      clearTimeout(this.activation);
      $("voice-question").textContent = `You: ${turn.transcript}`;
      conversation.begin(turn.transcript, turn.plan.lookup === true);
      $("voice-cancel").hidden = false;
      this.state(["chat", "clarify", "direct"].includes(turn.plan.mode) ? "Thinking…" : "Checking visual evidence…");
      let jobId = null;
      const plan = turn.plan;
      if (["chat", "clarify", "direct"].includes(plan.mode)) $("answer-panel").hidden = true;
      let visualStarted = performance.now();
      let visualMs = 0;
      if (!["clarify", "chat", "direct"].includes(plan.mode)) {
        if (plan.object_query) $("object-query").value = plan.object_query;
        stage = "agent";
        let checking = true;
        if (plan.lookup !== false) this.sayChecking(turn, () => active() && checking);
        let response;
        try { response = await companion.request(turn.transcript, turn); }
        finally { checking = false; this.stopPlayback(); }
        jobId = response.jobId;
        $("voice-answer").textContent = `Nyx: ${response.result.answer}`;
        const output = response.result.visual;
        if (!active()) return;
        if (output?.scope) showAnswer(output);
        visualMs = Math.round(performance.now() - visualStarted);
      }
      stage = "speech";
      this.state("Preparing speech…");
      const reply = await this.streamReply(turn, jobId, active, attemptId, endedAt);
      if (!active()) return;
      $("voice-answer").textContent = `Nyx: ${reply.answer}`;
      conversation.answer(reply.answer);
      const timings = { ...turn.timings, visual_ms: visualMs, ...reply.timings, total_ms: Math.round(performance.now() - began) };
      $("voice-timing").textContent = Object.entries(timings).map(([name, ms]) => `${name.replace(/_ms$/, "").replaceAll("_", " ")}: ${(ms / 1000).toFixed(2)}s`).join(" · ");
      this.refresh().catch(() => {});
      if (!active()) return;
      if (reply.audio) {
        stage = "playback";
        const bytes = Uint8Array.from(atob(reply.audio), (c) => c.charCodeAt(0));
        this.url = URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
        const player = new Audio(this.url);
        this.player = player;
        this.playing = true;
        this.state('Speaking · say “Hey Nyx” to interrupt');
        player.onended = () => {
          if (!active()) return;
          this.stopPlayback();
          this.reset();
          $("voice-cancel").hidden = true;
          this.listen(turn.id).catch(() => this.state('Listening locally · say “Hey Nyx”'));
        };
        player.onerror = () => { if (active()) { this.diagnostic("playback_failed", attemptId, stage); this.stopPlayback(); this.state("Audio could not play. The answer is shown above."); } };
        try {
          await player.play();
          this.diagnostic("playback_started", attemptId, stage);
          timings.end_of_speech_to_playback_ms = Math.round(performance.now() - endedAt);
          $("voice-timing").textContent = Object.entries(timings).map(([name, ms]) => `${name.replace(/_ms$/, "").replaceAll("_", " ")}: ${(ms / 1000).toFixed(2)}s`).join(" · ");
        }
        catch { this.diagnostic("playback_blocked", attemptId, stage); this.playing = false; this.state("Browser blocked speech playback. Click Play answer."); $("voice-play").hidden = false; }
      } else { this.state(reply.warning || 'Listening locally · say “Hey Nyx”'); await this.listen(turn.id); }
    } catch (error) {
      this.diagnostic("browser_turn_failed", attemptId, stage);
      this.refresh().catch(() => {});
      if (active()) {
        if (["Let me check…", "Thinking…"].includes($("conversation-answer").textContent)) conversation.answer("I couldn’t finish that request. Please try again.");
        if (stage !== "transcription") await api("/api/voice/cancel", { method: "POST", headers: { ...this.headers(), "x-nyx-cancel-reason": "error_cleanup" } }).catch(() => {});
        this.stopPlayback();
        this.state(`${error.message} Say “Hey Nyx” to retry.`);
      }
    } finally {
      this.working = false;
      conversation.render();
      if (this.pending && this.token) { const next = this.pending; this.pending = null; this.hear(next.pcm, next.endedAt); }
      if (!this.playing) $("voice-cancel").hidden = true;
    }
  },

  async refresh() {
    const status = await api("/api/voice");
    $("voice-history").replaceChildren();
    for (const row of status.conversations) {
      const line = document.createElement("p");
      line.textContent = `${new Date(row.at).toLocaleString()} · You: ${row.transcript} · Nyx: ${row.answer || row.status}${row.sources_available ? "" : " · Source deleted; this transcript is not visual evidence."}`;
      $("voice-history").append(line);
    }
  },
};

$("voice-enable").onclick = () => voice.enable();
$("voice-mute").onclick = () => voice.stop();
$("voice-cancel").onclick = () => voice.cancel();
$("voice-play").onclick = async () => {
  $("voice-play").hidden = true;
  const text = $("voice-answer").textContent.replace(/^Nyx: /, "");
  // The existing audio URL is ephemeral; a blocked playback can be retried without a cloud request.
  if (voice.player) { voice.playing = true; await voice.player.play().catch(() => { voice.playing = false; voice.state("Playback still blocked."); $("voice-play").hidden = false; }); }
  else voice.state(`Answer available on screen: ${text}`);
};
window.addEventListener("nyx-source-deleted", () => voice.refresh().catch(() => {}));
window.addEventListener("nyx-camera-stopped", () => voice.stop("Camera stopped. Microphone muted too."));
window.addEventListener("pagehide", () => voice.stop("Page closed."));

(async () => {
  try {
    const status = await api("/api/voice");
    if (!status.configured) return;
    $("voice-panel").hidden = false;
    $("preview-caption").textContent = "Camera and local wake listening start with Nyx. Allow browser permissions when prompted.";
    await voice.refresh();
    const coverage = await refreshCoverage();
    if (coverage.session && ["recording", "paused"].includes(coverage.session.state)) {
      voice.state("Another recording session is open. Stop it before starting here.");
      return;
    }
    await Promise.all([startCapture(), voice.start()]);
  } catch (error) { voice.state(`Could not start automatically: ${error.message}`); }
})();

$("voice-listen-now").onclick = async () => {
  try {
    if (!voice.token) await voice.start();
    if (voice.working || companion.working) { voice.state("A request is running. Stop it first if you want to start another."); return; }
    await voice.cancel("listen_now");
    const result = await api("/api/voice/activate", { method: "POST", headers: voice.headers() });
    voice.wakeUntil = performance.now() + result.seconds * 1000;
    voice.state("I'm listening. Tell me what you're showing or where you're putting it.");
    voice.acknowledge();
    clearTimeout(voice.activation);
    voice.activation = setTimeout(() => { if (!voice.working && !voice.playing) voice.state('Listening locally · say “Hey Nyx”'); }, result.seconds * 1000);
  } catch (error) { voice.state(error.message); }
};
