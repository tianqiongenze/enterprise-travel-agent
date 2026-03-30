# Distributed Load Test Plan (k6 + Locust)

## Goal

Validate system behavior under distributed high-concurrency scenarios beyond local single-node limits.

## Scenario matrix

1. Connection-heavy scenario (gateway realtime focus)
2. Active AI request scenario (runtime/tool fan-out focus)
3. Reconnect storm scenario
4. Partial dependency outage scenario

## k6 script template

Use k6 for HTTP-focused pressure:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 1000 },
    { duration: '5m', target: 5000 },
    { duration: '2m', target: 0 },
  ],
};

export default function () {
  const payload = JSON.stringify({
    city: '北京',
    days: 3,
    budget: 3200,
    travelers: 2,
    preferences: ['family', 'budget']
  });
  const res = http.post('http://gateway/api/v1/travel/recommend', payload, { headers: { 'Content-Type': 'application/json' } });
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(1);
}
```

## Locust distributed template

- Master node coordinates target RPS
- 10~100 worker nodes produce distributed load
- Capture p95/p99, error rate, saturation signals

## Acceptance thresholds (example)

- Error rate < 0.5%
- p95 < 800ms
- p99 < 1500ms
- No sustained retry storm or cascading failure
