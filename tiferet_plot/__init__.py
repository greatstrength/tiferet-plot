"""A plot is a declared record, not a Matplotlib figure."""

# *** imports

# ** app
from .domain.plot import (
    Mark,
    Plot,
    Series,
)
from .mappers.plot import (
    PlotAggregate,
    SeriesAggregate,
)

# *** exports

__all__ = [
    'Mark',
    'Plot',
    'PlotAggregate',
    'Series',
    'SeriesAggregate',
]
