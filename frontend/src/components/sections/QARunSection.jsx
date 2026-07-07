import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Download,FolderGit2, Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import { startScan, getScanStatus, getScanReport } from "@/lib/api";
import { toast } from "sonner";

import ScanTerminal from "@/components/qa/ScanTerminal";

const POLL_INTERVAL_MS = 2500;

const initialForm = {
  repo_url: "",
  app_name: "",
  frontend_subdirectory: "",
  backend_subdirectory: "",
  tier: "free",
};

export default function QARunSection() {
  const [form, setForm] = useState(initialForm);
  const [scanId, setScanId] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | queued | running | completed | failed
  const [currentStep, setCurrentStep] = useState(null);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);
  const pollRef = useRef(null);

  const isRunning = status === "queued" || status === "running";

  useEffect(() => () => clearInterval(pollRef.current), []);

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const resetForNewScan = () => {
    setStatus("idle");
    setCurrentStep(null);
    setError(null);
    setReport(null);
    setScanId(null);
  };

  const handleTierChange = (value) => {
  if (value === "pro") {
    toast.info("Pro is coming soon — your scan will run on Free for now.");
    return;
  }
  setForm((f) => ({ ...f, tier: value }));
};

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.repo_url || !form.app_name) return;

    resetForNewScan();
    setStatus("queued");

    try {
      const payload = {
        repo_url: form.repo_url,
        app_name: form.app_name,
        frontend_subdirectory: form.frontend_subdirectory || null,
        backend_subdirectory: form.backend_subdirectory || null,
        tier: form.tier,
      };
      const { scan_id } = await startScan(payload);
      setScanId(scan_id);

      pollRef.current = setInterval(async () => {
        try {
          const s = await getScanStatus(scan_id);
          setStatus(s.status);
          setCurrentStep(s.current_step);

          if (s.status === "completed") {
            clearInterval(pollRef.current);
            const r = await getScanReport(scan_id);
            setReport(r);
          } else if (s.status === "failed") {
            clearInterval(pollRef.current);
            setError(s.error || "Scan failed");
          }
        } catch (err) {
          clearInterval(pollRef.current);
          setStatus("failed");
          setError("Lost connection to the scan service");
        }
      }, POLL_INTERVAL_MS);
    } catch (err) {
      setStatus("failed");
      setError("Couldn't start the scan. Check the API is reachable.");
    }
  };

  const handleDownload = () => {
    if (!report?.markdown) return;
    const blob = new Blob([report.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${form.app_name || "aegis"}-report.md`.replace(/\s+/g, "-").toLowerCase();
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const score = report?.report?.launch_readiness_score ?? report?.report?.score ?? null;
  const summary =
    report?.report?.executive_summary ?? report?.report?.summary ?? null;

  return (
    <section id="qa-run" className="border-b border-line-soft bg-ink py-24">
      <div className="mx-auto max-w-3xl px-6">
        <span className="font-mono text-[11px] uppercase tracking-wider text-cyan">
          Step 01
        </span>
        <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-paper sm:text-4xl">
          Configure your scan
        </h2>
        <p className="mt-3 text-fog">
          Point Aegis at any public GitHub repository. Agents run functional,
          accessibility, security, performance and journey passes in a
          disposable sandbox.
        </p>

        <form
          onSubmit={handleSubmit}
          className="mt-10 rounded-xl border border-line bg-panel p-6 sm:p-8"
        >
          <div className="grid gap-6">
            <div>
              <Label htmlFor="repo_url" className="font-mono text-xs uppercase tracking-wider text-fog">
                Repository URL
              </Label>
              <div className="relative mt-2">
                <FolderGit2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fog-2" />
                <Input
                  id="repo_url"
                  required
                  disabled={isRunning}
                  value={form.repo_url}
                  onChange={update("repo_url")}
                  placeholder="https://github.com/owner/repo"
                  className="bg-panel-2 pl-9 font-mono text-sm"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="app_name" className="font-mono text-xs uppercase tracking-wider text-fog">
                Application name
              </Label>
              <Input
                id="app_name"
                required
                disabled={isRunning}
                value={form.app_name}
                onChange={update("app_name")}
                placeholder="e.g. Orion Dashboard"
                className="mt-2 bg-panel-2 text-sm"
              />
            </div>

            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <Label htmlFor="frontend_subdirectory" className="font-mono text-xs uppercase tracking-wider text-fog">
                  Frontend subdir <span className="text-fog-2 normal-case">optional</span>
                </Label>
                <Input
                  id="frontend_subdirectory"
                  disabled={isRunning}
                  value={form.frontend_subdirectory}
                  onChange={update("frontend_subdirectory")}
                  placeholder="frontend"
                  className="mt-2 bg-panel-2 font-mono text-sm"
                />
              </div>
              <div>
                <Label htmlFor="backend_subdirectory" className="font-mono text-xs uppercase tracking-wider text-fog">
                  Backend subdir <span className="text-fog-2 normal-case">optional</span>
                </Label>
                <Input
                  id="backend_subdirectory"
                  disabled={isRunning}
                  value={form.backend_subdirectory}
                  onChange={update("backend_subdirectory")}
                  placeholder="backend"
                  className="mt-2 bg-panel-2 font-mono text-sm"
                />
              </div>
            </div>

            <div>
              <Label className="font-mono text-xs uppercase tracking-wider text-fog">Tier</Label>
              <Select
                disabled={isRunning}
                value={form.tier}
                onValueChange={handleTierChange}
                >
                <SelectTrigger className="mt-2 bg-panel-2 text-sm">
                    <SelectValue />
                </SelectTrigger>
                <SelectContent
                    position="popper"
                    sideOffset={6}
                    className="z-50 border border-line bg-panel-2 text-paper shadow-xl"
                >
                    <SelectItem value="free">Free · Core agents</SelectItem>
                    <SelectItem value="pro" className="text-fog-2">
                    Pro · Full multi-agent
                    <span className="ml-2 rounded-full border border-line px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-fog-2">
                        Soon
                    </span>
                    </SelectItem>
                </SelectContent>
                </Select>
            </div>

            <Button
              type="submit"
              disabled={isRunning}
              className="h-11 bg-cyan text-ink hover:bg-cyan/90 disabled:opacity-60"
            >
              {isRunning ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Scanning…
                </>
              ) : (
                "Start scan"
              )}
            </Button>
          </div>

          {(status !== "idle") && (
            <>
              <Separator className="my-6 bg-line" />
              <ScanTerminal status={status} currentStep={currentStep} error={error} />
            </>
          )}

          {status === "completed" && report && (
            <div className="mt-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
              <div className="rounded-lg border border-mint/30 bg-mint/5 p-5">
                <div className="flex items-start gap-3">
                  <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-mint" />
                  <div className="min-w-0 flex-1">
                    <p className="font-display text-base font-semibold text-paper">
                      Report ready
                      {score !== null && (
                        <span className="ml-2 font-mono text-sm text-mint">
                          {score}/100 launch readiness
                        </span>
                      )}
                    </p>
                    {summary && (
                      <p className="mt-2 text-sm leading-relaxed text-fog">{summary}</p>
                    )}
                  </div>
                </div>
                <Button
                  onClick={handleDownload}
                  variant="outline"
                  className="mt-4 border-mint/40 text-mint hover:bg-mint/10 hover:text-mint"
                >
                  <Download className="mr-2 h-4 w-4" />
                  Download full report
                </Button>
              </div>
            </div>
          )}

          {status === "failed" && (
            <div className="mt-6 flex items-start gap-3 rounded-lg border border-magenta/30 bg-magenta/5 p-5">
              <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-magenta" />
              <div>
                <p className="font-display text-base font-semibold text-paper">Scan failed</p>
                <p className="mt-1 text-sm text-fog">{error}</p>
              </div>
            </div>
          )}
        </form>
      </div>
    </section>
  );
}