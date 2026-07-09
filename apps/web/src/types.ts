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

export interface SourceSelectors {
  container: string;
  title: string;
  start: string;
  end: string | null;
  venue: string | null;
  url: string | null;
  image: string | null;
  price: string | null;
  description: string | null;
  date_format: string | null;
  url_attribute: string;
}

export type SourceType = "html_css" | "evvnt" | "cityspark" | "eventscom" | "tribe" | "localist";

export interface EvvntConfig {
  publisher_id: number;
  hits_per_page: number;
}

export interface CitySparkConfig {
  portal_slug: string;
  latitude: number;
  longitude: number;
  distance_miles: number;
  days_ahead: number;
  events_per_day: number;
}

export interface EventsComConfig {
  calendar_token: string;
  days_ahead: number;
  radius_miles: number;
}

export interface TribeConfig {
  base_url: string;
  days_ahead: number;
  per_page: number;
}

export interface LocalistConfig {
  calendar_url: string;
  days: number;
  pp: number;
}

export interface Source {
  id: string;
  name: string;
  url: string;
  source_type: SourceType;
  region: string;
  timezone: string;
  enabled: boolean;
  scrape_frequency_minutes: number;
  config: Record<string, unknown>;
  default_category: string;
  render_js: boolean;
  last_scraped_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourceInput {
  name: string;
  url: string;
  source_type: SourceType;
  region: string;
  timezone: string;
  enabled: boolean;
  scrape_frequency_minutes: number;
  default_category: string;
  render_js: boolean;
  selectors: SourceSelectors;
  evvnt: EvvntConfig;
  cityspark: CitySparkConfig;
  eventscom: EventsComConfig;
  tribe: TribeConfig;
  localist: LocalistConfig;
}

export interface ScrapeTestSample {
  title: string | null;
  start: string | null;
  venue: string | null;
  url: string | null;
  image: string | null;
}

export interface ScrapeTestResult {
  events_found: number;
  sample: ScrapeTestSample[];
}

export const EMPTY_SELECTORS: SourceSelectors = {
  container: "",
  title: "",
  start: "",
  end: null,
  venue: null,
  url: null,
  image: null,
  price: null,
  description: null,
  date_format: null,
  url_attribute: "href",
};

export const EMPTY_EVVNT_CONFIG: EvvntConfig = {
  publisher_id: 0,
  hits_per_page: 50,
};

export const EMPTY_CITYSPARK_CONFIG: CitySparkConfig = {
  portal_slug: "",
  latitude: 0,
  longitude: 0,
  distance_miles: 25,
  days_ahead: 30,
  events_per_day: 50,
};

export const EMPTY_EVENTSCOM_CONFIG: EventsComConfig = {
  calendar_token: "",
  days_ahead: 30,
  radius_miles: 25,
};

export const EMPTY_TRIBE_CONFIG: TribeConfig = {
  base_url: "",
  days_ahead: 90,
  per_page: 100,
};

export const EMPTY_LOCALIST_CONFIG: LocalistConfig = {
  calendar_url: "",
  days: 90,
  pp: 100,
};

export const EMPTY_SOURCE_INPUT: SourceInput = {
  name: "",
  url: "",
  source_type: "html_css",
  region: "SF Bay Area",
  timezone: "America/Los_Angeles",
  enabled: true,
  scrape_frequency_minutes: 1440,
  default_category: "music",
  render_js: false,
  selectors: { ...EMPTY_SELECTORS },
  evvnt: { ...EMPTY_EVVNT_CONFIG },
  cityspark: { ...EMPTY_CITYSPARK_CONFIG },
  eventscom: { ...EMPTY_EVENTSCOM_CONFIG },
  tribe: { ...EMPTY_TRIBE_CONFIG },
  localist: { ...EMPTY_LOCALIST_CONFIG },
};
