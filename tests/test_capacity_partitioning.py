"""Capacity partitioning checks."""

import unittest

from stress.capacity_cost_model import CapacityInput, estimate


class CapacityPartitioningTestCase(unittest.TestCase):
    def test_partition_fields_present(self) -> None:
        result = estimate(
            CapacityInput(
                peak_connected=1_000_000,
                active_ratio=0.1,
                gateway_conn_per_pod=12000,
                runtime_active_per_pod=100,
                safety_factor=1.8,
                hours_per_month=730,
                gateway_pod_cost_per_hour=0.08,
                runtime_pod_cost_per_hour=0.12,
                pulsar_cluster_cost_per_month=3500.0,
                vector_cluster_cost_per_month=4200.0,
            )
        )
        self.assertGreaterEqual(result.recommended_partitions, 3)
        self.assertGreater(result.runtime_per_partition, 0)


if __name__ == "__main__":
    unittest.main()
