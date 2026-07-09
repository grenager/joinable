import { useCallback, useEffect, useState } from "react";
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
  EMPTY_EVVNT_CONFIG,
  EMPTY_SELECTORS,
  EMPTY_SOURCE_INPUT,
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
};

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
  const isEvvnt = source.source_type === "evvnt";
  return {
    name: source.name,
    url: source.url,
    source_type: source.source_type,
    region: source.region,
    timezone: source.timezone,
    enabled: source.enabled,
    scrape_frequency_minutes: source.scrape_frequency_minutes,
    default_category: source.default_category,
    render_js: source.render_js,
    selectors: isEvvnt ? { ...EMPTY_SELECTORS } : configToSelectors(source.config),
    evvnt: isEvvnt
      ? {
          publisher_id: Number(source.config.publisher_id) || 0,
          hits_per_page: Number(source.config.hits_per_page) || 50,
        }
      : { ...EMPTY_EVVNT_CONFIG },
  };
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
  { key: "url_attribute", label: "URL attribute", placeholder: "href", required: false },
];

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
    setForm({
      ...EMPTY_SOURCE_INPUT,
      selectors: { ...EMPTY_SELECTORS },
      evvnt: { ...EMPTY_EVVNT_CONFIG },
    });
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
        ...prev,
        source_type: result.source_type,
        render_js: result.render_js,
        selectors:
          result.source_type === "evvnt"
            ? prev.selectors
            : configToSelectors(result.config),
        evvnt:
          result.source_type === "evvnt"
            ? {
                publisher_id: Number(result.config.publisher_id) || 0,
                hits_per_page: Number(result.config.hits_per_page) || 50,
              }
            : prev.evvnt,
      }));
      setDetectMsg(result.detail);
    } catch (err) {
      setDetectMsg(err instanceof Error ? err.message : "Detection failed");
    } finally {
      setDetecting(false);
    }
  };

  const runSavedTest = async (source: Source) => {
    if (!token) return;
    setNotice(null);
    setError(null);
    setSavedTest(null);
    try {
      const result = await testSource(token, source.id);
      setSavedTest({ name: source.name, result });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
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
      setNotice(`Scrape ${result.status} for "${source.name}".`);
    } catch (err) {
      setError(
        err instanceof Error
          ? `Could not queue scrape (worker/Redis may be offline): ${err.message}`
          : "Failed to queue scrape"
      );
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
              <th>Category</th>
              <th>Enabled</th>
              <th>Every</th>
              <th>Last scraped</th>
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
                <td>{s.default_category}</td>
                <td>{s.enabled ? "Yes" : "No"}</td>
                <td>{s.scrape_frequency_minutes}m</td>
                <td>{s.last_scraped_at ? new Date(s.last_scraped_at).toLocaleString() : "—"}</td>
                <td className="admin-actions">
                  <button type="button" className="btn" onClick={() => openEdit(s)}>
                    Edit
                  </button>
                  <button type="button" className="btn" onClick={() => void runSavedTest(s)}>
                    Test
                  </button>
                  <button type="button" className="btn" onClick={() => void runScrape(s)}>
                    Scrape
                  </button>
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={() => void removeSource(s)}
                  >
                    Delete
                  </button>
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
              <label>
                Default category
                <input
                  value={form.default_category}
                  onChange={(e) => setForm({ ...form, default_category: e.target.value })}
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
