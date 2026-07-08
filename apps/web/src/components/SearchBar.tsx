import type { DatePreset, SearchFilters } from "../types";

interface SearchBarProps {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
}

export function SearchBar({ filters, onChange }: SearchBarProps) {
  return (
    <div className="search-bar">
      <input
        type="search"
        placeholder="Search events..."
        value={filters.q}
        onChange={(e) => onChange({ ...filters, q: e.target.value })}
        className="search-input"
      />
      <select
        value={filters.category}
        onChange={(e) => onChange({ ...filters, category: e.target.value })}
        className="search-select"
      >
        <option value="music">Live Music</option>
        <option value="comedy">Comedy</option>
        <option value="theater">Theater</option>
        <option value="food">Food & Drink</option>
        <option value="sports">Sports</option>
        <option value="arts">Arts & Culture</option>
        <option value="community">Community</option>
        <option value="">All Categories</option>
      </select>
      <select
        value={filters.datePreset}
        onChange={(e) =>
          onChange({ ...filters, datePreset: e.target.value as DatePreset })
        }
        className="search-select"
      >
        <option value="tonight">Tonight</option>
        <option value="this_week">This Week</option>
        <option value="all">All Upcoming</option>
      </select>
      <select
        value={filters.radiusKm}
        onChange={(e) =>
          onChange({ ...filters, radiusKm: Number(e.target.value) })
        }
        className="search-select"
      >
        <option value={10}>10 km</option>
        <option value={25}>25 km</option>
        <option value={40}>40 km</option>
        <option value={80}>80 km</option>
      </select>
    </div>
  );
}
