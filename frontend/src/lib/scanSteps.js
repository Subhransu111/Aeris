// Maps the `current_step` values written by Backend/api/scan_runner.py
// into short present-tense log lines for the live terminal readout.
export const STEP_LABELS = {
  accepted: "Request accepted, queuing scan",
  starting_sandbox: "Booting isolated sandbox",
  waiting_for_server: "Waiting for application to start",
  provisioning_account: "Registering test account",
  account_ready: "Test account ready",
  crawling: "Crawling site structure",
  functional_agent: "Running functional test agent",
  accessibility_agent: "Running accessibility agent",
  security_agent: "Running security agent",
  performance_agent: "Running performance agent",
  journey_agent: "Running user-journey agent",
  generating_report: "Compiling engineering report",
  sandbox_failed: "Sandbox failed to start",
  provisioning_failed: "Test account setup failed",
  scan_exception: "Scan hit an unexpected error",
  authentication_failed_continuing: "Login setup failed — continuing with public pages only",

};

export function labelForStep(step) {
  if (!step) return "Waiting for agent output";
  return STEP_LABELS[step] || step.replaceAll("_", " ");
}