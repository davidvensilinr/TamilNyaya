/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.BACKEND_URL 
          ? `${process.env.BACKEND_URL}/api/:path*` 
          : 'http://127.0.0.1:8000/api/:path*',
      },
    ]
  },
}

export default nextConfig
