import { useCallback, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import {
  bookmarkEvent,
  fetchBookmarks,
  fetchEvents,
  unbookmarkEvent,
} from "./api";
import { getSession, getSupabase, signInWithGoogle, signOut } from "./auth";
import { EventCard } from "./components/EventCard";
import { LocationPicker } from "./components/LocationPicker";
import { SearchBar } from "./components/SearchBar";
import type { Event, GeoLocation, SearchFilters } from "./types";
import { SF_BAY_DEFAULT } from "./types";
import logoUrl from "./assets/logo.svg";
import "./App.css";

const DEFAULT_FILTERS: SearchFilters = {
  q: "",
  category: "music",
  datePreset: "all",
  radiusKm: 40,
};

function datePresetToStart(preset: SearchFilters["datePreset"]): string | undefined {
  if (preset === "all") return undefined;
  return preset;
}

export default function App() {
  const [location, setLocation] = useState<GeoLocation>(SF_BAY_DEFAULT);
  const [locationLabel, setLocationLabel] = useState<string>("SF Bay Area");
  const [filters, setFilters] = useState<SearchFilters>(DEFAULT_FILTERS);
  const [events, setEvents] = useState<Event[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [bookmarkedIds, setBookmarkedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocationLabel("Your location");
      },
      () => {
        setLocationLabel("SF Bay Area");
      },
      { timeout: 8000 }
    );
  }, []);

  const handleLocationSelect = useCallback((loc: GeoLocation, label: string) => {
    setLocation(loc);
    setLocationLabel(label);
  }, []);

  useEffect(() => {
    void getSession().then(setSession);
    const supabase = getSupabase();
    if (!supabase) return;
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const loadBookmarks = useCallback(async (token: string) => {
    try {
      const bookmarked = await fetchBookmarks(token);
      setBookmarkedIds(new Set(bookmarked.map((e) => e.id)));
    } catch {
      setBookmarkedIds(new Set());
    }
  }, []);

  useEffect(() => {
    if (session?.access_token) {
      void loadBookmarks(session.access_token);
    } else {
      setBookmarkedIds(new Set());
    }
  }, [session, loadBookmarks]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchEvents({
          location,
          q: filters.q || undefined,
          category: filters.category || undefined,
          start: datePresetToStart(filters.datePreset),
          radiusKm: filters.radiusKm,
          token: session?.access_token ?? null,
        });
        if (!cancelled) {
          setEvents(data.items);
          setTotal(data.total);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load events");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [location, filters, session?.access_token]);

  const handleBookmark = async (eventId: string) => {
    if (!session?.access_token) return;
    await bookmarkEvent(eventId, session.access_token);
    setBookmarkedIds((prev) => new Set([...prev, eventId]));
  };

  const handleUnbookmark = async (eventId: string) => {
    if (!session?.access_token) return;
    await unbookmarkEvent(eventId, session.access_token);
    setBookmarkedIds((prev) => {
      const next = new Set(prev);
      next.delete(eventId);
      return next;
    });
  };

  return (
    <div className="app">
      <header className="header">
        <img className="logo-img" src={logoUrl} alt="Joinable" />
        <p className="tagline">All live events, everywhere</p>
        <div className="header-actions">
          <LocationPicker label={locationLabel} onSelect={handleLocationSelect} />
          {session ? (
            <button type="button" className="auth-btn" onClick={() => void signOut()}>
              Sign out
            </button>
          ) : getSupabase() ? (
            <button type="button" className="auth-btn" onClick={() => void signInWithGoogle()}>
              Sign in with Google
            </button>
          ) : null}
          <a className="admin-link" href="#/admin" title="Admin console">
            Admin
          </a>
        </div>
      </header>

      <SearchBar filters={filters} onChange={setFilters} />

      <main className="main">
        {loading && <p className="status">Loading events...</p>}
        {error && <p className="error">{error}</p>}
        {!loading && !error && events.length === 0 && (
          <p className="status">No events found. Try expanding your radius or date range.</p>
        )}
        {!loading && !error && (
          <p className="results-count">
            {total} event{total !== 1 ? "s" : ""} found
          </p>
        )}
        <div className="event-list">
          {events.map((event) => (
            <EventCard
              key={event.id}
              event={event}
              isBookmarked={bookmarkedIds.has(event.id)}
              onBookmark={(id) => void handleBookmark(id)}
              onUnbookmark={(id) => void handleUnbookmark(id)}
              isLoggedIn={session !== null}
            />
          ))}
        </div>
      </main>
    </div>
  );
}
