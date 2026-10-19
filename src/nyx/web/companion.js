"use strict";

// Shares the existing camera; never opens another device or uploads images off localhost.
const companion = {
  epoch: 0, job: null, working: false, observing: false, delivering: false,
  armed: false, refreshBusy: false, player: null, delivery: null, deliveryIntention: null,
  deliveryEpoch: 0,

  interruptDelivery() {
    this.deliveryEpoch++;
    this.player?.pause();
  },

  snapshot(maxWidth = 1280) {
    const viewer = $("viewer");
    if (!enabled || !stream || !viewer.videoWidth) return {};
    const canvas = document.createElement("canvas");
    const scale = Math.min(1, maxWidth / viewer.videoWidth);
    canvas.width = Math.floor(viewer.videoWidth * scale);
    canvas.height = Math.floor(viewer.videoHeight * scale);
    canvas.getContext("2d").drawImage(viewer, 0, 0, canvas.width, canvas.height);
    return { snapshot: canvas.toDataURL("image/jpeg", 0.75).split(",")[1], captured_at: new Date().toISOString() };
  },

  async request(text, turn = null) {
    if (this.working) throw new Error("Finish or stop the current companion request first.");
    this.interruptDelivery();
    this.working = true;
    const epoch = ++this.epoch;
    $("companion-stop").hidden = false;
    $("companion-send").disabled = true;
    $("answer-panel").hidden = true;
    this.job = null;
    try {
      $("companion-status").textContent = "Preparing local reasoning…";
      await task("/api/companion/warmup", { method: "POST" });
      if (epoch !== this.epoch) throw new Error("Request stopped");
      const body = { message: text, request_id: turn?.id || crypto.randomUUID(), ...this.snapshot(), voice_turn_id: turn?.id || null };
      const headers = turn ? { "x-nyx-voice": voice.token, "content-type": "application/json" } : { "content-type": "application/json" };
      $("companion-status").textContent = "Checking evidence and deciding the next step…";
      const result = await task("/api/agent", { method: "POST", headers, body: JSON.stringify(body) }, (id) => {
        this.job = id;
        if (epoch !== this.epoch) api(`/api/agent/${id}/cancel`, { method: "POST" }).catch(() => {});
      });
      if (epoch !== this.epoch) throw new Error("Request stopped");
      $("companion-status").textContent = result.answer;
      $("companion-steps").replaceChildren();
      for (const step of result.steps) {
        const line = document.createElement("p");
        line.textContent = `${step.action.replaceAll("_", " ")}${step.query ? ` · ${step.query}` : ""}${step.hours !== undefined ? ` · ${step.hours || "all dated"} hours` : ""}`;
        $("companion-steps").append(line);
      }
      if (result.visual?.scope) showAnswer(result.visual);
      await this.refresh();
      return { result, jobId: this.job };
    } finally {
      this.working = false;
      $("companion-stop").hidden = true;
      $("companion-send").disabled = false;
    }
  },

  async cancel() {
    this.interruptDelivery();
    this.epoch++;
    if (this.job) await api(`/api/agent/${this.job}/cancel`, { method: "POST" }).catch(() => {});
    $("companion-status").textContent = "Request stopped. Departure reminders have separate Cancel controls.";
  },

  async observe() {
    if (this.observing || !enabled || !captureSession || !this.armed) return;
    this.observing = true;
    try {
      const frame = this.snapshot(640);
      if (!frame.snapshot) return;
      await api("/api/observe", json({ session_id: captureSession.id, captured_at: frame.captured_at, image: frame.snapshot }));
    } catch (error) {
      $("observation-state").textContent = `Observation unavailable: ${error.message}`;
    } finally { this.observing = false; }
  },

  async deliver(item) {
    if (this.delivering || this.working || busy || voice.working || voice.playing || !enabled) return;
    this.delivering = true;
    const epoch = ++this.deliveryEpoch;
    this.deliveryIntention = item.intention_id;
    $("companion-stop").hidden = false;
    let outcome = "failed";
    try {
      const reply = await api(`/api/deliveries/${item.id}/claim`, { method: "POST" });
      this.delivery = item.id;
      this.deliveryIntention = reply.intention_id;
      if (epoch !== this.deliveryEpoch || !enabled) { outcome = "interrupted"; return; }
      $("companion-status").textContent = reply.message;
      if (!reply.audio) {
        $("companion-status").textContent += " · Spoken reminder unavailable; displayed only.";
        return;
      }
      if (!enabled) { outcome = "interrupted"; return; }
      const bytes = Uint8Array.from(atob(reply.audio), c => c.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
      try {
        const player = new Audio(url);
        this.player = player;
        $("companion-stop").hidden = false;
        outcome = await new Promise(resolve => {
          player.onended = () => resolve("played");
          player.onerror = () => resolve("failed");
          player.onpause = () => { if (!player.ended) resolve("interrupted"); };
          player.play().catch(() => resolve("failed"));
        });
      } finally { URL.revokeObjectURL(url); this.player = null; }
    } catch (error) {
      $("companion-status").textContent = `Reminder could not play: ${error.message}`;
    } finally {
      if (this.delivery) await api(`/api/deliveries/${item.id}/outcome`, json({ outcome })).catch(() => {});
      this.delivery = null;
      this.deliveryIntention = null;
      this.delivering = false;
      if (!this.working) $("companion-stop").hidden = true;
    }
  },

  async refresh() {
    if (this.refreshBusy) return;
    this.refreshBusy = true;
    try {
      const state = await api("/api/companion");
      this.armed = state.reminders.some(row => row.state === "armed");
      if (this.deliveryIntention && state.reminders.some(row => row.id === this.deliveryIntention && !["pending", "delivering"].includes(row.state))) this.interruptDelivery();
      $("companion-thread").replaceChildren();
      for (const turn of state.conversations.slice(-6)) {
        const row = document.createElement("p");
        row.textContent = `You: ${turn.transcript} · Nyx: ${turn.answer || turn.status}${turn.sources_available ? "" : " · Original visual source deleted"}`;
        $("companion-thread").append(row);
      }
      $("reminders").replaceChildren();
      for (const item of state.reminders) {
        const row = document.createElement("p");
        row.append(document.createTextNode(`${item.message} · ${item.state} `));
        if (["armed", "pending", "delivering"].includes(item.state)) {
          const cancel = document.createElement("button");
          cancel.textContent = "Cancel";
          cancel.onclick = async () => {
            if (this.deliveryIntention === item.id) this.interruptDelivery();
            await api(`/api/reminders/${item.id}`, { method: "DELETE" });
            await this.refresh();
          };
          row.append(cancel);
        }
        if (item.state === "delivered") {
          const acknowledge = document.createElement("button");
          acknowledge.textContent = "Got it";
          acknowledge.onclick = async () => { await api(`/api/reminders/${item.id}/acknowledge`, { method: "POST" }); await this.refresh(); };
          row.append(acknowledge);
        }
        $("reminders").append(row);
      }
      $("observation-state").textContent = !enabled ? "Camera off; departure reminders are waiting for observation." : state.observation.error ? `Observation interrupted: ${state.observation.error}` : `${this.armed ? "Watching locally for departure cues" : "No armed departure reminder"}${state.observation.judgment ? ` · ${state.observation.judgment.cue}` : ""}`;
      if (state.pending.length) this.deliver(state.pending[0]);
    } finally { this.refreshBusy = false; }
  },
};

$("companion-form").onsubmit = async event => {
  event.preventDefault();
  if (busy || companion.working || voice.working) return;
  try { await companion.request($("companion-message").value.trim()); }
  catch (error) { $("companion-status").textContent = error.message; }
};
$("companion-stop").onclick = () => { companion.cancel(); };
window.addEventListener("nyx-camera-stopped", () => { companion.interruptDelivery(); });
window.addEventListener("pagehide", () => { companion.cancel(); });
setInterval(() => companion.observe(), 750);
setInterval(() => companion.refresh().catch(() => {}), 1000);
companion.refresh().catch(error => { $("companion-status").textContent = error.message; });
