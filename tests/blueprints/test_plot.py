"""Tests for the plotter session blueprint."""

# *** imports

# ** core
import ast
from pathlib import Path

# ** infra
import pytest

# ** app
from tiferet import TiferetError
from tiferet.domain import ModelError
from tiferet.di import DIAppServiceContainer, DIDynamicServiceContainer
from tiferet.interfaces import ServiceError
from tiferet_plot.blueprints.plot import create_plotter_session, show_handler
from tiferet_plot.contexts.plot import (
    PLOT_FLAG,
    RENDERER_SERVICE_ID,
    PlotterSessionContext,
)
from tiferet_plot.domain.plot import (
    Mark,
    MatrixCell,
    Plot,
    PlotMatrix,
    Series,
)
from tiferet_plot.interfaces.plot import (
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
)
from tiferet_plot.repos.plot import (
    MatrixConfigRepository,
    PlotConfigRepository,
)
from tiferet_plot.utils.plot import MatplotlibRenderer
import tiferet_plot.blueprints.plot as blueprint_module

# *** constants

# ** constant: png_signature
PNG_SIGNATURE = bytes([
    0x89,
    0x50,
    0x4E,
    0x47,
    0x0D,
    0x0A,
    0x1A,
    0x0A,
])

# *** classes

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
    def render(self, plot, width, height) -> bytes:
        '''
        Record a plot picture call.

        :param plot: The plot record.
        :type plot: Any
        :param width: The picture width passed through.
        :type width: float
        :param height: The picture height passed through.
        :type height: float
        :return: Sentinel picture bytes.
        :rtype: bytes
        '''

        # Return bytes. Do not write a file or read a size from the plot.
        self.calls.append(('render', plot, width, height))
        return b'plot-png'

    # * method: render_matrix
    def render_matrix(self, matrix, width, height) -> bytes:
        '''
        Record a matrix picture call.

        :param matrix: The matrix record.
        :type matrix: Any
        :param width: The picture width passed through.
        :type width: float
        :param height: The picture height passed through.
        :type height: float
        :return: Sentinel picture bytes.
        :rtype: bytes
        '''

        # Return bytes. Do not write a file or invent a size per cell.
        self.calls.append(('render_matrix', matrix, width, height))
        return b'matrix-png'

# *** functions

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

    # Marks follow the kind. The session does not choose them.
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
        series=[
            Series(name='Revenue', marks=marks),
        ],
    )

# ** function: grid
def grid():
    '''
    Build a finished matrix with one occupied cell.

    :return: A declared matrix.
    :rtype: PlotMatrix
    '''

    # The plot id is supplied. Declaration of the cell does not fill it.
    return PlotMatrix(
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

# ** test: show_handler_calls_render_or_render_matrix_on_the_plot_flag
def test_show_handler_calls_render_or_render_matrix_on_the_plot_flag():
    '''
    The handler resolves the renderer on the plot flag and forwards the size.
    '''

    # The handler is composed here. It is not a function of the session module.
    assert show_handler.__module__ == 'tiferet_plot.blueprints.plot'
    plot = line_plot()
    bar = line_plot(kind='bar', plot_id='sales_bar')
    matrix = grid()
    renderer = RecordingRenderer()
    get_dependency, calls = resolver({
        RENDERER_SERVICE_ID: renderer,
    })
    handler = show_handler(get_dependency)

    # A line and a bar use the same render call, with the pair the caller named.
    assert handler(plot, 8, 4) == b'plot-png'
    assert handler(bar, 4, 8) == b'plot-png'
    assert renderer.calls == [
        ('render', plot, 8, 4),
        ('render', bar, 4, 8),
    ]
    assert calls == [
        (RENDERER_SERVICE_ID, (PLOT_FLAG,)),
        (RENDERER_SERVICE_ID, (PLOT_FLAG,)),
    ]
    assert all(flag != ('app',) for _, flag in calls)

    # A matrix is the other method. It is not a fourth kind.
    assert handler(matrix, 8, 6) == b'matrix-png'
    assert renderer.calls[-1] == ('render_matrix', matrix, 8, 6)
    assert calls[-1] == (RENDERER_SERVICE_ID, (PLOT_FLAG,))

    # The handler does not default the pair or read a size from the record.
    with pytest.raises(TypeError):
        handler(plot)
    assert not hasattr(plot, 'width')

# ** test: show_handler_does_not_invent_a_record
def test_show_handler_does_not_invent_a_record():
    '''
    The handler rejects a non-record before it resolves the renderer.
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

    # The record says whether it is a matrix. A mapping does not.
    handler = show_handler(get_dependency)
    with pytest.raises(AttributeError):
        handler({'name': 'Sales by Region'}, 8, 4)

# ** test: blueprint_constructs_the_session_itself
def test_blueprint_constructs_the_session_itself(tmp_path):
    '''
    The blueprint constructs the plotter session. The generic entry point does not.
    '''

    # The entry point returns this context, not a hub selected from configuration.
    session = create_plotter_session(
        plot_config=str(tmp_path / 'publication.yml'),
    )
    assert type(session) is PlotterSessionContext
    assert session.domain.id == 'plotter'

    # The source selects the class here. It does not call the generic entry point.
    source = Path(blueprint_module.__file__).read_text()
    assert 'PlotterSessionContext.from_domain' in source
    assert 'App(' not in source
    assert 'build_app(' not in source
    assert 'build_app_session_context' not in source
    imported = ' '.join(imported_modules(Path(blueprint_module.__file__)))
    assert 'matplotlib' not in imported
    assert 'repos' not in imported
    assert '.utils' not in imported

# ** test: renderer_is_resolved_on_the_plot_flag
def test_renderer_is_resolved_on_the_plot_flag(tmp_path):
    '''
    The renderer is a factory service on the plot flag, not an app singleton.
    '''

    # The plot container is factory-scoped. The framework container is not.
    session = create_plotter_session(
        plot_config=str(tmp_path / 'publication.yml'),
    )
    assert isinstance(
        session.resolver.get_container(PLOT_FLAG),
        DIDynamicServiceContainer,
    )
    assert isinstance(
        session.resolver.get_container('app'),
        DIAppServiceContainer,
    )

    # Two resolutions are two instances. The app flag does not have the renderer.
    first = session.get_dependency(RENDERER_SERVICE_ID, PLOT_FLAG)
    second = session.get_dependency(RENDERER_SERVICE_ID, PLOT_FLAG)
    assert first is not second
    assert type(first).__name__ == 'MatplotlibRenderer'
    with pytest.raises(ServiceError):
        session.get_dependency(RENDERER_SERVICE_ID, 'app')

# ** test: create_keeps_a_plot_and_returns_the_record
def test_create_keeps_a_plot_and_returns_the_record(tmp_path):
    '''
    Create of a plot calls the create event and returns the record.
    '''

    # A supplied id is kept. The result is the record, not a picture.
    path = tmp_path / 'publication.yml'
    session = create_plotter_session(plot_config=str(path))
    created = session.create(line_plot(plot_id='Custom-Id'))
    assert created.id == 'Custom-Id'
    assert created.name == 'Sales by Region'
    assert created.kind == 'line'
    assert not isinstance(created, (bytes, str))

    # The event kept it. The session did not open the file itself.
    assert PlotConfigRepository(str(path)).get('Custom-Id').name == 'Sales by Region'

    # A second create of that id fails, and the first record stays.
    with pytest.raises(TiferetError) as caught:
        session.create(line_plot(plot_id='Custom-Id'))
    assert caught.value.error_code == PLOT_ALREADY_KEPT_ID
    assert PlotConfigRepository(str(path)).get('Custom-Id').kind == 'line'

# ** test: create_keeps_a_matrix_and_returns_the_matrix
def test_create_keeps_a_matrix_and_returns_the_matrix(tmp_path):
    '''
    Create of a matrix calls the matrix create event and returns the matrix.
    '''

    # No matrix id is supplied. The event derives it. Cell plots stay in the matrix.
    path = tmp_path / 'publication.yml'
    session = create_plotter_session(plot_config=str(path))
    created = session.create(grid())
    assert created.id == 'sales_by_region'
    assert created.rows == 2
    assert created.cols == 2
    assert created.cells[0].plot.id == 'revenue_plot'
    assert not isinstance(created, (bytes, str))

    # The matrix root holds the record. The plots root does not gain the cell.
    raw = MatrixConfigRepository(str(path))._load()
    assert 'sales_by_region' in raw['matrices']
    assert 'revenue_plot' not in (raw.get('plots') or {})

# ** test: show_returns_png_bytes_and_does_not_write_a_file
def test_show_returns_png_bytes_and_does_not_write_a_file(tmp_path):
    '''
    Show of a plot and a matrix returns PNG bytes and does not write a publication file.
    '''

    # An unsaved line, an unsaved bar, and an unsaved matrix all use show.
    path = tmp_path / 'publication.yml'
    session = create_plotter_session(plot_config=str(path))
    line = session.show(line_plot(), 8, 4)
    bar = session.show(line_plot(kind='bar', plot_id='sales_bar'), 8, 4)
    picture = session.show(grid(), 8, 6)

    # The bytes are the picture. The publication file was not opened.
    assert line.startswith(PNG_SIGNATURE)
    assert bar.startswith(PNG_SIGNATURE)
    assert picture.startswith(PNG_SIGNATURE)
    assert picture != line
    assert not path.exists()

    # Showing a kept record does not rewrite the publication.
    created = session.create(line_plot())
    before = path.read_bytes()
    shown = session.show(created, 8, 4)
    assert shown.startswith(PNG_SIGNATURE)
    assert path.read_bytes() == before

    # Show does not invent a size. A missing or illegal pair returns no picture.
    with pytest.raises(TypeError):
        session.show(created)
    with pytest.raises(ModelError):
        session.show(created, 0, 4)
    assert path.read_bytes() == before

# ** test: show_returns_the_bytes_render_returns
def test_show_returns_the_bytes_render_returns(tmp_path):
    '''
    show returns the bytes render returns for that pair. There is no show_matrix.
    '''

    # The session does not read a size from the record, and it does not write a file.
    path = tmp_path / 'publication.yml'
    session = create_plotter_session(plot_config=str(path))
    plot = line_plot()
    shown = session.show(plot, 8, 4)
    rendered = MatplotlibRenderer().render(plot, 8, 4)

    # The same pair is the same picture. A matrix method is not added here.
    assert shown == rendered
    assert not path.exists()
    assert not hasattr(PlotterSessionContext, 'show_matrix')
    assert 'width' not in type(plot).model_fields

# ** test: chain_create_keeps_the_settled_ids
def test_chain_create_keeps_the_settled_ids(tmp_path):
    '''
    A chain create calls the existing create event and keeps the settled ids.
    '''

    # The chain does not open the file. The event does, and returns the record.
    path = tmp_path / 'publication.yml'
    session = create_plotter_session(plot_config=str(path))
    kept = session.draft(
        'Sales by Region',
        'line',
    ).add_series(
        'Revenue',
        [
            Mark(role='x', values=(1, 2)),
            Mark(role='y', values=(3, 4)),
        ],
    ).create()
    assert kept.id == 'sales_by_region'
    assert kept.series[0].id == 'revenue'
    assert PlotConfigRepository(str(path)).get('sales_by_region').name == 'Sales by Region'

    # Success drops the chain, so another draft can open.
    assert session.draft('Other', 'bar') is session

# ** test: chain_update_keeps_an_edit_and_does_not_insert
def test_chain_update_keeps_an_edit_and_does_not_insert(tmp_path):
    '''
    update calls UpdatePlot. A missing id fails and does not insert.
    '''

    # Keep a record first, then extend it through the chain.
    path = tmp_path / 'publication.yml'
    session = create_plotter_session(plot_config=str(path))
    created = session.create(line_plot(plot_id='sales_by_region'))
    updated = session.edit(created).append(
        'revenue',
        [
            Mark(role='x', values=(5,)),
            Mark(role='y', values=(6,)),
        ],
    ).update()
    assert updated.id == 'sales_by_region'
    loaded = PlotConfigRepository(str(path)).get('sales_by_region')
    assert loaded.series[0].marks[0].values == (1, 2, 5)
    assert loaded.series[0].id == 'revenue'
    assert session.draft('Other', 'bar') is session

    # An id that is not kept fails. The chain does not insert it.
    session.discard()
    session.draft('Missing Plot', 'line', id='missing').add_series(
        'Revenue',
        [
            Mark(role='x', values=(1, 2)),
            Mark(role='y', values=(3, 4)),
        ],
    )
    with pytest.raises(ServiceError) as caught:
        session.update()
    assert caught.value.error_code == PLOT_NOT_KEPT_ID
    assert PlotConfigRepository(str(path)).get('missing') is None
    with pytest.raises(ValueError):
        session.draft('Other', 'scatter')
