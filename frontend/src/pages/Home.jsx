// src/pages/Home.jsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import ContentGrid from '../components/ContentGrid'
import useAuthStore from '../store/authStore'
import useHistoryStore from '../store/historyStore'
import client from '../api/client'

export default function Home() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { history, fetchHistory } = useHistoryStore()
  const [hero, setHero] = useState(null)
  const [trending, setTrending] = useState([])
  const [recent, setRecent] = useState([])
  const [loading, setLoading] = useState(true)
  const [heroLoaded, setHeroLoaded] = useState(false)

  useEffect(() => {
    fetchTrending()
    if (user) fetchHistory()
  }, [user])

  const fetchTrending = async () => {
    setLoading(true)
    try {
      const res = await client.get('/content/trending', {
        params: { media_type: 'all', time_window: 'day' }
      })
      const data = res.data
      if (data.length > 0) {
        setHero(data[0])
        setTrending(data.slice(1, 11))
        setRecent(data.slice(11, 19))
      }
    } catch {
      // fallback
    } finally {
      setLoading(false)
    }
  }

  const handlePlay = () => {
    if (!hero) return
    if (hero.content_type === 'movie') {
      navigate(`/watch/${hero.id}`)
    } else {
      navigate(`/series/${hero.id}`)
    }
  }

  const handleInfo = () => {
    if (!hero) return
    if (hero.content_type === 'movie') {
      navigate(`/movie/${hero.id}`)
    } else {
      navigate(`/series/${hero.id}`)
    }
  }

  return (
    <div className="min-h-screen bg-bg">
      <Navbar />

      {/* ── hero ── */}
      <section className="relative h-[85vh] min-h-[560px] max-h-[800px] overflow-hidden">

        {/* backdrop */}
        <div className="absolute inset-0">
          {hero?.backdrop_path && (
            <img
              src={hero.backdrop_path}
              alt=""
              onLoad={() => setHeroLoaded(true)}
              className={`w-full h-full object-cover transition-opacity duration-700 ${
                heroLoaded ? 'opacity-40' : 'opacity-0'
              }`}
            />
          )}
          <div className="absolute inset-0 bg-gradient-to-r from-bg via-bg/80 to-transparent"/>
          <div className="absolute inset-0 bg-gradient-to-t from-bg via-transparent to-transparent"/>
          {/* accent glow */}
          <div className="absolute -top-20 -left-20 w-[500px] h-[500px] rounded-full pointer-events-none"
            style={{ background: 'radial-gradient(circle, rgba(250,204,21,0.1) 0%, transparent 65%)' }}/>
        </div>

        {/* content */}
        <div className="relative z-10 h-full flex flex-col justify-end pb-16 px-6 md:px-12 max-w-screen-xl mx-auto">
          {loading ? (
            <div className="space-y-4 max-w-lg">
              <div className="h-4 w-32 bg-surface rounded-full animate-pulse"/>
              <div className="h-12 w-80 bg-surface rounded animate-pulse"/>
              <div className="h-4 w-48 bg-surface rounded animate-pulse"/>
              <div className="h-16 w-96 bg-surface rounded animate-pulse"/>
              <div className="flex gap-3">
                <div className="h-11 w-32 bg-surface rounded-lg animate-pulse"/>
                <div className="h-11 w-28 bg-surface rounded-lg animate-pulse"/>
              </div>
            </div>
          ) : hero ? (
            <div className="max-w-lg">
              {/* badge */}
              <div className="inline-flex items-center gap-2 bg-accent/10 border border-accent/30 rounded-full px-3 py-1 mb-4">
                <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse"/>
                <span className="text-accent text-xs font-medium">Trending today</span>
              </div>

              {/* title */}
              <h1 className="text-4xl md:text-5xl font-extrabold leading-tight mb-3 tracking-tight">
                <span className="text-accent-gradient">{hero.title}</span>
              </h1>

              {/* meta */}
              <div className="flex flex-wrap items-center gap-2 mb-4 text-sm">
                {hero.rating && (
                  <span className="text-accent font-bold">★ {hero.rating?.toFixed(1)}</span>
                )}
                {hero.release_year && (
                  <>
                    <span className="w-1 h-1 bg-gray-600 rounded-full"/>
                    <span className="text-gray-400">{hero.release_year}</span>
                  </>
                )}
                {hero.content_type && (
                  <>
                    <span className="w-1 h-1 bg-gray-600 rounded-full"/>
                    <span className="px-2 py-0.5 rounded-full bg-accent/10 border border-accent/20 text-accent/80 text-xs capitalize">
                      {hero.content_type}
                    </span>
                  </>
                )}
              </div>

              {/* overview */}
              {hero.overview && (
                <p className="text-gray-400 text-sm leading-relaxed mb-6 line-clamp-3 max-w-md">
                  {hero.overview}
                </p>
              )}

              {/* actions */}
              <div className="flex items-center gap-3">
                <button
                  onClick={handlePlay}
                  className="flex items-center gap-2 accent-gradient text-[#0a0800] font-bold px-6 py-3 rounded-lg text-sm hover:opacity-90 transition-opacity"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M8 5v14l11-7z"/>
                  </svg>
                  Play now
                </button>
                <button
                  onClick={handleInfo}
                  className="flex items-center gap-2 bg-white/8 border border-white/12 text-white font-medium px-5 py-3 rounded-lg text-sm hover:bg-white/12 transition-colors"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  More info
                </button>
                <button className="w-11 h-11 flex items-center justify-center rounded-lg bg-accent/8 border border-accent/25 text-accent hover:bg-accent/15 transition-colors">
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                  </svg>
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      {/* ── content sections ── */}
      <div className="max-w-screen-xl mx-auto px-6 md:px-12 pb-20 space-y-10 -mt-8 relative z-10">

        {/* continue watching — logged in only */}
        {user && history.length > 0 && (
          <section>
            <SectionHeader title="Continue watching" onSeeAll={() => navigate('/search')} />
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {history.slice(0, 4).map((h) => (
                <ContinueCard key={h.id} item={h} />
              ))}
            </div>
          </section>
        )}

        {/* trending */}
        <section>
          <SectionHeader title="Trending now" onSeeAll={() => navigate('/search')} />
          <ContentGrid items={trending} loading={loading} showNumbers />
        </section>

        {/* genre pills */}
        <section>
          <SectionHeader title="Browse by genre" />
          <GenrePills />
        </section>

        {/* recently added */}
        {recent.length > 0 && (
          <section>
            <SectionHeader title="Recently added" onSeeAll={() => navigate('/search')} />
            <ContentGrid items={recent} loading={loading} />
          </section>
        )}
      </div>
    </div>
  )
}

// ── sub-components ─────────────────────────────────────────

function SectionHeader({ title, onSeeAll }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-3">
        <div className="w-1 h-5 rounded-full accent-gradient"/>
        <h2 className="text-white font-semibold text-base">{title}</h2>
      </div>
      {onSeeAll && (
        <button
          onClick={onSeeAll}
          className="flex items-center gap-1 text-accent text-xs hover:text-accent-dark transition-colors"
        >
          See all
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="m9 18 6-6-6-6"/>
          </svg>
        </button>
      )}
    </div>
  )
}

function ContinueCard({ item }) {
  const navigate = useNavigate()

  const handleClick = () => {
    if (item.season && item.episode) {
      navigate(`/watch/${item.content_id}?season=${item.season}&episode=${item.episode}`)
    } else {
      navigate(`/watch/${item.content_id}`)
    }
  }

  const pct = item.progress
    ? Math.min(100, Math.round((item.progress / 3600) * 100))
    : 0

  return (
    <div
      onClick={handleClick}
      className="rounded-lg overflow-hidden bg-surface border border-surface-border hover:border-accent/25 cursor-pointer group transition-all"
    >
      <div className="relative aspect-video bg-surface-hover flex items-center justify-center overflow-hidden">
        <span className="text-2xl font-black text-white/6">
          {item.content?.title?.slice(0, 3).toUpperCase() || 'NUD'}
        </span>
        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
          <div className="w-9 h-9 rounded-full accent-gradient flex items-center justify-center">
            <svg className="w-3.5 h-3.5 ml-0.5" viewBox="0 0 24 24" fill="#0a0800">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
        </div>
      </div>
      {/* progress bar */}
      <div className="h-0.5 bg-surface-hover">
        <div
          className="h-full accent-gradient rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="p-2.5">
        <p className="text-white text-xs font-medium truncate">{item.content?.title}</p>
        <p className="text-gray-500 text-xs mt-0.5">
          {item.season ? `S${item.season} E${item.episode}` : 'Movie'} · {pct}% watched
        </p>
      </div>
    </div>
  )
}

function GenrePills() {
  const navigate = useNavigate()
  const [active, setActive] = useState('all')

  const genres = [
    { id: 'all',     label: 'All',     color: '#facc15' },
    { id: 'anime',   label: 'Anime',   color: '#7c3aed' },
    { id: 'kdrama',  label: 'K-Drama', color: '#0891b2' },
    { id: 'movie',   label: 'Movies',  color: '#059669' },
    { id: 'action',  label: 'Action',  color: '#dc2626' },
    { id: 'romance', label: 'Romance', color: '#db2777' },
    { id: 'thriller',label: 'Thriller',color: '#6366f1' },
    { id: 'fantasy', label: 'Fantasy', color: '#10b981' },
  ]

  const handleGenre = (id) => {
    setActive(id)
    if (id === 'all') {
      navigate('/search')
    } else {
      navigate(`/search?genre=${id}`)
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {genres.map((g) => (
        <button
          key={g.id}
          onClick={() => handleGenre(g.id)}
          className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs border transition-all duration-200 ${
            active === g.id
              ? 'bg-accent/10 border-accent/35 text-accent'
              : 'bg-surface border-surface-border text-gray-500 hover:text-white hover:border-white/20'
          }`}
        >
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: g.color }}/>
          {g.label}
        </button>
      ))}
    </div>
  )
}