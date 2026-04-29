import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.COGENCY_API_URL ?? "http://localhost:8000"}/v1/:path*`,
      },
    ];
  },
};

export default config;
