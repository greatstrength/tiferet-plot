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
    Plot,
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
