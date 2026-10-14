import type { NextConfig } from "next";
import { initOpenNextCloudflareForDev } from "@opennextjs/cloudflare";

initOpenNextCloudflareForDev();

const config: NextConfig = {
  poweredByHeader: false,
  // pg usa pg-cloudflare (export só na condição `workerd`) para TCP no Worker.
  // Externos aqui, o OpenNext os empacota com as condições do workerd.
  serverExternalPackages: ["pg", "pg-cloudflare"],
  // Authorization codes/state in callback query strings must not enter dev logs.
  logging: { incomingRequests: false, browserToTerminal: false },
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "Cache-Control", value: "private, no-store" },
      { key: "Referrer-Policy", value: "same-origin" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ] }];
  },
};
export default config;
