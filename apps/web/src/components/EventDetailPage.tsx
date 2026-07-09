import { useCallback, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { bookmarkEvent, fetchBookmarks, fetchEvent, unbookmarkEvent } from "../api";
import { getSession, getSupabase, signInWithGoogle, signOut } from "../auth";
import type { Event } from "../types";
import logoUrl from "../assets/logo.svg";
import "../App.css";

interface EventDetailPageProps {
  eventId: string;
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatTimeRange(start: string, end: string | null): string {
  const startDate = new Date(start);
  const startTime = startDate.toLocaleString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
  if (!end) return startTime;
  const endDate = new Date(end);
  const endTime = endDate.toLocaleString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
  return `${startTime} – ${endTime}`;
}

function shareUrl(eventId: string): string {
  return `${window.location.origin}${window.location.pathname}#/events/${eventId}`;
}

function externalHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "source site";
  }
}

export function EventDetailPage({ eventId }: EventDetailPageProps) {
  const [event, setEvent] = useState<Event | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isBookmarked, setIsBookmarked] = useState<boolean>(false);
  const [shareCopied, setShareCopied] = useState<boolean>(false);

  useEffect(() => {
    void getSession().then(setSession);
    const supabase = getSupabase();
    if (!supabase) return;
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session?.access_token) {
      setIsBookmarked(false);
      return;
    }
    let cancelled = false;
    void fetchBookmarks(session.access_token).then((bookmarked) => {
      if (!cancelled) {
        setIsBookmarked(bookmarked.some((e) => e.id === eventId));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [session?.access_token, eventId]);

  useEffect(() => {
    let cancelled = false;
    const load = async (): Promise<void> => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchEvent(eventId);
        if (!cancelled) setEvent(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load event");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  const handleShare = useCallback(async (): Promise<void> => {
    const url = shareUrl(eventId);
    try {
      await navigator.clipboard.writeText(url);
      setShareCopied(true);
      window.setTimeout(() => setShareCopied(false), 2000);
    } catch {
      window.prompt("Copy this link:", url);
    }
  }, [eventId]);

  const handleBookmark = async (): Promise<void> => {
    if (!session?.access_token) return;
    await bookmarkEvent(eventId, session.access_token);
    setIsBookmarked(true);
  };

  const handleUnbookmark = async (): Promise<void> => {
    if (!session?.access_token) return;
    await unbookmarkEvent(eventId, session.access_token);
    setIsBookmarked(false);
  };

  return (
    <div className="app">
      <header className="header">
        <a href="#/" className="detail-back-link" aria-label="Back to events">
          ← Back
        </a>
        <img className="logo-img" src={logoUrl} alt="Joinable" />
        <div className="header-actions">
          {session ? (
            <button type="button" className="auth-btn" onClick={() => void signOut()}>
              Sign out
            </button>
          ) : getSupabase() ? (
            <button type="button" className="auth-btn" onClick={() => void signInWithGoogle()}>
              Sign in with Google
            </button>
          ) : null}
        </div>
      </header>

      <main className="main event-detail">
        {loading && <p className="status">Loading event...</p>}
        {error && <p className="error">{error}</p>}
        {!loading && !error && event && (
          <article className="event-detail-card">
            {event.image_url && (
              <img
                className="event-detail-image"
                src={event.image_url}
                alt={event.title}
              />
            )}
            <div className="event-detail-body">
              <div className="event-detail-header">
                <h1 className="event-detail-title">{event.title}</h1>
                {session && (
                  <button
                    type="button"
                    className={`bookmark-btn ${isBookmarked ? "bookmarked" : ""}`}
                    onClick={() =>
                      void (isBookmarked ? handleUnbookmark() : handleBookmark())
                    }
                    aria-label={isBookmarked ? "Remove bookmark" : "Bookmark event"}
                  >
                    {isBookmarked ? "★" : "☆"}
                  </button>
                )}
              </div>

              <p className="event-detail-datetime">{formatDate(event.start_time)}</p>
              <p className="event-detail-time">{formatTimeRange(event.start_time, event.end_time)}</p>

              {event.venue && (
                <p className="event-detail-venue">
                  {event.venue.name}
                  {event.venue.address && ` · ${event.venue.address}`}
                </p>
              )}

              {event.price_text && <p className="event-price">{event.price_text}</p>}

              {event.description && (
                <p className="event-detail-description">{event.description}</p>
              )}

              <div className="event-detail-actions">
                <button type="button" className="detail-action-btn" onClick={() => void handleShare()}>
                  {shareCopied ? "Link copied!" : "Share"}
                </button>
                {event.external_url && (
                  <a
                    className="detail-action-btn detail-action-btn-primary"
                    href={event.external_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View on {externalHost(event.external_url)}
                  </a>
                )}
              </div>
            </div>
          </article>
        )}
      </main>
    </div>
  );
}
