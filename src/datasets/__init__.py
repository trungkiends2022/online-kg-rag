"""Dataset adapters for running the pipeline on public QA benchmarks."""

from src.datasets.schema import DatasetExample
from src.datasets.hybridqa import load_hybridqa
from src.datasets.finqa import load_finqa
from src.datasets.hitab import load_hitab

__all__ = ["DatasetExample", "load_hybridqa", "load_finqa", "load_hitab"]
