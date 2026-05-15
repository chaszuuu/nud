// src/pages/Series.jsx
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import useAuthStore from '../store/authStore'
import client from '../api/client'

export default function Series() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [series, setSeries] = useState(null)
  const [seasons, setSeasons] = useState([])
  const [episodes, setEpisodes] = useState([])
  const [activeSeason, setActiveSeason] = useState(1)
  const [loading, setLoading] = useState(true)
  const [epLoading, setEpLoading] = useState(false)
  const [imgLoaded, setImgLoaded] = useState(false)

  useEffect(() => {
    fetchSeries()
  }, [id])

  useEffect(() => {
    if (series) fetchEpisodes(activeSeason)
  }, [activeSeason, series])

  const fetchSeries = async () => {
    setLoading(true)
    try {
      const res = await client.get(`/content/${id}`)
      setSeries(res.data)
      const seas = await client.get(`/content/${id}/seasons`)
      setSeasons(seas.data)
    } catch {
      navigate('/')
    } finally {
      setLoading(false)
    }
  }

  const fetchEpisodes = async (season) => {
    setEpLoading(true)
    try {
      const res = await client.get(`/content/${id}/episodes`, {
        params: { season }
      })
      setEpisodes(res.data)
    } catch {
      setEpisodes([])
    } finally {
      setEpLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-bg">
        <Navbar />
        <div className="h-[50vh] bg-surface animate-pulse"/>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-bg">
      <Navbar />

      {/* backdrop */}
      <div className="relative h-[55vh] overflow-hidden">
        {series?.backdrop_path && (
          <img
            src={series.backdrop_path}
            alt=""
            onLoad={() => setImgLoaded(true)}
            className={`w-full h-full object-cover transition-opacity duration-700 ${imgLoaded ? 'opacity-35' : 'opacity-0'}`}
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/60 to-transparent"/>
        <div className="absolute inset-0 bg-gradient-to-r from-bg via-transparent to-transparent"/>
      </div>

      <div className="max-w-screen-xl mx-auto px-6 md:px-12 -mt-56 relative z-10 pb-20">

        {/* info row */}
        <div className="flex flex-col md:flex-row gap-8 mb-12">
          <div className="shrink-0">
            <div className="w-36 md:w-44 rounded-xl overflow-hidden border border-surface-border shadow-2xl">
              {series?.poster_path ? (
                <img src={series.poster_path} alt={series.title} className="w-full h-auto"/>
              ) : (
                <div className="aspect-[2/3] bg-surface flex items-center justify-center">
                  <span className="text-2xl font-black text-white/10">
                    {series?.title?.slice(0, 3).toUpperCase()}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 pt-28 md:pt-40">
            <h1 className="text-3xl md:text-4xl font-extrabold text-white mb-3 tracking-tight">
              {series?.title}
            </h1>
            <div className="flex flex-wrap items-center gap-2 mb-4 text-sm">
              {series?.rating && (
                <span className="text-accent font-bold">★ {series.rating?.toFixed(1)}</span>
              )}
              {series?.release_year && (
                <>
                  <span className="w-1 h-1 bg-gray-600 rounded-full"/>
                  <span className="text-gray-400">{series.release_year}</span>
                </>
              )}
              <span className="w-1 h-1 bg-gray-600 rounded-full"/>
              <span className="px-2 py-0.5 rounded-full bg-accent/10 border border-accent/20 text-accent/80 text-xs">
                Series
              </span>
              {seasons.length > 0 && (
                <>
                  <span className="w-1 h-1 bg-gray-600 rounded-full"/>
                  <span className="text-gray-400">{seasons.length} Season{seasons.length > 1 ? 's' : ''}</span>
                </>
              )}
            </div>
            {series?.overview && (
              <p className="text-gray-400 text-sm leading-relaxed max-w-2xl">
                {series.overview}
              </p>
            )}
          </div>
        </div>

        {/* season selector */}
        {seasons.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-6">
            {seasons.map((s) => (
              <button
                key={s.season_number}
                onClick={() => setActiveSeason(s.season_number)}
                className={`px-4 py-2 rounded-lg text-xs font-medium border transition-all ${
                  activeSeason === s.season_number
                    ? 'accent-gradient text-[#0a0800] border-transparent'
                    : 'bg-surface border-surface-border text-gray-400 hover:text-white hover:border-white/20'
                }`}
              >
                Season {s.season_number}
              </button>
            ))}
          </div>
        )}

        {/* episode list */}
        <div className="space-y-2">
          {epLoading ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-20 bg-surface rounded-lg animate-pulse"/>
            ))
          ) : episodes.length > 0 ? (
            episodes.map((ep) => (
              <EpisodeRow
                key={ep.episode_number}
                ep={ep}
                seriesId={id}
                season={activeSeason}
                user={user}
                navigate={navigate}
              />
            ))
          ) : (
            <div className="py-16 text-center text-gray-600 text-sm">
              No episodes found for this season
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function EpisodeRow({ ep, seriesId, season, navigate }) {
  return (
    <div
      onClick={() => navigate(`/watch/${seriesId}?season=${season}&episode=${ep.episode_number}`)}
      className="flex items-center gap-4 p-3 rounded-lg bg-surface border border-surface-border hover:border-accent/25 cursor-pointer group transition-all"
    >
      {/* thumbnail */}
      <div className="relative shrink-0 w-32 md:w-40 aspect-video rounded-lg overflow-hidden bg-surface-hover">
        {ep.still_path ? (
          <img src={ep.still_path} alt={ep.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"/>
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <span className="text-white/10 font-black text-lg">{ep.episode_number}</span>
          </div>
        )}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/40">
          <div className="w-8 h-8 rounded-full accent-gradient flex items-center justify-center">
            <svg className="w-3 h-3 ml-0.5" viewBox="0 0 24 24" fill="#0a0800">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
        </div>
      </div>

      {/* info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-gray-600 text-xs">E{ep.episode_number}</span>
          <span className="text-white text-sm font-medium truncate">{ep.name}</span>
        </div>
        {ep.overview && (
          <p className="text-gray-500 text-xs leading-relaxed line-clamp-2">{ep.overview}</p>
        )}
        {ep.runtime && (
          <p className="text-gray-600 text-xs mt-1">{ep.runtime} min</p>
        )}
      </div>
    </div>
  )
}