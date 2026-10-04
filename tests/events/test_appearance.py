"""Tests for appearance on create and update."""

# *** imports

# ** core
import inspect

# ** infra
import pytest

# ** app
from tiferet.domain import ModelError
from tiferet.events import DomainEvent
from tiferet.interfaces import ServiceError
from tiferet_plot.domain.plot import Mark, Series
from tiferet_plot.events.plot import CreateMatrix, CreatePlot, UpdateMatrix, UpdatePlot
from tiferet_plot.interfaces.plot import MATRIX_NOT_KEPT_ID, PLOT_NOT_KEPT_ID
from tiferet_plot.mappers.plot import PlotAggregate, PlotMatrixAggregate

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

# ** function: series
def series(color=None):
    '''
    Build one Revenue series.

    :param color: Optional series color.
    :type color: str
    :return: The series.
    :rtype: Series
    '''

    # Color rides on the series. There is no separate color argument.
    return Series(name='Revenue', color=color, marks=line_marks())

# ** function: cell
def cell(plot_id, color):
    '''
    Build one occupied cell.

    :param plot_id: The supplied plot id.
    :type plot_id: str
    :param color: The series color.
    :type color: str
    :return: A cell mapping.
    :rtype: dict
    '''

    # The plot id is supplied. The matrix must not derive it.
    return {
        'row': 0,
        'col': 0 if plot_id == 'left' else 1,
        'plot': {
            'id': plot_id,
            'name': 'Revenue',
            'kind': 'line',
            'series': [
                {
                    'name': 'Revenue',
                    'color': color,
                    'marks': line_marks(),
                },
            ],
        },
    }

# *** classes

# ** class: memory_plot_service
class MemoryPlotService:
    '''
    An in-memory plot service for appearance events.
    '''

    # * init
    def __init__(self) -> None:
        '''
        Start with no kept records.
        '''

        # Records are keyed by plot id.
        self.records = {}
        self.update_calls = []

    # * method: exists
    def exists(self, id: str) -> bool:
        '''
        Check whether the id is kept.

        :param id: The plot id.
        :type id: str
        :return: True when get would return a record.
        :rtype: bool
        '''

        # Exists follows get.
        return id in self.records

    # * method: get
    def get(self, id: str):
        '''
        Return the kept plot, or nothing.

        :param id: The plot id.
        :type id: str
        :return: The plot, or None.
        :rtype: PlotAggregate | None
        '''

        # A missing id is nothing.
        return self.records.get(id)

    # * method: save
    def save(self, plot: PlotAggregate) -> None:
        '''
        Insert a plot.

        :param plot: The plot to keep.
        :type plot: PlotAggregate
        :return: None
        :rtype: None
        '''

        # Insert. These tests do not save twice.
        self.records[plot.id] = plot

    # * method: update
    def update(self, plot: PlotAggregate) -> None:
        '''
        Replace a kept plot.

        :param plot: The replacement plot.
        :type plot: PlotAggregate
        :return: None
        :rtype: None
        '''

        # Update does not insert.
        self.update_calls.append(plot.id)
        if plot.id not in self.records:
            raise ServiceError(PLOT_NOT_KEPT_ID, message='missing')
        self.records[plot.id] = plot

# ** class: memory_matrix_service
class MemoryMatrixService:
    '''
    An in-memory matrix service for appearance events.
    '''

    # * init
    def __init__(self) -> None:
        '''
        Start with no kept records.
        '''

        # Records are keyed by matrix id.
        self.records = {}
        self.updates = []

    # * method: exists
    def exists(self, id: str) -> bool:
        '''
        Check whether the id is kept.

        :param id: The matrix id.
        :type id: str
        :return: True when get would return a record.
        :rtype: bool
        '''

        # Exists follows get.
        return id in self.records

    # * method: get
    def get(self, id: str):
        '''
        Return the kept matrix, or nothing.

        :param id: The matrix id.
        :type id: str
        :return: The matrix, or None.
        :rtype: PlotMatrixAggregate | None
        '''

        # A missing id is nothing.
        return self.records.get(id)

    # * method: save
    def save(self, matrix: PlotMatrixAggregate) -> None:
        '''
        Insert a matrix.

        :param matrix: The matrix to keep.
        :type matrix: PlotMatrixAggregate
        :return: None
        :rtype: None
        '''

        # Insert. These tests do not save twice.
        self.records[matrix.id] = matrix

    # * method: update
    def update(self, matrix: PlotMatrixAggregate) -> None:
        '''
        Replace a kept matrix.

        :param matrix: The replacement matrix.
        :type matrix: PlotMatrixAggregate
        :return: None
        :rtype: None
        '''

        # Update does not insert.
        self.updates.append(matrix.id)
        if matrix.id not in self.records:
            raise ServiceError(MATRIX_NOT_KEPT_ID, message='missing')
        self.records[matrix.id] = matrix

# *** tests

# ** test: create_plot_accepts_appearance_and_has_no_color_parameter
def test_create_plot_accepts_appearance_and_has_no_color_parameter():
    '''
    CreatePlot accepts legend and font keywords and returns a record, not a picture.
    '''

    # Color is not a parameter beside series. Id and description do not move.
    signature = inspect.signature(CreatePlot.execute)
    assert 'show_legend' in signature.parameters
    assert 'font_family' in signature.parameters
    assert 'color' not in signature.parameters
    assert list(signature.parameters)[:6] == [
        'self',
        'name',
        'kind',
        'series',
        'id',
        'description',
    ]
    service = MemoryPlotService()
    created = DomainEvent.handle(
        CreatePlot,
        dependencies={'plot_service': service},
        name='Sales by Region',
        kind='line',
        series=[series(color='#ff0000')],
        description='A claim.',
        show_legend=False,
        font_family='serif',
    )

    # The record is kept. It is not a picture. The id is not derived from color.
    assert created.id == 'sales_by_region'
    assert created.description == 'A claim.'
    assert created.show_legend is False
    assert created.font_family == 'serif'
    assert created.series[0].color == '#ff0000'
    assert not isinstance(created, (bytes, str))

# ** test: update_clears_omitted_appearance_and_does_not_derive_an_id
def test_update_clears_omitted_appearance_and_does_not_derive_an_id():
    '''
    An omitted field on update clears it. A replacement series does not keep color.
    '''

    # Keep a hidden legend and a colored series.
    service = MemoryPlotService()
    DomainEvent.handle(
        CreatePlot,
        dependencies={'plot_service': service},
        name='Sales by Region',
        kind='line',
        series=[series(color='red')],
        show_legend=False,
        title_size=14,
    )
    updated = DomainEvent.handle(
        UpdatePlot,
        dependencies={'plot_service': service},
        id='sales_by_region',
        name='Quarterly Sales',
        kind='line',
        series=[series()],
        legend_label='ignored',
    )

    # legend_label is not a plot parameter, so it does not derive an id.
    assert 'legend_label' not in inspect.signature(UpdatePlot.execute).parameters
    assert updated.id == 'sales_by_region'
    assert updated.show_legend is None
    assert updated.title_size is None
    assert updated.series[0].color is None
    assert service.get('quarterly_sales') is None
    assert service.update_calls == ['sales_by_region']

# ** test: create_matrix_accepts_spacing_and_has_no_color_parameter
def test_create_matrix_accepts_spacing_and_has_no_color_parameter():
    '''
    CreateMatrix accepts the grid fields and does not take a color.
    '''

    # Color is not a matrix parameter.
    signature = inspect.signature(CreateMatrix.execute)
    assert 'show_legend' in signature.parameters
    assert 'row_spacing' in signature.parameters
    assert 'color' not in signature.parameters
    service = MemoryMatrixService()
    created = DomainEvent.handle(
        CreateMatrix,
        dependencies={'matrix_service': service},
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[cell('left', 'red')],
        show_legend=False,
        row_spacing=0.4,
    )

    # The record is kept. Zero-point-four is the supplied gap. It is not a picture.
    assert created.id == 'sales_by_region'
    assert created.show_legend is False
    assert created.row_spacing == 0.4
    assert not isinstance(created, (bytes, str))

# ** test: update_matrix_disagreement_leaves_the_kept_record
def test_update_matrix_disagreement_leaves_the_kept_record():
    '''
    An update that asks for a disagreeing legend fails and does not replace the matrix.
    '''

    # The first matrix does not ask, so the colors may disagree.
    service = MemoryMatrixService()
    DomainEvent.handle(
        CreateMatrix,
        dependencies={'matrix_service': service},
        name='Sales by Region',
        rows=1,
        cols=2,
        cells=[cell('left', '#1f77b4'), cell('right', '#ff7f0e')],
    )
    before = service.get('sales_by_region').model_dump()
    with pytest.raises(ModelError):
        DomainEvent.handle(
            UpdateMatrix,
            dependencies={'matrix_service': service},
            id='sales_by_region',
            name='Sales by Region',
            rows=1,
            cols=2,
            cells=[cell('left', '#1f77b4'), cell('right', '#ff7f0e')],
            show_legend=True,
        )

    # The kept matrix is unchanged. Update was not called.
    assert service.updates == []
    assert service.get('sales_by_region').model_dump() == before
    assert service.get('sales_by_region').show_legend is None
