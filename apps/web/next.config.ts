import type { NextConfig } from "next";

// The browser calls /api/hp/* on its own origin; Next forwards to FastAPI.
// Same-origin requests need no CORS setup in FastAPI, and the API address stays server-side.
const apiOrigin = (process.env.HOMEPILOT_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  agentRules: false,
  async rewrites() {
    return [{ source: "/api/hp/:path*", destination: `${apiOrigin}/api/v1/:path*` }];
  },
};

export default nextConfig;
