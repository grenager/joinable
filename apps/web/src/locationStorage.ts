import type { GeoLocation } from "./types";
import { SF_BAY_DEFAULT } from "./types";

const LOCATION_STORAGE_KEY = "joinable_location";

interface StoredLocation extends GeoLocation {
  label: string;
}

function isStoredLocation(value: unknown): value is StoredLocation {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.lat === "number" &&
    typeof record.lng === "number" &&
    typeof record.label === "string" &&
    Number.isFinite(record.lat) &&
    Number.isFinite(record.lng) &&
    record.label.trim().length > 0
  );
}

export function loadStoredLocation(): StoredLocation | null {
  try {
    const raw = localStorage.getItem(LOCATION_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isStoredLocation(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveStoredLocation(location: GeoLocation, label: string): void {
  const payload: StoredLocation = { lat: location.lat, lng: location.lng, label };
  localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(payload));
}

export function readInitialLocation(): { location: GeoLocation; label: string } {
  const stored = loadStoredLocation();
  if (stored) {
    return { location: { lat: stored.lat, lng: stored.lng }, label: stored.label };
  }
  return { location: SF_BAY_DEFAULT, label: "SF Bay Area" };
}
