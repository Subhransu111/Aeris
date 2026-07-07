const CODE_LINES = [
  { n: 1, tokens: [["comment", "// routes/auth.js"]] },
  { n: 2, tokens: [["keyword", "import"], ["plain", " { render } "], ["keyword", "from"], ["string", " \"./view\""]] },
  { n: 3, tokens: [] },
  { n: 4, tokens: [["keyword", "export function"], ["fn", " handleLogin"], ["plain", "(req, res) {"]] },
  { n: 5, tokens: [["keyword", "  const"], ["plain", " user = req.query."], ["fn", "name"], ["plain", ";"]] },
  {
    n: 6,
    flagged: true,
    tokens: [
      ["plain", "  res."],
      ["fn", "send"],
      ["plain", "(`<h1>Welcome "],
      ["magenta", "${user}"],
      ["plain", "</h1>`);"],
    ],
  },
  { n: 7, tokens: [["plain", "}"]] },
  { n: 8, tokens: [] },
  { n: 9, tokens: [["keyword", "export function"], ["fn", " handleRegister"], ["plain", "(req, res) {"]] },
  { n: 10, tokens: [["comment", "  // TODO: rate limit"]] },
  { n: 11, tokens: [["plain", "  ..."]] },
  { n: 12, tokens: [["plain", "}"]] },
];

const TOKEN_CLASS = {
  comment: "text-fog-2",
  keyword: "text-cyan",
  fn: "text-mint",
  string: "text-amber",
  magenta: "text-magenta",
  plain: "text-paper/90",
};

export default function CodeWindow({ className = "" }) {
  return (
    <div
      className={`relative overflow-hidden rounded-xl border border-line bg-panel shadow-[0_0_60px_-15px_rgba(76,224,255,0.25)] ${className}`}
    >
      {/* title bar */}
      <div className="flex items-center gap-2 border-b border-line px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-magenta/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-mint/70" />
        <span className="ml-3 font-mono text-[11px] text-fog-2">
          sandbox://127.0.0.1:60705/routes/auth.js
        </span>
        <span className="ml-auto flex items-center gap-1.5 font-mono text-[11px] text-cyan">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan animate-pulse" />
          scanning
        </span>
      </div>

      {/* code body */}
      <div className="relative px-4 py-4">
        <div className="absolute inset-x-0 top-0">
          <div className="scan-beam" />
        </div>

        <pre className="font-mono text-[13px] leading-6">
          {CODE_LINES.map((line) => (
            <div
              key={line.n}
              className={`flex rounded px-1.5 ${line.flagged ? "finding-pulse" : ""}`}
            >
              <span className="mr-4 w-4 select-none text-right text-fog-2">
                {line.n}
              </span>
              <span className="flex-1">
                {line.tokens.map((tok, i) => (
                  <span key={i} className={TOKEN_CLASS[tok[0]]}>
                    {tok[1]}
                  </span>
                ))}
                {line.flagged && (
                  <span className="finding-badge ml-3 rounded-full border border-magenta/40 bg-magenta/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-magenta">
                    Reflected XSS
                  </span>
                )}
              </span>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}