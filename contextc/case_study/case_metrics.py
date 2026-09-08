"""M11 metric boundary: reuse M6 math unchanged."""

from contextc.benchmark.metrics import calculate_raw_metrics
from contextc.benchmark.models import RawMetrics

calculate_case_metrics = calculate_raw_metrics

__all__ = ["RawMetrics", "calculate_case_metrics"]
