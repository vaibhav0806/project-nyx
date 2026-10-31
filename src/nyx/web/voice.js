"use strict";

// LiveKit owns conversational turns. This browser only gates wake audio and plays frames.
const voice = {
  token: null,
  epoch: 0,
  mic: null,
  context: null,
  outputContext: null,
  socket: null,
  working: false,
  playing: false,
  wakeUntil: 0,
  pre: [],
  preLength: 0,
  probePromise: null,
  lastProbe: 0,
  sources: new Set(),
  startedSegments: new Set(),
  segment: 0,
  pcmEnd: 0,
  answer: "",
  ready: false,
  state(text) {
    $("voice-state").textContent = text;
    window.dispatchEvent(new CustomEvent("nyx-voice-state", { detail: text }));
  },
  headers() {
    return { "x-nyx-voice": this.token };
  },
  send(event) {
    if (this.socket?.readyState === WebSocket.OPEN)
      this.socket.send(JSON.stringify(event));
  },
  async start() {
    if (this.mic || this.starting) return;
    this.starting = true;
    const epoch = ++this.epoch;
    try {
      const session = await api("/api/voice/session", { method: "POST" });
      if (epoch !== this.epoch) return;
      this.token = session.token;
      this.timer = setInterval(
        () =>
          api("/api/voice/heartbeat", {
            method: "POST",
            headers: this.headers(),
          }).catch(() => this.stop()),
        10000,
      );
      this.context = new AudioContext({ sampleRate: 16000 });
      this.outputContext = new AudioContext({ sampleRate: 24000 });
      const microphone = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });
      if (epoch !== this.epoch) {
        microphone.getTracks().forEach((track) => track.stop());
        return;
      }
      this.mic = microphone;
      await this.context.audioWorklet.addModule("/audio-worklet.js");
      this.node = new AudioWorkletNode(this.context, "nyx-audio");
      this.node.port.onmessage = (event) => this.samples(event.data);
      this.context.createMediaStreamSource(this.mic).connect(this.node);
      this.node.connect(this.context.destination);
      await Promise.all([this.context.resume(), this.outputContext.resume()]);
      const ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/voice/live`,
      );
      this.socket = ws;
      ws.onopen = () =>
        this.send({
          token: this.token,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        });
      this.messages = Promise.resolve();
      ws.onmessage = (event) => {
        this.messages = this.messages
          .then(() => this.receive(JSON.parse(event.data), epoch))
          .catch((error) => this.state(error.message));
      };
      ws.onclose = () => {
        if (epoch === this.epoch)
          this.stop("Voice connection closed. Enable mic to reconnect.");
      };
      $("voice-enable").hidden = true;
      $("voice-mute").hidden = false;
      this.state("Connecting");
    } catch (error) {
      await this.stop(error.message);
    } finally {
      this.starting = false;
    }
  },
  async enable() {
    if (!this.mic) await this.start();
    await this.context?.resume();
    await this.outputContext?.resume();
  },
  async activate() {
    if (!this.ready) {
      this.state("Connecting");
      return;
    }
    await api("/api/voice/activate", {
      method: "POST",
      headers: this.headers(),
    });
    this.wakeUntil = performance.now() + 30000;
    for (const part of this.pre) this.socket.send(part.buffer);
    this.pre = [];
    this.preLength = 0;
    this.state("Listening");
  },
  samples(samples) {
    if (!this.token) return;
    const pcm = Int16Array.from(samples, (s) =>
      Math.max(-32768, Math.min(32767, Math.round(s * 32768))),
    );
    let energy = 0;
    for (const s of samples) energy += s * s;
    $("voice-level").value = Math.min(
      1,
      Math.sqrt(energy / samples.length) * 12,
    );
    if (this.ready && performance.now() < this.wakeUntil) {
      if (this.socket.bufferedAmount < 96000) this.socket.send(pcm.buffer);
      else this.stop("Voice connection is too slow. Please reconnect.");
      return;
    }
    this.pre.push(pcm);
    this.preLength += pcm.length;
    while (this.preLength > 48000) this.preLength -= this.pre.shift().length;
    if (
      !this.ready ||
      this.probePromise ||
      this.preLength < 9600 ||
      performance.now() - this.lastProbe < 750 ||
      energy / samples.length < 0.00001
    )
      return;
    this.lastProbe = performance.now();
    const buffer = new Int16Array(this.preLength);
    let offset = 0;
    for (const part of this.pre) {
      buffer.set(part, offset);
      offset += part.length;
    }
    const epoch = this.epoch;
    this.probePromise = api("/api/voice/probe", {
      method: "POST",
      headers: this.headers(),
      body: buffer.buffer,
    })
      .then((reply) => {
        if (epoch === this.epoch && reply.state === "activated")
          return this.activate();
      })
      .catch(() => {})
      .finally(() => {
        this.probePromise = null;
      });
  },
  async receive(event, epoch) {
    if (epoch !== this.epoch) return;
    if (event.type === "ready") {
      this.ready = true;
      this.state("Listening");
    }
    if (event.type === "question") {
      this.answer = "";
      conversation.begin(event.text);
      $("voice-question").textContent = `You: ${event.text}`;
      this.lastTranscript = performance.now();
      this.wakeUntil = performance.now() + 30000;
    }
    if (event.type === "text") {
      this.answer += event.text;
      conversation.answer(this.answer);
      $("voice-answer").textContent = `Nyx: ${this.answer}`;
    }
    if (event.type === "state") {
      this.working = event.state === "thinking";
      this.playing = event.state === "speaking";
      if (event.state === "listening" && this.lastTranscript)
        this.wakeUntil = performance.now() + 10000;
      this.state(
        {
          listening: "Listening",
          thinking: "Thinking",
          speaking: "Speaking",
        }[event.state] || "Connecting",
      );
      conversation.render();
    }
    if (event.type === "audio") {
      if (event.segment < this.segment) return;
      const output = this.outputContext;
      await output.resume();
      const bytes = Uint8Array.from(atob(event.pcm), (c) => c.charCodeAt(0));
      const view = new DataView(bytes.buffer);
      const buffer = output.createBuffer(
        1,
        bytes.length / 2,
        event.sample_rate,
      );
      const channel = buffer.getChannelData(0);
      for (let i = 0; i < channel.length; i++)
        channel[i] = view.getInt16(i * 2, true) / 32768;
      const source = output.createBufferSource();
      source.buffer = buffer;
      source.connect(output.destination);
      const at = Math.max(output.currentTime + 0.015, this.pcmEnd);
      this.pcmEnd = at + buffer.duration;
      if (!this.startedSegments.has(event.segment)) {
        this.startedSegments.add(event.segment);
        setTimeout(
          () => {
            if (epoch === this.epoch && event.segment >= this.segment)
              this.send({
                type: "playback_started",
                segment: event.segment,
                after_transcript_ms: this.lastTranscript
                  ? Math.round(performance.now() - this.lastTranscript)
                  : null,
              });
          },
          Math.max(0, (at - output.currentTime) * 1000),
        );
      }
      this.sources.add(source);
      source.onended = () => {
        this.sources.delete(source);
        source.disconnect();
      };
      source.start(at);
    }
    if (event.type === "flush") {
      const segment = event.segment;
      setTimeout(
        () => {
          if (epoch === this.epoch && segment >= this.segment)
            this.send({ type: "played", segment });
        },
        Math.max(0, (this.pcmEnd - this.outputContext.currentTime) * 1000),
      );
    }
    if (event.type === "clear") {
      this.segment = event.segment;
      this.stopPlayback();
      this.answer = "";
    }
    if (event.type === "tool") {
      companion
        .request(event.message, { id: event.turn_id, request_id: event.id }, event.action)
        .then((response) => {
          if (epoch === this.epoch)
            this.send({
              type: "tool_result",
              id: event.id,
              answer: response.result.answer,
              sources: response.result.sources,
            });
        })
        .catch(() =>
          this.send({
            type: "tool_result",
            id: event.id,
            answer: "I couldn't finish that check.",
          }),
        );
    }
    if (event.type === "cancel_tool") await companion.cancel();
    if (event.type === "error") await this.stop(event.message);
  },
  stopPlayback() {
    for (const source of this.sources) {
      source.onended = null;
      source.stop();
    }
    this.sources.clear();
    this.pcmEnd = 0;
    this.playing = false;
  },
  async cancel() {
    this.send({ type: "interrupt" });
    this.stopPlayback();
    if (companion.working) await companion.cancel();
    this.working = false;
    this.state("Listening");
  },
  async stop(text = "Mic off") {
    this.epoch++;
    this.ready = false;
    this.lastTranscript = null;
    this.segment = 0;
    this.answer = "";
    this.startedSegments.clear();
    clearInterval(this.timer);
    this.socket?.close();
    this.socket = null;
    this.stopPlayback();
    this.mic?.getTracks().forEach((track) => track.stop());
    this.mic = null;
    this.node?.disconnect();
    await this.context?.close().catch(() => {});
    await this.outputContext?.close().catch(() => {});
    this.context = null;
    this.outputContext = null;
    const token = this.token;
    this.token = null;
    this.working = false;
    this.wakeUntil = 0;
    this.pre = [];
    this.preLength = 0;
    if (token)
      api("/api/voice/session", {
        method: "DELETE",
        headers: { "x-nyx-voice": token },
      }).catch(() => {});
    $("voice-enable").hidden = false;
    $("voice-mute").hidden = true;
    $("voice-play").hidden = true;
    this.state(text);
  },
  async refresh() {
    const status = await api("/api/voice");
    $("voice-history").replaceChildren();
    for (const row of status.conversations) {
      const line = document.createElement("p");
      line.textContent = `${new Date(row.at).toLocaleString()} · You: ${row.transcript} · Nyx: ${row.answer || row.status}`;
      $("voice-history").append(line);
    }
  },
};
$("voice-enable").onclick = () => voice.enable();
$("voice-mute").onclick = () => voice.stop();
$("voice-cancel").onclick = () => voice.cancel();
$("voice-listen-now").onclick = () => voice.activate();
$("voice-play").hidden = true;
window.addEventListener("pagehide", () => voice.stop("Page closed."));

window.addEventListener("nyx-source-deleted", () =>
  voice.refresh().catch(() => {}),
);
window.addEventListener("nyx-camera-stopped", () =>
  voice.stop("Camera stopped. Microphone muted too."),
);
(async () => {
  try {
    const status = await api("/api/voice");
    if (!status.configured) return;
    $("voice-panel").hidden = false;
    await voice.refresh();
    const coverage = await refreshCoverage();
    if (
      coverage.session &&
      ["recording", "paused"].includes(coverage.session.state)
    ) {
      voice.state(
        "Another recording session is open. Stop it before starting here.",
      );
      return;
    }
    await Promise.all([startCapture(), voice.start()]);
  } catch (error) {
    voice.state(`Could not start automatically: ${error.message}`);
  }
})();
