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
  Set,
  CustomEvent: class {},
  clearInterval() {},
  conversation: { stopReveal() {} },
  window: { addEventListener() {}, dispatchEvent() {} },
  api: async () => ({ configured: false }),
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
  socket: { bufferedAmount: 0, send() { forwarded++; }, close() {} },
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
  console.log("11 browser audio-transport checks passed");
}
run().catch((error) => { console.error(error); process.exitCode = 1; });
