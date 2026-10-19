class NyxAudio extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(320);
    this.offset = 0;
  }
  process(inputs) {
    const samples = inputs[0]?.[0];
    if (samples) {
      for (const sample of samples) {
        this.buffer[this.offset++] = sample;
        if (this.offset === this.buffer.length) {
          this.port.postMessage(this.buffer.slice());
          this.offset = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("nyx-audio", NyxAudio);
