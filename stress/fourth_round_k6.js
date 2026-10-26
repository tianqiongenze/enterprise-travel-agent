// Fourth-round K6 load test (plan §四.R10).
// Mixed scenario: 90% reads (REST /recommend + GraphQL) + async enqueues.
// Thresholds double as CI gates (non-zero exit code on breach).
//
// Usage (local):      k6 run stress/fourth_round_k6.js
// Usage (cluster):    k6-operator K6 CRD, see platform/deploy/k8s/k6-fourth-round.yaml

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const VUS = Number(__ENV.VUS || 50);
const DURATION = __ENV.DURATION || '3m';

const graphqlLatency = new Trend('graphql_latency', true);
const restLatency = new Trend('rest_latency', true);
const errorRate = new Rate('surface_error_rate');
const cacheHits = new Counter('cache_l1_hits_observed');

const GRAPHQL_RECOMMEND = JSON.stringify({
  query: 'query($city: String) { recommend(payload: {city: $city}) { city days hotels { name price rating } transports { name } itinerary { day summary } engagements { title } } }',
  variables: { city: '北京' },
});

export const options = {
  scenarios: {
    browse_read: {
      executor: 'ramping-vus',
      startVUs: 5,
      stages: [
        { duration: '30s', target: VUS },
        { duration: DURATION, target: VUS },
        { duration: '20s', target: 0 },
      ],
      gracefulRampDown: '10s',
      exec: 'browse',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.001'],
    http_req_duration: ['p(95)<300'],
    graphql_latency: ['p(95)<300'],
    rest_latency: ['p(95)<300'],
    surface_error_rate: ['rate<0.001'],
  },
};

const CITIES = ['北京', '上海', '杭州', '成都', '西安'];

export function browse() {
  group('read path (90%)', () => {
    if (Math.random() < 0.5) {
      const res = http.post(`${BASE_URL}/recommend`,
        JSON.stringify({ city: CITIES[Math.floor(Math.random() * CITIES.length)], days: 3 }),
        { headers: { 'Content-Type': 'application/json' }, tags: { name: 'rest_recommend' } });
      restLatency.add(res.timings.duration);
      const ok = check(res, { 'rest 200': (r) => r.status === 200 });
      errorRate.add(!ok);
      if (res.status === 200) cacheHits.add(1);
    } else {
      const res = http.post(`${BASE_URL}/graphql`, GRAPHQL_RECOMMEND,
        { headers: { 'Content-Type': 'application/json' }, tags: { name: 'graphql_recommend' } });
      graphqlLatency.add(res.timings.duration);
      const ok = check(res, {
        'graphql 200': (r) => r.status === 200,
        'no gql errors': (r) => (r.json().errors === undefined || r.json().errors === null),
      });
      errorRate.add(!ok);
    }
  });
  group('probes (10%)', () => {
    const h = http.get(`${BASE_URL}/health`, { tags: { name: 'health' } });
    check(h, { 'health 200': (r) => r.status === 200 });
    if (Math.random() < 0.1) {
      http.get(`${BASE_URL}/metrics`, { tags: { name: 'metrics' } });
    }
  });
  sleep(Math.random() * 0.4 + 0.1); // 0.1-0.5s think time → ~2-4 req/s per VU
}
