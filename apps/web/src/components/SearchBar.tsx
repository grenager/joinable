import { useEffect, useState } from "react";
import { fetchCategories } from "../api";
import type { Category, DatePreset, SearchFilters } from "../types";

interface SearchBarProps {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
}

const FALLBACK_CATEGORIES: Category[] = [
  { id: "music", label: "Live Music" },
  { id: "comedy", label: "Comedy" },
  { id: "theater", label: "Theater & Performance" },
  { id: "food_drink", label: "Food & Drink" },
  { id: "sports", label: "Sports & Fitness" },
  { id: "arts", label: "Arts & Museums" },
  { id: "community", label: "Community" },
  { id: "other", label: "Other" },
];

export function SearchBar({ filters, onChange }: SearchBarProps) {
  const [categories, setCategories] = useState<Category[]>(FALLBACK_CATEGORIES);

  useEffect(() => {
    void fetchCategories()
      .then(setCategories)
      .catch(() => {
        // keep fallback list
      });
  }, []);

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
        <option value="">All Categories</option>
        {categories.map((category) => (
          <option key={category.id} value={category.id}>
            {category.label}
          </option>
        ))}
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
