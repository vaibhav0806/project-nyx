/* Run on /markdown-it.js in a NEW isolated page, never the live application page.
   Only definitions are loaded: no app startup, capture, audio or real transport. */
(async () => {
  if (location.pathname !== "/markdown-it.js") throw new Error("Use an isolated static-script page");
  const [markdown, companionSource, voiceSource] = await Promise.all(
    ["/markdown-it.js", "/companion.js", "/voice.js"].map(async path => (await fetch(path)).text()),
  );
  const library = document.createElement("script");
  library.textContent = markdown;
  document.head.append(library);
  const definitions = document.createElement("script");
  definitions.textContent = `
    document.body.innerHTML = '<section class="conversation-stage"></section>';
    const $ = id => {
      let element = document.getElementById(id);
      if (!element) { element = document.createElement('div'); element.id = id; document.body.append(element); }
      return element;
    };
    $('replay').pause = () => {}; $('source-dialog').close = () => {};
    const companion = {};
    ${companionSource.split("const companion = {")[0]}
    ${voiceSource.split("\n};", 1)[0]}\n};
  `;
  document.head.append(definitions);
  const results = [];
  const check = (name, assertion) => {
    try { assertion(); results.push({ name, passed: true }); }
    catch (error) { results.push({ name, passed: false, error: error.message }); }
  };
  const assert = (value, message) => { if (!value) throw new Error(message); };
  const answer = $("conversation-answer");
  answer.replaceChildren();
  renderAnswer(answer, "The phone");
  const paragraph = answer.firstElementChild;
  const text = paragraph.firstChild;
  renderAnswer(answer, "The phone is on the shelf.");
  check("Keep settled answer paragraph", () => assert(answer.firstElementChild === paragraph, "Paragraph was replaced"));
  check("Keep settled answer text node", () => assert(answer.firstElementChild.firstChild === text, "Text node was replaced"));
  check("Append exact answer", () => assert(answer.textContent.trim() === "The phone is on the shelf.", "Incorrect text"));
  renderAnswer(answer, "The phone is on the shelf.\n\nYou said so.");
  check("Keep completed block when next block arrives", () => assert(answer.firstElementChild === paragraph, "Completed block was replaced"));

  renderAnswer(answer, "Try **ragi");
  renderAnswer(answer, "Try **ragi mudde**");
  const strong = answer.querySelector("strong");
  check("Resolve incomplete Markdown", () => assert(strong?.textContent === "ragi mudde", "Bold formatting failed"));
  renderAnswer(answer, "Try **ragi mudde** for dinner.");
  check("Preserve existing formatted node", () => assert(answer.querySelector("strong") === strong, "Formatted node was replaced"));
  renderAnswer(answer, "[Help](https://example.com/one)");
  renderAnswer(answer, "[Help](https://example.com/two)");
  check("Update changed link attributes", () => assert(answer.querySelector("a")?.getAttribute("href") === "https://example.com/two", "Stale link"));
  renderAnswer(answer, "<script>window.injected = true</script>");
  check("Preserve HTML escaping", () => assert(!answer.querySelector("script"), "Raw HTML executed"));
  renderAnswer(answer, "Hindi: चश्मा रसोई में है।");
  check("Preserve Unicode", () => assert(answer.textContent.includes("चश्मा रसोई में है।"), "Unicode changed"));

  conversation.render = () => {};
  conversation.begin("I keep");
  const question = document.getElementById("conversation-question");
  const inputText = question.firstChild;
  await voice.receive({ type: "transcript", text: "I keep my phone", new_turn: false }, voice.epoch);
  check("Preserve live transcript text node", () => assert(question.firstChild === inputText, "Transcript was deleted and re-added"));
  await voice.receive({ type: "transcript", text: "I kept my phone", new_turn: false }, voice.epoch);
  check("Allow genuine STT corrections", () => assert(question.textContent === "I kept my phone", "Correction ignored"));
  await voice.receive({ type: "question", text: "I kept my phone", turn_id: "synthetic", at: new Date().toISOString() }, voice.epoch);
  check("Canonical question keeps preview text node", () => assert(question.firstChild === inputText, "Final transcript remounted"));
  conversation.answer("Hello", true);
  const spokenParagraph = answer.firstElementChild;
  conversation.answer("Hello there", true);
  check("Spoken text stays synchronized without another reveal timer", () => assert(conversation.shownAnswer === "Hello there" && conversation.revealTimer === null && answer.firstElementChild === spokenParagraph, "Spoken streaming reset or delayed"));
  conversation.begin("New question");
  check("New turn resets previous answer", () => assert(!answer.textContent.includes("Hello there"), "Old answer retained"));

  await voice.receive({ type: "transcript", text: "I want some go", committed_text: "", interim_text: "I want some go", is_final: false, new_turn: true }, voice.epoch);
  await voice.receive({ type: "transcript", text: "I want some good food", committed_text: "", interim_text: "I want some good food", is_final: false, new_turn: false }, voice.epoch);
  check("Only agreeing complete draft words become visible", () => assert(question.textContent === "I want some", "Unstable trailing words were displayed"));
  await voice.receive({ type: "transcript", text: "I wanted local food", committed_text: "", interim_text: "I wanted local food", is_final: false, new_turn: false }, voice.epoch);
  check("Revised interim hypothesis does not erase visible preview", () => assert(question.textContent === "I want some", "Interim rewind erased stable words"));
  await voice.receive({ type: "transcript", text: "I wanted local food.", committed_text: "I wanted local food.", interim_text: "", is_final: true, new_turn: false }, voice.epoch);
  check("Provider final remains authoritative", () => assert(question.textContent === "I wanted local food.", "Final correction was hidden"));
  await voice.receive({ type: "transcript", text: "Look at this.", committed_text: "Look at this.", interim_text: "", is_final: true, new_turn: true }, voice.epoch);
  await voice.receive({ type: "transcript", text: "Look at this. I plan to", committed_text: "Look at this.", interim_text: "I plan to", is_final: false, new_turn: false }, voice.epoch);
  check("Finalized segments remain visible while next draft starts", () => assert(question.textContent === "Look at this.", "Finalized prefix was lost"));
  await voice.receive({ type: "transcript", text: "Look at this. I plan to keep it", committed_text: "Look at this.", interim_text: "I plan to keep it", is_final: false, new_turn: false }, voice.epoch);
  check("Stable draft appends to finalized segments without duplication", () => assert(question.textContent === "Look at this. I plan", "Segment assembly duplicated or lost text"));
  await voice.receive({ type: "transcription_rejected", committed_text: "" }, voice.epoch);
  await voice.receive({ type: "state", state: "listening" }, voice.epoch);
  check("Rejected-language notice survives listening transition", () => assert($("voice-state").textContent.includes("Please repeat"), "Rejection notice disappeared"));
  await voice.receive({ type: "transcript", text: "Hello", is_final: true, new_turn: true }, voice.epoch);
  check("Valid next input clears rejection notice", () => assert(!voice.transcriptionNotice, "Stale notice retained"));

  const oldStop = voice.stop;
  let stopped = false;
  voice.stop = () => { stopped = true; };
  voice.token = "synthetic"; voice.ready = true; voice.wakeUntil = performance.now() + 30000;
  voice.socket = { readyState: WebSocket.OPEN, bufferedAmount: 0, send(data) { this.bufferedAmount += typeof data === "string" ? new TextEncoder().encode(data).byteLength : data.byteLength; } };
  voice.send({ type: "visual_context", visual_frames: [{ snapshot: "x".repeat(150000) }] });
  voice.samples(new Float32Array(320));
  check("Queued image bytes do not trigger audio-disconnect guard", () => assert(!stopped, "Camera payload was mistaken for audio backlog"));
  voice.socket.bufferedAmount = 0;
  for (let i = 0; i < 160; i++) voice.samples(new Float32Array(320));
  check("Genuine stalled audio still stops within budget", () => assert(stopped, "Audio backlog became unbounded"));
  voice.socket.bufferedAmount = 0;
  voice.write("x".repeat(150000));
  voice.write(new ArrayBuffer(640), true);
  voice.write("hi");
  voice.write(new ArrayBuffer(640), true);
  voice.socket.bufferedAmount = 1282;
  check("Draining images preserves queued audio accounting", () => assert(voice.bufferedAudioBytes() === 1280, "FIFO accounting lost audio"));
  voice.socket.bufferedAmount = 642;
  check("Partial drain accounts for intervening control frames", () => assert(voice.bufferedAudioBytes() === 640, "Audio/control drain mismatch"));
  voice.socket.bufferedAmount = 0;
  check("Fully drained socket clears queue accounting", () => assert(voice.bufferedAudioBytes() === 0 && voice.queuedSends.length === 0, "Stale backlog retained"));
  voice.stop = oldStop;
  return { passed: results.filter(row => row.passed).length, total: results.length, results };
})();
