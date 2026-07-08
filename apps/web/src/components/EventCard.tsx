import type { Event } from "../types";

interface EventCardProps {
  event: Event;
  isBookmarked: boolean;
  onBookmark: (eventId: string) => void;
  onUnbookmark: (eventId: string) => void;
  isLoggedIn: boolean;
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function EventCard({
  event,
  isBookmarked,
  onBookmark,
  onUnbookmark,
  isLoggedIn,
}: EventCardProps) {
  return (
    <article className="event-card">
      {event.image_url && (
        <img
          className="event-image"
          src={event.image_url}
          alt={event.title}
          loading="lazy"
        />
      )}
      <div className="event-card-body">
        <div className="event-card-header">
          <h2 className="event-title">
            {event.external_url ? (
              <a href={event.external_url} target="_blank" rel="noopener noreferrer">
                {event.title}
              </a>
            ) : (
              event.title
            )}
          </h2>
          {isLoggedIn && (
            <button
              type="button"
              className={`bookmark-btn ${isBookmarked ? "bookmarked" : ""}`}
              onClick={() =>
                isBookmarked ? onUnbookmark(event.id) : onBookmark(event.id)
              }
              aria-label={isBookmarked ? "Remove bookmark" : "Bookmark event"}
            >
              {isBookmarked ? "★" : "☆"}
            </button>
          )}
        </div>
        <p className="event-meta">
          {formatDate(event.start_time)}
          {event.venue && ` · ${event.venue.name}`}
          {event.distance_km != null && ` · ${event.distance_km.toFixed(1)} km`}
        </p>
        {event.price_text && <p className="event-price">{event.price_text}</p>}
        {event.description && <p className="event-desc">{event.description}</p>}
      </div>
    </article>
  );
}
