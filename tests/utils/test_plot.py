"""Tests for rendering a plot to PNG bytes."""

# *** imports

# ** core
import ast
import inspect
from pathlib import Path

# ** infra
import pytest

# ** app
from tiferet.domain import ModelError
import tiferet_plot
from tiferet_plot.domain.plot import (
    Mark,
    MatrixCell,
    Plot,
    PlotMatrix,
    Series,
)
from tiferet_plot.interfaces.plot import RendererService
from tiferet_plot.mappers.plot import (
    PlotAggregate,
    SeriesAggregate,
)
from tiferet_plot.utils.plot import MatplotlibRenderer
import tiferet_plot.utils.plot as renderer_module

# *** constants

# ** constant: png_signature
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

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

    # Return the two required roles. Do not rename them.
    return [
        Mark(role='category', values=category),
        Mark(role='height', values=height),
    ]

# ** function: line_plot
def line_plot(kind='line', y=(3, 4)):
    '''
    Declare an unsaved line or scatter record.

    :param kind: The plot kind.
    :type kind: str
    :param y: The y values.
    :type y: tuple
    :return: A declared plot that has not been kept.
    :rtype: Plot
    '''

    # No id is supplied. Declaration may derive one. Render must not.
    return Plot(
        name='Sales by Region',
        kind=kind,
        series=[
            Series(name='Revenue', marks=line_marks(y=y)),
        ],
    )

# ** function: bar_plot
def bar_plot(height=(10, 12)):
    '''
    Declare an unsaved bar record.

    :param height: The bar heights.
    :type height: tuple
    :return: A declared bar plot that has not been kept.
    :rtype: Plot
    '''

    # Category and height are the roles. There is no store.
    return Plot(
        name='Sales by Region',
        kind='bar',
        series=[
            Series(name='Revenue', marks=bar_marks(height=height)),
        ],
    )

# ** function: illegal_record
def illegal_record(kind, marks):
    '''
    Build a record that bypasses declaration.

    Render must refuse it. Declaration is not this step.

    :param kind: The plot kind.
    :type kind: str
    :param marks: The series marks.
    :type marks: list
    :return: An unchecked plot record.
    :rtype: Plot
    '''

    # model_construct skips the declaration validators.
    return Plot.model_construct(
        id='sales_by_region',
        name='Sales by Region',
        kind=kind,
        description=None,
        series=[
            Series.model_construct(
                id='revenue',
                name='Revenue',
                marks=marks,
            ),
        ],
    )

# ** function: image_data
def image_data(png: bytes) -> bytes:
    '''
    Return the PNG image chunks, without ancillary text.

    :param png: The rendered bytes.
    :type png: bytes
    :return: The concatenated IDAT payloads.
    :rtype: bytes
    '''

    # A picture starts with the PNG signature.
    assert png.startswith(PNG_SIGNATURE)
    pos = 8
    parts = []
    while pos + 8 <= len(png):
        length = int.from_bytes(png[pos:pos + 4], 'big')
        kind = png[pos + 4:pos + 8]
        data = png[pos + 8:pos + 8 + length]
        if kind == b'IDAT':
            parts.append(data)
        pos += 12 + length
        if kind == b'IEND':
            break

    # Pixel data is the picture. A timestamp in a text chunk is not.
    return b''.join(parts)

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
    tree = ast.parse(path.read_text())
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)

    # Return the imported module names.
    return names

# ** function: png_size
def png_size(png: bytes) -> tuple:
    '''
    Return the pixel width and height of a PNG.

    :param png: The rendered bytes.
    :type png: bytes
    :return: Width and height.
    :rtype: tuple
    '''

    # IHDR is the first chunk. Its data starts with width and height.
    assert png.startswith(PNG_SIGNATURE)
    assert png[12:16] == b'IHDR'
    width = int.from_bytes(png[16:20], 'big')
    height = int.from_bytes(png[20:24], 'big')
    return width, height

# ** function: occupied_matrix
def occupied_matrix(plots):
    '''
    Place plots in row-major order on a 2 by 2 grid.

    :param plots: The occupied plots, at most four.
    :type plots: list
    :return: A declared matrix that has not been kept.
    :rtype: PlotMatrix
    '''

    # Empty corners are the cells that were not passed.
    cells = [
        MatrixCell(row=index // 2, col=index % 2, plot=plot)
        for index, plot in enumerate(plots)
    ]
    return PlotMatrix(
        name='Sales by Region',
        rows=2,
        cols=2,
        cells=cells,
    )

# ** function: draw
def draw(plot, monkeypatch, width=8, height=4):
    '''
    Render one plot and return the picture, the figure, and the axes.

    :param plot: The declared plot.
    :type plot: Plot
    :param monkeypatch: The pytest monkeypatch fixture.
    :type monkeypatch: Any
    :param width: The picture width, in inches.
    :type width: float
    :param height: The picture height, in inches.
    :type height: float
    :return: The PNG bytes, the figure, and the axes.
    :rtype: tuple
    '''

    # Keep the figure the renderer built. Do not import the drawing tool here.
    figures = []
    real = renderer_module.Figure

    def spy(*args, **kwargs):
        '''
        Record the figure and delegate.

        :param args: Figure arguments.
        :type args: tuple
        :param kwargs: Figure keyword arguments.
        :type kwargs: dict
        :return: The figure.
        :rtype: Any
        '''

        # One plot is one figure. The size is the caller's pair.
        figure = real(*args, **kwargs)
        figures.append((figure, kwargs.get('figsize')))
        return figure

    monkeypatch.setattr(renderer_module, 'Figure', spy)
    png = MatplotlibRenderer().render(plot, width, height)

    # Return the picture and the artists that drew it.
    figure, figsize = figures[0]
    return png, figure, figure.axes[0], figsize

# ** function: point_labels
def point_labels(axes) -> list:
    '''
    Return point-label artists. A subtitle is not one of them.

    :param axes: The drawn axes.
    :type axes: Any
    :return: Annotation artists.
    :rtype: list
    '''

    # A point label carries an offset. Figure text does not.
    return [text for text in axes.texts if hasattr(text, 'xyann')]

# ** function: subtitles
def subtitles(axes) -> list:
    '''
    Return subtitle artists.

    :param axes: The drawn axes.
    :type axes: Any
    :return: Text artists that are not point labels.
    :rtype: list
    '''

    # The subtitle is text on the axes. It is not an annotation.
    return [text for text in axes.texts if not hasattr(text, 'xyann')]

# ** function: render_parameters
def render_parameters() -> list:
    '''
    Return the parameter names of the concrete render method.

    :return: Parameter names, including self.
    :rtype: list
    '''

    # The service takes a plot and the picture size. Nothing else.
    return list(inspect.signature(MatplotlibRenderer.render).parameters)

# ** function: grid
def grid(rows, cols, plots=None):
    '''
    Declare a matrix with the given shape and occupied plots.

    :param rows: The declared row count.
    :type rows: int
    :param cols: The declared column count.
    :type cols: int
    :param plots: Occupied plots, placed in row-major order.
    :type plots: list | None
    :return: A declared matrix that has not been kept.
    :rtype: PlotMatrix
    '''

    # One plot fills the first cell when the caller does not pass any.
    if plots is None:
        plots = [line_plot()]
    cells = [
        MatrixCell(row=index // cols, col=index % cols, plot=plot)
        for index, plot in enumerate(plots)
    ]
    return PlotMatrix(
        name='Sales by Region',
        rows=rows,
        cols=cols,
        cells=cells,
    )

# ** function: refuse_figure
def refuse_figure(*args, **kwargs):
    '''
    Fail if a picture is started.

    :param args: Figure arguments.
    :type args: tuple
    :param kwargs: Figure keyword arguments.
    :type kwargs: dict
    '''

    # A refused size or record must not construct a figure.
    raise AssertionError('renderer started a picture')

# ** function: draw_matrix
def draw_matrix(matrix, monkeypatch, width=8, height=6):
    '''
    Render one matrix and return the picture, the figure, and the size.

    :param matrix: The declared matrix.
    :type matrix: PlotMatrix
    :param monkeypatch: The pytest monkeypatch fixture.
    :type monkeypatch: Any
    :param width: The picture width, in inches.
    :type width: float
    :param height: The picture height, in inches.
    :type height: float
    :return: The PNG bytes, the figure, the requested size, and render calls.
    :rtype: tuple
    '''

    # Keep the figure the renderer built. Do not import the drawing tool here.
    figures = []
    real = renderer_module.Figure

    def spy(*args, **kwargs):
        '''
        Record the figure and delegate.

        :param args: Figure arguments.
        :type args: tuple
        :param kwargs: Figure keyword arguments.
        :type kwargs: dict
        :return: The figure.
        :rtype: Any
        '''

        # One matrix is one figure. The size is the caller's pair.
        figure = real(*args, **kwargs)
        figures.append((figure, kwargs.get('figsize')))
        return figure

    monkeypatch.setattr(renderer_module, 'Figure', spy)
    renderer = MatplotlibRenderer()
    calls = []

    def wrapped(*args, **kwargs):
        '''
        Record a render call. The grid must not make one.

        :param args: Render arguments.
        :type args: tuple
        :param kwargs: Render keyword arguments.
        :type kwargs: dict
        :return: Nothing. The call is recorded and refused.
        :rtype: None
        '''

        # A cell is not a second picture.
        calls.append((args, kwargs))
        raise AssertionError('render_matrix called render')

    renderer.render = wrapped
    png = renderer.render_matrix(matrix, width, height)

    # Return the picture and the artists that drew it.
    figure, figsize = figures[0]
    return png, figure, figsize, calls

# ** function: drawn_text
def drawn_text(figure) -> list:
    '''
    Return every text string the picture drew.

    :param figure: The drawn figure.
    :type figure: Any
    :return: Text strings, including empty artists.
    :rtype: list
    '''

    # Figure text, axes text, and legend text. A missing artist is not a string.
    texts = [text.get_text() for text in figure.texts]
    suptitle = getattr(figure, '_suptitle', None)
    if suptitle is not None:
        texts.append(suptitle.get_text())
    for axes in figure.axes:
        texts.append(axes.title.get_text())
        texts.append(axes.xaxis.label.get_text())
        texts.append(axes.yaxis.label.get_text())
        texts.extend(label.get_text() for label in axes.get_xticklabels())
        texts.extend(label.get_text() for label in axes.get_yticklabels())
        texts.extend(text.get_text() for text in axes.texts)
        legend = axes.get_legend()
        if legend is not None:
            texts.extend(text.get_text() for text in legend.get_texts())
            texts.append(legend.get_title().get_text())
    for legend in figure.legends:
        texts.extend(text.get_text() for text in legend.get_texts())
        texts.append(legend.get_title().get_text())
    return texts

# ** function: axes_inches
def axes_inches(figure, axes) -> tuple:
    '''
    Return an axes box in inches.

    :param figure: The drawn figure.
    :type figure: Any
    :param axes: The axes.
    :type axes: Any
    :return: Left, bottom, width, and height, in inches.
    :rtype: tuple
    '''

    # Figure fractions become inches. The figure size is the requested pair.
    pos = axes.get_position()
    return (
        pos.x0 * figure.get_figwidth(),
        pos.y0 * figure.get_figheight(),
        pos.width * figure.get_figwidth(),
        pos.height * figure.get_figheight(),
    )

# ** function: area_inches
def area_inches(figure) -> tuple:
    '''
    Return the outer edges of the drawn subplots, in inches.

    A full grid's outer edges are the subplot area.

    :param figure: The drawn figure.
    :type figure: Any
    :return: Left, bottom, right, and top, in inches.
    :rtype: tuple
    '''

    # The outer edges include the gap between slots. They are not one cell.
    boxes = [axes_inches(figure, axes) for axes in figure.axes]
    left = min(box[0] for box in boxes)
    bottom = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes)
    top = max(box[1] + box[3] for box in boxes)
    return left, bottom, right, top

# *** tests

# ** test: line_and_scatter_render_from_x_and_y
def test_line_and_scatter_render_from_x_and_y():
    '''
    A valid line record and a valid scatter record render from x and y.
    '''

    # Both kinds draw the same roles. The pictures are not empty.
    renderer = MatplotlibRenderer()
    line = renderer.render(line_plot(), 8, 4)
    scatter = renderer.render(line_plot(kind='scatter'), 8, 4)
    changed = renderer.render(line_plot(y=(30, 40)), 8, 4)

    # The bytes are a PNG, and the y values are in the picture.
    assert isinstance(line, bytes)
    assert image_data(line)
    assert image_data(scatter)
    assert image_data(line) != image_data(changed)
    assert image_data(line) != image_data(scatter)

# ** test: bar_renders_from_category_and_height
def test_bar_renders_from_category_and_height():
    '''
    A valid bar record renders from category and height.
    '''

    # Declare a bar. The roles are not x and y.
    plot = bar_plot()
    assert [mark.role for mark in plot.series[0].marks] == [
        'category',
        'height',
    ]

    # Render, then change only the height.
    renderer = MatplotlibRenderer()
    picture = renderer.render(plot, 8, 4)
    taller = renderer.render(bar_plot(height=(80, 12)), 8, 4)

    # The picture uses the heights. The record's roles are unchanged.
    assert image_data(picture)
    assert image_data(picture) != image_data(taller)
    assert [mark.role for mark in plot.series[0].marks] == [
        'category',
        'height',
    ]

# ** test: unsaved_record_renders_without_a_store
def test_unsaved_record_renders_without_a_store(tmp_path, monkeypatch):
    '''
    Render of an unsaved record succeeds and writes no publication file.
    '''

    # A declared record has not been kept. A supplied id must stay.
    monkeypatch.chdir(tmp_path)
    plot = Plot(
        id='Custom-Id',
        name='Sales by Region',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    aggregate = PlotAggregate(
        name='Quarterly Sales',
        kind='scatter',
        series=[
            SeriesAggregate(name='Revenue', marks=line_marks()),
        ],
    )

    # Render both. Neither call has a store.
    renderer = MatplotlibRenderer()
    picture = renderer.render(plot, 8, 4)
    aggregate_picture = renderer.render(aggregate, 8, 4)

    # The pictures exist. No file was written. Ids were not rewritten.
    assert image_data(picture)
    assert image_data(aggregate_picture)
    assert plot.id == 'Custom-Id'
    assert plot.name == 'Sales by Region'
    assert aggregate.id == 'quarterly_sales'
    assert list(tmp_path.iterdir()) == []

# ** test: illegal_kind_fails_and_returns_no_picture
@pytest.mark.parametrize('kind', ['histogram', 'Line', 'pie'])
def test_illegal_kind_fails_and_returns_no_picture(kind, monkeypatch, tmp_path):
    '''
    A kind other than line, scatter, or bar fails and returns no picture.
    '''

    # Drawing must not start. A file must not appear.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        renderer_module,
        'Figure',
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError('renderer started a picture')
        ),
    )
    record = illegal_record(kind, line_marks())

    # The failure is the picture not being returned.
    with pytest.raises(ModelError):
        MatplotlibRenderer().render(record, 8, 4)
    assert list(tmp_path.iterdir()) == []

# ** test: illegal_marks_fail_and_return_no_picture
@pytest.mark.parametrize('kind,marks', [
    ('line', line_marks() + [Mark(role='category', values=('North', 'South'))]),
    ('scatter', line_marks() + [Mark(role='category', values=('North', 'South'))]),
    ('bar', bar_marks() + [Mark(role='x', values=(1, 2))]),
    ('bar', bar_marks() + [Mark(role='y', values=(1, 2))]),
    ('line', [Mark(role='y', values=(3, 4))]),
    ('bar', [Mark(role='height', values=(10, 12))]),
    ('bar', bar_marks() + [Mark(role='label', values=('North', 'South'))]),
])
def test_illegal_marks_fail_and_return_no_picture(
        kind, marks, monkeypatch, tmp_path):
    '''
    Marks that do not match the kind fail, including category on a line and x or y on a bar.
    '''

    # These marks would not survive declaration. Render still refuses them.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        renderer_module,
        'Figure',
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError('renderer started a picture')
        ),
    )

    # No picture, and no publication file.
    with pytest.raises(ModelError):
        MatplotlibRenderer().render(illegal_record(kind, marks), 8, 4)
    assert list(tmp_path.iterdir()) == []

# ** test: renderer_does_not_keep_or_import_a_store
def test_renderer_does_not_keep_or_import_a_store():
    '''
    Render does not call PlotService and does not write a publication file.
    '''

    # The utility has no store, no path argument, and no file writer.
    assert render_parameters() == ['self', 'plot', 'width', 'height']
    source = Path(renderer_module.__file__).read_text()
    assert 'PlotService' not in source
    assert 'open(' not in source
    imported = imported_modules(Path(renderer_module.__file__))
    assert 'repos' not in ' '.join(imported)
    assert not any(
        name == 'domain'
        or name.startswith('domain.')
        or 'tiferet_plot.domain' in name
        for name in imported
    )

# ** test: matplotlib_renderer_implements_the_service
def test_matplotlib_renderer_implements_the_service():
    '''
    The Matplotlib utility is a renderer service, not a figure type.
    '''

    # Callers depend on the service. The utility is one implementation.
    renderer = MatplotlibRenderer()
    assert issubclass(MatplotlibRenderer, RendererService)
    assert isinstance(renderer, RendererService)
    assert not hasattr(renderer, 'savefig')

# ** test: only_the_matplotlib_utility_imports_matplotlib
def test_only_the_matplotlib_utility_imports_matplotlib():
    '''
    The only module that imports Matplotlib is the renderer utility.
    '''

    # Scan the package and the tests. A drawing-tool import elsewhere fails.
    roots = [
        Path(tiferet_plot.__file__).parent,
        Path(__file__).resolve().parents[1],
    ]
    offenders = []
    utility = Path(renderer_module.__file__).resolve()
    for root in roots:
        for path in root.rglob('*.py'):
            imported = imported_modules(path)
            if any(
                    name == 'matplotlib' or name.startswith('matplotlib.')
                    for name in imported):
                if path.resolve() != utility:
                    offenders.append(str(path))

    # The utility itself must be the one importer.
    utility_imports = imported_modules(utility)
    assert any(name.startswith('matplotlib') for name in utility_imports)
    assert offenders == []

# ** test: drawing_tool_is_not_a_package_export
def test_drawing_tool_is_not_a_package_export():
    '''
    The package export is the service, not the drawing tool.
    '''

    # Root callers can depend on the contract without loading the utility.
    assert 'RendererService' in tiferet_plot.__all__
    assert 'MatplotlibRenderer' not in tiferet_plot.__all__
    imported = ' '.join(imported_modules(Path(tiferet_plot.__file__)))
    assert 'matplotlib' not in imported
    assert 'utils' not in imported

# ** test: render_matrix_does_not_call_render
def test_render_matrix_does_not_call_render(tmp_path, monkeypatch):
    '''
    A grid is one PNG. render is not called, and an empty position is not a subplot.
    '''

    # One occupied cell in a 2 by 2 grid. The record has not been kept.
    monkeypatch.chdir(tmp_path)
    plot = line_plot()
    matrix = occupied_matrix([plot])
    renderer = MatplotlibRenderer()
    calls = []

    def wrapped(record, width, height):
        '''
        Fail if the grid draws a cell by calling render.

        :param record: The cell plot.
        :type record: Plot
        :param width: The picture width.
        :type width: float
        :param height: The picture height.
        :type height: float
        :return: Nothing. The call is a failure.
        :rtype: None
        '''

        # A cell is a subplot. It is not a second picture.
        calls.append((record, width, height))
        raise AssertionError('render_matrix called render')

    renderer.render = wrapped
    grid = renderer.render_matrix(matrix, 8, 6)
    alone = MatplotlibRenderer().render(plot, 8, 6)

    # No call. One picture. The grid is not that cell's picture.
    assert calls == []
    assert grid.startswith(PNG_SIGNATURE)
    assert grid.count(b'IEND') == 1
    assert image_data(grid)
    assert image_data(grid) != image_data(alone)
    assert list(tmp_path.iterdir()) == []
    assert render_parameters() == ['self', 'plot', 'width', 'height']

# ** test: same_plot_id_is_two_subplots
def test_same_plot_id_is_two_subplots(monkeypatch):
    '''
    Two cells with the same plot id are two subplots. render is not called.
    '''

    # Same id, different payloads. Each cell is drawn from the record it carries.
    first = line_plot(y=(3, 4))
    second = Plot(
        id=first.id,
        name='Cost',
        kind='line',
        series=[
            Series(name='Cost', marks=line_marks(y=(30, 40))),
        ],
    )
    matrix = occupied_matrix([first, second])
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch)

    # Two subplots, two objects, one picture. The id is not a merge key.
    assert calls == []
    assert len(figure.axes) == 2
    assert first is not second
    assert first.id == second.id
    assert image_data(png)
    assert png.count(b'IEND') == 1
    assert figsize == (8, 6)

# ** test: render_matrix_fails_when_a_cell_fails
def test_render_matrix_fails_when_a_cell_fails(tmp_path, monkeypatch):
    '''
    If a cell plot would fail render, render_matrix fails and returns no picture.
    '''

    # The second cell is not a legal plot. Declaration is bypassed on purpose.
    monkeypatch.chdir(tmp_path)
    bad = illegal_record('histogram', line_marks())
    matrix = PlotMatrix.model_construct(
        id='sales_by_region',
        name='Sales by Region',
        description=None,
        rows=2,
        cols=2,
        cells=[
            MatrixCell(row=0, col=0, plot=line_plot()),
            MatrixCell.model_construct(row=0, col=1, plot=bad),
        ],
    )

    # The failure is the picture not being returned. No file is written.
    with pytest.raises(ModelError):
        MatplotlibRenderer().render_matrix(matrix, 8, 6)
    assert list(tmp_path.iterdir()) == []

# ** test: render_matrix_does_not_open_a_store
def test_render_matrix_does_not_open_a_store():
    '''
    render_matrix does not call a plot or matrix service.
    '''

    # The method takes a matrix. It has no store and no path argument.
    signature = inspect.signature(MatplotlibRenderer.render_matrix)
    assert list(signature.parameters) == ['self', 'matrix', 'width', 'height']
    source = inspect.getsource(MatplotlibRenderer.render_matrix)
    assert 'PlotService' not in source
    assert 'MatrixService' not in source
    assert 'heatmap' not in source.lower()

# ** test: no_event_imports_the_utility_or_returns_png
def test_no_event_imports_the_utility_or_returns_png():
    '''
    No create, get, list, update, or remove event imports the utility.
    '''

    # This RFP adds no events. A later event module must not draw.
    events = Path(tiferet_plot.__file__).parent / 'events'
    if not events.exists():
        return

    for path in events.rglob('*.py'):
        imported = ' '.join(imported_modules(path))
        source = path.read_text()
        assert 'utils' not in imported
        assert 'matplotlib' not in imported
        assert 'MatplotlibRenderer' not in source
        assert 'png' not in source.lower()

# ** test: grid_title_changes_the_picture
def test_grid_title_changes_the_picture():
    '''
    A matrix title is figure text. It changes the picture and is not written back.
    '''

    # The cells are the same record. The figure title is not a cell title.
    plain = line_plot()
    matrix = occupied_matrix([plain])
    titled_grid = PlotMatrix(
        name='Other Name',
        title='Quarterly sales by region',
        description='A grid subtitle.',
        rows=2,
        cols=2,
        cells=matrix.cells,
    )
    before = titled_grid.model_dump()
    renderer = MatplotlibRenderer()
    plain_png = renderer.render_matrix(matrix, 8, 6)
    titled_png = renderer.render_matrix(titled_grid, 8, 6)

    # The title is in the picture. The stored title is unchanged.
    assert image_data(plain_png) != image_data(titled_png)
    assert titled_grid.model_dump() == before
    assert titled_grid.title == 'Quarterly sales by region'

# ** test: requested_size_changes_the_picture
def test_requested_size_changes_the_picture(tmp_path, monkeypatch):
    '''
    Width 8 and height 4, and the swapped pair, are different pictures.
    '''

    # An unsaved record is enough. Render must not write a publication file.
    monkeypatch.chdir(tmp_path)
    plot = line_plot()
    renderer = MatplotlibRenderer()
    wide = renderer.render(plot, 8, 4)
    tall = renderer.render(plot, 4, 8)

    # The bytes are a PNG, and the requested extents are in the picture.
    assert image_data(wide)
    assert image_data(tall)
    assert image_data(wide) != image_data(tall)
    wide_px = png_size(wide)
    tall_px = png_size(tall)
    assert wide_px[0] > wide_px[1]
    assert tall_px[1] > tall_px[0]
    assert wide_px != tall_px
    assert list(tmp_path.iterdir()) == []
    assert 'width' not in type(plot).model_fields
    assert 'height' not in type(plot).model_fields

# ** test: omitted_or_illegal_size_returns_no_picture
@pytest.mark.parametrize('width,height', [
    (None, 4),
    (8, None),
    (0, 4),
    (8, 0),
    (-1, 4),
    (8, -2),
    (True, 4),
    (False, 4),
    (8, True),
    ('8', 4),
    (8, '6'),
])
def test_omitted_or_illegal_size_returns_no_picture(
        width, height, monkeypatch, tmp_path):
    '''
    None, zero, a negative number, a bool, or text fails and returns no picture.
    '''

    # Drawing must not start. A file must not appear.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(renderer_module, 'Figure', refuse_figure)
    plot = line_plot()
    matrix = occupied_matrix([plot])

    # The same failures apply to one plot and to the grid.
    with pytest.raises(ModelError):
        MatplotlibRenderer().render(plot, width, height)
    with pytest.raises(ModelError):
        MatplotlibRenderer().render_matrix(matrix, width, height)
    assert list(tmp_path.iterdir()) == []

# ** test: omitting_width_or_height_returns_no_picture
@pytest.mark.parametrize('call', [
    lambda renderer, plot, matrix: renderer.render(plot),
    lambda renderer, plot, matrix: renderer.render(plot, 8),
    lambda renderer, plot, matrix: renderer.render(plot, width=8),
    lambda renderer, plot, matrix: renderer.render(plot, height=4),
    lambda renderer, plot, matrix: renderer.render_matrix(matrix),
    lambda renderer, plot, matrix: renderer.render_matrix(matrix, 8),
    lambda renderer, plot, matrix: renderer.render_matrix(matrix, width=8),
    lambda renderer, plot, matrix: renderer.render_matrix(matrix, height=6),
])
def test_omitting_width_or_height_returns_no_picture(call, monkeypatch):
    '''
    A missing width or height fails. There is no default picture size.
    '''

    # The call fails before a figure exists.
    monkeypatch.setattr(renderer_module, 'Figure', refuse_figure)
    renderer = MatplotlibRenderer()
    with pytest.raises(TypeError):
        call(renderer, line_plot(), occupied_matrix([line_plot()]))

# ** test: matrix_picture_is_one_requested_size
def test_matrix_picture_is_one_requested_size(monkeypatch):
    '''
    One pair sizes the grid picture. Rows and columns do not.
    '''

    # Record every figure size. A cell call must not use a different pair.
    seen = []
    real_figure = renderer_module.Figure

    def spy(*args, **kwargs):
        '''
        Record the figure size and delegate.

        :param args: Figure arguments.
        :type args: tuple
        :param kwargs: Figure keyword arguments.
        :type kwargs: dict
        :return: The figure.
        :rtype: Any
        '''

        # The drawing tool receives inches. It does not receive a resolution.
        assert 'dpi' not in kwargs
        seen.append(kwargs.get('figsize'))
        return real_figure(*args, **kwargs)

    monkeypatch.setattr(renderer_module, 'Figure', spy)
    renderer = MatplotlibRenderer()
    one = grid(1, 1)
    two = grid(2, 2, [line_plot(), line_plot(y=(30, 40))])

    # The same pair is the same requested size on a 1 by 1 and a 2 by 2.
    first = renderer.render_matrix(one, 8, 6)
    one_sizes = list(seen)
    seen.clear()
    second = renderer.render_matrix(two, 8, 6)
    two_sizes = list(seen)
    other = renderer.render_matrix(two, 5, 7)

    # One non-empty PNG. A different pair is a different picture.
    assert image_data(first)
    assert image_data(second)
    assert image_data(other)
    assert image_data(second) != image_data(other)
    assert png_size(first) == png_size(second)
    assert png_size(second) != png_size(other)
    assert one_sizes == [(8, 6)]
    assert two_sizes == [(8, 6)]
    assert (4, 3) not in one_sizes
    source = Path(renderer_module.__file__).read_text()
    assert '4 * cols' not in source
    assert '3 * rows' not in source

# ** test: render_does_not_fill_omitted_appearance
def test_render_does_not_fill_omitted_appearance(tmp_path, monkeypatch):
    '''
    A valid picture is the requested size. Omitted appearance stays omitted.
    '''

    # An unsaved record has no size and no appearance fields filled in.
    monkeypatch.chdir(tmp_path)
    plot = line_plot()
    before = plot.model_dump()
    png, figure, axes, figsize = draw(plot, monkeypatch)

    # The bytes are a PNG of that size. No file, no dpi argument, no tight crop.
    assert image_data(png)
    assert figsize == (8, 4)
    assert tuple(figure.get_size_inches()) == (8, 4)
    assert png_size(png) == (
        round(8 * figure.dpi),
        round(4 * figure.dpi),
    )
    assert plot.model_dump() == before
    assert 'width' not in plot.model_dump()
    assert 'height' not in plot.model_dump()
    assert list(tmp_path.iterdir()) == []
    assert render_parameters() == ['self', 'plot', 'width', 'height']
    source = Path(renderer_module.__file__).read_text()
    assert 'bbox_inches' not in source
    assert 'rcParams' not in source
    assert not hasattr(axes, 'palette')

# ** test: title_and_subtitle_use_declared_text_and_sizes
def test_title_and_subtitle_use_declared_text_and_sizes(monkeypatch):
    '''
    A present title and description are drawn at the declared sizes and family.
    '''

    # No size fields. The catalog name is not the title.
    plot = Plot(
        name='Sales by Region',
        title='Quarterly sales, 2024',
        description='Revenue compared across regions.',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    before = plot.model_dump()
    png, figure, axes, figsize = draw(plot, monkeypatch)
    subtitle = subtitles(axes)

    # Absent sizes are 12 and 10, in sans-serif. The name is not a second title.
    assert image_data(png)
    assert axes.title.get_text() == 'Quarterly sales, 2024'
    assert axes.title.get_fontsize() == 12
    assert axes.title.get_fontfamily() == ['sans-serif']
    assert len(subtitle) == 1
    assert subtitle[0].get_text() == 'Revenue compared across regions.'
    assert subtitle[0].get_fontsize() == 10
    assert subtitle[0].get_fontfamily() == ['sans-serif']
    assert plot.id not in axes.title.get_text()
    assert plot.model_dump() == before
    assert plot.title_size is None
    assert plot.font_family is None

    # A present size and family are used, and stay stored.
    styled = Plot(
        name='Sales by Region',
        title='Quarterly sales, 2024',
        description='Revenue compared across regions.',
        title_size=14,
        font_family='serif',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    styled_before = styled.model_dump()
    png, figure, axes, figsize = draw(styled, monkeypatch)
    renderer = figure.canvas.get_renderer()
    title_box = axes.title.get_window_extent(renderer)
    subtitle_box = subtitles(axes)[0].get_window_extent(renderer)
    axes_box = axes.get_window_extent(renderer)

    # The subtitle sits under the title. The stored values are unchanged.
    assert axes.title.get_text() == 'Quarterly sales, 2024'
    assert axes.title.get_fontsize() == 14
    assert axes.title.get_fontfamily() == ['serif']
    assert subtitles(axes)[0].get_fontfamily() == ['serif']
    assert subtitle_box.y1 <= title_box.y0 + 1
    assert subtitle_box.y0 >= axes_box.y1 - 1
    assert styled.model_dump() == styled_before

# ** test: absent_title_draws_the_name_and_blank_description_draws_no_subtitle
def test_absent_title_draws_the_name_and_blank_description_draws_no_subtitle(
        monkeypatch):
    '''
    An absent title draws the catalog name. A blank description draws no subtitle.
    '''

    # A blank description is not a subtitle. Render does not add a subtitle field.
    plot = Plot(
        name='Sales by Region',
        description='   ',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    assert plot.title is None
    assert 'subtitle' not in type(plot).model_fields
    before = plot.model_dump()
    png, figure, axes, figsize = draw(plot, monkeypatch)

    # The name is the title for this picture only. It is not written back.
    assert axes.title.get_text() == 'Sales by Region'
    assert subtitles(axes) == []
    assert plot.model_dump() == before
    assert plot.title is None
    assert plot.description == before['description']

# ** test: unit_is_composed_beside_the_title_at_draw_time
def test_unit_is_composed_beside_the_title_at_draw_time(monkeypatch):
    '''
    A unit sits beside its title in the picture and stays apart on the record.
    '''

    # No separator field. Absent axis-label size stays absent.
    plot = Plot(
        name='Sales by Region',
        kind='line',
        x_title='Year',
        x_unit='USD',
        y_title='Revenue',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    assert 'separator' not in type(plot).model_fields
    before = plot.model_dump()
    png, figure, axes, figsize = draw(plot, monkeypatch)

    # The picture composes the pair. The record does not.
    assert axes.xaxis.label.get_text() == 'Year (USD)'
    assert axes.yaxis.label.get_text() == 'Revenue'
    assert axes.xaxis.label.get_fontsize() == 10
    assert axes.yaxis.label.get_fontsize() == 10
    assert axes.xaxis.label.get_rotation() == 0
    assert plot.model_dump() == before
    assert plot.x_title == 'Year'
    assert plot.x_unit == 'USD'
    assert plot.axis_label_size is None

# ** test: legend_reads_declared_text_and_absent_defaults
def test_legend_reads_declared_text_and_absent_defaults(monkeypatch):
    '''
    An absent legend is drawn from the series name, and is not written back.
    '''

    # One series. Absent show, location, and size stay absent.
    plot = line_plot()
    before = plot.model_dump()
    png, figure, axes, figsize = draw(plot, monkeypatch)
    legend = axes.get_legend()
    renderer = figure.canvas.get_renderer()
    legend_box = legend.get_window_extent(renderer)
    axes_box = axes.get_window_extent(renderer)

    # Upper right, inside the axes, 10 points, one column, no title.
    assert [text.get_text() for text in legend.get_texts()] == ['Revenue']
    assert legend.get_texts()[0].get_fontsize() == 10
    assert legend._ncols == 1
    assert legend.get_title().get_text() == ''
    assert legend_box.x1 <= axes_box.x1 + 1
    assert legend_box.y1 <= axes_box.y1 + 1
    assert legend_box.x0 > (axes_box.x0 + axes_box.x1) / 2
    assert legend_box.y0 > (axes_box.y0 + axes_box.y1) / 2
    assert plot.model_dump() == before
    assert plot.show_legend is None
    assert plot.legend_location is None
    assert plot.legend_size is None

    # False hides the legend and does not clear a stored place or title.
    hidden = Plot(
        name='Sales by Region',
        kind='line',
        show_legend=False,
        legend_location='lower_left',
        legend_title='Series',
        series=[
            Series(
                name='Revenue',
                legend_label='Quarterly revenue',
                marks=line_marks(),
            ),
        ],
    )
    hidden_before = hidden.model_dump()
    png, figure, axes, figsize = draw(hidden, monkeypatch)
    assert axes.get_legend() is None
    assert hidden.model_dump() == hidden_before

    # Two series are two entries, in record order, even when the text matches.
    paired = Plot(
        name='Sales by Region',
        kind='line',
        series=[
            Series(
                name='Revenue',
                legend_label='Quarterly revenue',
                marks=line_marks(),
            ),
            Series(
                name='Cost',
                legend_label='Quarterly revenue',
                marks=line_marks(y=(5, 6)),
            ),
        ],
    )
    paired_before = paired.model_dump()
    png, figure, axes, figsize = draw(paired, monkeypatch)
    labels = [text.get_text() for text in axes.get_legend().get_texts()]
    assert labels == ['Quarterly revenue', 'Quarterly revenue']
    assert paired.series[0].legend_label == 'Quarterly revenue'
    assert paired.series[0].name == 'Revenue'
    assert paired.model_dump() == paired_before
    assert 'run-1' not in labels

# ** test: outside_right_legend_stays_inside_the_requested_figure
def test_outside_right_legend_stays_inside_the_requested_figure(monkeypatch):
    '''
    outside_right sits beside the axes, inside the requested figure.
    '''

    # The token is not a margin field and is not rewritten.
    plot = Plot(
        name='Sales by Region',
        kind='line',
        legend_location='outside_right',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    assert 'margin' not in type(plot).model_fields
    before = plot.model_dump()
    png, figure, axes, figsize = draw(plot, monkeypatch, width=8, height=4)
    legend = axes.get_legend()
    renderer = figure.canvas.get_renderer()
    legend_box = legend.get_window_extent(renderer)
    axes_box = axes.get_window_extent(renderer)
    gap = (legend_box.x0 - axes_box.x1) * 72 / figure.dpi
    top = (legend_box.y1 - axes_box.y1) * 72 / figure.dpi

    # Four points to the right, top-aligned, still inside the requested inches.
    assert gap == pytest.approx(4, abs=0.5)
    assert top == pytest.approx(0, abs=0.5)
    assert legend_box.x0 > axes_box.x1
    assert legend_box.x1 <= figure.get_figwidth() * figure.dpi + 1
    assert figsize == (8, 4)
    assert tuple(figure.get_size_inches()) == (8, 4)
    assert png_size(png) == (round(8 * figure.dpi), round(4 * figure.dpi))
    assert plot.model_dump() == before
    assert plot.legend_location == 'outside_right'

# ** test: absent_color_uses_the_cycle_and_a_name_is_not_written_back
def test_absent_color_uses_the_cycle_and_a_name_is_not_written_back(monkeypatch):
    '''
    Absent color is the cycle hex. A name is mapped and not written back.
    '''

    # Neither series carries a color. The index is the series position.
    plot = Plot(
        name='Sales by Region',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
            Series(name='Cost', marks=line_marks(y=(5, 6))),
        ],
    )
    before = plot.model_dump()
    png, figure, axes, figsize = draw(plot, monkeypatch)
    assert axes.lines[0].get_color() == '#1f77b4'
    assert axes.lines[1].get_color() == '#ff7f0e'
    assert plot.series[0].color is None
    assert plot.series[1].color is None
    assert plot.model_dump() == before

    # A present color does not shift the next series off its index.
    indexed = Plot(
        name='Sales by Region',
        kind='line',
        series=[
            Series(name='Revenue', color='red', marks=line_marks()),
            Series(name='Cost', marks=line_marks(y=(5, 6))),
        ],
    )
    png, figure, axes, figsize = draw(indexed, monkeypatch)
    assert axes.lines[1].get_color() == '#ff7f0e'
    assert indexed.series[1].color is None

    # A supplied name is drawn as hex and stays a name. A hex stays a hex.
    named = Plot(
        name='Sales by Region',
        kind='line',
        series=[
            Series(name='Revenue', color='red', marks=line_marks()),
            Series(name='Cost', color='#ff0000', marks=line_marks(y=(5, 6))),
        ],
    )
    named_before = named.model_dump()
    png, figure, axes, figsize = draw(named, monkeypatch)
    assert axes.lines[0].get_color() == '#ff0000'
    assert axes.lines[1].get_color() == '#ff0000'
    assert named.series[0].color == 'red'
    assert named.series[1].color == '#ff0000'
    assert named.model_dump() == named_before

    # The dictionary is the sixteen names. grey is not a key. There is no second map.
    colors = renderer_module.CSS_COLOR_HEX
    assert set(colors) == {
        'aqua', 'black', 'blue', 'fuchsia', 'gray', 'green', 'lime',
        'maroon', 'navy', 'olive', 'purple', 'red', 'silver', 'teal',
        'white', 'yellow',
    }
    assert colors['red'] == '#ff0000'
    assert 'grey' not in colors
    source = Path(renderer_module.__file__).read_text()
    assert source.count("'aqua'") == 1
    package = Path(tiferet_plot.__file__).parent
    assert not (package / 'assets').exists()
    assert not (package / 'assets.py').exists()

# ** test: line_and_scatter_style_defaults_are_not_written_back
def test_line_and_scatter_style_defaults_are_not_written_back(
        monkeypatch, tmp_path):
    '''
    Absent line and scatter style is drawn and not stored.
    '''

    # A line with no style fields is solid, 1.5, and has no marker.
    plot = line_plot()
    before = plot.model_dump()
    png, figure, axes, figsize = draw(plot, monkeypatch)
    line = axes.lines[0]
    assert line.get_linestyle() in ('solid', '-')
    assert line.get_linewidth() == 1.5
    assert line.get_marker() in (None, 'None', 'none')
    assert plot.model_dump() == before
    assert plot.series[0].linestyle is None
    assert plot.series[0].linewidth is None
    assert plot.series[0].marker is None

    # circle stays circle. Absent markersize is 6 points. dashed is not rewritten.
    marked = Plot(
        name='Sales by Region',
        kind='line',
        series=[
            Series(
                name='Revenue',
                marker='circle',
                linestyle='dashed',
                marks=line_marks(),
            ),
        ],
    )
    marked_before = marked.model_dump()
    calls = []
    axes_cls = type(axes)
    real = axes_cls.plot

    def spy(self, *args, **kwargs):
        '''
        Record the line arguments and delegate.

        :param self: The axes.
        :type self: Any
        :param args: Positional arguments.
        :type args: tuple
        :param kwargs: Keyword arguments.
        :type kwargs: dict
        :return: The drawn lines.
        :rtype: list
        '''

        # The stored word is what the tool receives. It is not rewritten to --.
        calls.append(kwargs)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(axes_cls, 'plot', spy)
    png, figure, axes, figsize = draw(marked, monkeypatch)
    assert calls[0]['linestyle'] == 'dashed'
    assert calls[0]['marker'] == 'o'
    assert calls[0]['markersize'] == 6
    assert marked.series[0].marker == 'circle'
    assert marked.series[0].markersize is None
    assert marked.series[0].linestyle == 'dashed'
    assert marked.model_dump() == marked_before

    # An absent scatter marker draws circle and does not store circle.
    scatter_calls = []
    real_scatter = axes_cls.scatter

    def spy_scatter(self, *args, **kwargs):
        '''
        Record the scatter arguments and delegate.

        :param self: The axes.
        :type self: Any
        :param args: Positional arguments.
        :type args: tuple
        :param kwargs: Keyword arguments.
        :type kwargs: dict
        :return: The collection.
        :rtype: Any
        '''

        # The tool code is o. The record does not gain circle.
        scatter_calls.append(kwargs)
        return real_scatter(self, *args, **kwargs)

    monkeypatch.setattr(axes_cls, 'scatter', spy_scatter)
    absent = line_plot(kind='scatter')
    absent_before = absent.model_dump()
    draw(absent, monkeypatch)
    assert scatter_calls[0]['marker'] == 'o'
    assert scatter_calls[0]['s'] == 36
    assert absent.series[0].marker is None
    assert absent.model_dump() == absent_before

    # no_marker draws nothing and stays no_marker.
    scatter_calls.clear()
    bare = Plot(
        name='Sales by Region',
        kind='scatter',
        series=[
            Series(name='Revenue', marker='no_marker', marks=line_marks()),
        ],
    )
    bare_before = bare.model_dump()
    draw(bare, monkeypatch)
    assert scatter_calls[0]['marker'] == 'none'
    assert bare.series[0].marker == 'no_marker'
    assert bare.model_dump() == bare_before

    # A scatter that carries linestyle fails, and no picture is returned.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(renderer_module, 'Figure', refuse_figure)
    illegal = Plot.model_construct(
        id='sales_by_region',
        name='Sales by Region',
        kind='scatter',
        description=None,
        series=[
            Series.model_construct(
                id='revenue',
                name='Revenue',
                marks=line_marks(),
                linestyle='solid',
            ),
        ],
    )
    with pytest.raises(ModelError):
        MatplotlibRenderer().render(illegal, 8, 4)
    assert list(tmp_path.iterdir()) == []

# ** test: grouped_bars_keep_the_slot_shift_and_category_ticks
def test_grouped_bars_keep_the_slot_shift_and_category_ticks(monkeypatch):
    '''
    Two bar series sit beside each other. A scale changes width, not shift.
    '''

    # Absent bar width, rotation, and tick size stay absent.
    plot = Plot(
        name='Sales by Region',
        kind='bar',
        series=[
            Series(name='Revenue', marks=bar_marks()),
            Series(name='Cost', marks=bar_marks(height=(8, 9))),
        ],
    )
    before = plot.model_dump()
    png, figure, axes, figsize = draw(plot, monkeypatch)
    first, second = axes.containers
    north = first.patches[0]
    south = first.patches[1]
    other = second.patches[0]

    # Slot width is 0.4. The shift centers the pair on the category tick.
    assert north.get_width() == pytest.approx(0.4)
    assert north.get_x() + north.get_width() / 2 == pytest.approx(-0.2)
    assert south.get_x() + south.get_width() / 2 == pytest.approx(0.8)
    assert other.get_x() + other.get_width() / 2 == pytest.approx(0.2)
    assert [label.get_text() for label in axes.get_xticklabels()] == [
        'North',
        'South',
    ]
    assert axes.get_xticklabels()[0].get_fontsize() == 8
    assert axes.get_xticklabels()[0].get_rotation() == 45
    assert axes.get_xticklabels()[0].get_ha() == 'right'
    assert plot.model_dump() == before
    assert plot.series[0].bar_width is None
    assert plot.x_tick_rotation is None
    assert plot.tick_label_size is None

    # A scale of 2 draws width 0.8 at the same shift. A stored 1 stays 1.
    scaled = Plot(
        name='Sales by Region',
        kind='bar',
        x_tick_rotation=0,
        series=[
            Series(name='Revenue', bar_width=1, marks=bar_marks()),
            Series(name='Cost', bar_width=2, marks=bar_marks(height=(8, 9))),
        ],
    )
    scaled_before = scaled.model_dump()
    png, figure, axes, figsize = draw(scaled, monkeypatch)
    first, second = axes.containers
    assert first.patches[0].get_width() == pytest.approx(0.4)
    assert second.patches[0].get_width() == pytest.approx(0.8)
    assert second.patches[0].get_x() + second.patches[0].get_width() / 2 == (
        pytest.approx(0.2)
    )
    assert axes.get_xticklabels()[0].get_rotation() == 0
    assert scaled.series[0].bar_width == 1
    assert scaled.series[1].bar_width == 2
    assert scaled.x_tick_rotation == 0
    assert scaled.model_dump() == scaled_before

# ** test: text_axis_ticks_and_point_labels_are_drawing_policy
def test_text_axis_ticks_and_point_labels_are_drawing_policy(monkeypatch):
    '''
    Text x is tick text. A point label is beside the point, not a tick.
    '''

    # Rotation and size are absent. The second label is an empty string.
    plot = Plot(
        name='Sales by Region',
        kind='line',
        series=[
            Series(
                name='Revenue',
                marks=[
                    Mark(role='x', values=('alpha', 'beta')),
                    Mark(role='y', values=(3, 4)),
                    Mark(role='label', values=('run-1', '')),
                ],
            ),
        ],
    )
    before = plot.model_dump()
    png, figure, axes, figsize = draw(plot, monkeypatch)
    labels = point_labels(axes)

    # Text ticks are 45 and 8. Numeric y ticks are 0 and 8. None is written back.
    assert [label.get_text() for label in axes.get_xticklabels()] == [
        'alpha',
        'beta',
    ]
    assert axes.get_xticklabels()[0].get_rotation() == 45
    assert axes.get_xticklabels()[0].get_fontsize() == 8
    assert axes.get_yticklabels()[0].get_rotation() == 0
    assert axes.get_yticklabels()[0].get_fontsize() == 8
    assert len(labels) == 1
    assert labels[0].get_text() == 'run-1'
    assert labels[0].get_fontsize() == 8
    assert labels[0].get_rotation() == 0
    assert labels[0].xyann == (4, 4)
    assert axes.title.get_text() != 'run-1'
    assert 'run-1' not in [
        label.get_text() for label in axes.get_xticklabels()
    ]
    assert [text.get_text() for text in axes.get_legend().get_texts()] == [
        'Revenue',
    ]
    assert plot.model_dump() == before
    assert list(plot.series[0].marks[0].values) == ['alpha', 'beta']

    # A stored rotation of 90 does not rotate the point label.
    turned = Plot(
        name='Sales by Region',
        kind='line',
        x_tick_rotation=90,
        series=plot.series,
    )
    turned_before = turned.model_dump()
    png, figure, axes, figsize = draw(turned, monkeypatch)
    assert axes.get_xticklabels()[0].get_rotation() == 90
    assert point_labels(axes)[0].get_rotation() == 0
    assert turned.x_tick_rotation == 90
    assert turned.model_dump() == turned_before

# ** test: decimal_count_formats_numeric_ticks_and_is_not_written_back
def test_decimal_count_formats_numeric_ticks_and_is_not_written_back(monkeypatch):
    '''
    A stored decimal count formats a numeric axis. Absent does not.
    '''

    # Absent is not stored as 0, and it does not set a format.
    plot = line_plot()
    before = plot.model_dump()
    png, figure, axes, figsize = draw(plot, monkeypatch)
    assert type(axes.xaxis.get_major_formatter()).__name__ != 'FormatStrFormatter'
    assert plot.x_tick_decimals is None
    assert plot.model_dump() == before
    assert not any('format' in name for name in type(plot).model_fields)

    # Zero shows no digits after the decimal and stays 0.
    zero = Plot(
        name='Sales by Region',
        kind='line',
        x_tick_decimals=0,
        y_tick_decimals=2,
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    zero_before = zero.model_dump()
    png, figure, axes, figsize = draw(zero, monkeypatch)
    assert axes.xaxis.get_major_formatter().fmt == '%.0f'
    assert axes.xaxis.get_major_formatter()(4) == '4'
    assert '.' not in axes.xaxis.get_major_formatter()(4)
    assert axes.yaxis.get_major_formatter().fmt == '%.2f'
    assert axes.yaxis.get_major_formatter()(3) == '3.00'
    assert zero.x_tick_decimals == 0
    assert zero.model_dump() == zero_before

    # On a bar, x decimals do not format category and are not cleared.
    bars = Plot(
        name='Sales by Region',
        kind='bar',
        x_tick_decimals=2,
        series=[
            Series(name='Revenue', marks=bar_marks()),
        ],
    )
    bars_before = bars.model_dump()
    png, figure, axes, figsize = draw(bars, monkeypatch)
    assert [label.get_text() for label in axes.get_xticklabels()] == [
        'North',
        'South',
    ]
    assert bars.x_tick_decimals == 2
    assert bars.model_dump() == bars_before

# ** test: text_on_both_axes_or_a_bar_label_returns_no_picture
def test_text_on_both_axes_or_a_bar_label_returns_no_picture(
        monkeypatch, tmp_path):
    '''
    Text x with text y fails. A bar that carries label fails. No picture.
    '''

    # Declaration is bypassed. Render still does not derive an id or rename a role.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(renderer_module, 'Figure', refuse_figure)
    both = illegal_record(
        'line',
        [
            Mark(role='x', values=('alpha', 'beta')),
            Mark(role='y', values=('one', 'two')),
        ],
    )
    labeled = illegal_record(
        'bar',
        bar_marks() + [Mark(role='label', values=('North', 'South'))],
    )
    with pytest.raises(ModelError):
        MatplotlibRenderer().render(both, 8, 4)
    with pytest.raises(ModelError):
        MatplotlibRenderer().render(labeled, 8, 4)
    assert both.id == 'sales_by_region'
    assert [mark.role for mark in labeled.series[0].marks] == [
        'category',
        'height',
        'label',
    ]
    assert list(tmp_path.iterdir()) == []

# ** test: one_occupied_corner_is_one_subplot
def test_one_occupied_corner_is_one_subplot(tmp_path, monkeypatch):
    '''
    One occupied cell is one subplot. Empty corners have no axes and are not spanned.
    '''

    # Row 0, column 1. The other three positions are the absence of a cell.
    monkeypatch.chdir(tmp_path)
    plot = line_plot()
    matrix = PlotMatrix(
        name='Sales by Region',
        rows=2,
        cols=2,
        cells=[
            MatrixCell(row=0, col=1, plot=plot),
        ],
    )
    before = matrix.model_dump()
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch, width=8, height=6)
    alone = MatplotlibRenderer().render(plot, 8, 6)
    one = grid(1, 1)
    two = grid(2, 2, [line_plot(), line_plot(y=(30, 40))])
    same = MatplotlibRenderer().render_matrix(one, 8, 6)
    other_grid = MatplotlibRenderer().render_matrix(two, 8, 6)
    other_size = MatplotlibRenderer().render_matrix(two, 5, 7)

    # One subplot, in the right-hand top slot. It does not span the empty corners.
    assert calls == []
    assert image_data(png)
    assert image_data(png) != image_data(alone)
    assert len(figure.axes) == 1
    assert figure.axes[0].title.get_text() == ''
    pos = figure.axes[0].get_position()
    assert pos.x0 > 0.5
    assert pos.y0 > 0.5
    assert pos.width < 0.5
    assert pos.height < 0.5
    assert figsize == (8, 6)
    assert tuple(figure.get_size_inches()) == (8, 6)
    assert png_size(same) == png_size(other_grid)
    assert image_data(other_grid) != image_data(other_size)
    assert matrix.model_dump() == before
    assert 'width' not in matrix.model_dump()
    assert 'height' not in matrix.model_dump()
    assert list(tmp_path.iterdir()) == []

# ** test: absent_grid_title_draws_the_name_and_not_the_cell_text
def test_absent_grid_title_draws_the_name_and_not_the_cell_text(monkeypatch):
    '''
    An absent grid title draws the matrix name. A cell's text is not the figure title.
    '''

    # No size fields. The cell title is not drawn inside the grid.
    cell = Plot(
        id='revenue_plot',
        name='Revenue',
        title='Quarterly cell',
        description='A cell claim.',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    matrix = PlotMatrix(
        id='grid-id',
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=cell),
        ],
    )
    assert matrix.title is None
    before = matrix.model_dump()
    cell_before = cell.model_dump()
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch)
    texts = drawn_text(figure)

    # 12 points, sans-serif. The name is not written into title. The id is not drawn.
    assert image_data(png)
    assert figure._suptitle.get_text() == 'Sales by Region'
    assert figure._suptitle.get_fontsize() == 12
    assert figure._suptitle.get_fontfamily() == ['sans-serif']
    assert 'A cell claim.' not in texts
    assert 'Quarterly cell' not in texts
    assert 'grid-id' not in texts
    assert all(axes.title.get_text() == '' for axes in figure.axes)
    assert matrix.model_dump() == before
    assert matrix.title is None
    assert matrix.title_size is None
    assert matrix.font_family is None
    assert cell.model_dump() == cell_before

# ** test: present_grid_title_and_subtitle_use_matrix_sizes
def test_present_grid_title_and_subtitle_use_matrix_sizes(monkeypatch):
    '''
    A present title and description are the figure title and the subtitle under it.
    '''

    # The catalog name is not a second title. The stored sizes stay stored.
    matrix = PlotMatrix(
        name='Sales by Region',
        title='Quarterly sales by region',
        description='Revenue compared across regions.',
        title_size=14,
        subtitle_size=11,
        font_family='serif',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=line_plot()),
        ],
    )
    before = matrix.model_dump()
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch)
    subtitle = [
        text for text in figure.texts
        if text.get_text() == 'Revenue compared across regions.'
    ]
    renderer = figure.canvas.get_renderer()
    title_box = figure._suptitle.get_window_extent(renderer)
    subtitle_box = subtitle[0].get_window_extent(renderer)
    axes_box = figure.axes[0].get_window_extent(renderer)

    # The subtitle sits under the title and above the subplot. Values are unchanged.
    assert figure._suptitle.get_text() == 'Quarterly sales by region'
    assert figure._suptitle.get_fontsize() == 14
    assert figure._suptitle.get_fontfamily() == ['serif']
    assert len(subtitle) == 1
    assert subtitle[0].get_fontsize() == 11
    assert subtitle[0].get_fontfamily() == ['serif']
    assert subtitle_box.y1 <= title_box.y0 + 1
    assert subtitle_box.y0 >= axes_box.y1 - 1
    assert 'Sales by Region' not in [
        figure._suptitle.get_text(),
        subtitle[0].get_text(),
    ]
    assert matrix.model_dump() == before

    # A blank title is read as absent. A blank description draws no subtitle.
    blank = PlotMatrix.model_construct(
        id='sales_by_region',
        name='Sales by Region',
        title='   ',
        description='   ',
        rows=1,
        cols=1,
        cells=matrix.cells,
        show_legend=None,
        legend_location=None,
        legend_title=None,
        title_size=None,
        subtitle_size=None,
        legend_size=None,
        font_family=None,
        row_spacing=None,
        col_spacing=None,
    )
    blank_before = blank.model_dump()
    png, figure, figsize, calls = draw_matrix(blank, monkeypatch)
    assert figure._suptitle.get_text() == 'Sales by Region'
    assert '   ' not in drawn_text(figure)
    assert blank.model_dump() == blank_before
    assert blank.title == '   '
    assert blank.description == '   '

# ** test: cell_axis_text_is_subplot_text
def test_cell_axis_text_is_subplot_text(monkeypatch):
    '''
    A cell's axis text is that subplot's label. render of the plot alone still titles it.
    '''

    # No separator field. The matrix does not carry the cell's axis text.
    plot = Plot(
        name='Revenue',
        title='Quarterly cell',
        kind='line',
        x_title='Year',
        x_unit='USD',
        y_title='Revenue',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    matrix = PlotMatrix(
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=plot),
        ],
    )
    assert 'separator' not in type(plot).model_fields
    assert 'x_title' not in type(matrix).model_fields
    before = plot.model_dump()
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch)
    axes = figure.axes[0]

    # The composed label is subplot text. It is not written back.
    assert axes.xaxis.label.get_text() == 'Year (USD)'
    assert axes.yaxis.label.get_text() == 'Revenue'
    assert axes.xaxis.label.get_fontsize() == 10
    assert axes.yaxis.label.get_fontsize() == 10
    assert axes.get_xticklabels()
    assert plot.model_dump() == before
    assert plot.x_title == 'Year'
    assert plot.x_unit == 'USD'
    assert plot.axis_label_size is None

    # A lone render still draws the plot title. It gains no hide flag.
    alone_png, alone_figure, alone_axes, alone_size = draw(plot, monkeypatch)
    assert alone_axes.title.get_text() == 'Quarterly cell'
    assert 'hide' not in render_parameters()
    assert 'Quarterly cell' not in drawn_text(figure)

# ** test: a_cell_legend_is_not_drawn_in_the_grid
def test_a_cell_legend_is_not_drawn_in_the_grid(monkeypatch):
    '''
    A cell legend is not drawn, whether the cell asks or not. The fields stay.
    '''

    # Absent and true are the same for this picture. Neither is cleared.
    absent = Plot(
        name='Revenue',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    asked = Plot(
        name='Cost',
        kind='line',
        show_legend=True,
        legend_location='lower_left',
        series=[
            Series(name='Cost', marks=line_marks(y=(5, 6))),
        ],
    )
    matrix = PlotMatrix(
        name='Sales by Region',
        rows=1,
        cols=2,
        cells=[
            MatrixCell(row=0, col=0, plot=absent),
            MatrixCell(row=0, col=1, plot=asked),
        ],
    )
    before = matrix.model_dump()
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch)

    # No axes legend, and no grid legend. The cell flags are unchanged.
    assert figure.legends == []
    assert [axes.get_legend() for axes in figure.axes] == [None, None]
    assert matrix.model_dump() == before
    assert absent.show_legend is None
    assert asked.show_legend is True
    assert asked.legend_location == 'lower_left'

# ** test: absent_or_false_grid_legend_is_not_drawn
def test_absent_or_false_grid_legend_is_not_drawn(monkeypatch):
    '''
    An absent grid legend stays absent. False draws none and does not clear a place.
    '''

    # Absent is not stored as false.
    absent = PlotMatrix(
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=line_plot()),
        ],
    )
    absent_before = absent.model_dump()
    png, figure, figsize, calls = draw_matrix(absent, monkeypatch)
    assert figure.legends == []
    assert absent.show_legend is None
    assert absent.model_dump() == absent_before

    # A stored place stays, and it is not drawn.
    hidden = PlotMatrix(
        name='Sales by Region',
        show_legend=False,
        legend_location='lower_left',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=line_plot()),
        ],
    )
    hidden_before = hidden.model_dump()
    png, figure, figsize, calls = draw_matrix(hidden, monkeypatch)
    assert figure.legends == []
    assert hidden.show_legend is False
    assert hidden.legend_location == 'lower_left'
    assert hidden.model_dump() == hidden_before

# ** test: grid_legend_is_the_union_at_the_upper_right
def test_grid_legend_is_the_union_at_the_upper_right(monkeypatch):
    '''
    A requested grid legend is one union, inside the subplot area, not inside a cell.
    '''

    # Stored bottom-first. The union order is row, then column.
    cost = Plot(
        name='Cost plot',
        kind='line',
        series=[
            Series(name='Cost', marks=line_marks(y=(5, 6))),
        ],
    )
    revenue = Plot(
        name='Revenue plot',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    matrix = PlotMatrix(
        name='Sales by Region',
        show_legend=True,
        rows=1,
        cols=2,
        cells=[
            MatrixCell(row=0, col=1, plot=cost),
            MatrixCell(row=0, col=0, plot=revenue),
        ],
    )
    assert 'legend_entries' not in type(matrix).model_fields
    before = matrix.model_dump()
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch)
    legend = figure.legends[0]
    renderer = figure.canvas.get_renderer()
    legend_box = legend.get_window_extent(renderer)
    left, bottom, right, top = area_inches(figure)
    legend_left = legend_box.x0 / figure.dpi
    legend_bottom = legend_box.y0 / figure.dpi
    legend_right = legend_box.x1 / figure.dpi
    legend_top = legend_box.y1 / figure.dpi

    # Upper right of the subplot area, 10 points, one column, sans-serif.
    assert [text.get_text() for text in legend.get_texts()] == [
        'Revenue',
        'Cost',
    ]
    assert legend.get_texts()[0].get_fontsize() == 10
    assert legend.get_texts()[0].get_fontfamily() == ['sans-serif']
    assert legend._ncols == 1
    assert legend.get_title().get_text() == ''
    assert legend_right <= right + 0.02
    assert legend_top <= top + 0.02
    assert legend_left > (left + right) / 2
    assert legend_bottom > (bottom + top) / 2
    assert [axes.get_legend() for axes in figure.axes] == [None, None]
    assert matrix.model_dump() == before
    assert matrix.show_legend is True
    assert matrix.legend_location is None
    assert matrix.legend_size is None
    assert matrix.legend_title is None

# ** test: the_first_series_owns_a_repeated_legend_text
def test_the_first_series_owns_a_repeated_legend_text(monkeypatch):
    '''
    Two series with the same legend text are one entry. The first owns the handle.
    '''

    # Same swatch, different stroke width. The later cell is stored first.
    later = Plot(
        name='Later',
        kind='line',
        series=[
            Series(
                name='Later',
                legend_label='Revenue',
                color='red',
                linewidth=1,
                marks=line_marks(y=(5, 6)),
            ),
        ],
    )
    first = Plot(
        name='First',
        kind='line',
        series=[
            Series(
                name='First',
                legend_label='Revenue',
                color='red',
                linewidth=4,
                marks=line_marks(),
            ),
        ],
    )
    matrix = PlotMatrix(
        name='Sales by Region',
        show_legend=True,
        rows=1,
        cols=2,
        cells=[
            MatrixCell(row=0, col=1, plot=later),
            MatrixCell(row=0, col=0, plot=first),
        ],
    )
    before = matrix.model_dump()
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch)
    legend = figure.legends[0]

    # One entry. The handle is the owning series, not a stored list.
    assert [text.get_text() for text in legend.get_texts()] == ['Revenue']
    assert legend.legend_handles[0].get_linewidth() == 4
    assert matrix.model_dump() == before
    assert first.series[0].legend_label == 'Revenue'
    assert first.series[0].name == 'First'

# ** test: legend_title_is_drawn_only_when_present
def test_legend_title_is_drawn_only_when_present(monkeypatch):
    '''
    An absent legend title is not filled from the name. A present title uses legend size.
    '''

    # The matrix name is not a legend title.
    plain = PlotMatrix(
        name='Sales by Region',
        show_legend=True,
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=line_plot()),
        ],
    )
    plain_before = plain.model_dump()
    png, figure, figsize, calls = draw_matrix(plain, monkeypatch)
    assert figure.legends[0].get_title().get_text() == ''
    assert plain.legend_title is None
    assert plain.model_dump() == plain_before

    # A present title is drawn at the legend size, for the title and the entries.
    titled = PlotMatrix(
        name='Sales by Region',
        show_legend=True,
        legend_title='Series',
        legend_size=13,
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=line_plot()),
        ],
    )
    titled_before = titled.model_dump()
    png, figure, figsize, calls = draw_matrix(titled, monkeypatch)
    legend = figure.legends[0]
    assert legend.get_title().get_text() == 'Series'
    assert legend.get_title().get_fontsize() == 13
    assert legend.get_texts()[0].get_fontsize() == 13
    assert titled.model_dump() == titled_before

# ** test: outside_right_grid_legend_stays_inside_the_requested_figure
def test_outside_right_grid_legend_stays_inside_the_requested_figure(
        monkeypatch):
    '''
    outside_right sits beside the subplot area, inside the requested figure.
    '''

    # The token is not a margin field and is not rewritten.
    matrix = PlotMatrix(
        name='Sales by Region',
        show_legend=True,
        legend_location='outside_right',
        rows=1,
        cols=2,
        cells=[
            MatrixCell(row=0, col=0, plot=line_plot()),
            MatrixCell(row=0, col=1, plot=line_plot(y=(30, 40))),
        ],
    )
    assert 'margin' not in type(matrix).model_fields
    before = matrix.model_dump()
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch, width=8, height=6)
    legend = figure.legends[0]
    renderer = figure.canvas.get_renderer()
    legend_box = legend.get_window_extent(renderer)
    left, bottom, right, top = area_inches(figure)
    gap = legend_box.x0 / figure.dpi - right
    top_delta = legend_box.y1 / figure.dpi - top
    source = Path(renderer_module.__file__).read_text()

    # Four points to the right, top-aligned, still the requested inches.
    assert gap * 72 == pytest.approx(4, abs=0.5)
    assert top_delta * 72 == pytest.approx(0, abs=0.5)
    assert legend_box.x0 > right * figure.dpi
    assert legend_box.x1 <= figure.get_figwidth() * figure.dpi + 1
    assert figsize == (8, 6)
    assert tuple(figure.get_size_inches()) == (8, 6)
    assert png_size(png) == (round(8 * figure.dpi), round(6 * figure.dpi))
    assert matrix.legend_location == 'outside_right'
    assert matrix.model_dump() == before
    assert 'tight_layout' not in source
    assert 'constrained_layout' not in source
    assert 'bbox_inches' not in source
    assert 'imshow' not in source

# ** test: cell_color_uses_the_cell_index_and_the_one_dictionary
def test_cell_color_uses_the_cell_index_and_the_one_dictionary(monkeypatch):
    '''
    A name is mapped and not written back. The cycle index stays inside the cell.
    '''

    # The second cell's first series is index 0 in that cell, not index 2 of the grid.
    named = Plot(
        name='Named',
        kind='line',
        series=[
            Series(name='Revenue', color='red', marks=line_marks()),
            Series(name='Cost', marks=line_marks(y=(5, 6))),
        ],
    )
    plain = Plot(
        name='Plain',
        kind='line',
        series=[
            Series(name='Other', marks=line_marks(y=(7, 8))),
        ],
    )
    matrix = PlotMatrix(
        name='Sales by Region',
        rows=1,
        cols=2,
        cells=[
            MatrixCell(row=0, col=0, plot=named),
            MatrixCell(row=0, col=1, plot=plain),
        ],
    )
    before = matrix.model_dump()
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch)
    first, second = figure.axes

    # red stays red. The next cell starts the cycle again.
    assert first.lines[0].get_color() == '#ff0000'
    assert first.lines[1].get_color() == '#ff7f0e'
    assert second.lines[0].get_color() == '#1f77b4'
    assert named.series[0].color == 'red'
    assert named.series[1].color is None
    assert plain.series[0].color is None
    assert matrix.model_dump() == before
    assert renderer_module.CSS_COLOR_HEX['red'] == '#ff0000'
    package = Path(tiferet_plot.__file__).parent
    assert not (package / 'assets').exists()
    assert Path(renderer_module.__file__).read_text().count("'aqua'") == 1

# ** test: grouped_bars_and_point_labels_stay_inside_the_cell
def test_grouped_bars_and_point_labels_stay_inside_the_cell(monkeypatch):
    '''
    Grouped bars and point labels use the cell drawing rules. A second cell does not share them.
    '''

    # Absent bar width, rotation, and tick size stay absent.
    bars = Plot(
        name='Bars',
        kind='bar',
        series=[
            Series(name='Revenue', marks=bar_marks()),
            Series(name='Cost', marks=bar_marks(height=(8, 9))),
        ],
    )
    other = Plot(
        name='Other',
        kind='bar',
        series=[
            Series(
                name='East',
                marks=bar_marks(category=('East', 'West'), height=(1, 2)),
            ),
        ],
    )
    labeled = Plot(
        name='Labeled',
        kind='line',
        font_family='serif',
        x_title='Year',
        series=[
            Series(
                name='Revenue',
                marks=[
                    Mark(role='x', values=(1, 2)),
                    Mark(role='y', values=(3, 4)),
                    Mark(role='label', values=('run-1', '')),
                ],
            ),
        ],
    )
    matrix = PlotMatrix(
        name='Sales by Region',
        rows=1,
        cols=2,
        cells=[
            MatrixCell(row=0, col=0, plot=bars),
            MatrixCell(row=0, col=1, plot=other),
        ],
    )
    before = matrix.model_dump()
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch)
    bar_axes = figure.axes[0]
    other_axes = figure.axes[1]

    # Slot width is 0.4. The second cell keeps its own categories.
    assert bar_axes.containers[0].patches[0].get_width() == pytest.approx(0.4)
    assert [label.get_text() for label in bar_axes.get_xticklabels()] == [
        'North',
        'South',
    ]
    assert bar_axes.get_xticklabels()[0].get_rotation() == 45
    assert bar_axes.get_xticklabels()[0].get_fontsize() == 8
    assert bar_axes.get_xticklabels()[0].get_ha() == 'right'
    assert [label.get_text() for label in other_axes.get_xticklabels()] == [
        'East',
        'West',
    ]
    assert bars.series[0].bar_width is None
    assert bars.x_tick_rotation is None
    assert bars.tick_label_size is None
    assert matrix.model_dump() == before

    # The point label is beside the point. It is not the figure title.
    labeled_matrix = PlotMatrix(
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=labeled),
        ],
    )
    labeled_before = labeled.model_dump()
    png, figure, figsize, calls = draw_matrix(labeled_matrix, monkeypatch)
    labels = point_labels(figure.axes[0])
    assert len(labels) == 1
    assert labels[0].get_text() == 'run-1'
    assert labels[0].get_fontsize() == 8
    assert labels[0].get_rotation() == 0
    assert labels[0].xyann == (4, 4)
    assert labels[0].get_fontfamily() == ['serif']
    assert figure.axes[0].xaxis.label.get_fontfamily() == ['serif']
    assert figure.axes[0].get_xticklabels()[0].get_fontfamily() == ['serif']
    assert figure._suptitle.get_text() == 'Sales by Region'
    assert figure._suptitle.get_fontfamily() == ['sans-serif']
    assert figure._suptitle.get_text() != 'run-1'
    assert 'run-1' not in [
        label.get_text() for label in figure.axes[0].get_xticklabels()
    ]
    assert labeled.font_family == 'serif'
    assert labeled_matrix.font_family is None
    assert labeled.model_dump() == labeled_before

# ** test: spacing_is_a_fraction_of_the_declared_slot
def test_spacing_is_a_fraction_of_the_declared_slot(monkeypatch):
    '''
    Absent spacing is the fraction 0.2. A stored fraction stays that fraction.
    '''

    # Four occupied cells, so the gap between them is the declared fraction.
    plots = [line_plot(y=(3 + index, 4 + index)) for index in range(4)]
    matrix = PlotMatrix(
        name='Sales by Region',
        rows=2,
        cols=2,
        cells=[
            MatrixCell(row=index // 2, col=index % 2, plot=plot)
            for index, plot in enumerate(plots)
        ],
    )
    before = matrix.model_dump()
    png, figure, figsize, calls = draw_matrix(matrix, monkeypatch)
    boxes = sorted(
        [axes_inches(figure, axes) for axes in figure.axes],
        key=lambda box: (-box[1], box[0]),
    )
    col_gap = (boxes[1][0] - (boxes[0][0] + boxes[0][2])) / boxes[0][2]
    row_gap = (boxes[0][1] - (boxes[2][1] + boxes[2][3])) / boxes[0][3]

    # 0.2 of the slot, not inches, and not written back.
    assert col_gap == pytest.approx(0.2)
    assert row_gap == pytest.approx(0.2)
    assert matrix.row_spacing is None
    assert matrix.col_spacing is None
    assert matrix.model_dump() == before

    # A stored 0 is a gap of zero. 0.5 stays 0.5.
    spaced = PlotMatrix(
        name='Sales by Region',
        rows=2,
        cols=2,
        row_spacing=0,
        col_spacing=0.5,
        cells=matrix.cells,
    )
    spaced_before = spaced.model_dump()
    png, figure, figsize, calls = draw_matrix(spaced, monkeypatch)
    boxes = sorted(
        [axes_inches(figure, axes) for axes in figure.axes],
        key=lambda box: (-box[1], box[0]),
    )
    col_gap = (boxes[1][0] - (boxes[0][0] + boxes[0][2])) / boxes[0][2]
    row_gap = (boxes[0][1] - (boxes[2][1] + boxes[2][3])) / boxes[0][3]
    assert col_gap == pytest.approx(0.5)
    assert row_gap == pytest.approx(0)
    assert spaced.row_spacing == 0
    assert spaced.col_spacing == 0.5
    assert spaced.model_dump() == spaced_before

    # A 1-by-1 may carry a gap. The drawer does not fail.
    single = PlotMatrix(
        name='Sales by Region',
        rows=1,
        cols=1,
        row_spacing=0.5,
        col_spacing=0.5,
        cells=[
            MatrixCell(row=0, col=0, plot=line_plot()),
        ],
    )
    png, figure, figsize, calls = draw_matrix(single, monkeypatch)
    assert len(figure.axes) == 1
    assert single.row_spacing == 0.5
    assert single.col_spacing == 0.5

# ** test: a_cell_that_cannot_be_drawn_returns_no_grid
def test_a_cell_that_cannot_be_drawn_returns_no_grid(tmp_path, monkeypatch):
    '''
    A bar that carries label, or text on both axes, makes the grid fail.
    '''

    # Declaration is bypassed. No partial grid and no file.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(renderer_module, 'Figure', refuse_figure)
    labeled = illegal_record(
        'bar',
        bar_marks() + [Mark(role='label', values=('North', 'South'))],
    )
    both = illegal_record(
        'line',
        [
            Mark(role='x', values=('alpha', 'beta')),
            Mark(role='y', values=('one', 'two')),
        ],
    )
    for bad in (labeled, both):
        matrix = PlotMatrix.model_construct(
            id='sales_by_region',
            name='Sales by Region',
            description=None,
            rows=1,
            cols=2,
            cells=[
                MatrixCell(row=0, col=0, plot=line_plot()),
                MatrixCell.model_construct(row=0, col=1, plot=bad),
            ],
            show_legend=None,
            legend_location=None,
            legend_title=None,
            title_size=None,
            subtitle_size=None,
            legend_size=None,
            font_family=None,
            row_spacing=None,
            col_spacing=None,
        )
        with pytest.raises(ModelError):
            MatplotlibRenderer().render_matrix(matrix, 8, 6)
    assert list(tmp_path.iterdir()) == []
    source = inspect.getsource(MatplotlibRenderer.render_matrix)
    assert 'self.render' not in source
    assert 'PlotService' not in source
    assert 'MatrixService' not in source
