"""Tests for the plotter session."""

# *** imports

# ** core
import ast
import inspect
from pathlib import Path
from types import SimpleNamespace

# ** infra
import pytest
from pydantic import ValidationError

# ** app
from tiferet import TiferetAPIError
from tiferet.contexts.app import AppSession, AppSessionContext
from tiferet.contexts.core import BaseContext
from tiferet.domain import ModelError
from tiferet.interfaces import ServiceError
from tiferet_plot.contexts.plot import (
    CREATE_MATRIX_EVENT_ID,
    CREATE_PLOT_EVENT_ID,
    PLOT_FLAG,
    UPDATE_PLOT_EVENT_ID,
    PlotterSessionContext,
    create_handler,
)
from tiferet_plot.events.plot import CreateMatrix, CreatePlot, UpdatePlot
from tiferet_plot.interfaces.plot import MatrixService, PlotService
from tiferet_plot.domain.plot import (
    ADDITION_ROLE_MISSING_ID,
    ADDITION_ROLE_NOT_IN_SERIES_ID,
    ADDITION_SORT_MISMATCH_ID,
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

# ** class: recording_show_handler
class RecordingShowHandler:
    '''
    A show-handler stand-in that records the record and the size it received.

    The handler itself is a blueprint. The session only has to call it.
    '''

    # * init
    def __init__(self) -> None:
        '''
        Start with no picture calls.
        '''

        # Each call proves what the session forwarded.
        self.calls = []

    # * method: __call__
    def __call__(self, record, width, height) -> bytes:
        '''
        Record the call and return sentinel picture bytes.

        :param record: The plot or matrix record.
        :type record: Any
        :param width: The picture width passed through.
        :type width: float
        :param height: The picture height passed through.
        :type height: float
        :return: Sentinel picture bytes.
        :rtype: bytes
        '''

        # Return bytes. The session does not read a size from the record.
        self.calls.append((record, width, height))
        return b'picture-png'

# *** functions

# ** function: line_marks
def line_marks(x=(1, 2), y=(3, 4)):
    '''
    Build numeric x and y marks.

    :param x: The x values.
    :type x: tuple
    :param y: The y values.
    :type y: tuple
    :return: Marks for a line or scatter series.
    :rtype: list
    '''

    # Return the two required roles.
    return [
        Mark(role='x', values=x),
        Mark(role='y', values=y),
    ]

# ** function: bar_marks
def bar_marks(category=('North', 'South'), height=(10, 12)):
    '''
    Build category and height marks.

    :param category: The category labels.
    :type category: tuple
    :param height: The bar heights.
    :type height: tuple
    :return: Marks for a bar series.
    :rtype: list
    '''

    # Return the two required roles.
    return [
        Mark(role='category', values=category),
        Mark(role='height', values=height),
    ]

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
def bound(create=None, show=None, get_dependency=None):
    '''
    Bind a plotter session without the blueprint.

    :param create: The create handler, or None when unwired.
    :type create: Callable | None
    :param show: The show handler, or None when unwired.
    :type show: Callable | None
    :param get_dependency: The DI resolver, or a no-op when omitted.
    :type get_dependency: Callable | None
    :return: A session bound to an app session.
    :rtype: PlotterSessionContext
    '''

    # The five framework handlers are absent, so an unwired one still fails.
    if get_dependency is None:
        get_dependency = lambda *args, **kwargs: None
    return PlotterSessionContext.from_domain(
        AppSession(
            id='plotter',
            name='Plotter',
        ),
        get_dependency=get_dependency,
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

# ** function: mark_values
def mark_values(plot, index=0):
    '''
    Return the mark value tuples on one series.

    :param plot: The plot record.
    :type plot: Plot
    :param index: The series index.
    :type index: int
    :return: Value tuples in mark order.
    :rtype: list
    '''

    # Compare values, not mark object identity.
    return [
        tuple(mark.values)
        for mark in plot.series[index].marks
    ]

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

    # Create and show are handlers. The chain is methods on this session.
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
    assert 'update_handler' not in params
    for name in (
        'draft',
        'edit',
        'add_series',
        'append',
        'discard',
        'update',
    ):
        assert hasattr(PlotterSessionContext, name)
    assert not hasattr(context_module, 'PlotterFluentContext')
    assert not hasattr(PlotterSessionContext, 'show_line')
    assert not hasattr(PlotterSessionContext, 'show_bar')
    assert not hasattr(PlotterSessionContext, 'show_matrix')
    assert not hasattr(context_module, 'show_matrix')
    assert not (Path(context_module.__file__).parent / 'fluent.py').exists()

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
        session.show(plot, 8, 4)
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

# ** test: show_forwards_the_record_and_the_size_to_the_handler
def test_show_forwards_the_record_and_the_size_to_the_handler():
    '''
    Show passes the record and the caller's pair to the injected handler.
    '''

    # The handler is injected. The session does not resolve the renderer.
    plot = line_plot()
    bar = line_plot(kind='bar', plot_id='sales_bar')
    grid = matrix()
    handler = RecordingShowHandler()
    session = bound(show=handler)

    # A line, a bar, and a matrix all go through the one handler.
    assert session.show(plot, 8, 4) == b'picture-png'
    assert session.show(bar, 4, 8) == b'picture-png'
    assert session.show(grid, 8, 6) == b'picture-png'
    assert handler.calls == [
        (plot, 8, 4),
        (bar, 4, 8),
        (grid, 8, 6),
    ]

    # Show forwards the pair. It does not default it or keep it.
    signature = inspect.signature(PlotterSessionContext.show)
    assert list(signature.parameters) == ['self', 'record', 'width', 'height']
    assert signature.parameters['width'].default is inspect.Parameter.empty
    assert signature.parameters['height'].default is inspect.Parameter.empty
    assert not hasattr(session, 'width')

# ** test: declaring_and_keeping_do_not_take_a_size
def test_declaring_and_keeping_do_not_take_a_size():
    '''
    The chain, the events, and the keep contracts do not take width or height.
    '''

    # The chain declares a record. A picture size is not part of that call.
    for method in (
        PlotterSessionContext.draft,
        PlotterSessionContext.edit,
        PlotterSessionContext.add_series,
        PlotterSessionContext.append,
        PlotterSessionContext.create,
        PlotterSessionContext.update,
    ):
        names = inspect.signature(method).parameters
        assert 'width' not in names
        assert 'height' not in names

    # Create, update, and the keep contracts carry the record, not a size.
    for method in (
        CreatePlot.execute,
        UpdatePlot.execute,
        CreateMatrix.execute,
        PlotService.save,
        PlotService.update,
        MatrixService.save,
        MatrixService.update,
    ):
        names = inspect.signature(method).parameters
        assert 'width' not in names
        assert 'height' not in names

    # The record has no size to read back.
    assert not hasattr(line_plot(), 'width')
    assert not hasattr(matrix(), 'height')

# ** test: a_non_record_is_not_created
def test_a_non_record_is_not_created():
    '''
    Create does not invent a record from something else.
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

    session = bound(create=create_handler(get_dependency))
    with pytest.raises(AttributeError):
        session.create(object())

# ** test: session_does_not_import_the_drawing_tool_or_a_store
def test_session_does_not_import_the_drawing_tool_or_a_store():
    '''
    The session module does not import Matplotlib, the renderer utility, or a repository.
    '''

    # Imports are the boundary. Naming a service id is not an import.
    imported = ' '.join(imported_modules(Path(context_module.__file__)))
    assert 'matplotlib' not in imported
    assert 'mappers' not in imported
    assert 'repos' not in imported
    assert 'utils' not in imported
    assert 'tiferet.di' not in imported
    source = Path(context_module.__file__).read_text()
    assert 'PlotConfigRepository' not in source
    assert 'MatrixConfigRepository' not in source
    assert 'MatplotlibRenderer' not in source
    assert 'PlotterFluentContext' not in source
    assert 'update_handler' not in source
    assert 'open(' not in source

# ** test: draft_and_add_series_settle_ids_once
def test_draft_and_add_series_settle_ids_once():
    '''
    A line chain derives the plot id and the series id once, then keeps them.
    '''

    # The chain returns the session. Ids are settled before create.
    session = bound(create=lambda record: record)
    assert session.draft('Sales by Region', 'line') is session
    assert session.add_series('Revenue', line_marks()) is session
    assert session.add_series('Cost', line_marks(x=(7, 8), y=(9, 10))) is session
    assert session.append('revenue', line_marks(x=(5,), y=(6,))) is session
    kept = session.create()

    # Later additions do not recompute the ids settled at draft and add_series.
    assert kept.id == 'sales_by_region'
    assert kept.series[0].id == 'revenue'
    assert kept.series[1].id == 'cost'
    assert mark_values(kept) == [(1, 2, 5), (3, 4, 6)]
    assert mark_values(kept, index=1) == [(7, 8), (9, 10)]

    # Success drops the in-memory plot.
    assert session.draft('Other', 'bar') is session

# ** test: supplied_ids_are_kept_and_blank_ids_are_derived
def test_supplied_ids_are_kept_and_blank_ids_are_derived():
    '''
    A supplied id is kept. A blank id is derived, not stored as given.
    '''

    # A supplied plot id and a supplied series id are not rewritten.
    session = bound(create=lambda record: record)
    session.draft('Sales by Region', 'line', id='Custom-Id', description='A claim.')
    session.add_series('Revenue', line_marks(), id='rev-1')
    kept = session.create()
    assert kept.id == 'Custom-Id'
    assert kept.series[0].id == 'rev-1'
    assert kept.description == 'A claim.'

    # A blank id is the omitted case. The name still identifies the record.
    session.draft('Sales by Region', 'line', id='   ')
    session.add_series('Q3 Revenue', line_marks(), id='')
    derived = session.create()
    assert derived.id == 'sales_by_region'
    assert derived.series[0].id == 'q3_revenue'

    # A name that cannot identify the record still keeps a supplied id.
    session.draft('!!!', 'line', id='kept')
    session.add_series('Revenue', line_marks())
    assert session.create().id == 'kept'

# ** test: empty_derivation_opens_no_plot
@pytest.mark.parametrize('name', ['---', '   ', '!!!'])
def test_empty_derivation_opens_no_plot(name):
    '''
    A name that snake-cases to nothing, with no id, opens no plot.
    '''

    # The failure leaves the session able to open a different plot.
    session = bound()
    with pytest.raises(ValueError):
        session.draft(name, 'line')
    assert session.draft('Sales by Region', 'line') is session

# ** test: add_series_rejects_illegal_marks_and_a_duplicate_id
def test_add_series_rejects_illegal_marks_and_a_duplicate_id():
    '''
    Illegal marks add no series. A duplicate series id leaves the first series.
    '''

    # A line plot does not accept bar marks. The draft stays empty.
    calls = []

    def handler(record):
        '''
        Record a create and return the plot.

        :param record: The plot passed to the handler.
        :type record: Plot
        :return: The same plot.
        :rtype: Plot
        '''

        # An empty draft must not reach this handler.
        calls.append(record)
        return record

    session = bound(create=handler)
    session.draft('Sales by Region', 'line')
    with pytest.raises(ValidationError):
        session.add_series('Revenue', bar_marks())
    with pytest.raises(ValueError):
        session.create()
    assert calls == []

    # The first successful series stays when a second id collides.
    session.add_series('Revenue', line_marks())
    with pytest.raises(ValidationError):
        session.add_series('Other', line_marks(), id='revenue')
    with pytest.raises(ValidationError):
        session.add_series('Revenue', line_marks())
    kept = session.create()
    assert len(kept.series) == 1
    assert kept.series[0].id == 'revenue'
    assert kept.series[0].name == 'Revenue'
    assert kept.kind == 'line'

# ** test: append_extends_one_series_and_keeps_the_kind_rules
@pytest.mark.parametrize('kind,marks,added,expected', [
    (
        'line',
        line_marks(),
        line_marks(x=(5,), y=(6,)),
        [(1, 2, 5), (3, 4, 6)],
    ),
    (
        'scatter',
        line_marks(),
        line_marks(x=(5,), y=(6,)),
        [(1, 2, 5), (3, 4, 6)],
    ),
    (
        'bar',
        bar_marks(),
        bar_marks(category=('East',), height=(8,)),
        [('North', 'South', 'East'), (10, 12, 8)],
    ),
])
def test_append_extends_one_series_and_keeps_the_kind_rules(kind, marks, added, expected):
    '''
    Append adds the same non-empty count to every required role and keeps ids.
    '''

    # A second series of a different length must stay as it was.
    session = bound(create=lambda record: record)
    session.draft('Sales by Region', kind)
    session.add_series('Revenue', marks)
    other = line_marks(x=(1, 2, 3), y=(4, 5, 6)) if kind != 'bar' else bar_marks(
        category=('A', 'B', 'C'),
        height=(1, 2, 3),
    )
    session.add_series('Cost', other, id='cost')
    assert session.append('revenue', added) is session
    kept = session.create()

    # The addressed series grew. The other series and both ids did not.
    assert kept.id == 'sales_by_region'
    assert kept.series[0].id == 'revenue'
    assert kept.series[1].id == 'cost'
    assert mark_values(kept) == expected
    assert mark_values(kept, index=1) == [tuple(mark.values) for mark in other]

# ** test: append_addresses_a_series_by_id
def test_append_addresses_a_series_by_id():
    '''
    Two series may share a name. Append uses the id, not the name.
    '''

    # Both series are named Revenue. Only the addressed id grows.
    session = bound(create=lambda record: record)
    session.draft('Sales by Region', 'line')
    session.add_series('Revenue', line_marks(), id='rev-a')
    session.add_series('Revenue', line_marks(), id='rev-b')
    session.append('rev-a', line_marks(x=(9,), y=(8,)))
    kept = session.create()
    assert kept.series[0].name == kept.series[1].name == 'Revenue'
    assert mark_values(kept) == [(1, 2, 9), (3, 4, 8)]
    assert mark_values(kept, index=1) == [(1, 2), (3, 4)]

# ** test: append_failures_leave_the_marks_unchanged
@pytest.mark.parametrize('kind,bad', [
    ('line', [Mark(role='x', values=(5,)), Mark(role='y', values=(6, 7))]),
    ('line', []),
    ('line', [{'role': 'x', 'values': ()}, {'role': 'y', 'values': ()}]),
    ('line', [Mark(role='x', values=(5,))]),
    ('line', line_marks(x=(5,), y=(6,)) + [Mark(role='category', values=('East',))]),
    ('scatter', [Mark(role='x', values=(5,)), Mark(role='y', values=(6, 7))]),
    ('bar', [Mark(role='category', values=('East',)), Mark(role='height', values=(1, 2))]),
    ('line', bar_marks()),
    ('bar', line_marks()),
])
def test_append_failures_leave_the_marks_unchanged(kind, bad):
    '''
    An illegal addition does not change the marks.
    '''

    # The original marks are what create still sees.
    session = bound(create=lambda record: record)
    original = bar_marks() if kind == 'bar' else line_marks()
    session.draft('Sales by Region', kind)
    session.add_series('Revenue', original)
    with pytest.raises(ValidationError):
        session.append('revenue', bad)
    kept = session.create()
    assert mark_values(kept) == [tuple(mark.values) for mark in original]
    assert kept.id == 'sales_by_region'
    assert kept.series[0].id == 'revenue'

# ** test: append_of_an_unknown_series_leaves_the_marks_unchanged
def test_append_of_an_unknown_series_leaves_the_marks_unchanged():
    '''
    An unknown series id fails, and the marks are unchanged.
    '''

    # The series is addressed by id. A name is not a key.
    session = bound(create=lambda record: record)
    session.draft('Sales by Region', 'line')
    session.add_series('Revenue', line_marks())
    with pytest.raises(ValueError):
        session.append('missing', line_marks(x=(5,), y=(6,)))
    kept = session.create()
    assert mark_values(kept) == [(1, 2), (3, 4)]

# ** test: create_keeps_the_chain_and_drops_it
def test_create_keeps_the_chain_and_drops_it():
    '''
    create with no argument calls the create handler and returns its record.
    '''

    # The handler is the existing create path. The event sees the settled ids.
    event = RecordingEvent(None)

    def execute(**kwargs):
        '''
        Keep the arguments and return a record with those ids.

        :param kwargs: The event arguments.
        :type kwargs: dict
        :return: The kept record.
        :rtype: Plot
        '''

        # The chain passed the ids it already settled.
        event.kwargs = kwargs
        event.result = Plot(
            id=kwargs['id'],
            name=kwargs['name'],
            kind=kwargs['kind'],
            description=kwargs.get('description'),
            series=kwargs['series'],
        )
        return event.result

    event.execute = execute
    get_dependency, calls = resolver({
        CREATE_PLOT_EVENT_ID: event,
    })
    session = bound(create=create_handler(get_dependency))
    session.draft('Sales by Region', 'line', description='A claim.')
    session.add_series('Revenue', line_marks())
    kept = session.create()

    # The returned record is the event's record, and the chain is gone.
    assert calls == [(CREATE_PLOT_EVENT_ID, (PLOT_FLAG,))]
    assert kept is event.result
    assert kept.id == 'sales_by_region'
    assert kept.series[0].id == 'revenue'
    assert kept.description == 'A claim.'
    assert session.draft('Other', 'scatter') is session

# ** test: create_of_an_empty_draft_does_not_call_the_handler
def test_create_of_an_empty_draft_does_not_call_the_handler():
    '''
    create on a draft with no series does not call the create handler.
    '''

    # No open plot fails too, and also does not call the handler.
    calls = []
    session = bound(create=lambda record: calls.append(record))
    with pytest.raises(ValueError):
        session.create()
    session.draft('Sales by Region', 'line')
    with pytest.raises(ValueError):
        session.create()
    assert calls == []
    with pytest.raises(ValueError):
        session.draft('Other', 'line')

# ** test: explicit_create_does_not_send_or_drop_the_draft
def test_explicit_create_does_not_send_or_drop_the_draft():
    '''
    An explicit plot or matrix wins. The open draft is not sent and not dropped.
    '''

    # The draft has no series. The explicit records are what the handler sees.
    plot = line_plot(plot_id='explicit')
    grid = matrix()
    plot_event = RecordingEvent('kept-plot')
    matrix_event = RecordingEvent('kept-matrix')
    get_dependency, calls = resolver({
        CREATE_PLOT_EVENT_ID: plot_event,
        CREATE_MATRIX_EVENT_ID: matrix_event,
    })
    session = bound(create=create_handler(get_dependency))
    session.draft('Sales by Region', 'line')
    assert session.create(plot) == 'kept-plot'
    assert plot_event.kwargs['id'] == 'explicit'
    assert session.create(grid) == 'kept-matrix'
    assert matrix_event.kwargs['id'] == grid.id
    assert calls == [
        (CREATE_PLOT_EVENT_ID, (PLOT_FLAG,)),
        (CREATE_MATRIX_EVENT_ID, (PLOT_FLAG,)),
    ]

    # The draft is still open, and a later chain create sends that draft.
    with pytest.raises(ValueError):
        session.draft('Other', 'bar')
    session.add_series('Revenue', line_marks())
    assert session.create() == 'kept-plot'
    assert plot_event.kwargs['id'] == 'sales_by_region'
    assert plot_event.kwargs['series'][0].id == 'revenue'

# ** test: create_failure_leaves_the_chain
def test_create_failure_leaves_the_chain():
    '''
    A failed create leaves the in-memory plot and does not call update.
    '''

    # The handler fails. The chain does not resolve UpdatePlot.
    resolved = []

    def get_dependency(*args, **kwargs):
        '''
        Fail if update resolves a service after a failed create.

        :param args: Resolution arguments.
        :type args: tuple
        :param kwargs: Resolution keyword arguments.
        :type kwargs: dict
        '''

        # Create does not fall through to update.
        resolved.append(args)
        raise AssertionError('resolved a service')

    def handler(record):
        '''
        Fail the keep. The chain must remain.

        :param record: The in-memory plot.
        :type record: Plot
        '''

        # The store is the handler's concern. This stand-in does not insert.
        raise RuntimeError('already kept')

    session = bound(create=handler, get_dependency=get_dependency)
    session.draft('Sales by Region', 'line').add_series('Revenue', line_marks())
    with pytest.raises(RuntimeError):
        session.create()
    assert resolved == []
    with pytest.raises(ValueError):
        session.draft('Other', 'line')

# ** test: update_calls_update_plot_and_drops_the_chain
def test_update_calls_update_plot_and_drops_the_chain():
    '''
    update calls UpdatePlot with the open plot and does not change its id.
    '''

    # The event returns the record it was given. The chain returns that record.
    event = RecordingEvent(None)

    def execute(**kwargs):
        '''
        Record the call and return a record with the supplied id.

        :param kwargs: The event arguments.
        :type kwargs: dict
        :return: The kept record.
        :rtype: Plot
        '''

        # The id is the one the chain already settled.
        event.kwargs = kwargs
        event.result = Plot(
            id=kwargs['id'],
            name=kwargs['name'],
            kind=kwargs['kind'],
            description=kwargs.get('description'),
            series=kwargs['series'],
        )
        return event.result

    event.execute = execute
    get_dependency, calls = resolver({
        UPDATE_PLOT_EVENT_ID: event,
    })
    created = []
    session = bound(
        create=lambda record: created.append(record),
        get_dependency=get_dependency,
    )
    session.draft('Sales by Region', 'line', id='Custom-Id')
    session.add_series('Revenue', line_marks(), id='rev-1')
    kept = session.update()

    # Update does not create, and success drops the chain.
    assert calls == [(UPDATE_PLOT_EVENT_ID, (PLOT_FLAG,))]
    assert event.kwargs['id'] == 'Custom-Id'
    assert event.kwargs['series'][0].id == 'rev-1'
    assert kept is event.result
    assert kept.id == 'Custom-Id'
    assert created == []
    assert session.draft('Other', 'bar') is session

# ** test: update_failure_leaves_the_chain_and_does_not_insert
def test_update_failure_leaves_the_chain_and_does_not_insert():
    '''
    A failed update leaves the in-memory plot. It does not insert.
    '''

    # The event refuses an id that is not kept. The chain does not create.
    event = RecordingEvent(None)

    def execute(**kwargs):
        '''
        Record the call and fail as an id that is not kept.

        :param kwargs: The event arguments.
        :type kwargs: dict
        '''

        # Nothing is inserted. The chain must keep its plot.
        event.kwargs = kwargs
        raise ServiceError(
            'PLOT_NOT_KEPT',
            message='Plot is not kept.',
        )

    event.execute = execute
    get_dependency, calls = resolver({
        UPDATE_PLOT_EVENT_ID: event,
    })
    created = []
    session = bound(
        create=lambda record: created.append(record) or record,
        get_dependency=get_dependency,
    )
    session.draft('Sales by Region', 'line', id='missing')
    session.add_series('Revenue', line_marks())
    with pytest.raises(ServiceError):
        session.update()

    # The in-memory plot remains, and create was not used as a fallback.
    assert calls == [(UPDATE_PLOT_EVENT_ID, (PLOT_FLAG,))]
    assert event.kwargs['id'] == 'missing'
    assert created == []
    with pytest.raises(ValueError):
        session.draft('Other', 'line')
    kept = session.create()
    assert kept.id == 'missing'
    assert mark_values(kept) == [(1, 2), (3, 4)]

# ** test: update_of_an_empty_draft_does_not_resolve_the_event
def test_update_of_an_empty_draft_does_not_resolve_the_event():
    '''
    update on a draft with no series does not resolve UpdatePlot.
    '''

    # No open plot fails the same way: the event is not resolved.
    def get_dependency(*args, **kwargs):
        '''
        Fail if an empty chain resolves a service.

        :param args: Resolution arguments.
        :type args: tuple
        :param kwargs: Resolution keyword arguments.
        :type kwargs: dict
        '''

        # A draft with no series is not an update.
        raise AssertionError('resolved a service')

    session = bound(get_dependency=get_dependency)
    with pytest.raises(ValueError):
        session.update()
    session.draft('Sales by Region', 'line')
    with pytest.raises(ValueError):
        session.update()

# ** test: edit_then_append_does_not_recompute_ids_or_mutate_the_caller
def test_edit_then_append_does_not_recompute_ids_or_mutate_the_caller():
    '''
    edit keeps the caller's ids, holds its own record, and does not load a plot.
    '''

    # Resolution must not run. edit does not call GetPlot.
    def get_dependency(*args, **kwargs):
        '''
        Fail if edit or append resolves a service.

        :param args: Resolution arguments.
        :type args: tuple
        :param kwargs: Resolution keyword arguments.
        :type kwargs: dict
        '''

        # The caller already holds the plot. Do not load it.
        raise AssertionError('resolved a service')

    original = line_plot(plot_id='Custom-Id')
    before = original.model_dump()
    session = bound(
        create=lambda record: record,
        get_dependency=get_dependency,
    )
    assert session.edit(original) is session
    session.append('revenue', line_marks(x=(5,), y=(6,)))
    kept = session.create()

    # The chain's record grew. The object the caller passed did not.
    assert kept is not original
    assert kept.id == 'Custom-Id'
    assert kept.series[0].id == 'revenue'
    assert mark_values(kept) == [(1, 2, 5), (3, 4, 6)]
    assert original.model_dump() == before

# ** test: edit_of_a_matrix_or_an_invalid_plot_opens_nothing
def test_edit_of_a_matrix_or_an_invalid_plot_opens_nothing():
    '''
    edit of a matrix fails. A non-record opens nothing.
    '''

    # The matrix says it is a matrix. A non-record has no such description.
    session = bound()
    with pytest.raises(ValueError):
        session.edit(matrix())
    with pytest.raises(AttributeError):
        session.edit(SimpleNamespace(
            id='sales_by_region',
            name='Sales by Region',
            kind='line',
            description=None,
            series=[],
        ))
    assert session.draft('Sales by Region', 'line') is session

# ** test: a_second_draft_fails_and_discard_drops_the_chain
def test_a_second_draft_fails_and_discard_drops_the_chain():
    '''
    A second draft leaves the first plot. discard drops it and calls no event.
    '''

    # Discard must not resolve a service, including a removal.
    resolved = []

    def get_dependency(*args, **kwargs):
        '''
        Fail if discard resolves a service.

        :param args: Resolution arguments.
        :type args: tuple
        :param kwargs: Resolution keyword arguments.
        :type kwargs: dict
        '''

        # discard is not a removal of a kept record.
        resolved.append(args)
        raise AssertionError('resolved a service')

    session = bound(
        create=lambda record: record,
        get_dependency=get_dependency,
    )
    session.draft('Sales by Region', 'line')
    with pytest.raises(ValueError):
        session.draft('Other', 'bar')
    with pytest.raises(ValueError):
        session.edit(line_plot(plot_id='other'))
    session.add_series('Revenue', line_marks())
    assert session.discard() is session
    with pytest.raises(ValueError):
        session.create()
    assert resolved == []

    # The first plot was dropped, so a new draft can open.
    session.draft('Other', 'bar')
    session.add_series('Revenue', bar_marks())
    kept = session.create()
    assert kept.id == 'other'
    assert kept.kind == 'bar'

# ** test: show_does_not_read_or_drop_an_open_draft
def test_show_does_not_read_or_drop_an_open_draft():
    '''
    show of an explicit plot, while a draft is open, returns that picture.
    '''

    # The handler sees the explicit plot. The draft stays open.
    explicit = line_plot(plot_id='explicit')
    handler = RecordingShowHandler()
    session = bound(show=handler)
    session.draft('Draft Name', 'line')
    assert session.show(explicit, 8, 4) == b'picture-png'
    assert handler.calls == [(explicit, 8, 4)]
    with pytest.raises(ValueError):
        session.draft('Other', 'line')

# ** test: draft_carries_title_and_does_not_shift_the_id
def test_draft_carries_title_and_does_not_shift_the_id():
    '''
    draft keeps title through add_series. A third positional argument is the id.
    '''

    # There is no chain method that sets this text after draft.
    for name in (
        'set_title',
        'set_x_title',
        'set_x_unit',
        'set_y_title',
        'set_y_unit',
        'set_subtitle',
    ):
        assert not hasattr(PlotterSessionContext, name)

    # A later series does not clear the text the draft set, or recompute the id.
    session = bound(create=lambda record: record)
    session.draft(
        'Sales by Region',
        'line',
        title='Quarterly sales, 2024',
        x_title='Year',
        y_unit='USD',
    )
    session.add_series('Revenue', line_marks())
    kept = session.create()
    assert kept.id == 'sales_by_region'
    assert kept.title == 'Quarterly sales, 2024'
    assert kept.x_title == 'Year'
    assert kept.y_unit == 'USD'
    assert kept.x_unit is None

    # The third positional argument is still the id, not the title.
    session.draft('Sales by Region', 'line', 'custom-id')
    session.add_series('Revenue', line_marks())
    positional = session.create()
    assert positional.id == 'custom-id'
    assert positional.title is None

# ** test: edit_and_update_send_figure_text
def test_edit_and_update_send_figure_text():
    '''
    edit copies title. update sends title and the axis fields without changing the id.
    '''

    # The caller already holds the title. edit does not derive an id from it.
    original = Plot(
        id='Custom-Id',
        name='Sales by Region',
        kind='line',
        title='Quarterly sales, 2024',
        x_title='Year',
        y_unit='USD',
        series=[
            Series(id='revenue', name='Revenue', marks=line_marks()),
        ],
    )
    event = RecordingEvent(None)

    def execute(**kwargs):
        '''
        Record the update call and return a record with the supplied id.

        :param kwargs: The event arguments.
        :type kwargs: dict
        :return: The kept record.
        :rtype: Plot
        '''

        # The chain sends the text it copied. It does not derive an id.
        event.kwargs = kwargs
        event.result = Plot(
            id=kwargs['id'],
            name=kwargs['name'],
            kind=kwargs['kind'],
            description=kwargs.get('description'),
            title=kwargs.get('title'),
            x_title=kwargs.get('x_title'),
            y_unit=kwargs.get('y_unit'),
            series=kwargs['series'],
        )
        return event.result

    event.execute = execute
    get_dependency, calls = resolver({
        UPDATE_PLOT_EVENT_ID: event,
    })
    session = bound(get_dependency=get_dependency)
    assert session.edit(original) is session
    kept = session.update()
    assert calls == [(UPDATE_PLOT_EVENT_ID, (PLOT_FLAG,))]
    assert event.kwargs['id'] == 'Custom-Id'
    assert event.kwargs['title'] == 'Quarterly sales, 2024'
    assert event.kwargs['x_title'] == 'Year'
    assert event.kwargs['y_unit'] == 'USD'
    assert kept.id == 'Custom-Id'
    assert kept.title == 'Quarterly sales, 2024'
    assert original.title == 'Quarterly sales, 2024'

# ** test: create_handler_passes_title_and_y_title
def test_create_handler_passes_title_and_y_title():
    '''
    The session create handler passes title and y_title for a finished plot.
    '''

    # A finished plot carries both strings. A matrix carries title only.
    plot = Plot(
        id='sales_by_region',
        name='Sales by Region',
        kind='line',
        title='Quarterly sales, 2024',
        y_title='Revenue',
        series=[
            Series(id='revenue', name='Revenue', marks=line_marks()),
        ],
    )
    grid = PlotMatrix(
        id='sales_by_region',
        name='Sales by Region',
        title='Quarterly sales by region',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=plot),
        ],
    )
    plot_event = RecordingEvent('kept-plot')
    matrix_event = RecordingEvent('kept-matrix')
    get_dependency, _calls = resolver({
        CREATE_PLOT_EVENT_ID: plot_event,
        CREATE_MATRIX_EVENT_ID: matrix_event,
    })
    session = bound(create=create_handler(get_dependency))
    assert session.create(plot) == 'kept-plot'
    assert plot_event.kwargs['title'] == 'Quarterly sales, 2024'
    assert plot_event.kwargs['y_title'] == 'Revenue'
    assert plot_event.kwargs['id'] == plot.id
    assert plot_event.kwargs['description'] == plot.description

    # A matrix passes title and does not gain an axis parameter.
    assert session.create(grid) == 'kept-matrix'
    assert matrix_event.kwargs['title'] == 'Quarterly sales by region'
    assert 'x_title' not in matrix_event.kwargs
    assert 'y_title' not in matrix_event.kwargs

# ** test: add_series_has_no_labels_parameter
def test_add_series_has_no_labels_parameter():
    '''
    add_series takes marks. It does not take a labels argument.
    '''

    # Text rides on the marks. It is not a second parameter.
    assert 'labels' not in inspect.signature(
        PlotterSessionContext.add_series).parameters
    assert 'rotation' not in inspect.signature(
        PlotterSessionContext.add_series).parameters

# ** test: draft_add_series_and_append_do_not_derive_ids_from_text
def test_draft_add_series_and_append_do_not_derive_ids_from_text():
    '''
    Text on x and label does not become the plot id or the series id.
    '''

    # Draft derives the plot id from the name. The text is not that name.
    session = bound(create=lambda record: record)
    session.draft('Design Response', 'line')
    session.add_series('Trial', [
        Mark(role='x', values=('alpha', 'beta')),
        Mark(role='y', values=(1, 2)),
        Mark(role='label', values=('run-1', 'run-2')),
    ])
    assert session.append('trial', [
        Mark(role='x', values=('gamma',)),
        Mark(role='y', values=(3,)),
        Mark(role='label', values=('run-3',)),
    ]) is session
    kept = session.create()

    # Neither id was recomputed from the text. The roles stayed.
    assert kept.id == 'design_response'
    assert kept.series[0].id == 'trial'
    assert kept.id not in ('alpha', 'beta', 'gamma', 'run-1', 'run-3')
    assert kept.series[0].id not in ('alpha', 'beta', 'gamma', 'run-1', 'run-3')
    assert mark_values(kept) == [
        ('alpha', 'beta', 'gamma'),
        (1, 2, 3),
        ('run-1', 'run-2', 'run-3'),
    ]

# ** test: append_role_and_sort_mismatches_leave_the_marks_unchanged
def test_append_role_and_sort_mismatches_leave_the_marks_unchanged():
    '''
    An addition that does not match the series' roles or sorts changes nothing.
    '''

    # A labeled text-x series rejects a missing label and a numeric x.
    session = bound(create=lambda record: record)
    session.draft('Design Response', 'line')
    labeled = [
        Mark(role='x', values=('alpha', 'beta')),
        Mark(role='y', values=(1, 2)),
        Mark(role='label', values=('run-1', 'run-2')),
    ]
    session.add_series('Trial', labeled)
    with pytest.raises(ModelError) as omitted:
        session.append('trial', [
            Mark(role='x', values=('gamma',)),
            Mark(role='y', values=(3,)),
        ])
    with pytest.raises(ModelError) as wrong_sort:
        session.append('trial', [
            Mark(role='x', values=(9,)),
            Mark(role='y', values=(3,)),
            Mark(role='label', values=('run-3',)),
        ])
    kept = session.create()

    # The domain named the defect. The marks did not change.
    assert omitted.value.error_code == ADDITION_ROLE_MISSING_ID
    assert wrong_sort.value.error_code == ADDITION_SORT_MISMATCH_ID
    assert kept.id == 'design_response'
    assert kept.series[0].id == 'trial'
    assert mark_values(kept) == [
        ('alpha', 'beta'),
        (1, 2),
        ('run-1', 'run-2'),
    ]

    # A series without label rejects an addition that includes one.
    session = bound(create=lambda record: record)
    session.draft('Sales by Region', 'line')
    session.add_series('Revenue', line_marks())
    with pytest.raises(ModelError) as added_label:
        session.append('revenue', line_marks(x=(5,), y=(6,)) + [
            Mark(role='label', values=('run-3',)),
        ])
    with pytest.raises(ModelError) as text_y:
        session.append('revenue', [
            Mark(role='x', values=(5,)),
            Mark(role='y', values=('6',)),
        ])
    kept = session.create()
    assert added_label.value.error_code == ADDITION_ROLE_NOT_IN_SERIES_ID
    assert text_y.value.error_code == ADDITION_SORT_MISMATCH_ID
    assert kept.id == 'sales_by_region'
    assert kept.series[0].id == 'revenue'
    assert mark_values(kept) == [(1, 2), (3, 4)]
