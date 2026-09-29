"""A plot is a declared record, not a Matplotlib figure."""

# *** exports

# ** app
# Wrap runtime imports in a try/except so that build tools can import
# __version__ without requiring the full dependency tree to be installed.
try:
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
    from .contexts.plot import PlotterSessionContext
    from .blueprints.plot import create_plotter_session
except Exception as e:
    import os, sys
    if not os.getenv('TIFERET_PLOT_SILENT_IMPORTS'):
        print(f'Warning: Failed to import tiferet_plot modules: {e}', file=sys.stderr)

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
    'PlotterSessionContext',
    'RemoveMatrix',
    'RemovePlot',
    'RendererService',
    'Series',
    'SeriesAggregate',
    'UpdateMatrix',
    'UpdatePlot',
    'create_plotter_session',
]

# *** version

__version__ = '1.0.0b1'
