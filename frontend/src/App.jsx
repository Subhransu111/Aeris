import Navbar from "@/components/layout/Navbar";
import Hero from "@/components/sections/Hero";
import QARunSection from "@/components/sections/QARunSection";
import ContactSection from "@/components/sections/ContactSection";
import { Toaster } from "@/components/ui/sonner";

export default function App() {
  return (
    <div className="min-h-screen bg-ink font-sans text-paper antialiased">
      <Navbar />
      <main>
        <Hero />
        <QARunSection />
        <ContactSection />
      </main>
      <Toaster theme="dark" />
    </div>
  );
}