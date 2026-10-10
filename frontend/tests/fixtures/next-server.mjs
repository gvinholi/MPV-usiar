// Test-only Next.js launcher with deterministic shutdown on Windows.
import http from "node:http";
import next from "next";

const port = Number(process.argv[2] ?? "3300");
const dev = process.argv[3] !== "production";
const hostname = "127.0.0.1";
const app = next({ dev, dir: process.cwd(), hostname, port });
await app.prepare();
const handler = app.getRequestHandler();
const server = http.createServer((request, response) => handler(request, response));
server.listen(port, hostname);

let stopping = false;
const shutdown = async () => {
  if (stopping) return;
  stopping = true;
  server.close();
  server.closeAllConnections();
  await Promise.race([app.close(), new Promise(resolve => setTimeout(resolve, 1000))]);
  process.exit(0);
};
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
