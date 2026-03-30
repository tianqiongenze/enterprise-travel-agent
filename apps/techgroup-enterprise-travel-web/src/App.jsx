import { useMutation } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  readSessionDefaults,
  recommendTravel,
  saveAuthToken,
  saveSessionDefaults,
} from './api';
import { setToken } from './auth';

const allTools = ['search_hotels', 'search_transports', 'search_attractions'];

function newConversationId() {
  return `conv-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function initialForm() {
  const stored = readSessionDefaults();
  if (stored) {
    return {
      ...stored,
      allowedTools: Array.isArray(stored.allowedTools) ? stored.allowedTools : [...allTools],
    };
  }
  return {
    tenantId: 'tenant-demo',
    userId: 'user-web',
    policyId: 'policy-default',
    conversationId: newConversationId(),
    idempotencyKey: `idem-${Date.now()}`,
    city: '北京',
    days: 3,
    budget: 3000,
    travelers: 2,
    preferences: 'family,budget',
    maxAgentSteps: 10,
    maxToolCalls: 10,
    allowedTools: [...allTools],
    authToken: '',
  };
}

function renderListCard(title, items) {
  return (
    <div className="result-card">
      <h3>{title}</h3>
      {items.length === 0 && <p>No records</p>}
      {items.map((item, index) => (
        <div key={`${title}-${index}`} className="result-row">
          {Object.entries(item || {}).map(([key, value]) => (
            <div key={`${title}-${index}-${key}`} className="result-item">
              <span className="result-key">{key}</span>
              <span className="result-value">{String(value)}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const navigate = useNavigate();
  const [form, setForm] = useState(initialForm);
  const [jsonMode, setJsonMode] = useState(false);

  const mutation = useMutation({
    mutationFn: recommendTravel,
  });

  const payload = useMemo(() => {
    const preferences = form.preferences
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    return {
      ...form,
      days: Number(form.days),
      budget: Number(form.budget),
      travelers: Number(form.travelers),
      maxAgentSteps: Number(form.maxAgentSteps),
      maxToolCalls: Number(form.maxToolCalls),
      preferences,
      authToken: undefined,
    };
  }, [form]);

  const onSubmit = (event) => {
    event.preventDefault();
    saveAuthToken(form.authToken);
    saveSessionDefaults({ ...form, authToken: '' });
    mutation.mutate(payload);
  };

  const onToolToggle = (tool) => {
    setForm((prev) => {
      const exists = prev.allowedTools.includes(tool);
      return {
        ...prev,
        allowedTools: exists
          ? prev.allowedTools.filter((item) => item !== tool)
          : [...prev.allowedTools, tool],
      };
    });
  };

  const hasData = mutation.isSuccess && mutation.data;
  const hotels = hasData ? mutation.data.hotelOptions || [] : [];
  const transports = hasData ? mutation.data.transportOptions || [] : [];
  const itinerary = hasData ? mutation.data.itinerary || [] : [];

  return (
    <div className="page">
      <header>
        <h1>Enterprise Travel Agent Web</h1>
        <p>Production-grade client with retries, session persistence, and structured result cards.</p>
        <div className="header-actions">
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setToken('');
              navigate('/login', { replace: true });
            }}
          >
            Sign Out
          </button>
        </div>
      </header>

      <main className="layout">
        <section className="panel">
          <h2>Request Form</h2>
          <form onSubmit={onSubmit} className="form-grid">
            {[
              ['tenantId', 'Tenant ID'],
              ['userId', 'User ID'],
              ['policyId', 'Policy ID'],
              ['conversationId', 'Conversation ID'],
              ['idempotencyKey', 'Idempotency Key'],
              ['city', 'City'],
            ].map(([key, label]) => (
              <label key={key}>
                <span>{label}</span>
                <input
                  value={form[key]}
                  onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))}
                  required
                />
              </label>
            ))}

            <label>
              <span>Auth Token (optional)</span>
              <input
                value={form.authToken}
                onChange={(e) => setForm((prev) => ({ ...prev, authToken: e.target.value }))}
                placeholder="Bearer token without prefix"
              />
            </label>

            <label>
              <span>Days</span>
              <input type="number" min="1" value={form.days} onChange={(e) => setForm((prev) => ({ ...prev, days: e.target.value }))} required />
            </label>
            <label>
              <span>Budget</span>
              <input type="number" min="1" value={form.budget} onChange={(e) => setForm((prev) => ({ ...prev, budget: e.target.value }))} required />
            </label>
            <label>
              <span>Travelers</span>
              <input type="number" min="1" value={form.travelers} onChange={(e) => setForm((prev) => ({ ...prev, travelers: e.target.value }))} required />
            </label>
            <label>
              <span>Preferences (comma-separated)</span>
              <input value={form.preferences} onChange={(e) => setForm((prev) => ({ ...prev, preferences: e.target.value }))} />
            </label>
            <label>
              <span>Max Agent Steps</span>
              <input type="number" min="1" value={form.maxAgentSteps} onChange={(e) => setForm((prev) => ({ ...prev, maxAgentSteps: e.target.value }))} required />
            </label>
            <label>
              <span>Max Tool Calls</span>
              <input type="number" min="1" value={form.maxToolCalls} onChange={(e) => setForm((prev) => ({ ...prev, maxToolCalls: e.target.value }))} required />
            </label>

            <div className="tools">
              <span>Allowed Tools</span>
              <div className="tool-grid">
                {allTools.map((tool) => (
                  <label key={tool} className="check">
                    <input
                      type="checkbox"
                      checked={form.allowedTools.includes(tool)}
                      onChange={() => onToolToggle(tool)}
                    />
                    {tool}
                  </label>
                ))}
              </div>
            </div>

            <button type="submit" disabled={mutation.isPending || form.allowedTools.length === 0}>
              {mutation.isPending ? 'Requesting...' : 'Get Recommendation'}
            </button>
          </form>
        </section>

        <section className="panel">
          <div className="result-header">
            <h2>Response</h2>
            <button type="button" className="secondary" onClick={() => setJsonMode((v) => !v)}>
              {jsonMode ? 'Show Cards' : 'Show Raw JSON'}
            </button>
          </div>

          {mutation.isError && <pre className="error">{String(mutation.error?.message || mutation.error)}</pre>}

          {hasData && jsonMode && <pre>{JSON.stringify(mutation.data, null, 2)}</pre>}

          {hasData && !jsonMode && (
            <div className="cards">
              {renderListCard('Hotel Options', hotels)}
              {renderListCard('Transport Options', transports)}
              {renderListCard('Itinerary', itinerary)}
            </div>
          )}

          {!hasData && !mutation.isError && <p>Submit the form to view recommendation response payload.</p>}
        </section>
      </main>
    </div>
  );
}
