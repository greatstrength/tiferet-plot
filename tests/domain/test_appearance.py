"""Tests for declared appearance on the record."""

# *** imports

# ** core
import ast
import inspect
from pathlib import Path

# ** infra
import pytest
from pydantic import ValidationError

# ** app
from tiferet.domain import ModelError
from tiferet_plot.domain.plot import (
    ABSENT_COLOR_CYCLE,
    CSS_COLOR_NAMES,
    Mark,
    MatrixCell,
    Plot,
    PlotMatrix,
    Series,
)
from tiferet_plot.mappers.plot import PlotAggregate, SeriesAggregate
import tiferet_plot.domain.plot as plot_module
from tiferet_plot.utils.plot import CSS_COLOR_HEX, MatplotlibRenderer

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

# ** function: line_series
def line_series(name='Revenue', **style):
    '''
    Build one line series.

    :param name: The series name.
    :type name: str
    :param style: Optional series style.
    :type style: dict
    :return: The series.
    :rtype: Series
    '''

    # Style is optional. An omitted field stays absent.
    return Series(name=name, marks=line_marks(), **style)

# ** function: declared_plot
def declared_plot(kind='line', series=None, **fields):
    '''
    Declare the acceptance plot.

    :param kind: The chart kind.
    :type kind: str
    :param series: The series. One Revenue series when omitted.
    :type series: list
    :param fields: Optional plot fields.
    :type fields: dict
    :return: The declared plot.
    :rtype: Plot
    '''

    # The acceptance name has no supplied id.
    if series is None:
        series = [line_series()]
    return Plot(
        name='Sales by Region',
        kind=kind,
        series=series,
        **fields,
    )

# ** function: cell_plot
def cell_plot(plot_id, color=None, show_legend=None, name='Revenue'):
    '''
    Build a cell plot with a supplied id.

    :param plot_id: The plot id. Not derived by the matrix.
    :type plot_id: str
    :param color: Optional series color.
    :type color: str
    :param show_legend: Optional plot legend flag.
    :type show_legend: bool
    :param name: The series name.
    :type name: str
    :return: The cell plot.
    :rtype: Plot
    '''

    # The cell plot id is already set.
    return Plot(
        id=plot_id,
        name=name,
        kind='line',
        show_legend=show_legend,
        series=[
            Series(
                name='Revenue',
                color=color,
                marks=line_marks(),
            ),
        ],
    )

# *** tests

# ** test: a_b1_declaration_omits_appearance_and_keeps_the_ids
def test_a_b1_declaration_omits_appearance_and_keeps_the_ids():
    '''
    A declaration with no new field still derives both ids, and the fields stay absent.
    '''

    # No new field is set.
    plot = declared_plot()

    # Identity is still the snake_case names. Appearance is absent.
    assert plot.id == 'sales_by_region'
    assert plot.series[0].id == 'revenue'
    assert plot.series[0].legend_label is None
    assert plot.series[0].color is None
    assert plot.show_legend is None
    assert plot.font_family is None
    assert plot.title_size is None
    assert plot.series[0].legend_text == 'Revenue'

# ** test: legend_label_and_hex_color_do_not_change_ids
def test_legend_label_and_hex_color_do_not_change_ids():
    '''
    A supplied label is kept, and a mixed-case hex is stored lowercase.
    '''

    # Supply the label and a mixed-case hex.
    plot = declared_plot(series=[
        line_series(legend_label='Quarterly revenue', color='#AbCdEf'),
    ])

    # The ids are unchanged. The color spelling is one lowercase hex.
    assert plot.id == 'sales_by_region'
    assert plot.series[0].id == 'revenue'
    assert plot.series[0].legend_label == 'Quarterly revenue'
    assert plot.series[0].color == '#abcdef'
    assert plot.series[0].legend_text == 'Quarterly revenue'

# ** test: a_blank_legend_label_is_absent_and_is_not_filled
@pytest.mark.parametrize('label', ['', '   '])
def test_a_blank_legend_label_is_absent_and_is_not_filled(label):
    '''
    A blank legend label is absent, not an empty string and not the series name.
    '''

    # Blank is the omitted case.
    plot = declared_plot(series=[line_series(legend_label=label)])

    # The drawer reads the series name. The name is not written back.
    assert plot.series[0].legend_label is None
    assert plot.series[0].legend_text == 'Revenue'

# ** test: appearance_is_not_a_mark_role_or_a_series_title
@pytest.mark.parametrize('role', ['color', 'marker', 'rotation', 'size'])
def test_appearance_is_not_a_mark_role_or_a_series_title(role):
    '''
    A series has no title. Color, marker, rotation, and size are not mark roles.
    '''

    # Mark is still role and values. Kind is still the three declared kinds.
    assert set(Mark.model_fields) == {'role', 'values'}
    assert 'title' not in Series.model_fields
    assert plot_module.PLOT_KINDS == ('line', 'scatter', 'bar')
    with pytest.raises(ValidationError):
        Series(name='Revenue', title='Not a series title', marks=line_marks())
    with pytest.raises(ValidationError):
        declared_plot(series=[
            Series(
                name='Revenue',
                marks=line_marks() + [Mark(role=role, values=(1, 2))],
            ),
        ])

# ** test: line_style_is_stored_and_inapplicable_style_fails
def test_line_style_is_stored_and_inapplicable_style_fails():
    '''
    A line stores its style. A tool spelling and a bar width fail.
    '''

    # The stored marker is the token, not the tool code.
    plot = declared_plot(series=[
        line_series(linestyle='dashed', linewidth=2, marker='circle', markersize=8),
    ])
    assert plot.series[0].linestyle == 'dashed'
    assert plot.series[0].linewidth == 2
    assert plot.series[0].marker == 'circle'
    assert plot.series[0].markersize == 8

    # A tool spelling and a bar width do not belong on a line.
    with pytest.raises(ValidationError):
        declared_plot(series=[line_series(linestyle='--')])
    with pytest.raises(ModelError):
        declared_plot(series=[line_series(bar_width=1)])

# ** test: scatter_and_bar_reject_style_they_do_not_show
def test_scatter_and_bar_reject_style_they_do_not_show():
    '''
    A present style the kind does not show fails. An omitted marker stays absent.
    '''

    # An omitted scatter marker is not stored as circle.
    scatter = declared_plot(kind='scatter')
    assert scatter.series[0].marker is None
    stored = declared_plot(
        kind='scatter',
        series=[line_series(marker='no_marker')],
    )
    assert stored.series[0].marker == 'no_marker'

    # Stroke fields do not belong on a scatter.
    with pytest.raises(ModelError):
        declared_plot(kind='scatter', series=[line_series(linestyle='solid')])
    with pytest.raises(ModelError):
        declared_plot(kind='scatter', series=[line_series(linewidth=1.5)])

    # A marker does not belong on a bar. A scale is stored as supplied.
    with pytest.raises(ModelError):
        Plot(
            name='Sales by Region',
            kind='bar',
            series=[Series(name='Revenue', marker='circle', marks=bar_marks())],
        )
    with pytest.raises(ModelError):
        Plot(
            name='Sales by Region',
            kind='bar',
            series=[Series(name='Revenue', markersize=6, marks=bar_marks())],
        )
    bar = Plot(
        name='Sales by Region',
        kind='bar',
        series=[Series(name='Revenue', bar_width=2, marks=bar_marks())],
    )
    assert bar.series[0].bar_width == 2
    assert bar.series[0].bar_width not in (0.8, 0.4, 1.6)
    omitted = Plot(
        name='Sales by Region',
        kind='bar',
        series=[Series(name='Revenue', marks=bar_marks())],
    )
    assert omitted.series[0].bar_width is None

# ** test: color_names_and_closed_tokens
@pytest.mark.parametrize('color,stored', [
    ('red', 'red'),
    ('Red', 'red'),
    ('grey', 'gray'),
    ('GREY', 'gray'),
    ('#ff0000', '#ff0000'),
])
def test_color_names_and_closed_tokens(color, stored):
    '''
    A name stays a name. grey is stored as gray. A hex is not rewritten to a name.
    '''

    # The stored color is the one spelling this round keeps.
    plot = declared_plot(series=[line_series(color=color)])
    assert plot.series[0].color == stored
    assert plot.id == 'sales_by_region'

# ** test: illegal_colors_and_tokens_fail_without_matplotlib
@pytest.mark.parametrize('fields', [
    {'color': 'reddish'},
    {'color': 'orange'},
    {'color': '#ff00'},
    {'color': '#ff0000ff'},
])
def test_illegal_colors_and_tokens_fail_without_matplotlib(fields):
    '''
    An unknown color fails in the domain, which does not import Matplotlib.
    '''

    # The domain constant is the names, without hex and without grey.
    source = Path(plot_module.__file__).read_text()
    imported = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.startswith('matplotlib') for name in imported)
    assert 'grey' not in CSS_COLOR_NAMES
    assert 'palette' not in Plot.model_fields
    assert 'palette' not in Series.model_fields
    with pytest.raises(ValidationError):
        declared_plot(series=[line_series(**fields)])

# ** test: font_legend_and_forbidden_fields
def test_font_legend_and_forbidden_fields():
    '''
    Closed tokens succeed. A raw family, best, and a text bool fail.
    '''

    # A legal family and place do not change the id.
    plot = declared_plot(
        font_family='serif',
        legend_location='upper_right',
        show_legend=False,
    )
    assert plot.font_family == 'serif'
    assert plot.legend_location == 'upper_right'
    assert plot.show_legend is False
    assert plot.id == 'sales_by_region'

    # Near spellings and a text bool are not stored.
    for fields in (
        {'font_family': 'DejaVu Sans'},
        {'legend_location': 'best'},
        {'legend_location': 'upper right'},
        {'show_legend': 'false'},
    ):
        with pytest.raises(ValidationError):
            declared_plot(**fields)

# ** test: sizes_rotations_decimals_and_extra_fields_fail
def test_sizes_rotations_decimals_and_extra_fields_fail():
    '''
    A non-positive size, a text rotation, and a float decimal count fail.
    '''

    # Zero and a negative size are not sizes. Text is not a rotation.
    for fields in (
        {'title_size': 0},
        {'tick_label_size': -1},
        {'x_tick_rotation': '45'},
        {'x_tick_decimals': 2.0},
        {'row_spacing': 0},
        {'width': 4},
        {'height': 3},
        {'kwargs': {}},
        {'rc': {}},
        {'theme': 'dark'},
        {'style': {}},
    ):
        with pytest.raises(ValidationError):
            declared_plot(**fields)
    with pytest.raises(ValidationError):
        declared_plot(series=[line_series(linewidth=True)])

    # A numeric rotation is stored. Zero decimals are supplied, not absent.
    plot = declared_plot(x_tick_rotation=45, x_tick_decimals=0)
    assert plot.x_tick_rotation == 45
    assert plot.x_tick_decimals == 0
    assert 'width' not in Plot.model_fields
    assert 'height' not in Plot.model_fields

# ** test: rename_and_replace_marks_keep_appearance_and_ids
def test_rename_and_replace_marks_keep_appearance_and_ids():
    '''
    Renaming and replacing marks do not clear style or recompute an id.
    '''

    # Color and the label are already settled.
    plot = PlotAggregate(
        name='Sales by Region',
        kind='line',
        series=[
            SeriesAggregate(
                name='Revenue',
                legend_label='Quarterly revenue',
                color='red',
                marks=line_marks(),
            ),
        ],
    )
    plot.rename('Quarterly Sales')
    plot.rename_series('revenue', 'Cost')
    plot.series[0].color = '#00ff00'
    plot.replace_marks('revenue', line_marks(y=(9, 8)))

    # Neither id moved. The label stayed. The new color is the assigned one.
    assert plot.id == 'sales_by_region'
    assert plot.series[0].id == 'revenue'
    assert plot.series[0].legend_label == 'Quarterly revenue'
    assert plot.series[0].color == '#00ff00'
    assert plot.series[0].marks[1].values == (9, 8)

# ** test: illegal_marks_still_fail_when_appearance_is_set
def test_illegal_marks_still_fail_when_appearance_is_set():
    '''
    Appearance does not bypass the kind rules.
    '''

    # A color does not make bar marks legal on a line.
    with pytest.raises(ValidationError):
        declared_plot(series=[
            Series(name='Revenue', color='red', marks=bar_marks()),
        ])

# ** test: a_matrix_omits_grid_fields_and_rejects_series_style
def test_a_matrix_omits_grid_fields_and_rejects_series_style():
    '''
    A matrix with no new field stores the grid fields as absent.
    '''

    # No new field is set. The id still comes only from the name.
    matrix = PlotMatrix(
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[
            MatrixCell(row=0, col=0, plot=cell_plot('revenue_plot')),
        ],
    )
    assert matrix.id == 'sales_by_region'
    assert matrix.show_legend is None
    assert matrix.row_spacing is None
    assert 'width' not in PlotMatrix.model_fields
    assert 'height' not in PlotMatrix.model_fields

    # Series style and axis formatting do not belong on the matrix.
    for fields in (
        {'color': 'red'},
        {'legend_label': 'Revenue'},
        {'bar_width': 1},
        {'axis_label_size': 10},
    ):
        with pytest.raises(ValidationError):
            PlotMatrix(
                name='Sales by Region',
                rows=1,
                cols=1,
                cells=[
                    MatrixCell(row=0, col=0, plot=cell_plot('revenue_plot')),
                ],
                **fields,
            )

# ** test: a_requested_grid_legend_fails_when_swatches_disagree
def test_a_requested_grid_legend_fails_when_swatches_disagree():
    '''
    Two Revenue series with different colors fail only when the matrix asks.
    '''

    # Each cell keeps its own color. The texts fall back to the same name.
    cells = [
        MatrixCell(row=0, col=0, plot=cell_plot('left', color='#1f77b4')),
        MatrixCell(row=0, col=1, plot=cell_plot('right', color='#ff7f0e')),
    ]
    with pytest.raises(ModelError):
        PlotMatrix(
            name='Sales by Region',
            rows=1,
            cols=2,
            show_legend=True,
            cells=cells,
        )

    # Absent does not ask, so the cells stay legal and keep their colors.
    quiet = PlotMatrix(
        name='Sales by Region',
        rows=1,
        cols=2,
        cells=cells,
    )
    assert quiet.show_legend is None
    assert quiet.cells[0].plot.series[0].color == '#1f77b4'
    assert quiet.cells[1].plot.series[0].color == '#ff7f0e'

# ** test: a_cell_legend_flag_does_not_filter_the_union
def test_a_cell_legend_flag_does_not_filter_the_union():
    '''
    A cell show_legend false does not hide that series from the grid union.
    '''

    # The cell flag is not the grid flag. The colors still disagree.
    cells = [
        MatrixCell(
            row=0,
            col=0,
            plot=cell_plot('left', color='#1f77b4', show_legend=False),
        ),
        MatrixCell(row=0, col=1, plot=cell_plot('right', color='#ff7f0e')),
    ]
    with pytest.raises(ModelError):
        PlotMatrix(
            name='Sales by Region',
            rows=1,
            cols=2,
            show_legend=True,
            cells=cells,
        )

# ** test: agreeing_swatches_and_zero_spacing_are_stored
def test_agreeing_swatches_and_zero_spacing_are_stored():
    '''
    A requested legend succeeds when the swatches agree. Zero spacing is stored.
    '''

    # Same text, same stored color, same kind. Zero is a supplied gap.
    matrix = PlotMatrix(
        name='Sales by Region',
        rows=1,
        cols=2,
        show_legend=True,
        row_spacing=0,
        cells=[
            MatrixCell(row=0, col=0, plot=cell_plot('left', color='red')),
            MatrixCell(row=0, col=1, plot=cell_plot('right', color='red')),
        ],
    )
    assert matrix.id == 'sales_by_region'
    assert matrix.row_spacing == 0
    assert matrix.show_legend is True
    assert 'legend_entries' not in PlotMatrix.model_fields

# ** test: absent_colors_use_the_cell_index_and_are_not_written_back
def test_absent_colors_use_the_cell_index_and_are_not_written_back():
    '''
    Two absent colors in one cell disagree by cycle index. The hex is not stored.
    '''

    # Index zero and index one are different cycle colors. The names match.
    plot = Plot(
        id='revenue_plot',
        name='Revenue',
        kind='line',
        series=[
            Series(name='Revenue', marks=line_marks()),
            Series(name='Revenue', id='other', marks=line_marks()),
        ],
    )
    assert plot.series[0].color is None
    assert plot.series[1].color is None
    assert ABSENT_COLOR_CYCLE[0] != ABSENT_COLOR_CYCLE[1]
    with pytest.raises(ModelError):
        PlotMatrix(
            name='Sales by Region',
            rows=1,
            cols=1,
            show_legend=True,
            cells=[MatrixCell(row=0, col=0, plot=plot)],
        )

# ** test: the_name_map_sits_beside_the_renderer_and_render_does_not_read_it
def test_the_name_map_sits_beside_the_renderer_and_render_does_not_read_it():
    '''
    The hex dictionary matches the domain names. render does not read appearance.
    '''

    # grey is an alias, not a second key. The renderer methods do not read fields.
    assert set(CSS_COLOR_HEX) == set(CSS_COLOR_NAMES)
    assert 'grey' not in CSS_COLOR_HEX
    method_source = inspect.getsource(MatplotlibRenderer.render)
    method_source += inspect.getsource(MatplotlibRenderer.render_matrix)
    for name in (
        'show_legend',
        'legend_label',
        'font_family',
        'bar_width',
        'CSS_COLOR_HEX',
    ):
        assert name not in method_source
