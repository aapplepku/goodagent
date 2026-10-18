export interface Caption {
  startMs: number;
  endMs: number;
  text: string;
}

export function loopbackOrigin(value: string | undefined): string {
  if (!value) throw new Error("An explicit loopback origin is required");
  const url = new URL(value);
  if (
    url.protocol !== "http:" ||
    !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) ||
    url.username || url.password || url.pathname !== "/" || url.search || url.hash
  ) throw new Error("Only a plain HTTP loopback origin is allowed");
  return url.origin;
}

export function webVtt(captions: Caption[]): string {
  function timestamp(ms: number): string {
    if (!Number.isSafeInteger(ms) || ms < 0) throw new Error("Invalid caption time");
    return `${String(Math.floor(ms / 3600000)).padStart(2, "0")}:${String(Math.floor(ms / 60000) % 60).padStart(2, "0")}:${String(Math.floor(ms / 1000) % 60).padStart(2, "0")}.${String(ms % 1000).padStart(3, "0")}`;
  }
  let previous = 0;
  return "WEBVTT\n\n" + captions.map((cue, index) => {
    if (cue.startMs < previous || cue.endMs <= cue.startMs || !cue.text.trim() || /[<>\r\n]/.test(cue.text)) {
      throw new Error("Invalid or overlapping caption");
    }
    previous = cue.endMs;
    return `${index + 1}\n${timestamp(cue.startMs)} --> ${timestamp(cue.endMs)}\n${cue.text}\n`;
  }).join("\n");
}
