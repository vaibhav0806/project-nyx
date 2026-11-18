// Run the actual browser transport with synthetic PCM; never open browser hardware.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

let now = 0;
let forwarded = 0;
const elements = new Map();
const context = {
  performance: { now: () => now },
  Float32Array,
  Int16Array,
  TextEncoder,
  WebSocket: { OPEN: 1 },
  Set,
  CustomEvent: class {},
  clearInterval() {},
  conversation: {
    stopReveal() {}, render() {}, answer() {},
    begin(text) { context.$("conversation-question").textContent = text; },
  },
  companion: { freezeContext() { return { visual_frames: [] }; } },
  window: { addEventListener() {}, dispatchEvent() {} },
  api: async () => ({ configured: false }),
  renderQuestion(text) { context.$("conversation-question").textContent = text; },
  updateStreamingText(element, text) { element.textContent = text; },
  $: (id) => {
    if (!elements.has(id)) elements.set(id, {});
    return elements.get(id);
  },
};
vm.createContext(context);
const source = fs.readFileSync(path.join(__dirname, "../src/nyx/web/voice.js"), "utf8");
vm.runInContext(`${source}\nglobalThis.subject = voice;`, context);
const voice = context.subject;
Object.assign(voice, {
  token: "synthetic",
  ready: true,
  epoch: 1,
  socket: { readyState: 1, bufferedAmount: 0, send() { forwarded++; }, close() {} },
});
const pcm = new Float32Array(320).fill(0.05);

function sample(expected, message) {
  const before = forwarded;
  voice.samples(pcm);
  assert.equal(forwarded - before, expected, message);
}

async function run() {
  voice.working = true;
  sample(0, "thinking without activation must not open the audio gate");
  voice.working = false;
  voice.wakeUntil = 10000;
  now = 9000;
  sample(1, "activated audio must reach the transport");

  now = 11000;
  voice.working = true;
  sample(1, "the idle deadline must not cut off an active response");
  voice.working = false;
  voice.playing = true;
  sample(1, "speech output must still allow a user interruption");
  voice.playing = false;
  await voice.receive({ type: "user_state", state: "speaking" }, 1);
  sample(1, "the idle deadline must not cut off an utterance");

  voice.lastTranscript = 1;
  await voice.receive({ type: "user_state", state: "listening" }, 1);
  sample(1, "finishing speech must allow the follow-up window");
  now = 22000;
  sample(0, "idle audio must stay local after the follow-up window");

  await voice.receive({ type: "user_state", state: "speaking" }, 0);
  sample(0, "events from an old connection must not reopen audio");
  voice.ready = false;
  voice.working = true;
  sample(0, "a muted connection must not forward even while thinking");
  voice.userSpeaking = true;
  await voice.stop();
  assert.equal(voice.userSpeaking, false, "stopping must clear the previous speech activity");
  voice.ready = true;
  voice.token = "new-synthetic-session";
  sample(0, "a new connection must require a fresh activation");
  await voice.receive({ type: "transcript", text: "Look at this.", new_turn: true }, voice.epoch);
  await voice.receive({ type: "question", text: "Look at this.", display_text: "Look at this.", turn_id: "one" }, voice.epoch);
  await voice.receive({ type: "transcript", text: "Look at this. I plan to keep it in the kitchen.", new_turn: false }, voice.epoch);
  assert.equal(elements.get("conversation-question").textContent, "Look at this. I plan to keep it in the kitchen.", "continued speech must be visible before slow memory finishes");
  await voice.receive({ type: "question", text: "I plan to keep it in the kitchen.", display_text: "Look at this. I plan to keep it in the kitchen.", turn_id: "two" }, voice.epoch);
  assert.equal(elements.get("conversation-question").textContent, "Look at this. I plan to keep it in the kitchen.", "accepting the continuation must not replace its first part");
  assert.equal(voice.turnVisual.id, "two", "display grouping must preserve actual tool ownership");
  const frozen = { context_at: "2026-11-18T00:00:00Z", visual_frames: [{ captured_at: "2026-11-17T23:59:59Z", snapshot: "shown-image" }] };
  context.companion.freezeContext = () => frozen;
  const sent = [];
  voice.send = (event) => sent.push(event);
  await voice.receive({ type: "freeze_context", id: "speech-final", at: frozen.context_at }, voice.epoch);
  assert.equal(sent[0].type, "visual_context", "speech-final must immediately return frames without a tool or memory request");
  context.companion.freezeContext = () => { throw new Error("delayed question must not capture a new scene"); };
  await voice.receive({ type: "question", turn_id: "three", text: "this", at: "2026-11-18T00:00:20Z", context_at: frozen.context_at, visual_context_ids: ["speech-final"] }, voice.epoch);
  assert.equal(voice.turnVisual.context.visual_frames[0].snapshot, "shown-image", "a delayed canonical turn must retain its original shown frame");
  assert.equal(voice.turnVisual.context.context_at, frozen.context_at, "the original evidence clock must survive delayed processing");
  await voice.stop();
  assert.equal(voice.visualContexts.size, 0, "stopping clears retained context");
  console.log("18 browser audio/transcript/context checks passed");
}
run().catch((error) => { console.error(error); process.exitCode = 1; });
