import { describe, expect, it } from "vitest";
import { loopbackOrigin, webVtt } from "../../capture/alpha-recording-utils";

describe("private alpha recording guards", () => {
  it.each(["http://127.0.0.1:3000", "http://localhost:4000/", "http://[::1]:5000"])("accepts %s", (value) => {
    expect(loopbackOrigin(value)).toBe(new URL(value).origin);
  });
  it.each([undefined, "https://example.com", "http://api", "http://localhost.evil.test", "http://127.0.0.1/store", "http://localhost/?token=x", "http://localhost/#token"])("rejects nonlocal or credentialed destinations", (value) => {
    expect(() => loopbackOrigin(value)).toThrow();
  });
  it("rejects URL credentials before any network request", () => {
    const url = new URL("http://localhost");
    url.username = "synthetic-test-user";
    url.password = "synthetic-test-password";
    expect(() => loopbackOrigin(url.toString())).toThrow();
  });
  it("writes millisecond captions without shortening waits", () => {
    expect(webVtt([{ startMs: 0, endMs: 61234, text: "Actual indexing wait." }])).toContain("00:00:00.000 --> 00:01:01.234");
  });
  it("retains successive captions and their order", () => {
    const output = webVtt([{ startMs: 0, endMs: 20, text: "First" }, { startMs: 20, endMs: 30, text: "Second" }]);
    expect(output).toContain("1\n00:00:00.000 --> 00:00:00.020\nFirst");
    expect(output).toContain("2\n00:00:00.020 --> 00:00:00.030\nSecond");
  });
  it.each([
    [{ startMs: -1, endMs: 1, text: "Invalid" }],
    [{ startMs: 0, endMs: 0, text: "Invalid" }],
    [{ startMs: 0, endMs: 1.5, text: "Invalid" }],
    [{ startMs: 0, endMs: 2, text: "<script>" }],
    [{ startMs: 0, endMs: 2, text: "line\nline" }],
    [{ startMs: 0, endMs: 2, text: " " }],
    [{ startMs: 0, endMs: 20, text: "First" }, { startMs: 19, endMs: 30, text: "Overlap" }],
  ].map((cues) => ({ cues })))("rejects unsafe or invalid caption cues", ({ cues }) => {
    expect(() => webVtt(cues)).toThrow(/Invalid/);
  });
});
