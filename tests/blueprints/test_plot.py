"""Tests for the plotter session blueprint."""

# *** imports

# ** core
import ast
from pathlib import Path

# ** infra
import pytest

# ** app
from tiferet import TiferetError
from tiferet.di import DIAppServiceContainer, DIDynamicServiceContainer
from tiferet.interfaces import ServiceError
from tiferet_plot.blueprints.plot import create_plotter_session
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
from tiferet_plot.interfaces.plot import PLOT_ALREADY_KEPT_ID
from tiferet_plot.repos.plot import (
    MatrixConfigRepository,
    PlotConfigRepository,
)
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
    line = session.show(line_plot())
    bar = session.show(line_plot(kind='bar', plot_id='sales_bar'))
    picture = session.show(grid())

    # The bytes are the picture. The publication file was not opened.
    assert line.startswith(PNG_SIGNATURE)
    assert bar.startswith(PNG_SIGNATURE)
    assert picture.startswith(PNG_SIGNATURE)
    assert picture != line
    assert not path.exists()

    # Showing a kept record does not rewrite the publication.
    created = session.create(line_plot())
    before = path.read_bytes()
    shown = session.show(created)
    assert shown.startswith(PNG_SIGNATURE)
    assert path.read_bytes() == before
