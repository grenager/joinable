import type { Category, Event, EventListResponse, GeoLocation } from "./types";

const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface FetchEventsParams {
  location: GeoLocation;
  q?: string;
  category?: string;
  start?: string;
  radiusKm?: number;
  limit?: number;
  offset?: number;
  token?: string | null;
}

export async function fetchEvents(params: FetchEventsParams): Promise<EventListResponse> {
  const searchParams = new URLSearchParams({
    lat: String(params.location.lat),
    lng: String(params.location.lng),
    radius_km: String(params.radiusKm ?? 40),
    limit: String(params.limit ?? 20),
    offset: String(params.offset ?? 0),
  });

  if (params.q) searchParams.set("q", params.q);
  if (params.category) searchParams.set("category", params.category);
  if (params.start) searchParams.set("start", params.start);

  const headers: HeadersInit = { Accept: "application/json" };
  if (params.token) {
    headers.Authorization = `Bearer ${params.token}`;
  }

  const response = await fetch(`${API_URL}/v1/events?${searchParams.toString()}`, { headers });
  if (!response.ok) {
    throw new Error(`Failed to fetch events: ${response.status}`);
  }
  return response.json() as Promise<EventListResponse>;
}

export async function fetchCategories(): Promise<Category[]> {
  const response = await fetch(`${API_URL}/v1/categories`);
  if (!response.ok) {
    throw new Error(`Failed to fetch categories: ${response.status}`);
  }
  return response.json() as Promise<Category[]>;
}

export async function bookmarkEvent(eventId: string, token: string): Promise<void> {
  const response = await fetch(`${API_URL}/v1/bookmarks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ event_id: eventId }),
  });
  if (!response.ok && response.status !== 409) {
    throw new Error(`Failed to bookmark: ${response.status}`);
  }
}

export async function unbookmarkEvent(eventId: string, token: string): Promise<void> {
  const response = await fetch(`${API_URL}/v1/bookmarks/${eventId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok && response.status !== 404) {
    throw new Error(`Failed to remove bookmark: ${response.status}`);
  }
}

export async function fetchBookmarks(token: string): Promise<Event[]> {
  const response = await fetch(`${API_URL}/v1/bookmarks`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch bookmarks: ${response.status}`);
  }
  const data = (await response.json()) as Array<{ event: Event | null }>;
  return data.map((b) => b.event).filter((e): e is Event => e !== null);
}
