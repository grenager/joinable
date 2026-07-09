import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  AdminApiError,
  createSource,
  deleteSource,
  detectSource,
  listSources,
  testScrape,
  testSource,
  triggerScrape,
  updateSource,
} from "../adminApi";
import {
  EMPTY_CITYSPARK_CONFIG,
  EMPTY_EVENTSCOM_CONFIG,
  EMPTY_EVVNT_CONFIG,
  EMPTY_LOCALIST_CONFIG,
  EMPTY_SELECTORS,
  EMPTY_SOURCE_INPUT,
  EMPTY_TRIBE_CONFIG,
  type ScrapeTestResult,
  type Source,
  type SourceInput,
  type SourceSelectors,
  type SourceType,
} from "../types";
import logoUrl from "../assets/logo.svg";

const TOKEN_KEY = "joinable_admin_token";

const SOURCE_TYPE_LABELS: Record<SourceType, string> = {
  html_css: "HTML + CSS",
  evvnt: "evvnt API",
  cityspark: "CitySpark API",
  eventscom: "Events.com API",
  tribe: "The Events Calendar",
  localist: "Localist API",
};

function hasAdvancedHtmlCssConfig(config: Record<string, unknown>): boolean {
  return Array.isArray(config.profiles) || config.pagination != null;
}

function configToSelectors(config: Record<string, unknown>): SourceSelectors {
  const result: SourceSelectors = { ...EMPTY_SELECTORS };
  for (const key of Object.keys(result) as (keyof SourceSelectors)[]) {
    const value = config[key];
    if (typeof value === "string") {
      result[key] = value;
    }
  }
  return result;
}

function sourceToInput(source: Source): SourceInput {
  const base: SourceInput = {
    name: source.name,
    url: source.url,
    source_type: source.source_type,
    region: source.region,
    timezone: source.timezone,
    enabled: source.enabled,
    scrape_frequency_minutes: source.scrape_frequency_minutes,
    default_category: source.default_category,
    render_js: source.render_js,
    selectors: { ...EMPTY_SELECTORS },
    html_css_raw_config: null,
    evvnt: { ...EMPTY_EVVNT_CONFIG },
    cityspark: { ...EMPTY_CITYSPARK_CONFIG },
    eventscom: { ...EMPTY_EVENTSCOM_CONFIG },
    tribe: { ...EMPTY_TRIBE_CONFIG },
    localist: { ...EMPTY_LOCALIST_CONFIG },
  };

  switch (source.source_type) {
    case "evvnt":
      return {
        ...base,
        evvnt: {
          publisher_id: Number(source.config.publisher_id) || 0,
          hits_per_page: Number(source.config.hits_per_page) || 50,
        },
      };
    case "cityspark":
      return {
        ...base,
        cityspark: {
          portal_slug: String(source.config.portal_slug ?? ""),
          latitude: Number(source.config.latitude) || 0,
          longitude: Number(source.config.longitude) || 0,
          distance_miles: Number(source.config.distance_miles) || 25,
          days_ahead: Number(source.config.days_ahead) || 30,
          events_per_day: Number(source.config.events_per_day) || 50,
        },
      };
    case "eventscom":
      return {
        ...base,
        eventscom: {
          calendar_token: String(source.config.calendar_token ?? ""),
          days_ahead: Number(source.config.days_ahead) || 30,
          radius_miles: Number(source.config.radius_miles) || 25,
        },
      };
    case "tribe":
      return {
        ...base,
        tribe: {
          base_url: String(source.config.base_url ?? ""),
          days_ahead: Number(source.config.days_ahead) || 90,
          per_page: Number(source.config.per_page) || 100,
        },
      };
    case "localist":
      return {
        ...base,
        localist: {
          calendar_url: String(source.config.calendar_url ?? ""),
          days: Number(source.config.days) || 90,
          pp: Number(source.config.pp) || 100,
        },
      };
    default:
      return {
        ...base,
        selectors: configToSelectors(source.config),
        html_css_raw_config: hasAdvancedHtmlCssConfig(source.config) ? source.config : null,
      };
  }
}

function applyDetectedConfig(
  prev: SourceInput,
  sourceType: SourceType,
  config: Record<string, unknown>
): SourceInput {
  const next: SourceInput = {
    ...prev,
    source_type: sourceType,
    selectors: sourceType === "html_css" ? configToSelectors(config) : prev.selectors,
  };

  switch (sourceType) {
    case "evvnt":
      return {
        ...next,
        evvnt: {
          publisher_id: Number(config.publisher_id) || 0,
          hits_per_page: Number(config.hits_per_page) || 50,
        },
      };
    case "cityspark":
      return {
        ...next,
        cityspark: {
          portal_slug: String(config.portal_slug ?? prev.cityspark.portal_slug),
          latitude: Number(config.latitude) || prev.cityspark.latitude || 0,
          longitude: Number(config.longitude) || prev.cityspark.longitude || 0,
          distance_miles: Number(config.distance_miles) || prev.cityspark.distance_miles,
          days_ahead: Number(config.days_ahead) || prev.cityspark.days_ahead,
          events_per_day: Number(config.events_per_day) || prev.cityspark.events_per_day,
        },
      };
    case "eventscom":
      return {
        ...next,
        eventscom: {
          calendar_token: String(config.calendar_token ?? ""),
          days_ahead: Number(config.days_ahead) || 30,
          radius_miles: Number(config.radius_miles) || 25,
        },
      };
    case "tribe":
      return {
        ...next,
        tribe: {
          base_url: String(config.base_url ?? prev.url),
          days_ahead: Number(config.days_ahead) || 90,
          per_page: Number(config.per_page) || 100,
        },
      };
    case "localist":
      return {
        ...next,
        localist: {
          calendar_url: String(config.calendar_url ?? prev.url),
          days: Number(config.days) || 90,
          pp: Number(config.pp) || 100,
        },
      };
    default:
      return next;
  }
}

interface SelectorField {
  key: keyof SourceSelectors;
  label: string;
  placeholder: string;
  required: boolean;
}

const SELECTOR_FIELDS: SelectorField[] = [
  { key: "container", label: "Container *", placeholder: ".event-card", required: true },
  { key: "title", label: "Title *", placeholder: "h3.title", required: true },
  { key: "start", label: "Start *", placeholder: ".date", required: true },
  { key: "end", label: "End", placeholder: ".end-time", required: false },
  { key: "venue", label: "Venue", placeholder: ".venue", required: false },
  { key: "url", label: "URL", placeholder: "a.event-link", required: false },
  { key: "image", label: "Image", placeholder: "img.poster", required: false },
  { key: "price", label: "Price", placeholder: ".price", required: false },
  { key: "description", label: "Description", placeholder: ".summary", required: false },
  { key: "date_format", label: "Date format", placeholder: "%b %d, %Y %I:%M %p", required: false },
  { key: "start_attribute", label: "Start attribute", placeholder: "data-event-date", required: false },
  { key: "end_attribute", label: "End attribute", placeholder: "data-event-date-end", required: false },
  { key: "url_attribute", label: "URL attribute", placeholder: "href", required: false },
];

function formatLastScrape(source: Source): string {
  if (!source.last_scraped_at) return "—";
  const when = new Date(source.last_scraped_at).toLocaleString();
  if (source.last_scrape_events_found == null) return when;
  const total = source.last_scrape_events_found;
  const newCount = source.last_scrape_events_new ?? 0;
  return `${when} · ${total} found (${newCount} new)`;
}

export function AdminPage() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [tokenInput, setTokenInput] = useState<string>("");

  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [editorOpen, setEditorOpen] = useState<boolean>(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<SourceInput>({ ...EMPTY_SOURCE_INPUT });
  const [saving, setSaving] = useState<boolean>(false);

  const [testResult, setTestResult] = useState<ScrapeTestResult | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [testing, setTesting] = useState<boolean>(false);
  const [detecting, setDetecting] = useState<boolean>(false);
  const [detectMsg, setDetectMsg] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [savedTest, setSavedTest] = useState<{ name: string; result: ScrapeTestResult } | null>(
    null
  );
  const [savedTestOpen, setSavedTestOpen] = useState<boolean>(false);
  const [testingSourceId, setTestingSourceId] = useState<string | null>(null);

  const load = useCallback(async (t: string) => {
    setLoading(true);
    setError(null);
    try {
      setSources(await listSources(t));
    } catch (err) {
      if (err instanceof AdminApiError && (err.status === 401 || err.status === 403)) {
        setError("Invalid or unauthorized admin token.");
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load sources");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (token) void load(token);
  }, [token, load]);

  const saveToken = () => {
    const t = tokenInput.trim();
    if (!t) return;
    localStorage.setItem(TOKEN_KEY, t);
    setToken(t);
    setTokenInput("");
  };

  const clearToken = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setSources([]);
  };

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY_SOURCE_INPUT });
    setTestResult(null);
    setTestError(null);
    setDetectMsg(null);
    setEditorOpen(true);
  };

  const openEdit = (source: Source) => {
    setEditingId(source.id);
    setForm(sourceToInput(source));
    setTestResult(null);
    setTestError(null);
    setDetectMsg(null);
    setEditorOpen(true);
  };

  const closeEditor = () => {
    setEditorOpen(false);
    setEditingId(null);
    setTestResult(null);
    setTestError(null);
    setDetectMsg(null);
  };

  const setSelector = (key: keyof SourceSelectors, value: string) => {
    setForm((prev) => ({
      ...prev,
      selectors: {
        ...prev.selectors,
        [key]: key === "container" || key === "title" || key === "start" || key === "url_attribute"
          ? value
          : value || null,
      },
    }));
  };

  const save = async () => {
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      if (editingId) {
        await updateSource(token, editingId, form);
        setNotice(`Updated "${form.name}"`);
      } else {
        await createSource(token, form);
        setNotice(`Created "${form.name}"`);
      }
      closeEditor();
      await load(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save source");
    } finally {
      setSaving(false);
    }
  };

  const runDryTest = async () => {
    if (!token) return;
    setTesting(true);
    setTestError(null);
    setTestResult(null);
    try {
      setTestResult(await testScrape(token, form));
    } catch (err) {
      setTestError(err instanceof Error ? err.message : "Test failed");
    } finally {
      setTesting(false);
    }
  };

  const runDetect = async () => {
    if (!token || !form.url) return;
    setDetecting(true);
    setDetectMsg(null);
    setTestError(null);
    try {
      const result = await detectSource(token, form.url);
      setForm((prev) => ({
        ...applyDetectedConfig(prev, result.source_type, result.config),
        render_js: result.render_js,
      }));
      setDetectMsg(result.detail);
    } catch (err) {
      setDetectMsg(err instanceof Error ? err.message : "Detection failed");
    } finally {
      setDetecting(false);
    }
  };

  const runSavedTest = async (source: Source) => {
    if (!token || testingSourceId !== null) return;
    setNotice(null);
    setError(null);
    setTestingSourceId(source.id);
    try {
      const result = await testSource(token, source.id);
      setSavedTest({ name: source.name, result });
      setSavedTestOpen(true);
    } catch (err) {
      setSavedTestOpen(false);
      setError(err instanceof Error ? err.message : "Test failed");
    } finally {
      setTestingSourceId(null);
    }
  };

  const removeSource = async (source: Source) => {
    if (!token) return;
    if (!window.confirm(`Delete "${source.name}"? This cannot be undone.`)) return;
    setError(null);
    try {
      await deleteSource(token, source.id);
      setNotice(`Deleted "${source.name}"`);
      await load(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete source");
    }
  };

  const runScrape = async (source: Source) => {
    if (!token) return;
    setNotice(null);
    setError(null);
    try {
      const result = await triggerScrape(token, source.id);
      if (result.status === "success") {
        setNotice(`${source.name}: ${result.message}`);
      } else {
        setError(`${source.name}: ${result.message}`);
      }
      await load(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run scrape");
    }
  };

  if (!token) {
    return (
      <div className="admin">
        <AdminHeader onExit={undefined} />
        <div className="admin-token-gate">
          <h2>Admin access</h2>
          <p>Enter your admin token to manage scrape sources.</p>
          <input
            type="password"
            className="admin-token-input"
            placeholder="ADMIN_API_TOKEN"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") saveToken();
            }}
          />
          <button type="button" className="btn btn-primary" onClick={saveToken}>
            Continue
          </button>
          {error && <p className="admin-error">{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="admin">
      <AdminHeader onExit={clearToken} />

      <div className="admin-toolbar">
        <h2>Scrape sources</h2>
        <button type="button" className="btn btn-primary" onClick={openCreate}>
          + New source
        </button>
      </div>

      {notice && <p className="admin-notice">{notice}</p>}
      {savedTest && (
        <p className="admin-notice">
          "{savedTest.name}": found {savedTest.result.events_found} event(s).{" "}
          <button type="button" className="admin-linkbtn" onClick={() => setSavedTestOpen(true)}>
            Inspect extracted events →
          </button>
        </p>
      )}
      {error && <p className="admin-error">{error}</p>}
      {testingSourceId && (
        <p className="admin-status">
          Testing source… this can take up to 15 seconds for calendar APIs.
        </p>
      )}
      {loading && <p className="admin-status">Loading…</p>}

      {!loading && sources.length === 0 && (
        <p className="admin-status">No sources yet. Create one to start scraping.</p>
      )}

      {sources.length > 0 && (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>URL</th>
              <th>Type</th>
              <th>Enabled</th>
              <th>Every</th>
              <th>Last scrape</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td className="admin-url">
                  <a href={s.url} target="_blank" rel="noreferrer">
                    {s.url}
                  </a>
                </td>
                <td>{SOURCE_TYPE_LABELS[s.source_type] ?? s.source_type}</td>
                <td>{s.enabled ? "Yes" : "No"}</td>
                <td>{s.scrape_frequency_minutes}m</td>
                <td>{formatLastScrape(s)}</td>
                <td className="admin-actions">
                  <IconButton label="Edit" onClick={() => openEdit(s)}>
                    <IconEdit />
                  </IconButton>
                  <IconButton label="Test" loading={testingSourceId === s.id} onClick={() => void runSavedTest(s)}>
                    <IconTest />
                  </IconButton>
                  <IconButton label="Scrape" onClick={() => void runScrape(s)}>
                    <IconScrape />
                  </IconButton>
                  <IconButton
                    label="Delete"
                    variant="danger"
                    onClick={() => void removeSource(s)}
                  >
                    <IconDelete />
                  </IconButton>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editorOpen && (
        <div className="admin-modal-backdrop" onMouseDown={closeEditor}>
          <div className="admin-modal" onMouseDown={(e) => e.stopPropagation()}>
            <h3>{editingId ? "Edit source" : "New source"}</h3>

            <div className="admin-form-grid">
              <label>
                Name
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </label>
              <label className="admin-form-wide">
                Calendar URL
                <div className="admin-url-row">
                  <input
                    value={form.url}
                    placeholder="https://venue.com/calendar"
                    onChange={(e) => setForm({ ...form, url: e.target.value })}
                  />
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void runDetect()}
                    disabled={detecting || !form.url}
                    title="Fetch the URL and auto-detect the platform (e.g. evvnt)"
                  >
                    {detecting ? "Detecting…" : "Detect"}
                  </button>
                </div>
              </label>
              <label>
                Source type
                <select
                  value={form.source_type}
                  onChange={(e) =>
                    setForm({ ...form, source_type: e.target.value as SourceType })
                  }
                >
                  {(Object.keys(SOURCE_TYPE_LABELS) as SourceType[]).map((t) => (
                    <option key={t} value={t}>
                      {SOURCE_TYPE_LABELS[t]}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Region
                <input
                  value={form.region}
                  onChange={(e) => setForm({ ...form, region: e.target.value })}
                />
              </label>
              <label>
                Timezone
                <input
                  value={form.timezone}
                  onChange={(e) => setForm({ ...form, timezone: e.target.value })}
                />
              </label>
              <label>
                Frequency (minutes)
                <input
                  type="number"
                  min={5}
                  value={form.scrape_frequency_minutes}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      scrape_frequency_minutes: Number(e.target.value) || 0,
                    })
                  }
                />
              </label>
              <label className="admin-checkbox">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
                Enabled
              </label>
              <label className="admin-checkbox" title="Use ScrapingBee JS rendering (costs more credits)">
                <input
                  type="checkbox"
                  checked={form.render_js}
                  onChange={(e) => setForm({ ...form, render_js: e.target.checked })}
                />
                Render JS
              </label>
            </div>

            {detectMsg && <p className="admin-notice">{detectMsg}</p>}

            {form.source_type === "html_css" && (
              <>
                <h4>CSS selectors</h4>
                <div className="admin-form-grid">
                  {SELECTOR_FIELDS.map((field) => (
                    <label key={field.key}>
                      {field.label}
                      <input
                        value={form.selectors[field.key] ?? ""}
                        placeholder={field.placeholder}
                        onChange={(e) => setSelector(field.key, e.target.value)}
                      />
                    </label>
                  ))}
                </div>
              </>
            )}

            {form.source_type === "evvnt" && (
              <>
                <h4>evvnt API config</h4>
                <div className="admin-form-grid">
                  <label>
                    Publisher ID *
                    <input
                      type="number"
                      value={form.evvnt.publisher_id || ""}
                      placeholder="4298"
                      onChange={(e) =>
                        setForm({
                          ...form,
                          evvnt: { ...form.evvnt, publisher_id: Number(e.target.value) || 0 },
                        })
                      }
                    />
                  </label>
                  <label>
                    Events per fetch
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={form.evvnt.hits_per_page}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          evvnt: { ...form.evvnt, hits_per_page: Number(e.target.value) || 50 },
                        })
                      }
                    />
                  </label>
                </div>
                <p className="admin-status">
                  Tip: paste the calendar URL above and click “Detect” to fill the publisher ID
                  automatically.
                </p>
              </>
            )}

            {form.source_type === "cityspark" && (
              <>
                <h4>CitySpark config</h4>
                <div className="admin-form-grid">
                  <label className="admin-form-wide">
                    Portal slug *
                    <input
                      value={form.cityspark.portal_slug}
                      placeholder="MarinIndependent"
                      onChange={(e) =>
                        setForm({
                          ...form,
                          cityspark: { ...form.cityspark, portal_slug: e.target.value },
                        })
                      }
                    />
                  </label>
                  <label>
                    Latitude *
                    <input
                      type="number"
                      step="any"
                      value={form.cityspark.latitude || ""}
                      placeholder="37.9735"
                      onChange={(e) =>
                        setForm({
                          ...form,
                          cityspark: {
                            ...form.cityspark,
                            latitude: Number(e.target.value) || 0,
                          },
                        })
                      }
                    />
                  </label>
                  <label>
                    Longitude *
                    <input
                      type="number"
                      step="any"
                      value={form.cityspark.longitude || ""}
                      placeholder="-122.5311"
                      onChange={(e) =>
                        setForm({
                          ...form,
                          cityspark: {
                            ...form.cityspark,
                            longitude: Number(e.target.value) || 0,
                          },
                        })
                      }
                    />
                  </label>
                  <label>
                    Radius (miles)
                    <input
                      type="number"
                      min={1}
                      max={500}
                      value={form.cityspark.distance_miles}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          cityspark: {
                            ...form.cityspark,
                            distance_miles: Number(e.target.value) || 25,
                          },
                        })
                      }
                    />
                  </label>
                  <label>
                    Days ahead
                    <input
                      type="number"
                      min={1}
                      max={90}
                      value={form.cityspark.days_ahead}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          cityspark: {
                            ...form.cityspark,
                            days_ahead: Number(e.target.value) || 30,
                          },
                        })
                      }
                    />
                  </label>
                </div>
                <p className="admin-status">
                  Tip: paste the calendar URL and click “Detect” to extract the portal slug from the
                  CitySpark embed script.
                </p>
              </>
            )}

            {form.source_type === "eventscom" && (
              <>
                <h4>Events.com config</h4>
                <div className="admin-form-grid">
                  <label className="admin-form-wide">
                    Calendar token *
                    <input
                      value={form.eventscom.calendar_token}
                      placeholder="68b81b25-b6de-11eb-abbe-42010a0a0a0b"
                      onChange={(e) =>
                        setForm({
                          ...form,
                          eventscom: { ...form.eventscom, calendar_token: e.target.value },
                        })
                      }
                    />
                  </label>
                  <label>
                    Days ahead
                    <input
                      type="number"
                      min={1}
                      max={370}
                      value={form.eventscom.days_ahead}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          eventscom: {
                            ...form.eventscom,
                            days_ahead: Number(e.target.value) || 30,
                          },
                        })
                      }
                    />
                  </label>
                  <label>
                    Radius (miles)
                    <input
                      type="number"
                      min={1}
                      max={500}
                      value={form.eventscom.radius_miles}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          eventscom: {
                            ...form.eventscom,
                            radius_miles: Number(e.target.value) || 25,
                          },
                        })
                      }
                    />
                  </label>
                </div>
              </>
            )}

            {form.source_type === "tribe" && (
              <>
                <h4>The Events Calendar config</h4>
                <div className="admin-form-grid">
                  <label className="admin-form-wide">
                    Site base URL *
                    <input
                      value={form.tribe.base_url}
                      placeholder="https://demo.theeventscalendar.com"
                      onChange={(e) =>
                        setForm({
                          ...form,
                          tribe: { ...form.tribe, base_url: e.target.value },
                        })
                      }
                    />
                  </label>
                  <label>
                    Days ahead
                    <input
                      type="number"
                      min={1}
                      max={365}
                      value={form.tribe.days_ahead}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          tribe: { ...form.tribe, days_ahead: Number(e.target.value) || 90 },
                        })
                      }
                    />
                  </label>
                  <label>
                    Events per page
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={form.tribe.per_page}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          tribe: { ...form.tribe, per_page: Number(e.target.value) || 100 },
                        })
                      }
                    />
                  </label>
                </div>
              </>
            )}

            {form.source_type === "localist" && (
              <>
                <h4>Localist config</h4>
                <div className="admin-form-grid">
                  <label className="admin-form-wide">
                    Calendar URL *
                    <input
                      value={form.localist.calendar_url}
                      placeholder="https://events.wfu.edu"
                      onChange={(e) =>
                        setForm({
                          ...form,
                          localist: { ...form.localist, calendar_url: e.target.value },
                        })
                      }
                    />
                  </label>
                  <label>
                    Days ahead
                    <input
                      type="number"
                      min={1}
                      max={370}
                      value={form.localist.days}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          localist: { ...form.localist, days: Number(e.target.value) || 90 },
                        })
                      }
                    />
                  </label>
                  <label>
                    Events per page
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={form.localist.pp}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          localist: { ...form.localist, pp: Number(e.target.value) || 100 },
                        })
                      }
                    />
                  </label>
                </div>
              </>
            )}

            <div className="admin-modal-actions">
              <button type="button" className="btn" onClick={() => void runDryTest()} disabled={testing}>
                {testing ? "Testing…" : "Test scrape"}
              </button>
              <div className="admin-modal-actions-right">
                <button type="button" className="btn" onClick={closeEditor}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void save()}
                  disabled={saving}
                >
                  {saving ? "Saving…" : editingId ? "Save changes" : "Create source"}
                </button>
              </div>
            </div>

            {testError && <p className="admin-error">{testError}</p>}
            {testResult && (
              <div className="admin-test-result">
                <p className="admin-notice">
                  Found {testResult.events_found} event(s). Showing up to {testResult.sample.length}:
                </p>
                <table className="admin-table admin-sample">
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Start</th>
                      <th>Venue</th>
                      <th>URL</th>
                      <th>Image</th>
                    </tr>
                  </thead>
                  <tbody>
                    {testResult.sample.map((row, i) => (
                      <tr key={i}>
                        <td>{row.title ?? "—"}</td>
                        <td>{row.start ?? "—"}</td>
                        <td>{row.venue ?? "—"}</td>
                        <td className="admin-url">
                          {row.url ? (
                            <a href={row.url} target="_blank" rel="noreferrer">
                              link
                            </a>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>{row.image ? "✓" : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {savedTestOpen && savedTest && (
        <div className="admin-modal-backdrop" onMouseDown={() => setSavedTestOpen(false)}>
          <div className="admin-modal" onMouseDown={(e) => e.stopPropagation()}>
            <div className="admin-modal-head">
              <h3>{savedTest.name} — extracted events</h3>
              <button type="button" className="btn" onClick={() => setSavedTestOpen(false)}>
                Close
              </button>
            </div>
            <p className="admin-status">
              Found {savedTest.result.events_found} event(s); showing{" "}
              {savedTest.result.sample.length} as JSON.
            </p>
            <pre className="admin-json">{JSON.stringify(savedTest.result.sample, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

function AdminHeader({ onExit }: { onExit: (() => void) | undefined }) {
  return (
    <header className="admin-header">
      <a className="admin-brand" href="#/">
        <img src={logoUrl} alt="Joinable" />
        <span>Admin</span>
      </a>
      <div className="admin-header-actions">
        <a className="btn" href="#/">
          ← Back to app
        </a>
        {onExit && (
          <button type="button" className="btn" onClick={onExit}>
            Sign out
          </button>
        )}
      </div>
    </header>
  );
}

interface IconButtonProps {
  label: string;
  onClick: () => void;
  variant?: "default" | "danger";
  loading?: boolean;
  disabled?: boolean;
}

function IconButton({
  label,
  onClick,
  variant = "default",
  loading = false,
  disabled = false,
  children,
}: IconButtonProps & { children: ReactNode }) {
  return (
    <button
      type="button"
      className={`btn btn-icon${variant === "danger" ? " btn-danger" : ""}${loading ? " btn-icon-loading" : ""}`}
      onClick={onClick}
      disabled={disabled || loading}
      aria-label={label}
      title={label}
      aria-busy={loading}
    >
      {loading ? <IconSpinner /> : children}
    </button>
  );
}

function IconEdit() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

function IconTest() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  );
}

function IconScrape() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M12 3v12" />
      <path d="m8 11 4 4 4-4" />
      <path d="M4 14v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />
    </svg>
  );
}

function IconDelete() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
    </svg>
  );
}

function IconSpinner() {
  return (
    <svg
      className="btn-spinner"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <path d="M12 2v4" />
      <path d="M12 18v4" />
      <path d="m4.93 4.93 2.83 2.83" />
      <path d="m16.24 16.24 2.83 2.83" />
      <path d="M2 12h4" />
      <path d="M18 12h4" />
      <path d="m4.93 19.07 2.83-2.83" />
      <path d="m16.24 7.76 2.83-2.83" />
    </svg>
  );
}
