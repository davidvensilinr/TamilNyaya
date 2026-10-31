import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'TamilNyaya-Bench | Legal LLM Hallucination Benchmark',
  description: 'Auditable benchmark testing language models on Indian and Tamil Nadu law with real knowledge base verification.',
}

export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: '#0b1117',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="ta" className="bg-[#0b1117]">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+Tamil:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased min-h-screen text-[#d7e0e8] bg-[#0b1117] selection:bg-[#66d9e8]/20 selection:text-[#66d9e8]">
        {children}
      </body>
    </html>
  )
}
