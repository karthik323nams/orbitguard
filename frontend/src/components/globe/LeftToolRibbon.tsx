import React from 'react';
import {
  Crosshair,
  Orbit,
  History,
  Bookmark,
  Database,
  Share2,
  Flag,
  Palette,
  Radar,
  Radio,
  BarChart3,
  Calendar,
  Layers,
  Grid,
} from 'lucide-react';
import type { SatType } from '../../lib/tle';

export type LeftToolRibbonProps = {
  activeTool: string;
  onSelectTool: (tool: string) => void;
  activeFilter: SatType | 'all';
  onSetFilter: (filter: SatType | 'all') => void;
};

export function LeftToolRibbon({
  activeTool,
  onSelectTool,
  activeFilter,
  onSetFilter,
}: LeftToolRibbonProps) {
  const tools = [
    { id: 'focus', icon: Crosshair, color: '#ef4444', title: 'Sensor Target & Focus' },
    { id: 'orbit', icon: Orbit, color: '#f87171', title: 'Toggle Orbital Tracks' },
    { id: 'history', icon: History, color: '#fb923c', title: 'TLE Epoch History' },
    { id: 'watchlist', icon: Bookmark, color: '#facc15', title: 'Watchlist & Starred' },
    { id: 'database', icon: Database, color: '#2dd4f0', title: 'Satellite Database Catalog' },
    { id: 'constellations', icon: Share2, color: '#f87171', title: 'Constellations & Groups' },
    { id: 'country', icon: Flag, color: '#f87171', title: 'Filter by Launch Country' },
    { id: 'palette', icon: Palette, color: '#f87171', title: 'Color Mode & Themes' },
    { id: 'sensors', icon: Radar, color: '#fb923c', title: 'Ground Sensor FOV & Cones' },
    { id: 'rf', icon: Radio, color: '#94a3b8', title: 'Radio Frequencies & Telemetry' },
    { id: 'analytics', icon: BarChart3, color: '#94a3b8', title: 'Conjunction Analytics' },
    { id: 'calendar', icon: Calendar, color: '#a3e635', title: 'Pass Planner & Visibility' },
    { id: 'grid', icon: Grid, color: '#ef4444', title: 'Celestial Grid & Equator' },
  ];

  return (
    <aside className="kt-left-ribbon">
      {tools.map((tool) => {
        const Icon = tool.icon;
        const isActive = activeTool === tool.id;
        return (
          <button
            key={tool.id}
            className={`kt-ribbon-btn ${isActive ? 'active' : ''}`}
            onClick={() => onSelectTool(tool.id)}
            title={tool.title}
          >
            <Icon size={16} style={{ color: isActive ? '#fff' : tool.color }} />
          </button>
        );
      })}
    </aside>
  );
}

