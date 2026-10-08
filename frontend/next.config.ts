import type { NextConfig } from "next";

const config: NextConfig = {
  poweredByHeader: false,
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
