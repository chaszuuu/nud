// src/components/Player.jsx
import { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'

export default function Player({ streamUrl, subtitles = [], title, onProgress, onEnded }) {
  const videoRef = useRef(null)
  const hlsRef = useRef(null)
  const progressRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [muted, setMuted] = useState(false)
  const [volume, setVolume] = useState(1)
  const [currentTime, setCurrent] = useState(0)
  const [duration, setDuration] = useState(0)
  const [buffered, setBuffered] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)
  const [showControls, setShowControls] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [quality, setQuality] = useState(-1)
  const [qualities, setQualities] = useState([])
  const [showQuality, setShowQuality] = useState(false)
  const [activeSubtitle, setActiveSubtitle] = useState(null)
  const [showSubtitles, setShowSubtitles] = useState(false)
  const [currentCue, setCurrentCue] = useState(null)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const [showSpeed, setShowSpeed] = useState(false)
  const vttCuesRef = useRef([])
  const controlsTimer = useRef(null)
  const containerRef = useRef(null)

  // ── HLS setup ─────────────────────────────────────────────
  useEffect(() => {
    if (!streamUrl || !videoRef.current) return

    const video = videoRef.current
    setError(null)
    setLoading(true)

    if (Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: true,
        lowLatencyMode: false,
        maxBufferLength: 60,
        maxMaxBufferLength: 120,
        maxBufferSize: 200 * 1000 * 1000,
        maxBufferHole: 0.5,
        fragLoadingMaxRetry: 4,
        fragLoadingRetryDelay: 500,
        fragLoadingMaxRetryTimeout: 4000,
        startLevel: -1,
        abrEwmaDefaultEstimate: 5000000,
        abrBandWidthFactor: 0.95,
        abrBandWidthUpFactor: 0.7,
        highBufferWatchdogPeriod: 2,
        nudgeOffset: 0.2,
        nudgeMaxRetry: 5,
        manifestLoadingMaxRetry: 3,
        manifestLoadingRetryDelay: 500,
        backBufferLength: 30,
      })

      hls.loadSource(streamUrl)
      hls.attachMedia(video)

      hls.on(Hls.Events.MANIFEST_PARSED, (_, data) => {
        setLoading(false)
        const levels = data.levels.map((l, i) => ({
          index: i,
          label: l.height ? `${l.height}p` : `Level ${i}`,
        }))
        setQualities([{ index: -1, label: 'Auto' }, ...levels])
        video.play().catch(() => {})
      })

      hls.on(Hls.Events.MEDIA_ATTACHED, () => {
        hls.startLoad(-1)
      })

      hls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              hls.startLoad()
              break
            case Hls.ErrorTypes.MEDIA_ERROR:
              hls.recoverMediaError()
              break
            default:
              setError('Stream failed to load')
              break
          }
        }
      })

      hlsRef.current = hls
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = streamUrl
      video.addEventListener('loadedmetadata', () => setLoading(false))
    } else {
      setError('HLS not supported in this browser')
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy()
        hlsRef.current = null
      }
    }
  }, [streamUrl])

  // ── VTT parser ────────────────────────────────────────────
  const parseVTT = (text) => {
    const cues = []
    const normalized = text
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n')
      .replace(/^\uFEFF/, '')
      .replace(/^WEBVTT[^\n]*\n/, '')
      .trim()

    const blocks = normalized.split(/\n{2,}/)

    const parseTime = (t) => {
      const parts = t.trim().replace(',', '.').split(':')
      return parts.reduce((acc, p, i) =>
        acc + parseFloat(p) * Math.pow(60, parts.length - 1 - i), 0)
    }

    for (const block of blocks) {
      const lines = block.trim().split('\n')
      const timeIdx = lines.findIndex(l => l.includes('-->'))
      if (timeIdx === -1) continue

      const timeParts = lines[timeIdx].split('-->')
      const startStr = timeParts[0].split(' ')[0]
      const endStr = timeParts[1].trim().split(' ')[0]
      const start = parseTime(startStr)
      const end = parseTime(endStr)
      if (isNaN(start) || isNaN(end)) continue

      const textLines = lines.slice(timeIdx + 1).join('\n').trim()
      if (textLines) cues.push({ start, end, text: textLines })
    }

    return cues
  }

  // ── Load VTT when active subtitle changes ─────────────────
  useEffect(() => {
    vttCuesRef.current = []
    setCurrentCue(null)
    if (!activeSubtitle) return
    const sub = subtitles.find(s => s.label === activeSubtitle)
    if (!sub) return
    fetch(sub.file)
      .then(r => r.text())
      .then(text => {
        vttCuesRef.current = parseVTT(text)
      })
      .catch(e => console.warn('VTT load failed:', e))
  }, [activeSubtitle, subtitles])

  // ── Update current cue on time update ─────────────────────
  useEffect(() => {
    const video = videoRef.current
    if (!video) return
    const onTime = () => {
      const t = video.currentTime
      const cue = vttCuesRef.current.find(c => t >= c.start && t < c.end) ?? null
      setCurrentCue(cue?.text ?? null)
    }
    video.addEventListener('timeupdate', onTime)
    return () => video.removeEventListener('timeupdate', onTime)
  }, [])

  // ── Pick default subtitle on load ─────────────────────────
  useEffect(() => {
    if (!subtitles.length) return
    const preferred =
      subtitles.find(s => s.default) ||
      subtitles.find(s => s.label?.toLowerCase().includes('english - dub')) ||
      subtitles.find(s => s.label?.toLowerCase() === 'english') ||
      null
    setActiveSubtitle(preferred?.label ?? null)
  }, [subtitles])

  // ── video event listeners ──────────────────────────────────
  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const onPlay = () => setPlaying(true)
    const onPause = () => setPlaying(false)
    const onWaiting = () => setLoading(true)
    const onPlaying = () => setLoading(false)
    const onEnding = () => { onEnded?.(); setPlaying(false) }

    const onTimeUpdate = () => {
      setCurrent(video.currentTime)
      if (video.buffered.length > 0) {
        setBuffered(video.buffered.end(video.buffered.length - 1))
      }
      if (Math.round(video.currentTime) % 10 === 0) {
        onProgress?.(video.currentTime)
      }
    }

    const onDurationChange = () => setDuration(video.duration)

    video.addEventListener('play', onPlay)
    video.addEventListener('pause', onPause)
    video.addEventListener('waiting', onWaiting)
    video.addEventListener('playing', onPlaying)
    video.addEventListener('ended', onEnding)
    video.addEventListener('timeupdate', onTimeUpdate)
    video.addEventListener('durationchange', onDurationChange)

    return () => {
      video.removeEventListener('play', onPlay)
      video.removeEventListener('pause', onPause)
      video.removeEventListener('waiting', onWaiting)
      video.removeEventListener('playing', onPlaying)
      video.removeEventListener('ended', onEnding)
      video.removeEventListener('timeupdate', onTimeUpdate)
      video.removeEventListener('durationchange', onDurationChange)
    }
  }, [onProgress, onEnded])

  // ── controls auto-hide ─────────────────────────────────────
  const resetControlsTimer = () => {
    setShowControls(true)
    clearTimeout(controlsTimer.current)
    controlsTimer.current = setTimeout(() => {
      if (playing) setShowControls(false)
    }, 3000)
  }

  useEffect(() => {
    return () => clearTimeout(controlsTimer.current)
  }, [])

  // ── fullscreen listener ────────────────────────────────────
  useEffect(() => {
    const onChange = () => setFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  // ── keyboard shortcuts ─────────────────────────────────────
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT') return
      switch (e.key) {
        case ' ':
        case 'k':
          e.preventDefault()
          togglePlay()
          break
        case 'ArrowRight':
          seek(videoRef.current.currentTime + 10)
          break
        case 'ArrowLeft':
          seek(videoRef.current.currentTime - 10)
          break
        case 'ArrowUp':
          changeVolume(Math.min(1, volume + 0.1))
          break
        case 'ArrowDown':
          changeVolume(Math.max(0, volume - 0.1))
          break
        case 'f':
          toggleFullscreen()
          break
        case 'm':
          toggleMute()
          break
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [playing, volume])

  // ── helpers ────────────────────────────────────────────────
  const togglePlay = () => {
    const video = videoRef.current
    if (!video) return
    playing ? video.pause() : video.play()
  }

  const seek = (time) => {
    const video = videoRef.current
    if (!video) return
    video.currentTime = Math.max(0, Math.min(time, duration))
  }

  const seekByClick = (e) => {
    const bar = progressRef.current
    if (!bar) return
    const rect = bar.getBoundingClientRect()
    const pct = (e.clientX - rect.left) / rect.width
    seek(pct * duration)
  }

  const changeVolume = (val) => {
    const video = videoRef.current
    if (!video) return
    video.volume = val
    setVolume(val)
    setMuted(val === 0)
  }

  const toggleMute = () => {
    const video = videoRef.current
    if (!video) return
    video.muted = !muted
    setMuted(!muted)
  }

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen()
    } else {
      document.exitFullscreen()
    }
  }

  const setQualityLevel = (index) => {
    if (hlsRef.current) {
      hlsRef.current.currentLevel = index
      setQuality(index)
    }
    setShowQuality(false)
  }

  const selectSubtitle = (label) => {
    setActiveSubtitle(label)
    setShowSubtitles(false)
  }

  const changeSpeed = (speed) => {
    if (videoRef.current) videoRef.current.playbackRate = speed
    setPlaybackSpeed(speed)
    setShowSpeed(false)
  }

  const fmt = (s) => {
    if (!s || isNaN(s)) return '0:00'
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    const sec = Math.floor(s % 60)
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  const progressPct = duration ? (currentTime / duration) * 100 : 0
  const bufferedPct = duration ? (buffered / duration) * 100 : 0

  const handleContainerClick = (e) => {
    if (showQuality || showSubtitles || showSpeed) {
      setShowQuality(false)
      setShowSubtitles(false)
      setShowSpeed(false)
    } else {
      togglePlay()
    }
  }

  return (
    <div
      ref={containerRef}
      onMouseMove={resetControlsTimer}
      onMouseLeave={() => playing && setShowControls(false)}
      onClick={handleContainerClick}
      className="relative w-full bg-black select-none"
      style={{ aspectRatio: '16/9' }}
    >
      <video
        ref={videoRef}
        className="w-full h-full"
        playsInline
      />

      {/* subtitle overlay */}
      {currentCue && (
        <div className="absolute bottom-16 left-0 right-0 flex justify-center pointer-events-none px-8">
          <span
            className="text-white text-sm md:text-base font-medium text-center px-3 py-1 rounded"
            style={{
              background: 'rgba(0,0,0,0.75)',
              textShadow: '0 1px 3px rgba(0,0,0,0.9)',
              lineHeight: '1.5',
              whiteSpace: 'pre-line',
            }}
            dangerouslySetInnerHTML={{ __html: currentCue.replace(/<[^>]+>/g, '') }}
          />
        </div>
      )}

      {/* loading spinner */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40 pointer-events-none">
          <div className="w-12 h-12 border-2 border-surface-border border-t-accent rounded-full animate-spin"/>
        </div>
      )}

      {/* error */}
      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80">
          <svg className="w-10 h-10 text-red-500 mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <p className="text-white text-sm">{error}</p>
        </div>
      )}

      {/* controls */}
      <div
        onClick={(e) => e.stopPropagation()}
        className={`absolute inset-0 flex flex-col justify-between transition-opacity duration-300 ${
          showControls ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      >
        {/* top bar */}
        <div className="bg-gradient-to-b from-black/70 to-transparent px-4 pt-4 pb-8">
          <p className="text-white text-sm font-medium truncate">{title}</p>
        </div>

        {/* bottom bar */}
        <div className="bg-gradient-to-t from-black/90 to-transparent px-4 pb-4 pt-10">

          {/* progress bar */}
          <div
            ref={progressRef}
            onClick={seekByClick}
            className="relative h-1 rounded-full bg-white/20 mb-3 cursor-pointer group/prog"
          >
            <div
              className="absolute inset-y-0 left-0 bg-white/30 rounded-full"
              style={{ width: `${bufferedPct}%` }}
            />
            <div
              className="absolute inset-y-0 left-0 accent-gradient rounded-full"
              style={{ width: `${progressPct}%` }}
            />
            <div
              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-accent opacity-0 group-hover/prog:opacity-100 transition-opacity"
              style={{ left: `calc(${progressPct}% - 6px)` }}
            />
          </div>

          {/* controls row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">

              {/* play/pause */}
              <button onClick={togglePlay} className="text-white hover:text-accent transition-colors">
                {playing ? (
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                  </svg>
                ) : (
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M8 5v14l11-7z"/>
                  </svg>
                )}
              </button>

              {/* skip back */}
              <button onClick={() => seek(currentTime - 10)} className="text-white hover:text-accent transition-colors">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
                </svg>
              </button>

              {/* skip forward */}
              <button onClick={() => seek(currentTime + 10)} className="text-white hover:text-accent transition-colors">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8z"/>
                </svg>
              </button>

              {/* volume */}
              <div className="flex items-center gap-2 group/vol">
                <button onClick={toggleMute} className="text-white hover:text-accent transition-colors">
                  {muted || volume === 0 ? (
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
                    </svg>
                  )}
                </button>
                <input
                  type="range" min="0" max="1" step="0.05"
                  value={muted ? 0 : volume}
                  onChange={(e) => changeVolume(parseFloat(e.target.value))}
                  className="w-0 group-hover/vol:w-16 transition-all duration-200 accent-[#facc15]"
                />
              </div>

              {/* time */}
              <span className="text-white/70 text-xs tabular-nums">
                {fmt(currentTime)} / {fmt(duration)}
              </span>
            </div>

            <div className="flex items-center gap-3">

              {/* subtitle picker */}
              {subtitles.length > 0 && (
                <div className="relative">
                  <button
                    onClick={() => { setShowSubtitles(!showSubtitles); setShowQuality(false); setShowSpeed(false) }}
                    className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded border transition-all ${
                      activeSubtitle
                        ? 'text-accent border-accent/50 bg-accent/10'
                        : 'text-white/70 border-white/20 hover:text-white hover:border-accent/50'
                    }`}
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-8 11H6v-2h6v2zm8 0h-6v-2h6v2zm0-4H6V9h14v2z"/>
                    </svg>
                    {activeSubtitle
                      ? activeSubtitle.length > 10
                        ? activeSubtitle.slice(0, 10) + '…'
                        : activeSubtitle
                      : 'CC'}
                  </button>
                  {showSubtitles && (
                    <div className="absolute bottom-8 right-0 bg-surface border border-surface-border rounded-lg overflow-hidden shadow-xl w-48 max-h-64 overflow-y-auto">
                      <button
                        onClick={() => selectSubtitle(null)}
                        className={`w-full px-3 py-2 text-xs text-left transition-colors ${
                          activeSubtitle === null
                            ? 'text-accent bg-accent/10'
                            : 'text-gray-300 hover:text-white hover:bg-surface-hover'
                        }`}
                      >
                        Off
                      </button>
                      {subtitles.map((sub) => (
                        <button
                          key={sub.label}
                          onClick={() => selectSubtitle(sub.label)}
                          className={`w-full px-3 py-2 text-xs text-left transition-colors ${
                            activeSubtitle === sub.label
                              ? 'text-accent bg-accent/10'
                              : 'text-gray-300 hover:text-white hover:bg-surface-hover'
                          }`}
                        >
                          {sub.label}
                          {sub.default && (
                            <span className="ml-1 text-accent/60 text-[10px]">default</span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* playback speed */}
              <div className="relative">
                <button
                  onClick={() => { setShowSpeed(!showSpeed); setShowQuality(false); setShowSubtitles(false) }}
                  className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded border border-white/20 text-white/70 hover:text-white hover:border-accent/50 transition-all"
                >
                  {playbackSpeed === 1 ? '1x' : `${playbackSpeed}x`}
                </button>
                {showSpeed && (
                  <div className="absolute bottom-8 right-0 bg-surface border border-surface-border rounded-lg overflow-hidden shadow-xl w-24">
                    {[0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2].map(speed => (
                      <button
                        key={speed}
                        onClick={() => changeSpeed(speed)}
                        className={`w-full px-3 py-2 text-xs text-left transition-colors ${
                          playbackSpeed === speed
                            ? 'text-accent bg-accent/10'
                            : 'text-gray-300 hover:text-white hover:bg-surface-hover'
                        }`}
                      >
                        {speed === 1 ? 'Normal' : `${speed}x`}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* quality picker */}
              {qualities.length > 1 && (
                <div className="relative">
                  <button
                    onClick={() => { setShowQuality(!showQuality); setShowSubtitles(false); setShowSpeed(false) }}
                    className="text-white/70 hover:text-white text-xs font-medium px-2 py-1 rounded border border-white/20 hover:border-accent/50 transition-all"
                  >
                    {quality === -1 ? 'Auto' : qualities.find(q => q.index === quality)?.label}
                  </button>
                  {showQuality && (
                    <div className="absolute bottom-8 right-0 bg-surface border border-surface-border rounded-lg overflow-hidden shadow-xl min-w-20">
                      {qualities.map((q) => (
                        <button
                          key={q.index}
                          onClick={() => setQualityLevel(q.index)}
                          className={`w-full px-3 py-2 text-xs text-left transition-colors ${
                            quality === q.index
                              ? 'text-accent bg-accent/10'
                              : 'text-gray-300 hover:text-white hover:bg-surface-hover'
                          }`}
                        >
                          {q.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* fullscreen */}
              <button onClick={toggleFullscreen} className="text-white hover:text-accent transition-colors">
                {fullscreen ? (
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"/>
                  </svg>
                ) : (
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}