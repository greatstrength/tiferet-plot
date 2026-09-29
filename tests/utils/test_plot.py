"""Tests for rendering a plot to PNG bytes."""

# *** imports

# ** core
import ast
import inspect
from pathlib import Path

# ** infra
import pytest

# ** app
import tiferet_plot
from tiferet_plot.domain.plot import (
    Mark,
    Plot,
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

# ** function: render_parameters
def render_parameters() -> list:
    '''
    Return the parameter names of the concrete render method.

    :return: Parameter names, including self.
    :rtype: list
    '''

    # The service takes a plot and nothing else.
    return list(inspect.signature(MatplotlibRenderer.render).parameters)

# *** tests

# ** test: line_and_scatter_render_from_x_and_y
def test_line_and_scatter_render_from_x_and_y():
    '''
    A valid line record and a valid scatter record render from x and y.
    '''

    # Both kinds draw the same roles. The pictures are not empty.
    renderer = MatplotlibRenderer()
    line = renderer.render(line_plot())
    scatter = renderer.render(line_plot(kind='scatter'))
    changed = renderer.render(line_plot(y=(30, 40)))

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
    picture = renderer.render(plot)
    taller = renderer.render(bar_plot(height=(80, 12)))

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
    picture = renderer.render(plot)
    aggregate_picture = renderer.render(aggregate)

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
    with pytest.raises(ValueError):
        MatplotlibRenderer().render(record)
    assert list(tmp_path.iterdir()) == []

# ** test: illegal_marks_fail_and_return_no_picture
@pytest.mark.parametrize('kind,marks', [
    ('line', line_marks() + [Mark(role='category', values=('North', 'South'))]),
    ('scatter', line_marks() + [Mark(role='category', values=('North', 'South'))]),
    ('bar', bar_marks() + [Mark(role='x', values=(1, 2))]),
    ('bar', bar_marks() + [Mark(role='y', values=(1, 2))]),
    ('line', [Mark(role='y', values=(3, 4))]),
    ('bar', [Mark(role='height', values=(10, 12))]),
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
    with pytest.raises(ValueError):
        MatplotlibRenderer().render(illegal_record(kind, marks))
    assert list(tmp_path.iterdir()) == []

# ** test: renderer_does_not_keep_or_import_a_store
def test_renderer_does_not_keep_or_import_a_store():
    '''
    Render does not call PlotService and does not write a publication file.
    '''

    # The utility has no store, no path argument, and no file writer.
    assert render_parameters() == ['self', 'plot']
    source = Path(renderer_module.__file__).read_text()
    assert 'PlotService' not in source
    assert 'open(' not in source
    imported = ' '.join(imported_modules(Path(renderer_module.__file__)))
    assert 'repos' not in imported
    assert 'domain' not in imported

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
