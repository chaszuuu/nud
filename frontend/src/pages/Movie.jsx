// src/pages/Movie.jsx
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import ContentGrid from '../components/ContentGrid'
import useAuthStore from '../store/authStore'
import client from '../api/client'

export default function Movie() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [movie, setMovie] = useState(null)
  const [related, setRelated] = useState([])
  const [loading, setLoading] = useState(true)
  const [imgLoaded, setImgLoaded] = useState(false)

  useEffect(() => {
    fetchMovie()
  }, [id])

  const fetchMovie = async () => {
    setLoading(true)
    try {
      const res = await client.get(`/content/${id}`)
      setMovie(res.data)
      if (res.data.title) {
        const rel = await client.get('/search/', {
          params: { q: res.data.title.split(' ')[0], page: 1 }
        })
        setRelated(rel.data.filter((r) => r.id !== id).slice(0, 10))
      }
    } catch {
      navigate('/')
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <LoadingSkeleton />

  return (
    <div className="min-h-screen bg-bg">
      <Navbar />

      {/* backdrop */}
      <div className="relative h-[60vh] overflow-hidden">
        {movie?.backdrop_path && (
          <img
            src={movie.backdrop_path}
            alt=""
            onLoad={() => setImgLoaded(true)}
            className={`w-full h-full object-cover transition-opacity duration-700 ${imgLoaded ? 'opacity-35' : 'opacity-0'}`}
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/60 to-transparent"/>
        <div className="absolute inset-0 bg-gradient-to-r from-bg via-transparent to-transparent"/>
      </div>

      <div className="max-w-screen-xl mx-auto px-6 md:px-12 -mt-64 relative z-10 pb-20">
        <div className="flex flex-col md:flex-row gap-8">

          {/* poster */}
          <div className="shrink-0">
            <div className="w-40 md:w-52 rounded-xl overflow-hidden border border-surface-border shadow-2xl">
              {movie?.poster_path ? (
                <img src={movie.poster_path} alt={movie.title} className="w-full h-auto"/>
              ) : (
                <div className="aspect-[2/3] bg-surface flex items-center justify-center">
                  <span className="text-3xl font-black text-white/10">
                    {movie?.title?.slice(0, 3).toUpperCase()}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* info */}
          <div className="flex-1 pt-32 md:pt-48">
            <h1 className="text-3xl md:text-4xl font-extrabold text-white mb-3 tracking-tight">
              {movie?.title}
            </h1>

            <div className="flex flex-wrap items-center gap-2 mb-5 text-sm">
              {movie?.rating && (
                <span className="text-accent font-bold">★ {movie.rating?.toFixed(1)}</span>
              )}
              {movie?.release_year && (
                <>
                  <span className="w-1 h-1 bg-gray-600 rounded-full"/>
                  <span className="text-gray-400">{movie.release_year}</span>
                </>
              )}
              <span className="w-1 h-1 bg-gray-600 rounded-full"/>
              <span className="px-2 py-0.5 rounded-full bg-accent/10 border border-accent/20 text-accent/80 text-xs">
                Movie
              </span>
              {movie?.source_site && (
                <>
                  <span className="w-1 h-1 bg-gray-600 rounded-full"/>
                  <span className="text-gray-500 text-xs">{movie.source_site}</span>
                </>
              )}
            </div>

            {movie?.overview && (
              <p className="text-gray-400 text-sm leading-relaxed mb-6 max-w-2xl">
                {movie.overview}
              </p>
            )}

            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate(`/watch/${id}`)}
                className="flex items-center gap-2 accent-gradient text-[#0a0800] font-bold px-6 py-3 rounded-lg text-sm hover:opacity-90 transition-opacity"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8 5v14l11-7z"/>
                </svg>
                Play movie
              </button>
              {!user && (
                <button
                  onClick={() => navigate('/login')}
                  className="flex items-center gap-2 bg-surface border border-surface-border text-gray-300 px-5 py-3 rounded-lg text-sm hover:border-accent/30 transition-colors"
                >
                  Sign in to save
                </button>
              )}
            </div>
          </div>
        </div>

        {/* related */}
        {related.length > 0 && (
          <div className="mt-16">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-1 h-5 rounded-full accent-gradient"/>
              <h2 className="text-white font-semibold">More like this</h2>
            </div>
            <ContentGrid items={related} />
          </div>
        )}
      </div>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="min-h-screen bg-bg">
      <Navbar />
      <div className="h-[60vh] bg-surface animate-pulse"/>
      <div className="max-w-screen-xl mx-auto px-6 md:px-12 -mt-32 relative z-10 pb-20">
        <div className="flex gap-8">
          <div className="w-52 aspect-[2/3] bg-surface rounded-xl animate-pulse shrink-0"/>
          <div className="flex-1 pt-48 space-y-4">
            <div className="h-10 w-80 bg-surface rounded animate-pulse"/>
            <div className="h-4 w-48 bg-surface rounded animate-pulse"/>
            <div className="h-20 w-full max-w-2xl bg-surface rounded animate-pulse"/>
            <div className="h-11 w-36 bg-surface rounded-lg animate-pulse"/>
          </div>
        </div>
      </div>
    </div>
  )
}