import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Play, Pause, Rewind, FastForward, Search, X } from 'lucide-react';
import type { ParsedSatellite } from '../../lib/tle';
import { getCountryFlag } from '../../lib/propagator';

export type KeepTrackHeaderProps = {
  time: Date;
  isPlaying: boolean;
  onTogglePlay: () => void;
  speed: number;
  onSetSpeed: (speed: number) => void;
  onResetTime: () => void;
  satelliteCount: number;
  satellites: ParsedSatellite[];
  onSelectSat: (sat: ParsedSatellite) => void;
  selectedSat: ParsedSatellite | null;
};

export function KeepTrackHeader({
  time,
  isPlaying,
  onTogglePlay,
  speed,
  onSetSpeed,
  onResetTime,
  satelliteCount,
  satellites,
  onSelectSat,
  selectedSat,
}: KeepTrackHeaderProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // Time format: HH:mm:ss
  const timeString = time.toISOString().substring(11, 19);

  // Close search on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Keyboard shortcut 'F' to focus search
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.key === 'f' || e.key === 'F') && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();
        setSearchOpen(true);
        const input = searchRef.current?.querySelector('input');
        input?.focus();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const searchResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];
    return satellites
      .filter((s) => {
        return (
          s.name.toLowerCase().includes(q) ||
          String(s.catalog_number).includes(q) ||
          (s.cosparId && s.cosparId.toLowerCase().includes(q))
        );
      })
      .slice(0, 10);
  }, [searchQuery, satellites]);

  const handleSelect = (sat: ParsedSatellite) => {
    onSelectSat(sat);
    setSearchOpen(false);
    setSearchQuery('');
  };

  // Timeline pass intervals
  const timeHours = [
    '14:00', '16:00', '18:00', '20:00', '22:00', '08-26', '02:00', '04:00', '06:00', '08:00', '10:00', '12:00'
  ];

  return (
    <header className="kt-top-container">
      <div className="kt-top-bar">
        {/* Brand & Object Count */}
        <div className="kt-brand-block">
          <span className="kt-brand-title">Astrail</span>
          <span className="kt-sat-count-badge" title="Total active cataloged objects">
            {satelliteCount.toLocaleString()}
          </span>
        </div>

        {/* Big Time Display */}
        <div className="kt-clock-display">
          <span className="kt-clock-val">{timeString}</span>
        </div>

        {/* Playback Controls */}
        <div className="kt-playback-controls">
          <button
            className="kt-ctrl-btn"
            onClick={() => onSetSpeed(Math.max(1, Math.floor(speed / 2)))}
            title="Slow down"
          >
            <Rewind size={13} />
          </button>
          <button
            className="kt-ctrl-btn kt-play-btn"
            onClick={onTogglePlay}
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? <Pause size={13} /> : <Play size={13} />}
          </button>
          <button
            className="kt-ctrl-btn"
            onClick={() => onSetSpeed(speed < 120 ? speed * 2 : 1)}
            title={`Speed up (Current: ${speed}x)`}
          >
            <FastForward size={13} />
          </button>
        </div>

        {/* Search Bar */}
        <div className="kt-search-wrapper" ref={searchRef}>
          <div className="kt-search-box">
            <Search size={14} className="kt-search-icon" />
            <input
              type="text"
              placeholder="Search... (F)"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => setSearchOpen(true)}
              className="kt-search-input"
            />
            {searchQuery && (
              <button className="kt-search-clear" onClick={() => setSearchQuery('')}>
                <X size={12} />
              </button>
            )}
          </div>

          {searchOpen && searchResults.length > 0 && (
            <div className="kt-search-dropdown">
              {searchResults.map((sat) => (
                <button
                  key={sat.catalog_number}
                  className="kt-search-row"
                  onClick={() => handleSelect(sat)}
                >
                  <span className="kt-search-flag">{getCountryFlag(sat.countryCode)}</span>
                  <div className="kt-search-meta">
                    <span className="kt-search-name">{sat.name}</span>
                    <span className="kt-search-sub">
                      NORAD: {sat.catalog_number} · {sat.type.toUpperCase()} · {sat.launchYear || '1998'}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Sub Header Ruler: Watchlist & Next Pass Timeline */}
      <div className="kt-timeline-ruler">
        <div className="kt-watchlist-info">
          <span className="kt-link-txt">Watchlist</span>
          <span className="kt-link-divider">|</span>
          <span className="kt-link-txt">Sensors</span>
          <span className="kt-pass-timer">
            Next pass in <strong>26m</strong> · 24 passes
          </span>
        </div>

        {/* Timeline ruler ticks with yellow pass markers */}
        <div className="kt-ruler-ticks">
          {timeHours.map((hour, idx) => (
            <div key={idx} className="kt-ruler-cell">
              <span className="kt-ruler-label">{hour}</span>
              {/* Pass indicator markers (golden yellow ticks like KeepTrack) */}
              {(idx % 2 === 0 || idx === 3 || idx === 7 || idx === 9) && (
                <span className="kt-pass-tick" />
              )}
            </div>
          ))}
          {/* Current time red marker needle */}
          <div className="kt-ruler-needle" />
        </div>
      </div>
    </header>
  );
}

