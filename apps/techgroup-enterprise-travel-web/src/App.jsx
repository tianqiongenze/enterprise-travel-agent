import { useMutation } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
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

function ItemCard({ item }) {
  const name = String(item?.name ?? item?.day ?? '');
  const price = item?.price;
  const score = item?.score ?? item?.rating;
  const reason = item?.reason ?? '';
  return (
    <div className="item-card">
      <div className="item-main">
        <span className="item-name">{name}</span>
        {reason && <span className="item-reason">{reason}</span>}
      </div>
      <div className="item-meta">
        {price !== undefined && price !== null && price !== '' && (
          <span className="item-price">¥{Number(price).toLocaleString('zh-CN')}</span>
        )}
        {score !== undefined && score !== null && score !== '' && (
          <span className="item-score">★ {Number(score).toFixed(1)}</span>
        )}
      </div>
    </div>
  );
}

function renderListCard(title, items) {
  return (
    <div className="result-card">
      <h3>{title}</h3>
      {items.length === 0 && <p className="empty">暂无数据</p>}
      {items.map((item, index) => (
        <ItemCard key={`${title}-${index}`} item={item} />
      ))}
    </div>
  );
}

function ResultSkeleton() {
  return (
    <div className="skeleton" role="status" aria-label="加载中">
      {[0, 1, 2].map((i) => (
        <div key={i} className="skeleton-line" style={{ width: `${88 - i * 18}%` }} />
      ))}
      <span className="visually-hidden">正在获取推荐结果…</span>
    </div>
  );
}

export default function App() {
  const navigate = useNavigate();
  const [form, setForm] = useState(initialForm);
  const [jsonMode, setJsonMode] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem('travel-theme') || 'light');

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('travel-theme', theme);
  }, [theme]);

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
            aria-label={theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'}
            onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
          >
            {theme === 'dark' ? '浅色' : '深色'}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setToken('');
              navigate('/login', { replace: true });
            }}
          >
            退出登录
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

          {mutation.isPending && <ResultSkeleton />}

          {mutation.isError && (
            <div role="alert" className="error" style={{ padding: 12, borderRadius: 8 }}>
              {String(mutation.error?.message || mutation.error)}
            </div>
          )}

          {hasData && jsonMode && <pre>{JSON.stringify(mutation.data, null, 2)}</pre>}

          {hasData && !jsonMode && (
            <div className="cards" aria-live="polite">
              {renderListCard('酒店推荐', hotels)}
              {renderListCard('交通推荐', transports)}
              {renderListCard('行程安排', itinerary)}
            </div>
          )}

          {!hasData && !mutation.isError && <p>提交表单后即可查看推荐结果。</p>}
        </section>
      </main>
    </div>
  );
}
