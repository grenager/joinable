export interface Venue {
  id: string;
  name: string;
  address: string | null;
  city: string | null;
  region: string | null;
  lat: number | null;
  lng: number | null;
}

export interface Event {
  id: string;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string | null;
  category: string;
  external_url: string | null;
  image_url: string | null;
  price_text: string | null;
  venue: Venue | null;
  distance_km: number | null;
}

export interface EventListResponse {
  items: Event[];
  total: number;
  limit: number;
  offset: number;
}

export interface Category {
  id: string;
  label: string;
}

export type DatePreset = "tonight" | "this_week" | "all";

export interface SearchFilters {
  q: string;
  category: string;
  datePreset: DatePreset;
  radiusKm: number;
}

export interface GeoLocation {
  lat: number;
  lng: number;
}

export const SF_BAY_DEFAULT: GeoLocation = { lat: 37.7749, lng: -122.4194 };
