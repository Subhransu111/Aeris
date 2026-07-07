// Maps the `current_step` values written by Backend/api/scan_runner.py
// into short present-tense log lines for the live terminal readout.
export const STEP_LABELS = {
  accepted: "Request accepted, queuing scan",
  starting_sandbox: "Booting isolated sandbox",
  crawling: "Crawling site structure",
  functional_agent: "Running functional test agent",
  accessibility_agent: "Running accessibility agent",
  security_agent: "Running security agent",
  performance_agent: "Running performance agent",
  journey_agent: "Running user-journey agent",
  generating_report: "Compiling engineering report",
  sandbox_failed: "Sandbox failed to start",
  scan_exception: "Scan hit an unexpected error",
};

export function labelForStep(step) {
  if (!step) return "Waiting for agent output";
  return STEP_LABELS[step] || step.replaceAll("_", " ");
}