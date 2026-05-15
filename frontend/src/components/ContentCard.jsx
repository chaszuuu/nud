// src/components/ContentCard.jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function ContentCard({ item, showNumber = false, number = null }) {
  const navigate = useNavigate()
  const [imgError, setImgError] = useState(false)

  const handleClick = () => {
    if (item.content_type === 'movie') {
      navigate(`/movie/${item.id}`)
    } else {
      navigate(`/series/${item.id}`)
    }
  }

  return (
    <div
      onClick={handleClick}
      className="relative group cursor-pointer rounded-lg overflow-hidden border border-surface-border hover:border-accent/30 transition-all duration-200"
    >
      {/* poster */}
      <div className="relative aspect-[2/3] bg-surface overflow-hidden">
        {item.poster_path && !imgError ? (
          <img
            src={item.poster_path}
            alt={item.title}
            onError={() => setImgError(true)}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-surface to-surface-hover">
            <span className="text-2xl font-black text-white/10 tracking-tighter">
              {item.title?.slice(0, 3).toUpperCase()}
            </span>
          </div>
        )}

        {/* trending number watermark */}
        {showNumber && number && (
          <span className="absolute bottom-10 left-2 text-5xl font-black leading-none select-none"
            style={{ color: 'rgba(250,204,21,0.15)', letterSpacing: '-3px' }}>
            {number}
          </span>
        )}

        {/* hover overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex flex-col justify-end p-3">
          {/* play button */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-3/4">
            <div className="w-10 h-10 rounded-full accent-gradient flex items-center justify-center shadow-lg">
              <svg className="w-4 h-4 ml-0.5" viewBox="0 0 24 24" fill="#0a0800">
                <path d="M8 5v14l11-7z"/>
              </svg>
            </div>
          </div>

          {/* info */}
          <div>
            <p className="text-white text-xs font-semibold leading-tight mb-1 line-clamp-2">
              {item.title}
            </p>
            <div className="flex items-center gap-1.5">
              {item.rating && (
                <span className="text-accent text-xs font-bold">★ {item.rating?.toFixed(1)}</span>
              )}
              {item.rating && item.release_year && (
                <span className="w-1 h-1 bg-gray-600 rounded-full"/>
              )}
              {item.release_year && (
                <span className="text-gray-400 text-xs">{item.release_year}</span>
              )}
              {item.content_type && (
                <>
                  <span className="w-1 h-1 bg-gray-600 rounded-full"/>
                  <span className="text-xs px-1.5 py-0.5 rounded-sm bg-accent/10 text-accent/80 capitalize">
                    {item.content_type}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* bottom label — always visible on mobile, hidden on desktop (shown on hover) */}
      <div className="md:hidden p-2 bg-surface">
        <p className="text-white text-xs font-medium truncate">{item.title}</p>
        <p className="text-gray-500 text-xs">{item.release_year}</p>
      </div>
    </div>
  )
}