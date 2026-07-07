import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ShieldCheck, Menu, X } from "lucide-react";

const LINKS = [
  { id: "home", label: "Home" },
  { id: "contact", label: "Contact Us" },
  { id: "qa-run", label: "QA Run" },
];

const NAV_OFFSET = 76;

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const scrollToId = (id) => (e) => {
    e.preventDefault();
    setOpen(false);
    const el = document.getElementById(id);
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY - NAV_OFFSET;
    window.scrollTo({ top, behavior: "smooth" });
  };

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
        scrolled
          ? "bg-ink/80 backdrop-blur-md border-b border-line-soft"
          : "bg-transparent border-b border-transparent"
      }`}
    >
      <nav className="mx-auto flex h-19 max-w-6xl items-center justify-between px-6">
        <a
          href="#home"
          onClick={scrollToId("home")}
          className="flex items-center gap-2 font-display text-lg font-semibold tracking-tight text-paper"
        >
          <ShieldCheck className="h-5 w-5 text-cyan" strokeWidth={1.75} />
          Aegis<span className="text-cyan">AI</span>
        </a>

        <ul className="hidden items-center gap-8 md:flex">
          {LINKS.map((link) => (
            <li key={link.id}>
              <a
                href={`#${link.id}`}
                onClick={scrollToId(link.id)}
                className="font-mono text-[13px] uppercase tracking-wider text-fog transition-colors hover:text-cyan"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="hidden md:block">
          <Button
            onClick={scrollToId("qa-run")}
            className="bg-cyan text-ink hover:bg-cyan/90 font-mono text-[13px]"
          >
            Start a scan
          </Button>
        </div>

        <button
          className="text-paper md:hidden"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </nav>

      {open && (
        <div className="border-t border-line-soft bg-ink/95 px-6 py-4 md:hidden">
          <ul className="flex flex-col gap-4">
            {LINKS.map((link) => (
              <li key={link.id}>
                <a
                  href={`#${link.id}`}
                  onClick={scrollToId(link.id)}
                  className="font-mono text-sm uppercase tracking-wider text-fog hover:text-cyan"
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </header>
  );
}