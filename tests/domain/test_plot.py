"""Tests for plot declaration."""

# *** imports

# ** core
import ast
from pathlib import Path

# ** infra
import pytest
from pydantic import ValidationError

# ** app
from tiferet_plot.domain.plot import (
    Mark,
    MatrixCell,
    Plot,
    PlotMatrix,
    Series,
)
import tiferet_plot.domain.plot as plot_module
import tiferet_plot.mappers.plot as mapper_module

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

# ** function: line_plot
def line_plot(plot_id='revenue_plot', name='Revenue'):
    '''
    Build a valid line plot with a supplied id.

    :param plot_id: The plot id. Not derived by the matrix.
    :type plot_id: str
    :param name: The plot name.
    :type name: str
    :return: A declared line plot.
    :rtype: Plot
    '''

    # The plot id is already set. Matrix declaration must not rewrite it.
    return Plot(
        id=plot_id,
        name=name,
        kind='line',
        description='Revenue compared across regions.',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )

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

# ** function: imported_modules
def imported_modules(module) -> list:
    '''
    List modules imported by a source file.

    :param module: The imported module to inspect.
    :type module: module
    :return: Imported module names.
    :rtype: list
    '''

    # Parse the module source rather than trusting a substring search.
    source = Path(module.__file__).read_text()
    tree = ast.parse(source)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)

    # Return the imported module names.
    return names

# *** tests

# ** test: declaration_derives_ids_and_excludes_renderer_and_store
def test_declaration_derives_ids_and_excludes_renderer_and_store():
    '''
    A named line plot with one named series derives both ids.
    '''

    # Declare the acceptance record. No plot id and no series id.
    plot = Plot(
        name='Sales by Region',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )

    # The ids are the snake_case names.
    assert plot.id == 'sales_by_region'
    assert plot.series[0].id == 'revenue'

    # The record has no renderer, path, or database handle.
    assert set(Plot.model_fields) == {
        'id',
        'name',
        'kind',
        'description',
        'series',
    }
    assert 'renderer' not in Plot.model_fields
    assert 'file_path' not in Plot.model_fields
    assert 'database' not in Plot.model_fields

# ** test: supplied_plot_id_is_kept
def test_supplied_plot_id_is_kept():
    '''
    A supplied plot id is stored as given.
    '''

    # Supply an id that is not the snake_case of the name.
    plot = Plot(
        id='Custom-Id',
        name='Sales by Region',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )

    # The supplied id is not rewritten.
    assert plot.id == 'Custom-Id'
    assert plot.name == 'Sales by Region'

# ** test: supplied_series_id_is_kept
def test_supplied_series_id_is_kept():
    '''
    A supplied series id is stored as given.
    '''

    # Supply a series id that is not the snake_case of its name.
    plot = Plot(
        name='Sales by Region',
        kind='line',
        series=[
            Series(id='rev-1', name='Revenue', marks=line_marks()),
        ],
    )

    # The series id is kept. The plot id is still derived.
    assert plot.series[0].id == 'rev-1'
    assert plot.id == 'sales_by_region'

# ** test: blank_id_is_derived
def test_blank_id_is_derived():
    '''
    A blank id is omitted, not stored as given.
    '''

    # A whitespace id is blank.
    plot = Plot(
        id='   ',
        name='Sales by Region',
        kind='line',
        series=[
            Series(id='', name='Q3 Revenue', marks=line_marks()),
        ],
    )

    # Both blank ids are derived. Q3 Revenue becomes q3_revenue.
    assert plot.id == 'sales_by_region'
    assert plot.series[0].id == 'q3_revenue'

# ** test: snake_case_collapses_separator_runs
def test_snake_case_collapses_separator_runs():
    '''
    A run of non-letters and non-digits becomes one underscore.
    '''

    # Punctuation and surrounding space are separators, not identity.
    plot = Plot(
        name='  Sales, by — Region  ',
        kind='scatter',
        series=[
            Series(name='Q3 Revenue', marks=line_marks()),
        ],
    )

    # Trim, lowercase, collapse, and strip ends.
    assert plot.id == 'sales_by_region'
    assert plot.series[0].id == 'q3_revenue'

# ** test: scatter_and_bar_declarations_succeed
def test_scatter_and_bar_declarations_succeed():
    '''
    Scatter accepts numeric x and y. Bar accepts text category and numeric height.
    '''

    # Scatter uses the same marks as line.
    scatter = Plot(
        name='Q3 Revenue',
        kind='scatter',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )

    # Bar uses category and height, not x and y.
    bar = Plot(
        name='Sales by Region',
        kind='bar',
        series=[
            Series(name='Revenue', marks=bar_marks()),
        ],
    )

    # Both declarations succeed and derive their ids.
    assert scatter.kind == 'scatter'
    assert scatter.id == 'q3_revenue'
    assert bar.kind == 'bar'
    assert bar.series[0].marks[0].role == 'category'

# ** test: description_is_not_identity
def test_description_is_not_identity():
    '''
    An optional description does not derive id or kind.
    '''

    # Description is claim text beside the name.
    plot = Plot(
        name='Sales by Region',
        description='Revenue compared across regions.',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )

    # Identity still comes from the name. Kind stays the supplied kind.
    assert plot.description == 'Revenue compared across regions.'
    assert plot.id == 'sales_by_region'
    assert plot.kind == 'line'

# ** test: illegal_mark_roles_fail
@pytest.mark.parametrize('kind,marks', [
    ('line', line_marks() + [Mark(role='category', values=('North', 'South'))]),
    ('scatter', line_marks() + [Mark(role='category', values=('North', 'South'))]),
    ('bar', bar_marks() + [Mark(role='x', values=(1, 2))]),
    ('bar', bar_marks() + [Mark(role='y', values=(1, 2))]),
])
def test_illegal_mark_roles_fail(kind, marks):
    '''
    A line or scatter series cannot carry category. A bar series cannot carry x or y.
    '''

    # The kind rectifies the roles. The extra role fails declaration.
    with pytest.raises(ValidationError):
        Plot(
            name='Sales by Region',
            kind=kind,
            series=[
                Series(name='Revenue', marks=marks),
            ],
        )

# ** test: empty_derivation_without_id_fails
@pytest.mark.parametrize('name', ['---', '   ', '!!!'])
def test_empty_derivation_without_id_fails(name):
    '''
    A name that snake-cases to an empty string fails when no id is supplied.
    '''

    # The name cannot identify the record.
    with pytest.raises(ValidationError):
        Plot(
            name=name,
            kind='line',
            series=[
                Series(name='Revenue', marks=line_marks()),
            ],
        )

# ** test: omitted_or_unrecognized_kind_fails
@pytest.mark.parametrize('kwargs', [
    {'name': 'Sales by Region', 'series': [Series(name='Revenue', marks=line_marks())]},
    {'name': 'Sales by Region', 'kind': 'histogram', 'series': [Series(name='Revenue', marks=line_marks())]},
    {'name': 'Sales by Region', 'kind': 'Line', 'series': [Series(name='Revenue', marks=line_marks())]},
])
def test_omitted_or_unrecognized_kind_fails(kwargs):
    '''
    Kind must be supplied. It is not inferred from the values, and it is not guessed from case.
    '''

    # Values that could have been a line do not select the kind.
    with pytest.raises(ValidationError):
        Plot(**kwargs)

# ** test: line_and_scatter_mark_values_fail
@pytest.mark.parametrize('kind,marks', [
    ('line', [Mark(role='y', values=(3, 4))]),
    ('line', [Mark(role='x', values=(1, 2))]),
    ('scatter', [Mark(role='x', values=(1, 2)), Mark(role='y', values=(3,))]),
    ('line', [Mark(role='x', values=(1, 2)), Mark(role='y', values=(3, '4'))]),
    ('scatter', [Mark(role='x', values=(1, True)), Mark(role='y', values=(3, 4))]),
    ('line', [Mark(role='x', values=(1, 2)), Mark(role='y', values=('3', '4'))]),
])
def test_line_and_scatter_mark_values_fail(kind, marks):
    '''
    Line and scatter require numeric x and y of equal non-empty length.
    '''

    # A missing role, a length mismatch, or a non-numeric value fails.
    with pytest.raises(ValidationError):
        Plot(
            name='Sales by Region',
            kind=kind,
            series=[
                Series(name='Revenue', marks=marks),
            ],
        )

# ** test: bar_mark_values_fail
@pytest.mark.parametrize('marks', [
    [Mark(role='height', values=(10, 12))],
    [Mark(role='category', values=('North', 'South'))],
    [Mark(role='category', values=('North',)), Mark(role='height', values=(10, 12))],
    [Mark(role='category', values=('North', 'South')), Mark(role='height', values=(10, '12'))],
    [Mark(role='category', values=(1, 2)), Mark(role='height', values=(10, 12))],
])
def test_bar_mark_values_fail(marks):
    '''
    Bar requires text category and numeric height of equal non-empty length.
    '''

    # A missing role, a length mismatch, or the wrong sort of value fails.
    with pytest.raises(ValidationError):
        Plot(
            name='Sales by Region',
            kind='bar',
            series=[
                Series(name='Revenue', marks=marks),
            ],
        )

# ** test: extra_mark_role_fails
def test_extra_mark_role_fails():
    '''
    An extra mark role is invalid in this round.
    '''

    # Color is not a role line, scatter, or bar selects.
    with pytest.raises(ValidationError):
        Plot(
            name='Sales by Region',
            kind='line',
            series=[
                Series(
                    name='Revenue',
                    marks=line_marks() + [Mark(role='color', values=('red', 'blue'))],
                ),
            ],
        )

# ** test: empty_series_or_empty_values_fail
def test_empty_series_or_empty_values_fail():
    '''
    A plot needs a series, and a required value sequence cannot be empty.
    '''

    # Zero series fails.
    with pytest.raises(ValidationError):
        Plot(name='Sales by Region', kind='line', series=[])

    # An empty required value sequence fails on the mark itself.
    with pytest.raises(ValidationError):
        Mark(role='y', values=())

# ** test: duplicate_series_ids_fail
def test_duplicate_series_ids_fail():
    '''
    Two series in one plot cannot resolve to the same id.
    '''

    # Derived ids collide when the names snake-case to the same id.
    with pytest.raises(ValidationError):
        Plot(
            name='Sales by Region',
            kind='line',
            series=[
                Series(name='Revenue', marks=line_marks()),
                Series(name='revenue', marks=line_marks((5, 6), (7, 8))),
            ],
        )

    # Supplied ids collide even when the names differ.
    with pytest.raises(ValidationError):
        Plot(
            name='Sales by Region',
            kind='line',
            series=[
                Series(id='rev', name='Revenue', marks=line_marks()),
                Series(id='rev', name='Cost', marks=line_marks((5, 6), (7, 8))),
            ],
        )

# ** test: renderer_and_store_fields_are_rejected
@pytest.mark.parametrize('extra', [
    {'renderer': 'matplotlib'},
    {'file_path': 'plot.yaml'},
    {'database': 'plots'},
])
def test_renderer_and_store_fields_are_rejected(extra):
    '''
    Declaration rejects a renderer, a file path, and a database handle.
    '''

    # Those are not fields of the record.
    with pytest.raises(ValidationError):
        Plot(
            name='Sales by Region',
            kind='line',
            series=[
                Series(name='Revenue', marks=line_marks()),
            ],
            **extra,
        )

# ** test: series_has_no_description
def test_series_has_no_description():
    '''
    Series do not carry a description in this round.
    '''

    # Description is plot claim text, not a series field.
    with pytest.raises(ValidationError):
        Series(
            name='Revenue',
            description='Not a series field.',
            marks=line_marks(),
        )

# ** test: domain_types_do_not_import_matplotlib_or_a_repository
def test_domain_types_do_not_import_matplotlib_or_a_repository():
    '''
    The domain types do not import Matplotlib and do not import a repository.
    '''

    # Inspect both modules that define the record and its aggregate.
    for module in (plot_module, mapper_module):
        imported = ' '.join(imported_modules(module))
        assert 'matplotlib' not in imported
        assert 'repos' not in imported
        assert 'repository' not in imported

# ** test: matrix_declaration_derives_id_and_keeps_the_cell_plot
def test_matrix_declaration_derives_id_and_keeps_the_cell_plot():
    '''
    A named matrix with one occupied cell derives its id and keeps the plot id.
    '''

    # Declare the acceptance record. No matrix id. One cell, three empty corners.
    plot = line_plot()
    matrix = PlotMatrix(
        name='Sales by Region',
        rows=2,
        cols=2,
        cells=[
            MatrixCell(row=0, col=1, plot=plot),
        ],
    )

    # The matrix id is the snake_case name. The cell plot id is unchanged.
    assert matrix.id == 'sales_by_region'
    assert matrix.cells[0].plot.id == 'revenue_plot'
    assert matrix.cells[0].plot is plot
    assert matrix.rows == 2
    assert matrix.cols == 2

    # The matrix is not a plot kind and has no drawing or store fields.
    assert set(PlotMatrix.model_fields) == {
        'id',
        'name',
        'description',
        'rows',
        'cols',
        'cells',
    }
    assert 'kind' not in PlotMatrix.model_fields
    assert 'marks' not in PlotMatrix.model_fields
    assert 'renderer' not in PlotMatrix.model_fields
    assert 'file_path' not in PlotMatrix.model_fields

# ** test: matrix_id_follows_the_plot_rule
def test_matrix_id_follows_the_plot_rule():
    '''
    A separator run becomes one underscore. A supplied id is kept.
    '''

    # Sales/Region has no id, so declaration derives one.
    derived = PlotMatrix(
        name='Sales/Region',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=line_plot()),
        ],
    )

    # A supplied id is not rewritten from the name.
    supplied = PlotMatrix(
        id='Custom-Id',
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=line_plot()),
        ],
    )

    # Blank is omitted, not stored. Description is not identity.
    blank = PlotMatrix(
        id='   ',
        name='Sales by Region',
        description='A grid of claims.',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=line_plot()),
        ],
    )

    # The plot rule, applied once to the matrix.
    assert derived.id == 'sales_region'
    assert supplied.id == 'Custom-Id'
    assert blank.id == 'sales_by_region'
    assert blank.description == 'A grid of claims.'

# ** test: cell_plot_missing_id_is_not_derived
@pytest.mark.parametrize('plot_id', [None, '', '   '])
def test_cell_plot_missing_id_is_not_derived(plot_id):
    '''
    A cell plot with a missing or blank id fails, and the name does not fill it.
    '''

    # The plot is a nested mapping, so matrix declaration is the one that sees it.
    plot = {
        'name': 'Revenue',
        'kind': 'line',
        'series': [
            {'name': 'Revenue', 'marks': line_marks()},
        ],
    }
    if plot_id is not None:
        plot['id'] = plot_id

    # Declaration fails. It does not become a plot id of revenue.
    with pytest.raises(ValidationError):
        PlotMatrix(
            name='Sales by Region',
            rows=1,
            cols=1,
            cells=[
                {'row': 0, 'col': 0, 'plot': plot},
            ],
        )

# ** test: illegal_grid_fails
@pytest.mark.parametrize('kwargs', [
    {'rows': 0, 'cols': 1, 'cells': [{'row': 0, 'col': 0}]},
    {'rows': 1, 'cols': 0, 'cells': [{'row': 0, 'col': 0}]},
    {'rows': 2, 'cols': 2, 'cells': []},
    {'rows': 2, 'cols': 2, 'cells': [{'row': 2, 'col': 0}]},
    {
        'rows': 2,
        'cols': 2,
        'cells': [
            {'row': 0, 'col': 1},
            {'row': 0, 'col': 1},
        ],
    },
])
def test_illegal_grid_fails(kwargs):
    '''
    A grid below 1, with no cells, an outside cell, or a shared position fails.
    '''

    # Each cell carries a valid plot. The grid rules are what fail.
    cells = []
    for cell in kwargs['cells']:
        cells.append({
            **cell,
            'plot': line_plot(),
        })

    # Rows and columns are not inferred from the occupied cells.
    with pytest.raises(ValidationError):
        PlotMatrix(
            name='Sales by Region',
            rows=kwargs['rows'],
            cols=kwargs['cols'],
            cells=cells,
        )

# ** test: same_plot_id_may_occupy_two_cells
def test_same_plot_id_may_occupy_two_cells():
    '''
    Two cells may share a plot id. Each keeps the record it carries.
    '''

    # Same id, different payloads. They are two placements.
    first = line_plot(name='Revenue')
    second = Plot(
        id='revenue_plot',
        name='Cost',
        kind='bar',
        series=[
            Series(name='Cost', marks=bar_marks()),
        ],
    )
    matrix = PlotMatrix(
        name='Shared',
        rows=1,
        cols=2,
        cells=[
            MatrixCell(row=0, col=0, plot=first),
            MatrixCell(row=0, col=1, plot=second),
        ],
    )

    # Neither payload is rewritten, and neither is required to match the other.
    assert matrix.cells[0].plot.id == matrix.cells[1].plot.id == 'revenue_plot'
    assert matrix.cells[0].plot.name == 'Revenue'
    assert matrix.cells[1].plot.name == 'Cost'
    assert matrix.cells[1].plot.kind == 'bar'

# ** test: plot_does_not_become_a_matrix
def test_plot_does_not_become_a_matrix():
    '''
    A plot does not gain a matrix field, and matrix is not a legal kind.
    '''

    # The plot record is unchanged by this round.
    assert 'matrix' not in Plot.model_fields
    assert 'matrix' not in plot_module.PLOT_KINDS
    with pytest.raises(ValidationError):
        Plot(
            name='Sales by Region',
            kind='matrix',
            series=[
                Series(name='Revenue', marks=line_marks()),
            ],
        )

    # A cell description, and a cell that stores only an id, are not this record.
    with pytest.raises(ValidationError):
        MatrixCell(row=0, col=0, plot=line_plot(), description='Not a cell field.')
    with pytest.raises(ValidationError):
        MatrixCell(row=0, col=0, plot='revenue_plot')
