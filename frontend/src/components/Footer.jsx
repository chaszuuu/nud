// src/components/Footer.jsx
export default function Footer() {
  return (
    <footer className="w-full border-t border-surface-border bg-surface px-5 sm:px-10 py-6 flex flex-col sm:flex-row items-center justify-between gap-3 font-sans">
      <div className="text-center sm:text-left">
        <p className="text-lg font-bold tracking-[3px] text-accent">NUD</p>
        <p className="text-[11px] text-white/30 mt-1">© 2026 Nud</p>
      </div>

      <div className="text-center text-[11px] text-white/30">
        Data provided by{' '}
        <a
          href="https://www.themoviedb.org"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent/80 font-semibold hover:text-accent transition-colors"
        >
          TMDB
        </a>
      </div>

      <div className="flex items-center gap-1 text-xs text-white/30">
        Made with{' '}
        <span className="text-accent text-base">♥</span>
        {' '}by{' '}
        <span className="text-white/60 font-semibold">chaszuu</span>
      </div>
    </footer>
  )
}