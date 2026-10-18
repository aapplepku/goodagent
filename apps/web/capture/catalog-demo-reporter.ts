import type { FullConfig, FullResult, Reporter, Suite, TestCase, TestResult } from "@playwright/test/reporter";

// API transport errors can contain cookies in Playwright's attached call log.
// Keep only fixed event names/statuses; raw protocol errors, steps and output stay unreported.
export default class CatalogDemoReporter implements Reporter {
  onBegin(_config: FullConfig, suite: Suite) {
    process.stdout.write(JSON.stringify({ event: "capture_begin", tests: suite.allTests().length }) + "\n");
  }
  onTestEnd(_test: TestCase, result: TestResult) {
    process.stdout.write(JSON.stringify({ event: "capture_test_end", status: result.status, duration_ms: result.duration }) + "\n");
  }
  onEnd(result: FullResult) {
    process.stdout.write(JSON.stringify({ event: "capture_end", status: result.status }) + "\n");
  }
  onError() { process.stdout.write('{"event":"capture_runner_error"}\n'); }
  onStdOut() {}
  onStdErr() {}
  printsToStdio() { return true; }
}
