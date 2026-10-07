import type { NextConfig } from "next";

// Sitio estatico: lo sirve el backend (o un proxy) en el mismo origen que la API.
const config: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
};

export default config;
