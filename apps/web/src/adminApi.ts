import type {
  ScrapeTestResult,
  Source,
  SourceInput,
  SourceType,
} from "./types";

const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function buildConfig(input: SourceInput): Record<string, unknown> {
  switch (input.source_type) {
    case "evvnt":
      return {
        publisher_id: input.evvnt.publisher_id,
        hits_per_page: input.evvnt.hits_per_page,
      };
    case "cityspark":
      return {
        portal_slug: input.cityspark.portal_slug,
        latitude: input.cityspark.latitude,
        longitude: input.cityspark.longitude,
        distance_miles: input.cityspark.distance_miles,
        days_ahead: input.cityspark.days_ahead,
        events_per_day: input.cityspark.events_per_day,
      };
    case "eventscom":
      return {
        calendar_token: input.eventscom.calendar_token,
        days_ahead: input.eventscom.days_ahead,
        radius_miles: input.eventscom.radius_miles,
      };
    case "tribe":
      return {
        base_url: input.tribe.base_url,
        days_ahead: input.tribe.days_ahead,
        per_page: input.tribe.per_page,
      };
    case "localist":
      return {
        calendar_url: input.localist.calendar_url,
        days: input.localist.days,
        pp: input.localist.pp,
      };
    default:
      return { ...input.selectors };
  }
}

function serializeSource(input: SourceInput): Record<string, unknown> {
  return {
    name: input.name,
    url: input.url,
    source_type: input.source_type,
    region: input.region,
    timezone: input.timezone,
    enabled: input.enabled,
    scrape_frequency_minutes: input.scrape_frequency_minutes,
    default_category: input.default_category,
    render_js: input.render_js,
    config: buildConfig(input),
  };
}

export class AdminApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "AdminApiError";
  }
}

function authHeaders(token: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    Accept: "application/json",
    "X-Admin-Token": token,
  };
}

async function parseError(response: Response): Promise<never> {
  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (body.detail != null) {
      detail = JSON.stringify(body.detail);
    }
  } catch {
    // ignore non-JSON error bodies
  }
  throw new AdminApiError(response.status, detail);
}

export async function listSources(token: string): Promise<Source[]> {
  const response = await fetch(`${API_URL}/v1/admin/sources`, {
    headers: authHeaders(token),
  });
  if (!response.ok) return parseError(response);
  return response.json() as Promise<Source[]>;
}

export async function createSource(token: string, input: SourceInput): Promise<Source> {
  const response = await fetch(`${API_URL}/v1/admin/sources`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(serializeSource(input)),
  });
  if (!response.ok) return parseError(response);
  return response.json() as Promise<Source>;
}

export async function updateSource(
  token: string,
  id: string,
  input: SourceInput
): Promise<Source> {
  const response = await fetch(`${API_URL}/v1/admin/sources/${id}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(serializeSource(input)),
  });
  if (!response.ok) return parseError(response);
  return response.json() as Promise<Source>;
}

export async function deleteSource(token: string, id: string): Promise<void> {
  const response = await fetch(`${API_URL}/v1/admin/sources/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!response.ok && response.status !== 204) return parseError(response);
}

export async function testScrape(
  token: string,
  input: SourceInput
): Promise<ScrapeTestResult> {
  const response = await fetch(`${API_URL}/v1/admin/sources/test`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      url: input.url,
      source_type: input.source_type,
      config: buildConfig(input),
      render_js: input.render_js,
    }),
  });
  if (!response.ok) return parseError(response);
  return response.json() as Promise<ScrapeTestResult>;
}

export interface DetectResult {
  source_type: SourceType;
  config: Record<string, unknown>;
  render_js: boolean;
  detail: string;
}

export async function detectSource(token: string, url: string): Promise<DetectResult> {
  const response = await fetch(`${API_URL}/v1/admin/sources/detect`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ url }),
  });
  if (!response.ok) return parseError(response);
  return response.json() as Promise<DetectResult>;
}

export async function testSource(token: string, id: string): Promise<ScrapeTestResult> {
  const response = await fetch(`${API_URL}/v1/admin/sources/${id}/test`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!response.ok) return parseError(response);
  return response.json() as Promise<ScrapeTestResult>;
}

export interface QueuedScrapeResult {
  source_id: string;
  status: string;
  message: string;
}

export async function triggerScrape(token: string, id: string): Promise<QueuedScrapeResult> {
  const response = await fetch(`${API_URL}/v1/admin/sources/${id}/scrape`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!response.ok) return parseError(response);
  return response.json() as Promise<QueuedScrapeResult>;
}
