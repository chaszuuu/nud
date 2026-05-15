// src/components/ContentGrid.jsx
import ContentCard from './ContentCard'

export default function ContentGrid({ items = [], loading = false, showNumbers = false }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="rounded-lg overflow-hidden border border-surface-border">
            <div className="aspect-[2/3] bg-surface animate-pulse"/>
            <div className="md:hidden p-2 bg-surface">
              <div className="h-3 bg-surface-hover rounded animate-pulse mb-1"/>
              <div className="h-2 bg-surface-hover rounded animate-pulse w-1/2"/>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!items.length) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-16 h-16 rounded-full bg-surface border border-surface-border flex items-center justify-center mb-4">
          <svg className="w-7 h-7 text-gray-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M7 4v16M17 4v16M3 8h4m10 0h4M3 16h4m10 0h4M4 20h16a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1z"/>
          </svg>
        </div>
        <p className="text-gray-500 text-sm">No content found</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
      {items.map((item, i) => (
        <ContentCard
          key={item.id || item.tmdb_id || i}
          item={item}
          showNumber={showNumbers}
          number={i + 1}
        />
      ))}
    </div>
  )
}