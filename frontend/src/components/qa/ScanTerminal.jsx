import { useEffect, useState } from "react";
import { labelForStep } from "@/lib/scanSteps";

const STATUS_COLOR = {
  queued: "text-fog",
  running: "text-cyan",
  completed: "text-mint",
  failed: "text-magenta",
};

function useElapsed(active) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!active) {
      setSeconds(0);
      return;
    }
    const start = Date.now();
    const id = setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, [active]);
  return seconds;
}

function formatElapsed(s) {
  const m = String(Math.floor(s / 60)).padStart(2, "0");
  const sec = String(s % 60).padStart(2, "0");
  return `${m}:${sec}`;
}

export default function ScanTerminal({ status, currentStep, error }) {
  const active = status === "queued" || status === "running";
  const elapsed = useElapsed(active);

  const line =
    status === "failed"
      ? error || "Scan failed"
      : status === "completed"
      ? "Report ready"
      : labelForStep(currentStep);

  return (
    <div className="relative overflow-hidden rounded-lg border border-line bg-panel-2 px-4 py-3 font-mono text-[13px]">
      {active && (
        <div className="pointer-events-none absolute inset-x-0 top-0 h-full opacity-40">
          <div className="scan-beam" style={{ animationDuration: "2.4s" }} />
        </div>
      )}
      <div className="relative flex items-center gap-3">
        <span className="text-fog-2">$ aegis --status</span>
        <span className={`${STATUS_COLOR[status] || "text-fog"} truncate`}>
          {line}
          {active && <span className="term-cursor" />}
        </span>
        {active && (
          <span className="ml-auto shrink-0 text-fog-2">{formatElapsed(elapsed)}</span>
        )}
      </div>
    </div>
  );
}