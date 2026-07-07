import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Mail, Send } from "lucide-react";
import { toast } from "sonner";

export default function ContactSection() {
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [sending, setSending] = useState(false);

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = (e) => {
    e.preventDefault();
    setSending(true);
    // Wire this up to your inbound-mail endpoint when it exists.
    setTimeout(() => {
      setSending(false);
      setForm({ name: "", email: "", message: "" });
      toast.success("Message sent — we'll get back to you shortly.");
    }, 700);
  };

  return (
    <section id="contact" className="border-b border-line-soft bg-panel py-24">
      <div className="mx-auto grid max-w-5xl gap-12 px-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
        <div>
          <span className="font-mono text-[11px] uppercase tracking-wider text-cyan">
            Get in touch
          </span>
          <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight text-paper sm:text-4xl">
            Questions before you scan?
          </h2>
          <p className="mt-4 max-w-sm text-fog">
            Enterprise rollout, private repos, on-prem sandboxes — talk to the
            team running Aegis before you point it at production.
          </p>
          <div className="mt-8 flex items-center gap-2 font-mono text-sm text-fog">
            <Mail className="h-4 w-4 text-cyan" />
            hello@aegis.ai
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="rounded-xl border border-line bg-panel-2 p-6 sm:p-8"
        >
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <Label htmlFor="name" className="font-mono text-xs uppercase tracking-wider text-fog">
                Name
              </Label>
              <Input
                id="name"
                required
                value={form.name}
                onChange={update("name")}
                placeholder="Ada Lovelace"
                className="mt-2 bg-ink text-sm"
              />
            </div>
            <div>
              <Label htmlFor="email" className="font-mono text-xs uppercase tracking-wider text-fog">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                required
                value={form.email}
                onChange={update("email")}
                placeholder="ada@company.com"
                className="mt-2 bg-ink text-sm"
              />
            </div>
          </div>

          <div className="mt-5">
            <Label htmlFor="message" className="font-mono text-xs uppercase tracking-wider text-fog">
              Message
            </Label>
            <Textarea
              id="message"
              required
              value={form.message}
              onChange={update("message")}
              placeholder="Tell us what you're shipping."
              className="mt-2 min-h-[120px] bg-ink text-sm"
            />
          </div>

          <Button
            type="submit"
            disabled={sending}
            className="mt-6 h-11 bg-cyan text-ink hover:bg-cyan/90"
          >
            <Send className="mr-2 h-4 w-4" />
            {sending ? "Sending…" : "Send message"}
          </Button>
        </form>
      </div>
    </section>
  );
}