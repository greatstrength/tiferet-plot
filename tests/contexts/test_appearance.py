"""Tests for appearance on the fluent chain and the create handler."""

# *** imports

# ** app
from tiferet.contexts.app import AppSession
from tiferet.events import DomainEvent
from tiferet_plot.contexts.plot import (
    CREATE_MATRIX_EVENT_ID,
    CREATE_PLOT_EVENT_ID,
    PLOT_FLAG,
    PlotterSessionContext,
    create_handler,
)
from tiferet_plot.domain.plot import Mark, MatrixCell, Plot, PlotMatrix, Series
from tiferet_plot.events.plot import CreateMatrix, CreatePlot

# *** classes

# ** class: memory_service
class MemoryService:
    '''
    An in-memory service that inserts whatever the event declares.
    '''

    # * init
    def __init__(self) -> None:
        '''
        Start with no kept records.
        '''

        # The id is the key. The value is the record.
        self.records = {}

    # * method: exists
    def exists(self, id: str) -> bool:
        '''
        Check whether the id is kept.

        :param id: The record id.
        :type id: str
        :return: True when the id is kept.
        :rtype: bool
        '''

        # Exists follows the mapping.
        return id in self.records

    # * method: save
    def save(self, record) -> None:
        '''
        Insert the record.

        :param record: The declared record.
        :type record: Any
        :return: None
        :rtype: None
        '''

        # Insert. These tests do not save twice.
        self.records[record.id] = record

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

# ** function: bound
def bound(mapping):
    '''
    Bind a session whose create handler resolves the given events.

    :param mapping: Service id to event.
    :type mapping: dict
    :return: The session.
    :rtype: PlotterSessionContext
    '''

    # The flag is recorded only by which event the handler asks for.
    def get_dependency(service_id, *flags):
        '''
        Return the mapped event.

        :param service_id: The service id.
        :type service_id: str
        :param flags: The DI flags.
        :type flags: tuple
        :return: The mapped event.
        :rtype: Any
        '''

        # The plot flag is the only namespace this handler uses.
        assert flags == (PLOT_FLAG,)
        return mapping[service_id]

    # The five framework handlers stay unwired.
    return PlotterSessionContext.from_domain(
        AppSession(id='plotter', name='Plotter'),
        get_dependency=get_dependency,
        create_handler=create_handler(get_dependency),
    )

# *** tests

# ** test: the_chain_keeps_appearance_and_does_not_shift_ids
def test_the_chain_keeps_appearance_and_does_not_shift_ids():
    '''
    draft and add_series keep positional ids and do not clear appearance.
    '''

    # A third positional argument is still the id, not a legend field.
    service = MemoryService()
    session = bound({
        CREATE_PLOT_EVENT_ID: CreatePlot(service),
    })
    assert not hasattr(session, 'set_color')
    assert not hasattr(session, 'set_legend')
    session.draft('Sales by Region', 'line', 'custom-id', show_legend=False)
    session.add_series('Revenue', line_marks(), color='#ff0000')
    kept = session.create()
    assert kept.id == 'custom-id'
    assert kept.show_legend is False
    assert kept.series[0].color == '#ff0000'

    # Omitting the id still derives it. A later series does not clear the flag.
    session.draft('Sales by Region', 'line', show_legend=False)
    session.add_series('Revenue', line_marks(), 'rev', color='#ff0000')
    session.append('rev', line_marks())
    derived = session.create()
    assert derived.id == 'sales_by_region'
    assert derived.series[0].id == 'rev'
    assert derived.show_legend is False
    assert derived.series[0].color == '#ff0000'

# ** test: edit_copies_color_and_does_not_derive_an_id
def test_edit_copies_color_and_does_not_derive_an_id():
    '''
    edit copies series color and does not derive an id from it.
    '''

    # The caller already holds a colored series and a supplied id.
    original = Plot(
        id='custom-id',
        name='Sales by Region',
        kind='line',
        series=[
            Series(
                id='rev',
                name='Revenue',
                color='#ff0000',
                marks=line_marks(),
            ),
        ],
    )
    service = MemoryService()
    session = bound({
        CREATE_PLOT_EVENT_ID: CreatePlot(service),
    })
    session.edit(original)
    kept = session.create()

    # The copy has the color. The id was not derived from it.
    assert kept.id == 'custom-id'
    assert kept.series[0].id == 'rev'
    assert kept.series[0].color == '#ff0000'
    assert original.series[0].color == '#ff0000'

# ** test: the_create_handler_passes_plot_and_matrix_appearance
def test_the_create_handler_passes_plot_and_matrix_appearance():
    '''
    The session create handler passes a plot legend flag and a matrix spacing.
    '''

    # The events return the records they declare, so a missed field is visible.
    plot_service = MemoryService()
    matrix_service = MemoryService()
    session = bound({
        CREATE_PLOT_EVENT_ID: CreatePlot(plot_service),
        CREATE_MATRIX_EVENT_ID: CreateMatrix(matrix_service),
    })
    plot = Plot(
        name='Sales by Region',
        kind='line',
        show_legend=False,
        series=[
            Series(name='Revenue', marks=line_marks()),
        ],
    )
    matrix = PlotMatrix(
        name='Sales by Region',
        rows=1,
        cols=1,
        row_spacing=0.4,
        cells=[
            MatrixCell(
                row=0,
                col=0,
                plot=Plot(
                    id='revenue_plot',
                    name='Revenue',
                    kind='line',
                    series=[Series(name='Revenue', marks=line_marks())],
                ),
            ),
        ],
    )

    # The handler passes the fields. It does not draw.
    kept_plot = session.create(plot)
    kept_matrix = session.create(matrix)
    assert kept_plot.show_legend is False
    assert kept_matrix.row_spacing == 0.4
    assert not isinstance(kept_plot, (bytes, str))
    assert not isinstance(kept_matrix, (bytes, str))
    assert DomainEvent is not None
