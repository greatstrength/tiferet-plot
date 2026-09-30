"""Tests for saving declared appearance."""

# *** imports

# ** infra
import pytest
from tiferet.interfaces import ServiceError

# ** app
from tiferet_plot.domain.plot import Mark, MatrixCell, Plot, Series
from tiferet_plot.interfaces.plot import PLOT_ALREADY_KEPT_ID
from tiferet_plot.mappers.plot import PlotAggregate, PlotMatrixAggregate, SeriesAggregate
from tiferet_plot.repos.plot import MatrixConfigRepository, PlotConfigRepository

# *** constants

# ** constant: b1_plot_yaml
B1_PLOT_YAML = '''\
plots:
  sales_by_region:
    name: Sales by Region
    kind: line
    series:
      - id: revenue
        name: Revenue
        marks:
          - role: x
            values: [1, 2]
          - role: y
            values: [3, 4]
'''

# *** functions

# ** function: line_marks
def line_marks():
    '''
    Build numeric x and y marks.

    :return: Marks for a line series.
    :rtype: list
    '''

    # Return the two required roles.
    return [
        Mark(role='x', values=(1, 2)),
        Mark(role='y', values=(3, 4)),
    ]

# *** tests

# ** test: save_writes_present_appearance_and_not_a_default
def test_save_writes_present_appearance_and_not_a_default(tmp_path):
    '''
    A present field is written. An absent field is not filled with a drawer default.
    '''

    # One series has style. The plot hides the legend and stores a zero count.
    plot = PlotAggregate(
        name='Sales by Region',
        kind='line',
        show_legend=False,
        x_tick_decimals=0,
        font_family='serif',
        series=[
            SeriesAggregate(
                name='Revenue',
                legend_label='Quarterly revenue',
                color='#abcdef',
                marks=line_marks(),
            ),
        ],
    )
    path = tmp_path / 'publication.yml'
    repo = PlotConfigRepository(str(path))
    repo.save(plot)
    body = repo._load()['plots']['sales_by_region']
    series = body['series'][0]

    # The id is the key. Present appearance is on the body and the series.
    assert 'id' not in body
    assert body['show_legend'] is False
    assert body['x_tick_decimals'] == 0
    assert body['font_family'] == 'serif'
    assert series['legend_label'] == 'Quarterly revenue'
    assert series['color'] == '#abcdef'
    assert 'title_size' not in body
    assert 'sans-serif' not in path.read_text()
    assert '12' not in series.values()

    # Loading returns the same strings and numbers.
    loaded = repo.get('sales_by_region')
    assert loaded.show_legend is False
    assert loaded.x_tick_decimals == 0
    assert loaded.font_family == 'serif'
    assert loaded.series[0].legend_label == 'Quarterly revenue'
    assert loaded.series[0].color == '#abcdef'
    assert loaded.title_size is None

# ** test: save_does_not_write_an_absent_default
def test_save_does_not_write_an_absent_default(tmp_path):
    '''
    Save does not write the series name into the label or a cycle hex into color.
    '''

    # No new field is set.
    plot = PlotAggregate(
        name='Sales by Region',
        kind='line',
        series=[
            SeriesAggregate(name='Revenue', marks=line_marks()),
        ],
    )
    path = tmp_path / 'publication.yml'
    repo = PlotConfigRepository(str(path))
    repo.save(plot)
    text = path.read_text()
    body = repo._load()['plots']['sales_by_region']
    series = body['series'][0]

    # Absent stays absent. A second save of that id still fails.
    assert 'legend_label' not in series
    assert 'color' not in series
    assert 'show_legend' not in body
    assert 'sans-serif' not in text
    assert '#1f77b4' not in text
    assert repo.get('sales_by_region').series[0].color is None
    with pytest.raises(ServiceError) as caught:
        repo.save(plot)
    assert caught.value.error_code == PLOT_ALREADY_KEPT_ID

# ** test: a_b1_body_loads_with_appearance_absent
def test_a_b1_body_loads_with_appearance_absent(tmp_path):
    '''
    A b1 body with none of the new keys loads, and those fields are absent.
    '''

    # The seeded body has no appearance keys.
    path = tmp_path / 'publication.yml'
    path.write_text(B1_PLOT_YAML, encoding='utf-8')
    loaded = PlotConfigRepository(str(path)).get('sales_by_region')
    assert loaded.id == 'sales_by_region'
    assert loaded.show_legend is None
    assert loaded.font_family is None
    assert loaded.title_size is None
    assert loaded.series[0].legend_label is None
    assert loaded.series[0].color is None

# ** test: matrix_save_writes_color_on_the_cell_not_the_matrix
def test_matrix_save_writes_color_on_the_cell_not_the_matrix(tmp_path):
    '''
    Series color is on the cell plot. The matrix body has no legend entry list.
    '''

    # The matrix asks for nothing. The cell series has a color.
    matrix = PlotMatrixAggregate(
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(
                row=0,
                col=0,
                plot=Plot(
                    id='revenue_plot',
                    name='Revenue',
                    kind='line',
                    series=[
                        Series(name='Revenue', color='#1f77b4', marks=line_marks()),
                    ],
                ),
            ),
        ],
    )
    path = tmp_path / 'publication.yml'
    repo = MatrixConfigRepository(str(path))
    repo.save(matrix)
    body = repo._load()['matrices']['sales_by_region']

    # The matrix body does not gain the series color or a stored entry list.
    assert 'color' not in body
    assert 'legend_entries' not in body
    assert 'show_legend' not in body
    assert 'row_spacing' not in body
    assert '0.2' not in path.read_text()
    assert body['cells'][0]['plot']['series'][0]['color'] == '#1f77b4'
    loaded = repo.get('sales_by_region')
    assert loaded.show_legend is None
    assert loaded.row_spacing is None
    assert loaded.cells[0].plot.series[0].color == '#1f77b4'
