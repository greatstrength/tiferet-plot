"""A plot is a declared record, not a Matplotlib figure."""

# *** imports

# ** app
from .domain.plot import (
    Mark,
    Plot,
    Series,
)
from .interfaces.plot import (
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
    PlotService,
    RendererService,
)
from .mappers.plot import (
    PlotAggregate,
    SeriesAggregate,
)
from .events.plot import (
    CreatePlot,
    GetPlot,
    ListPlots,
    PlotEvent,
    RemovePlot,
    UpdatePlot,
)

# *** exports

__all__ = [
    'PLOT_ALREADY_KEPT_ID',
    'PLOT_NOT_KEPT_ID',
    'CreatePlot',
    'GetPlot',
    'ListPlots',
    'Mark',
    'Plot',
    'PlotAggregate',
    'PlotEvent',
    'PlotService',
    'RemovePlot',
    'RendererService',
    'Series',
    'SeriesAggregate',
    'UpdatePlot',
]
