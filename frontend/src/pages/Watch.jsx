// src/pages/Watch.jsx
import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import Player from '../components/Player'
import useAuthStore from '../store/authStore'
import useHistoryStore from '../store/historyStore'
import client from '../api/client'

const POLL_INTERVAL_MS = 2000
const POLL_TIMEOUT_MS  = 120000 // stop polling after 2 min

export default function Watch() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { upsertHistory } = useHistoryStore()

  const season  = searchParams.get('season')  ? parseInt(searchParams.get('season'))  : null
  const episode = searchParams.get('episode') ? parseInt(searchParams.get('episode')) : null

  const [streamUrl, setStreamUrl]   = useState(null)
  const [subtitles, setSubtitles]   = useState([])
  const [content, setContent]       = useState(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)
  const [statusMsg, setStatusMsg]   = useState("Finding stream source...")

  const pollTimer    = useRef(null)
  const pollStart    = useRef(null)
  const jobIdRef     = useRef(null)

  const stopPolling = () => {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current)
      pollTimer.current = null
    }
  }

  const poll = useCallback(async (jobId) => {
    if (Date.now() - pollStart.current > POLL_TIMEOUT_MS) {
      stopPolling()
      setError("Stream timed out — please try again")
      setLoading(false)
      return
    }

    try {
      const res = await client.get(`/content/stream/status/${jobId}`)
      const data = res.data

      setStatusMsg(data.message || "Loading...")

      // After setting subtitles from the API response, rewrite the file URLs
      if (data.status === 'ready') {
        stopPolling()
        setStreamUrl(data.stream_url)
  
        // Proxy subtitle VTT files through backend to avoid CORS block
        const proxiedSubs = (data.subtitles || []).map(sub => ({
          ...sub,
          file: `${import.meta.env.VITE_API_URL}/proxy/hls?url=${encodeURIComponent(sub.file)}`
        }))
        setSubtitles(proxiedSubs)
        setLoading(false)
        return
        }

      if (data.status === 'failed') {
        stopPolling()
        setError(data.error || "Failed to load stream")
        setLoading(false)
        return
      }

      pollTimer.current = setTimeout(() => poll(jobId), POLL_INTERVAL_MS)

    } catch (e) {
      stopPolling()
      setError(e.response?.data?.detail || "Failed to load stream")
      setLoading(false)
    }
  }, [])

  const startStream = useCallback(async () => {
    setLoading(true)
    setError(null)
    setStreamUrl(null)
    setSubtitles([])
    setStatusMsg("Finding stream source...")
    stopPolling()

    try {
      const [contentRes, jobRes] = await Promise.all([
        client.get(`/content/${id}`),
        client.post('/content/stream/start', { content_id: id, season, episode }),
      ])

      setContent(contentRes.data)

      const jobId = jobRes.data.job_id
      jobIdRef.current = jobId
      pollStart.current = Date.now()

      pollTimer.current = setTimeout(() => poll(jobId), POLL_INTERVAL_MS)

    } catch (e) {
      setError(e.response?.data?.detail || "Failed to start stream")
      setLoading(false)
    }
  }, [id, season, episode, poll])

  useEffect(() => {
    startStream()
    return () => stopPolling()
  }, [id, season, episode])

  const handleProgress = useCallback(async (seconds) => {
    if (!user) return
    await upsertHistory({ content_id: id, season, episode, progress: seconds, completed: false })
  }, [id, season, episode, user])

  const handleEnded = useCallback(async () => {
    if (!user) return
    await upsertHistory({ content_id: id, season, episode, progress: 0, completed: true })
  }, [id, season, episode, user])

  const title = content
    ? season ? `${content.title} — S${season} E${episode}` : content.title
    : 'Loading...'

  return (
    <div className="min-h-screen bg-black flex flex-col">

      {/* top bar */}
      <div className="flex items-center gap-4 px-4 py-3 bg-black/80 backdrop-blur-sm border-b border-white/5">
        <button
          onClick={() => navigate(-1)}
          className="text-gray-400 hover:text-white transition-colors"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m15 18-6-6 6-6"/>
          </svg>
        </button>
        <h1 className="text-white text-sm font-medium truncate">{title}</h1>
        {!user && (
          <button
            onClick={() => navigate('/login')}
            className="ml-auto text-xs text-accent border border-accent/30 px-3 py-1.5 rounded-full hover:bg-accent/10 transition-colors"
          >
            Sign in to save progress
          </button>
        )}
      </div>

      {/* player area */}
      <div className="flex-1 flex flex-col items-center justify-center bg-black">
        {loading ? (
          <div className="flex flex-col items-center gap-4">
            <div className="relative w-14 h-14">
              <div className="w-14 h-14 border-2 border-surface-border rounded-full"/>
              <div className="absolute inset-0 w-14 h-14 border-2 border-t-accent rounded-full animate-spin"/>
            </div>
            <p className="text-white text-sm font-medium">{statusMsg}</p>
            <p className="text-gray-600 text-xs">This may take up to a minute</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center gap-4 text-center px-6">
            <svg className="w-12 h-12 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <p className="text-white font-medium">{error}</p>
            <div className="flex gap-3">
              <button
                onClick={startStream}
                className="accent-gradient text-[#0a0800] font-bold px-5 py-2.5 rounded-lg text-sm"
              >
                Try again
              </button>
              <button
                onClick={() => navigate(-1)}
                className="bg-surface border border-surface-border text-gray-300 px-5 py-2.5 rounded-lg text-sm"
              >
                Go back
              </button>
            </div>
          </div>
        ) : (
          <div className="w-full max-w-6xl px-0 md:px-6">
            <Player
              streamUrl={streamUrl}
              subtitles={subtitles}
              title={title}
              onProgress={handleProgress}
              onEnded={handleEnded}
            />
          </div>
        )}
      </div>
    </div>
  )
}