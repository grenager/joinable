import { useCallback, useEffect, useRef, useState } from "react";
import {
  geocodePlace,
  getPlaceDetails,
  suggestPlaces,
  type PlaceSuggestion,
} from "../api";
import type { GeoLocation } from "../types";

interface LocationPickerProps {
  label: string;
  onSelect: (location: GeoLocation, label: string) => void;
}

function newSessionToken(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

export function LocationPicker({ label, onSelect }: LocationPickerProps) {
  const [editing, setEditing] = useState<boolean>(false);
  const [query, setQuery] = useState<string>("");
  const [suggestions, setSuggestions] = useState<PlaceSuggestion[]>([]);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  const sessionTokenRef = useRef<string>(newSessionToken());
  const containerRef = useRef<HTMLDivElement | null>(null);

  const reset = useCallback(() => {
    setEditing(false);
    setQuery("");
    setSuggestions([]);
    setError(null);
    setActiveIndex(-1);
  }, []);

  useEffect(() => {
    if (!editing) return;
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setSuggestions([]);
      return;
    }
    const controller = new AbortController();
    const handle = window.setTimeout(async () => {
      try {
        const result = await suggestPlaces(trimmed, sessionTokenRef.current, controller.signal);
        setSuggestions(result.suggestions);
        setActiveIndex(-1);
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          setSuggestions([]);
        }
      }
    }, 250);
    return () => {
      controller.abort();
      window.clearTimeout(handle);
    };
  }, [query, editing]);

  useEffect(() => {
    if (!editing) return;
    const onClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        reset();
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [editing, reset]);

  const chooseSuggestion = useCallback(
    async (suggestion: PlaceSuggestion) => {
      setBusy(true);
      setError(null);
      try {
        const details = await getPlaceDetails(suggestion.place_id, sessionTokenRef.current);
        if (!details) {
          setError("Could not resolve location");
          return;
        }
        onSelect({ lat: details.lat, lng: details.lng }, suggestion.description);
        reset();
        sessionTokenRef.current = newSessionToken();
      } catch {
        setError("Lookup failed");
      } finally {
        setBusy(false);
      }
    },
    [onSelect, reset]
  );

  const submitFreeText = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed) {
      reset();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await geocodePlace(trimmed);
      if (!result) {
        setError("No match found");
        return;
      }
      onSelect({ lat: result.lat, lng: result.lng }, trimmed);
      reset();
    } catch {
      setError("Lookup failed");
    } finally {
      setBusy(false);
    }
  }, [query, onSelect, reset]);

  if (!editing) {
    return (
      <button
        type="button"
        className="location-badge"
        title="Change location"
        onClick={() => setEditing(true)}
      >
        {label}
      </button>
    );
  }

  return (
    <div className="location-picker" ref={containerRef}>
      <input
        className="location-input"
        type="text"
        autoFocus
        placeholder="Address, city, or place..."
        value={query}
        disabled={busy}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActiveIndex((i) => Math.max(i - 1, -1));
          } else if (e.key === "Enter") {
            e.preventDefault();
            if (activeIndex >= 0 && suggestions[activeIndex]) {
              void chooseSuggestion(suggestions[activeIndex]);
            } else {
              void submitFreeText();
            }
          } else if (e.key === "Escape") {
            reset();
          }
        }}
      />
      {suggestions.length > 0 && (
        <ul className="location-suggestions">
          {suggestions.map((s, i) => (
            <li key={s.place_id}>
              <button
                type="button"
                className={i === activeIndex ? "suggestion active" : "suggestion"}
                onMouseEnter={() => setActiveIndex(i)}
                onClick={() => void chooseSuggestion(s)}
              >
                {s.description}
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <span className="location-error">{error}</span>}
    </div>
  );
}
