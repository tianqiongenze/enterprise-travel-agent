# Multi-Region Fault Drill Evidence

- pass: False
- scenarioCount: 3
- passedScenarios: 2
- recoveryRtoMinutes: 10
- recoveryRpoSeconds: 30
- eventConsumerLagSeconds: 0.001002
- eventConsumerDlqTotal: 0.0
- evidenceSource: staging-drill
- runId: closure-sprint-drill
- environment: staging

## Scenarios

- region-outage-failover: PASS
- pulsar-lag-storm: PASS
- redis-cluster-failover: FAIL
