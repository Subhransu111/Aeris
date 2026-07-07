import { Button } from "@/components/ui/button";
import { ArrowRight, Radar } from "lucide-react";
import CodeWindow from "@/components/qa/CodeWindow";

const PACKETS = Array.from({ length: 14 }, (_, i) => ({
  left: `${8 + ((i * 37) % 84)}%`,
  bottom: `${(i * 23) % 70}%`,
  delay: `${(i * 0.6) % 6}s`,
  duration: `${5 + (i % 4)}s`,
  driftX: `${(i % 3) * 14 - 14}px`,
}));

function scrollToId(id) {
  return (e) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY - 76;
    window.scrollTo({ top, behavior: "smooth" });
  };
}

export default function Hero() {
  return (
    <section
      id="home"
      className="relative overflow-hidden border-b border-line-soft bg-ink pt-19"
    >
      <div className="bg-dot-grid pointer-events-none absolute inset-0 opacity-40 [mask-image:radial-gradient(ellipse_at_top,black,transparent_75%)]" />

      <div className="mx-auto grid max-w-6xl gap-16 px-6 py-20 lg:grid-cols-2 lg:items-center lg:py-28">
        {/* left: motion field + copy */}
        <div className="relative">
          <div className="pointer-events-none absolute -left-24 -top-16 h-[420px] w-[420px] opacity-70">
            <div className="radar-sweep absolute inset-0" />
            <div className="radar-ring absolute inset-[10%]" />
            <div className="radar-ring absolute inset-[28%]" />
            <div className="radar-ring absolute inset-[46%]" />
            {PACKETS.map((p, i) => (
              <span
                key={i}
                className="packet"
                style={{
                  left: p.left,
                  bottom: p.bottom,
                  animationDelay: p.delay,
                  animationDuration: p.duration,
                  "--drift-x": p.driftX,
                }}
              />
            ))}
          </div>

          <div className="relative">
            <span className="inline-flex items-center gap-2 rounded-full border border-line bg-panel-2 px-3 py-1 font-mono text-[11px] uppercase tracking-wider text-cyan">
              <Radar className="h-3.5 w-3.5" />
              Autonomous QA agents online
            </span>

            <h1 className="mt-6 font-display text-4xl font-semibold leading-[1.08] tracking-tight text-paper sm:text-5xl lg:text-[3.4rem]">
              Ship it once you've
              <br />
              <span className="text-cyan">seen it break.</span>
            </h1>

            <p className="mt-6 max-w-md text-base leading-relaxed text-fog">
              Point Aegis at a public repo. Five specialist agents spin up your
              app in an isolated sandbox, attack it, click through it, and
              hand back a launch-readiness verdict — not a wall of raw logs.
            </p>

            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Button
                onClick={scrollToId("qa-run")}
                className="group h-11 bg-cyan px-6 text-ink hover:bg-cyan/90"
              >
                Run a scan
                <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Button>
              <a
                href="#contact"
                onClick={scrollToId("contact")}
                className="font-mono text-sm text-fog underline decoration-line underline-offset-4 hover:text-cyan"
              >
                Talk to us instead
              </a>
            </div>
          </div>
        </div>

        {/* right: IDE scan window */}
        <div className="relative">
          <CodeWindow />
        </div>
      </div>
    </section>
  );
}