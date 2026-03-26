import '@/styles/globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Cheapest Groceries Aggregate',
  description: 'Compare groceries by aggregates of equivalent items',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="he" dir="rtl">
      <body>
        <nav style={{ padding: '1rem 2rem', borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
          <div style={{ maxWidth: '1200px', margin: '0 auto', fontWeight: 'bold' }}>
             מתכנן קניות חכם
          </div>
        </nav>
        {children}
      </body>
    </html>
  )
}
