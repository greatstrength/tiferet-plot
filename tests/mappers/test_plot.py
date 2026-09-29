"""Tests for plot aggregate edits."""

# *** imports

# ** infra
import pytest
from pydantic import ValidationError

# ** app
from tiferet_plot.domain.plot import Mark
from tiferet_plot.mappers.plot import (
    MatrixConfigObject,
    PlotAggregate,
    PlotMatrixAggregate,
    SeriesAggregate,
)

# *** functions

# ** function: line_marks
def line_marks(x=(1, 2), y=(3, 4)):
    '''
    Build numeric x and y marks.

    :param x: The x values.
    :type x: tuple
    :param y: The y values.
    :type y: tuple
    :return: Marks for a line series.
    :rtype: list
    '''

    # Return the two required roles.
    return [
        Mark(role='x', values=x),
        Mark(role='y', values=y),
    ]

# *** fixtures

# ** fixture: plot
@pytest.fixture
def plot() -> PlotAggregate:
    '''
    A declared line plot with one series and no supplied ids.

    :return: The plot aggregate.
    :rtype: PlotAggregate
    '''

    # Declare through the aggregate. Ids are derived once.
    return PlotAggregate(
        name='Sales by Region',
        kind='line',
        series=[
            SeriesAggregate(name='Revenue', marks=line_marks()),
        ],
    )

# *** tests

# ** test: rename_does_not_recompute_plot_id
def test_rename_does_not_recompute_plot_id(plot: PlotAggregate):
    '''
    Renaming a plot does not recompute its id.
    '''

    # The declaration id is the snake_case of the original name.
    assert plot.id == 'sales_by_region'

    # Rename the plot.
    plot.rename('Quarterly Sales')

    # The name changes. The id does not.
    assert plot.name == 'Quarterly Sales'
    assert plot.id == 'sales_by_region'

# ** test: rename_does_not_recompute_series_id
def test_rename_does_not_recompute_series_id(plot: PlotAggregate):
    '''
    Renaming a series does not recompute its id.
    '''

    # Rename the series through its own aggregate.
    series = SeriesAggregate(
        name='Revenue',
        marks=line_marks(),
    )
    assert series.id == 'revenue'
    series.rename('Cost')

    # And rename the series held by the plot aggregate.
    assert plot.series[0].id == 'revenue'
    plot.rename_series('revenue', 'Cost')

    # Both edits change the name and keep the declared id.
    assert series.name == 'Cost'
    assert series.id == 'revenue'
    assert plot.series[0].name == 'Cost'
    assert plot.series[0].id == 'revenue'
    assert plot.id == 'sales_by_region'

# ** test: replace_marks_keeps_series_id
def test_replace_marks_keeps_series_id():
    '''
    Replacing marks does not recompute the series id.
    '''

    # Declare a series, then replace its marks.
    series = SeriesAggregate(name='Revenue', marks=line_marks())
    series.replace_marks(line_marks((9, 8), (7, 6)))

    # The values change. The id does not.
    assert series.id == 'revenue'
    assert series.marks[0].values == (9, 8)
    assert series.marks[1].values == (7, 6)

# ** test: plot_replace_marks_rechecks_kind_and_keeps_ids
def test_plot_replace_marks_rechecks_kind_and_keeps_ids(plot: PlotAggregate):
    '''
    Replacing marks on a plot keeps ids and still rejects marks the kind does not allow.
    '''

    # A legal replacement changes the values only.
    plot.replace_marks('revenue', line_marks((9, 8, 7), (1, 2, 3)))

    # Ids stay as declared.
    assert plot.id == 'sales_by_region'
    assert plot.series[0].id == 'revenue'
    assert plot.series[0].marks[0].values == (9, 8, 7)

    # A category mark is still illegal on a line plot, and the record is unchanged.
    with pytest.raises(ValidationError):
        plot.replace_marks(
            'revenue',
            line_marks() + [Mark(role='category', values=('North', 'South'))],
        )
    assert plot.series[0].marks[0].values == (9, 8, 7)
    assert plot.series[0].id == 'revenue'

# ** test: rename_does_not_recompute_matrix_id
def test_rename_does_not_recompute_matrix_id():
    '''
    Renaming a matrix does not recompute its id or a cell plot id.
    '''

    # Declare a grid. The matrix id comes from the name. The plot id is supplied.
    matrix = PlotMatrixAggregate(
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[
            {
                'row': 0,
                'col': 0,
                'plot': {
                    'id': 'revenue_plot',
                    'name': 'Revenue',
                    'kind': 'line',
                    'series': [
                        SeriesAggregate(name='Revenue', marks=line_marks()),
                    ],
                },
            },
        ],
    )
    assert matrix.id == 'sales_by_region'
    assert matrix.cells[0].plot.id == 'revenue_plot'

    # Rename the matrix.
    matrix.rename('Quarterly Sales')

    # The name changes. Neither id does.
    assert matrix.name == 'Quarterly Sales'
    assert matrix.id == 'sales_by_region'
    assert matrix.cells[0].plot.id == 'revenue_plot'

# ** test: matrix_file_shape_keeps_the_plot_id_and_drops_the_matrix_id
def test_matrix_file_shape_keeps_the_plot_id_and_drops_the_matrix_id():
    '''
    The stored body excludes the matrix id and keeps the cell plot id.
    '''

    # Build the record, then the file shape. Do not hand-serialize.
    matrix = PlotMatrixAggregate(
        id='Custom-Id',
        name='Sales by Region',
        description='A grid of claims.',
        rows=2,
        cols=2,
        cells=[
            {
                'row': 0,
                'col': 1,
                'plot': {
                    'id': 'revenue_plot',
                    'name': 'Revenue',
                    'kind': 'line',
                    'description': 'Revenue compared across regions.',
                    'series': [
                        {
                            'id': 'rev-1',
                            'name': 'Revenue',
                            'marks': line_marks(),
                        },
                    ],
                },
            },
        ],
    )
    stored = MatrixConfigObject.from_model(matrix).to_primitive('to_data')

    # The matrix id is the key, not a body field. The plot id stays in the cell.
    assert 'id' not in stored
    assert 'renderer' not in stored
    assert 'file_path' not in stored
    assert stored['cells'][0]['plot']['id'] == 'revenue_plot'
    assert stored['cells'][0]['plot']['series'][0]['id'] == 'rev-1'

    # Load injects the key, then maps. The plot id comes back from the cell body.
    loaded = MatrixConfigObject.model_validate({
        **stored,
        'id': 'Custom-Id',
    }).map()
    assert loaded.id == 'Custom-Id'
    assert loaded.name == 'Sales by Region'
    assert loaded.description == 'A grid of claims.'
    assert loaded.cells[0].row == 0
    assert loaded.cells[0].col == 1
    assert loaded.cells[0].plot.id == 'revenue_plot'
    assert loaded.cells[0].plot.kind == 'line'
    assert loaded.cells[0].plot.series[0].marks[0].values == (1, 2)
