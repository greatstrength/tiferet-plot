"""Tests for the plotter session."""

# *** imports

# ** core
import ast
import inspect
from pathlib import Path

# ** infra
import pytest

# ** app
from tiferet import TiferetAPIError
from tiferet.contexts.app import AppSession, AppSessionContext
from tiferet.contexts.core import BaseContext
from tiferet_plot.contexts.plot import (
    CREATE_MATRIX_EVENT_ID,
    CREATE_PLOT_EVENT_ID,
    PLOT_FLAG,
    RENDERER_SERVICE_ID,
    PlotterSessionContext,
    create_handler,
    show_handler,
)
from tiferet_plot.domain.plot import (
    Mark,
    MatrixCell,
    Plot,
    PlotMatrix,
    Series,
)
import tiferet_plot.contexts.plot as context_module

# *** classes

# ** class: recording_event
class RecordingEvent:
    '''
    An event stand-in that records the call and returns a sentinel.
    '''

    # * init
    def __init__(self, result) -> None:
        '''
        Remember the value execute should return.

        :param result: The record the event returns.
        :type result: Any
        '''

        # The call proves which fields the handler passed.
        self.result = result
        self.args = None
        self.kwargs = None

    # * method: execute
    def execute(self, *args, **kwargs):
        '''
        Record the call and return the sentinel.

        :param args: Positional event arguments.
        :type args: tuple
        :param kwargs: Keyword event arguments.
        :type kwargs: dict
        :return: The sentinel record.
        :rtype: Any
        '''

        # Keep the arguments. Do not keep a store.
        self.args = args
        self.kwargs = kwargs
        return self.result

# ** class: recording_renderer
class RecordingRenderer:
    '''
    A renderer stand-in that records which picture method was called.
    '''

    # * init
    def __init__(self) -> None:
        '''
        Start with no picture calls.
        '''

        # The method name proves plot and matrix do not share a drawing call.
        self.calls = []

    # * method: render
    def render(self, plot) -> bytes:
        '''
        Record a plot picture call.

        :param plot: The plot record.
        :type plot: Any
        :return: Sentinel picture bytes.
        :rtype: bytes
        '''

        # Return bytes. Do not write a file.
        self.calls.append(('render', plot))
        return b'plot-png'

    # * method: render_matrix
    def render_matrix(self, matrix) -> bytes:
        '''
        Record a matrix picture call.

        :param matrix: The matrix record.
        :type matrix: Any
        :return: Sentinel picture bytes.
        :rtype: bytes
        '''

        # Return bytes. Do not write a file.
        self.calls.append(('render_matrix', matrix))
        return b'matrix-png'

# *** functions

# ** function: line_plot
def line_plot(kind='line', plot_id='sales_by_region'):
    '''
    Build a finished plot record.

    :param kind: The chart kind.
    :type kind: str
    :param plot_id: The plot id.
    :type plot_id: str
    :return: A declared plot.
    :rtype: Plot
    '''

    # The caller of this session passes a finished record.
    marks = [
        Mark(role='x', values=(1, 2)),
        Mark(role='y', values=(3, 4)),
    ]
    if kind == 'bar':
        marks = [
            Mark(role='category', values=('North', 'South')),
            Mark(role='height', values=(10, 12)),
        ]
    return Plot(
        id=plot_id,
        name='Sales by Region',
        kind=kind,
        description='A claim.',
        series=[
            Series(
                id='revenue',
                name='Revenue',
                marks=marks,
            ),
        ],
    )

# ** function: matrix
def matrix():
    '''
    Build a finished matrix record.

    :return: A declared matrix.
    :rtype: PlotMatrix
    '''

    # The cell plot id is already set. This session does not fill it.
    return PlotMatrix(
        id='sales_by_region',
        name='Sales by Region',
        rows=2,
        cols=2,
        cells=[
            MatrixCell(
                row=0,
                col=1,
                plot=line_plot(plot_id='revenue_plot'),
            ),
        ],
    )

# ** function: bound
def bound(create=None, show=None):
    '''
    Bind a plotter session without the blueprint.

    :param create: The create handler, or None when unwired.
    :type create: Callable | None
    :param show: The show handler, or None when unwired.
    :type show: Callable | None
    :return: A session bound to an app session.
    :rtype: PlotterSessionContext
    '''

    # The five framework handlers are absent, so an unwired one still fails.
    return PlotterSessionContext.from_domain(
        AppSession(
            id='plotter',
            name='Plotter',
        ),
        get_dependency=lambda *args, **kwargs: None,
        create_handler=create,
        show_handler=show,
    )

# ** function: resolver
def resolver(mapping):
    '''
    Build a get_dependency stand-in that records the flag.

    :param mapping: Service id to instance.
    :type mapping: dict
    :return: The resolver and the recorded calls.
    :rtype: tuple
    '''

    # The flag on the call is the proof. The instance is the dependency.
    calls = []

    def get_dependency(service_id, *flags):
        '''
        Record the resolution and return the mapped instance.

        :param service_id: The service id.
        :type service_id: str
        :param flags: The DI flags.
        :type flags: tuple
        :return: The mapped instance.
        :rtype: Any
        '''

        # Record the flag. Do not fall back to another namespace.
        calls.append((service_id, flags))
        return mapping[service_id]

    # Return the resolver and the call log.
    return get_dependency, calls

# ** function: imported_modules
def imported_modules(path: Path) -> list:
    '''
    List modules imported by a source file.

    :param path: The source file.
    :type path: Path
    :return: Imported module names.
    :rtype: list
    '''

    # Parse the source rather than trusting a substring search.
    names = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names

# *** tests

# ** test: context_extends_the_hub_and_omits_domain_type
def test_context_extends_the_hub_and_omits_domain_type():
    '''
    The plotter session extends the hub and does not steal its registry entry.
    '''

    # The class lives here, extends the hub, and does not declare domain_type.
    assert PlotterSessionContext.__module__ == 'tiferet_plot.contexts.plot'
    assert issubclass(PlotterSessionContext, AppSessionContext)
    assert 'domain_type' not in PlotterSessionContext.__dict__
    assert BaseContext.for_domain(AppSession) is AppSessionContext

    # Create and show are handlers. Fluent methods are not this session.
    params = inspect.signature(PlotterSessionContext.__init__).parameters
    for name in (
        'build_logger_handler',
        'execute_feature_handler',
        'create_request_handler',
        'raise_error_handler',
        'response_handler',
        'create_handler',
        'show_handler',
    ):
        assert name in params
    assert not hasattr(PlotterSessionContext, 'add_series')
    assert not hasattr(PlotterSessionContext, 'append')
    assert not hasattr(PlotterSessionContext, 'show_line')
    assert not hasattr(PlotterSessionContext, 'show_bar')

# ** test: unwired_handlers_fail
def test_unwired_handlers_fail():
    '''
    An unwired create or show handler fails. A framework handler still fails too.
    '''

    # Create and show fail the same way as an unwired hub handler.
    session = bound()
    plot = line_plot()
    with pytest.raises(TiferetAPIError) as caught:
        session.create(plot)
    assert 'create_handler' in caught.value.message
    assert 'plotter' in caught.value.message

    with pytest.raises(TiferetAPIError) as caught:
        session.show(plot)
    assert 'show_handler' in caught.value.message

    # The five framework handlers are still required.
    with pytest.raises(TiferetAPIError) as caught:
        session.build_logger()
    assert 'build_logger_handler' in caught.value.message

# ** test: create_calls_the_plot_or_matrix_event
def test_create_calls_the_plot_or_matrix_event():
    '''
    Create of a plot calls the plot event. Create of a matrix calls the matrix event.
    '''

    # The events return sentinels. The session does not build the record itself.
    plot = line_plot()
    grid = matrix()
    plot_event = RecordingEvent('kept-plot')
    matrix_event = RecordingEvent('kept-matrix')
    get_dependency, calls = resolver({
        CREATE_PLOT_EVENT_ID: plot_event,
        CREATE_MATRIX_EVENT_ID: matrix_event,
    })
    session = bound(create=create_handler(get_dependency))

    # A plot resolves on the plot flag and returns the event's record.
    assert session.create(plot) == 'kept-plot'
    assert calls == [(CREATE_PLOT_EVENT_ID, (PLOT_FLAG,))]
    assert plot_event.kwargs['name'] == plot.name
    assert plot_event.kwargs['kind'] == plot.kind
    assert plot_event.kwargs['series'] == plot.series
    assert plot_event.kwargs['id'] == plot.id
    assert plot_event.kwargs['description'] == plot.description
    assert matrix_event.kwargs is None

    # A matrix uses the other event. A bar would not.
    assert session.create(grid) == 'kept-matrix'
    assert calls[1] == (CREATE_MATRIX_EVENT_ID, (PLOT_FLAG,))
    assert matrix_event.kwargs['rows'] == grid.rows
    assert matrix_event.kwargs['cols'] == grid.cols
    assert matrix_event.kwargs['cells'] == grid.cells
    assert matrix_event.kwargs['id'] == grid.id

# ** test: show_calls_render_or_render_matrix_on_the_plot_flag
def test_show_calls_render_or_render_matrix_on_the_plot_flag():
    '''
    Show of a plot calls render. Show of a matrix calls render_matrix.
    '''

    # One renderer. The flag is plot, not the framework flag.
    plot = line_plot()
    bar = line_plot(kind='bar', plot_id='sales_bar')
    grid = matrix()
    renderer = RecordingRenderer()
    get_dependency, calls = resolver({
        RENDERER_SERVICE_ID: renderer,
    })
    session = bound(show=show_handler(get_dependency))

    # A line and a bar use the same show, and the same render call.
    assert session.show(plot) == b'plot-png'
    assert session.show(bar) == b'plot-png'
    assert renderer.calls == [('render', plot), ('render', bar)]
    assert calls == [
        (RENDERER_SERVICE_ID, (PLOT_FLAG,)),
        (RENDERER_SERVICE_ID, (PLOT_FLAG,)),
    ]
    assert all(flag != ('app',) for _, flag in calls)

    # A matrix is the other method. It is not a fourth kind.
    assert session.show(grid) == b'matrix-png'
    assert renderer.calls[-1] == ('render_matrix', grid)
    assert calls[-1] == (RENDERER_SERVICE_ID, (PLOT_FLAG,))

# ** test: a_non_record_is_not_created_or_shown
def test_a_non_record_is_not_created_or_shown():
    '''
    Create and show do not invent a record from something else.
    '''

    # Resolution must not run. The caller did not pass a finished record.
    def get_dependency(*args, **kwargs):
        '''
        Fail if the handler resolves a service for a non-record.

        :param args: Resolution arguments.
        :type args: tuple
        :param kwargs: Resolution keyword arguments.
        :type kwargs: dict
        '''

        # A non-record is rejected before any service is resolved.
        raise AssertionError('resolved a service for a non-record')

    session = bound(
        create=create_handler(get_dependency),
        show=show_handler(get_dependency),
    )
    with pytest.raises(ValueError):
        session.create(object())
    with pytest.raises(ValueError):
        session.show({'name': 'Sales by Region'})

# ** test: session_does_not_import_the_drawing_tool_or_a_store
def test_session_does_not_import_the_drawing_tool_or_a_store():
    '''
    The session module does not import Matplotlib, the renderer utility, or a repository.
    '''

    # Imports are the boundary. Naming a service id is not an import.
    imported = ' '.join(imported_modules(Path(context_module.__file__)))
    assert 'matplotlib' not in imported
    assert 'repos' not in imported
    assert 'utils' not in imported
    source = Path(context_module.__file__).read_text()
    assert 'PlotConfigRepository' not in source
    assert 'MatrixConfigRepository' not in source
    assert 'MatplotlibRenderer' not in source
    assert 'open(' not in source
    assert 'add_series' not in source
    assert 'def append' not in source
