const http = require("http");
const os = require("os");

const PORT = process.env.PORT || 3000;
const STRESS = process.env.STRESS_CPU === "true";

// Intentionally bad: synchronous CPU burn on /stress endpoint
function burnCPU(durationMs) {
  const end = Date.now() + durationMs;
  let i = 0;
  while (Date.now() < end) {
    Math.sqrt(i++); // tight loop — no yield
  }
}

const server = http.createServer((req, res) => {
  const url = req.url;

  if (url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", hostname: os.hostname() }));
    return;
  }

  if (url === "/stress") {
    console.log(`[WARN] CPU stress triggered on ${os.hostname()}`);
    burnCPU(5000); // burn CPU for 5 seconds per request
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("Stress done\n");
    return;
  }

  if (url === "/crash") {
    console.error(`[ERROR] Deliberate crash triggered on ${os.hostname()}`);
    process.exit(1); // simulate OOMKilled / crash loop
  }

  if (url === "/error") {
    console.error(`[ERROR] Application error: database connection failed`);
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Internal Server Error", detail: "DB connection timeout" }));
    return;
  }

  res.writeHead(200, { "Content-Type": "text/plain" });
  res.end(`Hello from PostmortemAI Demo App on ${os.hostname()}\n`);
});

// Auto-stress if env var set (simulates a broken deployment)
if (STRESS) {
  console.log("[INFO] Auto-stress mode enabled — burning CPU continuously");
  setInterval(() => burnCPU(3000), 4000);
}

server.listen(PORT, () => {
  console.log(`[INFO] Demo app listening on port ${PORT}`);
});
