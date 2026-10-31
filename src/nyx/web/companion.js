"use strict";

const conversation = {
  configured: false,
  status: "Getting ready…",
  begin(text, checking = false) {
    $("conversation-question").textContent = text;
    $("conversation-question").hidden = false;
    $("conversation-answer").textContent = checking ? "Let me check…" : "Thinking…";
    $("conversation-hint").hidden = true;
    $("answer-panel").hidden = true;
    $("replay-panel").hidden = true;
    $("replay").pause();
    $("source-dialog").close();
    this.status = "Thinking…";
    this.render();
  },
  answer(text) {
    $("conversation-answer").textContent = text;
    this.status = "Ready for your next question";
    this.render();
  },
  render() {
    const speaking = voice.playing || companion.delivering;
    const working = voice.working || companion.working;
    const stopping = speaking || working;
    const label = speaking ? "Stop speaking" : working ? "Stop request" : !$("voice-play").hidden ? "Play answer" : "Talk to Nyx";
    $("talk").setAttribute("aria-label", label);
    $("talk-label").textContent = label;
    $("talk").disabled = !this.configured && !stopping;
    const micOn = Boolean(voice.mic);
    $("talk").classList.toggle("is-muted", !micOn);
    $("mute").classList.toggle("is-muted", !micOn);
    $("mute").setAttribute("aria-pressed", String(!micOn));
    $("mute-label").textContent = micOn ? "Mute mic" : "Enable mic";
    $("mute").setAttribute("aria-label", micOn ? "Mute microphone" : "Enable microphone");
    $("mute").disabled = !this.configured;
    $("conversation-state").textContent = speaking ? "Nyx is speaking" : this.status;
    document.querySelector(".wave").classList.toggle("active", speaking || (micOn && voice.wakeUntil > performance.now()));
    $("view-source").hidden = $("answer-panel").hidden;
    $("camera-toggle").setAttribute("aria-label", enabled ? "Pause camera" : paused ? "Resume camera" : "Start camera");
    $("camera-toggle").disabled = requestingCamera || (!enabled && busy);
  },
};

// Shares the existing camera; selected images are sent to cloud inference by the server.
const companion = {
  epoch: 0, job: null, working: false, observing: false, delivering: false,
  armed: false, refreshBusy: false, player: null, delivery: null, deliveryIntention: null,
  deliveryEpoch: 0, reviewCandidate: null,

  interruptDelivery() {
    this.deliveryEpoch++;
    this.player?.pause();
  },

  snapshot(maxWidth = 1280, maxHeight = Infinity) {
    const viewer = $("viewer");
    if (!enabled || !stream || !viewer.videoWidth) return {};
    const canvas = document.createElement("canvas");
    const scale = Math.min(1, maxWidth / viewer.videoWidth, maxHeight / viewer.videoHeight);
    canvas.width = Math.floor(viewer.videoWidth * scale);
    canvas.height = Math.floor(viewer.videoHeight * scale);
    canvas.getContext("2d").drawImage(viewer, 0, 0, canvas.width, canvas.height);
    return { snapshot: canvas.toDataURL("image/jpeg", 0.75).split(",")[1], captured_at: new Date().toISOString() };
  },

  async request(text, turn = null) {
    if (this.working) throw new Error("Finish or stop the current companion request first.");
    this.interruptDelivery();
    this.working = true;
    if (!turn) conversation.begin(text);
    const epoch = ++this.epoch;
    $("companion-stop").hidden = false;
    $("companion-send").disabled = true;
    $("answer-panel").hidden = true;
    this.job = null;
    try {
      if (epoch !== this.epoch) throw new Error("Request stopped");
      const body = { ...this.reviewCandidate, message: text, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, request_id: turn?.id || crypto.randomUUID(), ...this.snapshot(), voice_turn_id: turn?.id || null };
      const headers = turn ? { "x-nyx-voice": voice.token, "content-type": "application/json" } : { "content-type": "application/json" };
      $("companion-status").textContent = "Checking evidence and deciding the next step…";
      const result = await task("/api/agent", { method: "POST", headers, body: JSON.stringify(body) }, (id) => {
        this.job = id;
        if (epoch !== this.epoch) api(`/api/agent/${id}/cancel`, { method: "POST" }).catch(() => {});
      });
      if (epoch !== this.epoch) throw new Error("Request stopped");
      $("companion-status").textContent = result.answer;
      if (!turn) conversation.answer(result.answer);
      $("companion-steps").replaceChildren();
      for (const step of result.steps) {
        const line = document.createElement("p");
        line.textContent = `${step.action.replaceAll("_", " ")}${step.query ? ` · ${step.query}` : ""}${step.hours !== undefined ? ` · ${step.hours || "all dated"} hours` : ""}`;
        $("companion-steps").append(line);
      }
      if (result.visual?.scope) showAnswer(result.visual);
      else this.reviewCandidate = null;
      await this.refresh();
      return { result, jobId: this.job };
    } finally {
      this.working = false;
      $("companion-stop").hidden = true;
      $("companion-send").disabled = false;
      conversation.render();
    }
  },

  async cancel() {
    this.interruptDelivery();
    this.epoch++;
    if (this.job) await api(`/api/agent/${this.job}/cancel`, { method: "POST" }).catch(() => {});
    $("companion-status").textContent = "Request stopped.";
    conversation.status = "Request stopped. You can ask again.";
    conversation.render();
  },

  async observe() {
    if (this.observing || !enabled || !captureSession || !this.armed) return;
    this.observing = true;
    try {
      const frame = this.snapshot(640, 360);
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
      conversation.answer(reply.message);
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
      conversation.render();
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
      const reminderStates = { armed: "Waiting for your next departure", pending: "Ready to speak", delivering: "Speaking", delivered: "Spoken; awaiting your acknowledgement", acknowledged: "Acknowledged", cancelled: "Cancelled", missed: "Delivery missed", interrupted: "Delivery interrupted", failed: "Could not speak" };
      for (const item of state.reminders) {
        const row = document.createElement("p");
        row.append(document.createTextNode(`${item.message} · ${reminderStates[item.state] || item.state} `));
        const created = new Date(item.created_at);
        const createdLabel = Number.isNaN(created.getTime()) ? "" : created.toLocaleString();
        if (createdLabel) {
          const timestamp = document.createElement("time");
          timestamp.dateTime = item.created_at;
          timestamp.textContent = ` · Requested ${createdLabel} `;
          row.append(timestamp);
        }
        if (["armed", "pending", "delivering"].includes(item.state)) {
          const cancel = document.createElement("button");
          cancel.textContent = "Cancel";
          cancel.setAttribute("aria-label", `Cancel reminder: ${item.message}${createdLabel ? `, requested ${createdLabel}` : ""}`);
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
      const phases = { quiet: "Waiting for activity", collecting: "Watching whether the change persists", active: "Following activity", settling: "Following activity", settled: "Activity settled" };
      const decisions = { superseded_evidence: "Scene changed or evidence expired; waiting for a fresh check", uncertain: "Departure unclear; continuing to watch", no_departure: "No departure indicated", missing_exit_cues: "Exit movement not established", unresolved_exit: "Cannot identify the home exit from this view", inconsistent_exit: "Exit location changed; waiting for consistent evidence", unconfirmed_approach: "Person movement does not confirm approaching the exit", no_matching_request: "Waiting for evidence after the request" };
      const phase = phases[state.observation.phase] || "Watching locally for departure cues";
      const continuity = { capture_stale: "Camera updates stopped; waiting for fresh evidence", evidence_window_lost: "The checked images are too old; waiting for a fresh check", scene_changed: "The scene changed while checking; watching again", scene_unsettled: "A new change is still settling; watching again" };
      const checking = state.observation.state === "checking";
      const decision = checking ? "Checking the recent activity" : continuity[state.observation.delivery_continuity?.reason] || decisions[state.observation.decision?.reason];
      $("observation-state").textContent = !enabled ? "Camera off; departure reminders are waiting for observation." : state.observation.error ? `Observation interrupted: ${state.observation.error}` : `${this.armed ? phase : "No armed departure reminder"}${this.armed && decision ? ` · ${decision}` : ""}${!checking && state.observation.judgment ? ` · ${state.observation.judgment.cue}` : ""}`;
      if (state.pending.length) this.deliver(state.pending[0]);
    } finally { this.refreshBusy = false; }
  },
};

$("companion-form").onsubmit = async event => {
  event.preventDefault();
  if (busy || companion.working || voice.working) return;
  try { await companion.request($("companion-message").value.trim()); }
  catch (error) {
    $("companion-status").textContent = error.message;
    conversation.answer(error.message === "Request stopped" ? "Request stopped." : "I couldn’t finish that request. Please try again.");
    conversation.status = error.message;
    conversation.render();
  }
};
$("companion-stop").onclick = () => { companion.cancel(); };
window.addEventListener("nyx-camera-stopped", () => { companion.interruptDelivery(); });
window.addEventListener("pagehide", () => { companion.cancel(); });
setInterval(() => companion.observe(), 100);
setInterval(() => companion.refresh().catch(() => {}), 1000);
companion.refresh().catch(error => { $("companion-status").textContent = error.message; });

$("open-settings").onclick = () => $("settings-dialog").showModal();
$("view-source").onclick = () => $("source-dialog").showModal();
for (const button of document.querySelectorAll("[data-close]")) button.onclick = () => $(button.dataset.close).close();
$("source-dialog").addEventListener("close", () => $("replay").pause());
$("type-toggle").onclick = () => {
  $("typing-panel").hidden = !$("typing-panel").hidden;
  $("type-toggle").setAttribute("aria-expanded", String(!$("typing-panel").hidden));
  if (!$("typing-panel").hidden) $("companion-message").focus();
};
$("talk").onclick = async () => {
  if (voice.playing || voice.working || companion.working || companion.delivering) {
    await voice.cancel();
    if (companion.delivering) companion.interruptDelivery();
  } else if (!$("voice-play").hidden) {
    await $("voice-play").onclick();
  } else {
    await voice.enable();
    if (voice.token && voice.context?.state === "running") await $("voice-listen-now").onclick();
  }
  conversation.render();
};
$("mute").onclick = async () => {
  if (voice.mic) await voice.stop("Microphone muted. Tap Enable mic to listen again.");
  else await voice.start();
  conversation.render();
};
$("camera-toggle").onclick = async () => {
  if (enabled) await stopCapture("Paused by user", "paused");
  else if (paused) await $("resume").onclick();
  else await startCapture();
  conversation.render();
};
window.addEventListener("nyx-ui-update", () => conversation.render());
window.addEventListener("nyx-voice-state", event => {
  conversation.status = event.detail;
  conversation.render();
});
window.addEventListener("nyx-source-deleted", () => {
  $("view-source").hidden = true;
  $("source-dialog").close();
});
api("/api/voice").then(status => {
  conversation.configured = status.configured;
  if (!status.configured) {
    conversation.status = "Voice isn’t configured. You can type a question.";
    $("conversation-hint").textContent = "Use Type instead to ask a question.";
  } else if (conversation.status === "Getting ready…") conversation.status = "Starting microphone…";
  conversation.render();
}).catch(error => { conversation.status = error.message; conversation.render(); });
