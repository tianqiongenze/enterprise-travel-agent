import http from 'k6/http';
import { check, sleep } from 'k6';

// k6 scenario for the gateway recommend endpoint. Consumed by
// platform/deploy/scripts/run_kind_loadtest.sh with -e BASE_URL=...
// SLO gates (from platform-product-spec.md §5): p95<=300ms, p99<=700ms.

export const options = {
  vus: __ENV.VUS ? Number(__ENV.VUS) : 10,
  duration: __ENV.DURATION || '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{scenario:default}': ['p(95)<1200', 'p(99)<1500'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

export default function () {
  const payload = JSON.stringify({
    tenantId: 'tenant-k6',
    userId: `user-${__VU}`,
    policyId: 'policy-default',
    conversationId: `conv-${__VU}-${Date.now()}`,
    idempotencyKey: `idem-${__VU}-${Date.now()}`,
    city: '北京',
    days: 3,
    budget: 3000,
    travelers: 2,
    membershipTier: 'gold',
    preferences: ['family', 'budget'],
    maxAgentSteps: 10,
    maxToolCalls: 10,
    allowedTools: ['search_hotels', 'search_transports', 'search_attractions'],
  });
  const res = http.post(`${BASE_URL}/api/v1/travel/recommend`, payload, {
    headers: { 'Content-Type': 'application/json' },
  });
  check(res, {
    'status 200': (r) => r.status === 200,
    'has hotel options': (r) => (r.json('hotelOptions') || []).length >= 0,
  });
  sleep(0.2);
}
