"""A plot is a declared record, not a Matplotlib figure."""

# *** imports

# ** app
from .domain.plot import (
    Mark,
    MatrixCell,
    Plot,
    PlotMatrix,
    Series,
)
from .interfaces.plot import (
    MATRIX_ALREADY_KEPT_ID,
    MATRIX_NOT_KEPT_ID,
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
    MatrixService,
    PlotService,
    RendererService,
)
from .mappers.plot import (
    MatrixCellAggregate,
    PlotAggregate,
    PlotMatrixAggregate,
    SeriesAggregate,
)
from .events.plot import (
    CreateMatrix,
    CreatePlot,
    GetMatrix,
    GetPlot,
    ListMatrices,
    ListPlots,
    MatrixEvent,
    PlotEvent,
    RemoveMatrix,
    RemovePlot,
    UpdateMatrix,
    UpdatePlot,
)

# *** exports

__all__ = [
    'MATRIX_ALREADY_KEPT_ID',
    'MATRIX_NOT_KEPT_ID',
    'PLOT_ALREADY_KEPT_ID',
    'PLOT_NOT_KEPT_ID',
    'CreateMatrix',
    'CreatePlot',
    'GetMatrix',
    'GetPlot',
    'ListMatrices',
    'ListPlots',
    'Mark',
    'MatrixCell',
    'MatrixCellAggregate',
    'MatrixEvent',
    'MatrixService',
    'Plot',
    'PlotAggregate',
    'PlotEvent',
    'PlotMatrix',
    'PlotMatrixAggregate',
    'PlotService',
    'RemoveMatrix',
    'RemovePlot',
    'RendererService',
    'Series',
    'SeriesAggregate',
    'UpdateMatrix',
    'UpdatePlot',
]
