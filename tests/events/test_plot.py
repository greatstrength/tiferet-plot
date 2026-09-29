"""Tests for creating, loading, and removing a plot."""

# *** imports

# ** core
import ast
import inspect
from pathlib import Path

# ** infra
import pytest
from pydantic import ValidationError

# ** app
from tiferet import TiferetError
from tiferet.events import DomainEvent
from tiferet.interfaces import ServiceError
from tiferet_plot.domain.plot import Mark, Series
from tiferet_plot.events.plot import (
    CreatePlot,
    GetPlot,
    ListPlots,
    PlotEvent,
    RemovePlot,
    UpdatePlot,
)
from tiferet_plot.interfaces.plot import (
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
    PlotService,
)
from tiferet_plot.mappers.plot import PlotAggregate
import tiferet_plot.events.plot as events_module

# *** classes

# ** class: fake_plot_service
class FakePlotService(PlotService):
    '''
    An in-memory plot service that records write calls.

    A failed create must be able to prove it did not call save.
    '''

    # * init
    def __init__(self) -> None:
        '''
        Start with no kept records and no write calls.
        '''

        # Records are keyed by plot id. Calls prove which writes ran.
        self.records = {}
        self.save_calls = []
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
        return self.get(id) is not None

    # * method: get
    def get(self, id: str) -> PlotAggregate | None:
        '''
        Return the kept plot, or nothing.

        :param id: The plot id.
        :type id: str
        :return: The plot, or None.
        :rtype: PlotAggregate | None
        '''

        # A missing id is nothing, not an error.
        return self.records.get(id)

    # * method: list
    def list(self) -> list[PlotAggregate]:
        '''
        Return the kept records.

        :return: The kept plots.
        :rtype: list[PlotAggregate]
        '''

        # Return records, not a display string.
        return list(self.records.values())

    # * method: save
    def save(self, plot: PlotAggregate) -> None:
        '''
        Insert a plot whose id is not kept.

        :param plot: The plot to keep.
        :type plot: PlotAggregate
        :return: None
        :rtype: None
        '''

        # Record the call before rejecting, so a forbidden save is visible.
        self.save_calls.append(plot.id)
        if plot.id in self.records:
            ServiceError.raise_for(
                self,
                PLOT_ALREADY_KEPT_ID,
                message=f'Plot {plot.id!r} is already kept.',
                plot_id=plot.id,
            )
        self.records[plot.id] = plot

    # * method: update
    def update(self, plot: PlotAggregate) -> None:
        '''
        Replace a kept plot with the same id.

        :param plot: The replacement plot.
        :type plot: PlotAggregate
        :return: None
        :rtype: None
        '''

        # Record the call. Update does not insert.
        self.update_calls.append(plot.id)
        if plot.id not in self.records:
            ServiceError.raise_for(
                self,
                PLOT_NOT_KEPT_ID,
                message=f'Plot {plot.id!r} is not kept.',
                plot_id=plot.id,
            )
        self.records[plot.id] = plot

    # * method: delete
    def delete(self, id: str) -> None:
        '''
        Remove a kept plot. A missing id changes nothing.

        :param id: The plot id.
        :type id: str
        :return: None
        :rtype: None
        '''

        # Pop is idempotent. Series live inside the record.
        self.records.pop(id, None)

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

# ** function: line_series
def line_series(name='Revenue', y=(3, 4)):
    '''
    Build one valid line series.

    :param name: The series name.
    :type name: str
    :param y: The y values.
    :type y: tuple
    :return: A series whose id will be derived from the name.
    :rtype: list
    '''

    # One series is enough for a declaration.
    return [
        Series(name=name, marks=line_marks(y=y)),
    ]

# ** function: run
def run(event, service, **kwargs):
    '''
    Execute a plot event against a fake service.

    :param event: The event class.
    :type event: type
    :param service: The plot service.
    :type service: PlotService
    :param kwargs: The event arguments.
    :type kwargs: dict
    :return: The event result.
    :rtype: object
    '''

    # The session calls handle. Tests do the same.
    return DomainEvent.handle(
        event,
        dependencies={'plot_service': service},
        **kwargs,
    )

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
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)

    # Return the imported module names.
    return names

# *** tests

# ** test: events_extend_one_base_and_do_not_draw
def test_events_extend_one_base_and_do_not_draw():
    '''
    The five events extend one base that holds the plot service.
    '''

    # One base holds the service. Concrete events add only execute.
    events = (CreatePlot, GetPlot, ListPlots, UpdatePlot, RemovePlot)
    assert PlotEvent.__bases__ == (DomainEvent,)
    assert 'plot_service' in inspect.signature(PlotEvent.__init__).parameters
    for event in events:
        assert event.__bases__ == (PlotEvent,)
        assert 'execute' in event.__dict__
        assert '__init__' not in event.__dict__

    # None of them import a drawing tool, a repository, or a renderer.
    imported = ' '.join(imported_modules(events_module))
    assert 'matplotlib' not in imported
    assert 'repos' not in imported
    assert 'utils' not in imported
    source = Path(events_module.__file__).read_text().lower()
    assert 'matplotlib' not in source
    assert 'plotconfigrepository' not in source
    assert 'png' not in source

# ** test: create_derives_id_and_keeps_the_record
def test_create_derives_id_and_keeps_the_record():
    '''
    Create with no id derives sales_by_region and keeps the record.
    '''

    # Declare and keep the acceptance record. No id is supplied.
    service = FakePlotService()
    created = run(
        CreatePlot,
        service,
        name='Sales by Region',
        kind='line',
        series=line_series(),
    )

    # The id is the snake_case name, and the record is kept.
    assert created.id == 'sales_by_region'
    assert created.series[0].id == 'revenue'
    assert service.exists('sales_by_region') is True
    assert service.get('sales_by_region').name == 'Sales by Region'
    assert not isinstance(created, (bytes, str))

# ** test: create_keeps_a_supplied_id
def test_create_keeps_a_supplied_id():
    '''
    A supplied id is kept and is not rewritten from the name.
    '''

    # Supply an id that is not the snake_case of the name.
    service = FakePlotService()
    created = run(
        CreatePlot,
        service,
        id='Custom-Id',
        name='Sales by Region',
        kind='line',
        series=line_series(),
    )

    # The supplied id is the kept id.
    assert created.id == 'Custom-Id'
    assert service.exists('Custom-Id') is True
    assert service.get('sales_by_region') is None

# ** test: create_of_a_kept_id_fails_and_leaves_the_first_record
def test_create_of_a_kept_id_fails_and_leaves_the_first_record():
    '''
    A second plot that resolves to a kept id fails before save.
    '''

    # Keep the first record.
    service = FakePlotService()
    run(
        CreatePlot,
        service,
        name='Sales by Region',
        kind='line',
        description='First claim.',
        series=line_series(),
    )
    before = service.get('sales_by_region').model_dump()

    # The same name resolves to the same id. Create must not save again.
    with pytest.raises(TiferetError) as caught:
        run(
            CreatePlot,
            service,
            name='Sales by Region',
            kind='line',
            description='Second claim.',
            series=line_series(y=(9, 8)),
        )

    # The failure is the rejected second save, and the first record stays.
    assert caught.value.error_code == PLOT_ALREADY_KEPT_ID
    assert service.save_calls == ['sales_by_region']
    assert service.get('sales_by_region').model_dump() == before

# ** test: create_with_invalid_kind_or_marks_does_not_save
@pytest.mark.parametrize('kind,marks', [
    ('histogram', line_marks()),
    ('line', [Mark(role='category', values=('North', 'South')),
              Mark(role='height', values=(1, 2))]),
])
def test_create_with_invalid_kind_or_marks_does_not_save(kind, marks):
    '''
    An invalid kind or illegal marks fail before save.
    '''

    # Declaration rejects the record. The store is not asked to keep it.
    service = FakePlotService()
    with pytest.raises(ValidationError):
        run(
            CreatePlot,
            service,
            name='Sales by Region',
            kind=kind,
            series=[Series(name='Revenue', marks=marks)],
        )

    # Nothing was kept.
    assert service.save_calls == []
    assert service.list() == []

# ** test: get_returns_the_record_or_fails
def test_get_returns_the_record_or_fails():
    '''
    Get of a kept id returns the record. Get of a missing id fails.
    '''

    # Keep one record, then load it by the kept id.
    service = FakePlotService()
    created = run(
        CreatePlot,
        service,
        name='Sales by Region',
        kind='line',
        series=line_series(),
    )
    loaded = run(GetPlot, service, id='sales_by_region')

    # The loaded record is the kept record, not a picture.
    assert loaded.id == created.id
    assert loaded.name == 'Sales by Region'
    assert not isinstance(loaded, (bytes, str))

    # A missing id fails. It is not derived from a name.
    with pytest.raises(TiferetError) as caught:
        run(GetPlot, service, id='missing')
    assert caught.value.error_code == PLOT_NOT_KEPT_ID
    assert service.get('missing') is None

# ** test: list_returns_records
def test_list_returns_records():
    '''
    List returns kept records. An empty store returns an empty list.
    '''

    # An empty store is an empty list, not a sentence and not a picture.
    service = FakePlotService()
    empty = run(ListPlots, service)
    assert empty == []
    assert not isinstance(empty, (str, bytes))

    # After one create, the list is that record.
    run(
        CreatePlot,
        service,
        name='Sales by Region',
        kind='line',
        series=line_series(),
    )
    listed = run(ListPlots, service)
    assert [plot.id for plot in listed] == ['sales_by_region']
    assert all(not isinstance(plot, (bytes, str)) for plot in listed)

# ** test: update_with_illegal_marks_does_not_call_update
def test_update_with_illegal_marks_does_not_call_update():
    '''
    Update re-checks kind and marks before it calls the service.
    '''

    # Keep a valid record, then offer marks the kind does not allow.
    service = FakePlotService()
    run(
        CreatePlot,
        service,
        name='Sales by Region',
        kind='line',
        series=line_series(),
    )
    before = service.get('sales_by_region').model_dump()
    with pytest.raises(ValidationError):
        run(
            UpdatePlot,
            service,
            id='sales_by_region',
            name='Sales by Region',
            kind='line',
            series=[
                Series(
                    name='Revenue',
                    marks=[
                        Mark(role='category', values=('North', 'South')),
                        Mark(role='height', values=(1, 2)),
                    ],
                ),
            ],
        )

    # The kept record is unchanged, and update was not called.
    assert service.update_calls == []
    assert service.get('sales_by_region').model_dump() == before

# ** test: update_keeps_an_edit_and_does_not_insert
def test_update_keeps_an_edit_and_does_not_insert():
    '''
    Update changes the name or marks and does not change the id.
    '''

    # Keep a record, then replace its name and marks.
    service = FakePlotService()
    run(
        CreatePlot,
        service,
        name='Sales by Region',
        kind='line',
        series=line_series(),
    )
    updated = run(
        UpdatePlot,
        service,
        id='sales_by_region',
        name='Quarterly Sales',
        kind='line',
        series=line_series(y=(9, 8)),
    )

    # The id stays. The new name did not become a second record.
    assert updated.id == 'sales_by_region'
    loaded = service.get('sales_by_region')
    assert loaded.name == 'Quarterly Sales'
    assert loaded.series[0].marks[1].values == (9, 8)
    assert service.get('quarterly_sales') is None
    assert service.exists('sales_by_region') is True

    # A missing id fails and does not insert.
    with pytest.raises(ServiceError) as caught:
        run(
            UpdatePlot,
            service,
            id='missing',
            name='Sales by Region',
            kind='line',
            series=line_series(),
        )
    assert caught.value.error_code == PLOT_NOT_KEPT_ID
    assert service.update_calls[-1] == 'missing'
    assert service.get('missing') is None
    assert service.get('sales_by_region').id == 'sales_by_region'

# ** test: remove_deletes_by_id_and_is_idempotent
def test_remove_deletes_by_id_and_is_idempotent():
    '''
    Remove of a kept id drops it. Remove of a missing id succeeds.
    '''

    # A missing id succeeds and returns the id, not a record.
    service = FakePlotService()
    missing = run(RemovePlot, service, id='missing')
    assert missing == 'missing'
    assert not isinstance(missing, PlotAggregate)
    assert service.list() == []

    # Keep a record, then remove it. The series go with the record.
    run(
        CreatePlot,
        service,
        name='Sales by Region',
        kind='line',
        series=line_series(),
    )
    removed = run(RemovePlot, service, id='sales_by_region')
    assert removed == 'sales_by_region'
    assert service.exists('sales_by_region') is False
    assert service.get('sales_by_region') is None

    # A second remove of that id still succeeds.
    assert run(RemovePlot, service, id='sales_by_region') == 'sales_by_region'
