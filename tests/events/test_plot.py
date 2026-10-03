"""Tests for creating a plot and a plot matrix."""

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
    CreateMatrix,
    CreatePlot,
    GetMatrix,
    GetPlot,
    ListMatrices,
    ListPlots,
    MatrixEvent,
    PlotEvent,
    RemoveMatrix,
    RemovePlot,
    UpdateMatrix,
    UpdatePlot,
)
from tiferet_plot.interfaces.plot import (
    MATRIX_ALREADY_KEPT_ID,
    MATRIX_NOT_KEPT_ID,
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
    MatrixService,
    PlotService,
)
from tiferet_plot.mappers.plot import (
    PlotAggregate,
    PlotConfigObject,
    PlotMatrixAggregate,
)
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

# ** class: memory_matrix_service
class MemoryMatrixService(MatrixService):
    '''
    An in-memory matrix service for event tests.

    It records save and update calls so a failed declaration can prove
    it did not keep anything.
    '''

    # * init
    def __init__(self) -> None:
        '''
        Start with no kept records.
        '''

        # The records are keyed by matrix id.
        self.records = {}
        self.saves = []
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
        return self.get(id) is not None

    # * method: get
    def get(self, id: str):
        '''
        Return the kept matrix, or nothing.

        :param id: The matrix id.
        :type id: str
        :return: The matrix, or None.
        :rtype: PlotMatrixAggregate | None
        '''

        # A missing id is nothing, not an error.
        return self.records.get(id)

    # * method: list
    def list(self):
        '''
        Return the kept records.

        :return: The kept matrices.
        :rtype: list
        '''

        # Return records, not a display string.
        return list(self.records.values())

    # * method: save
    def save(self, matrix: PlotMatrixAggregate) -> None:
        '''
        Insert a matrix whose id is not kept.

        :param matrix: The matrix to keep.
        :type matrix: PlotMatrixAggregate
        :return: None
        :rtype: None
        '''

        # A second save does not replace the first record.
        if matrix.id in self.records:
            ServiceError.raise_for(
                self,
                MATRIX_ALREADY_KEPT_ID,
                message=f'Matrix {matrix.id!r} is already kept.',
                matrix_id=matrix.id,
            )
        self.records[matrix.id] = matrix
        self.saves.append(matrix.id)

    # * method: update
    def update(self, matrix: PlotMatrixAggregate) -> None:
        '''
        Replace a kept matrix with the same id.

        :param matrix: The replacement matrix.
        :type matrix: PlotMatrixAggregate
        :return: None
        :rtype: None
        '''

        # Update does not insert.
        if matrix.id not in self.records:
            ServiceError.raise_for(
                self,
                MATRIX_NOT_KEPT_ID,
                message=f'Matrix {matrix.id!r} is not kept.',
                matrix_id=matrix.id,
            )
        self.records[matrix.id] = matrix
        self.updates.append(matrix.id)

    # * method: delete
    def delete(self, id: str) -> None:
        '''
        Remove a kept matrix. A missing id changes nothing.

        :param id: The matrix id.
        :type id: str
        :return: None
        :rtype: None
        '''

        # Pop is idempotent.
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

# ** function: design_series
def design_series(x=('alpha', 'beta'), y=(1, 2), label=('run-1', 'run-2')):
    '''
    Build one line series with text x, numeric y, and an optional label.

    :param x: The x values.
    :type x: tuple
    :param y: The y values.
    :type y: tuple
    :param label: The point labels. Omit the role when None.
    :type label: tuple | None
    :return: One series named Trial. The id is derived from that name.
    :rtype: list
    '''

    # The series name is Trial. The text is not the id.
    marks = [
        Mark(role='x', values=x),
        Mark(role='y', values=y),
    ]
    if label is not None:
        marks.append(Mark(role='label', values=label))
    return [
        Series(name='Trial', marks=marks),
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

# ** function: cell
def cell(plot_id='revenue_plot', row=0, col=0, name='Revenue'):
    '''
    Build one occupied cell. The plot id is supplied.

    :param plot_id: The plot id.
    :type plot_id: str
    :param row: The zero-based row.
    :type row: int
    :param col: The zero-based column.
    :type col: int
    :param name: The plot name.
    :type name: str
    :return: A cell mapping.
    :rtype: dict
    '''

    # Matrix declaration must not fill a missing plot id.
    return {
        'row': row,
        'col': col,
        'plot': {
            'id': plot_id,
            'name': name,
            'kind': 'line',
            'series': [
                {
                    'id': 'rev-1',
                    'name': 'Revenue',
                    'marks': line_marks(),
                },
            ],
        },
    }
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

# ** test: create_declares_and_keeps
def test_create_declares_and_keeps():
    '''
    Create with no id derives the matrix id and keeps the cell plot id.
    '''

    # Declare through the event. The service is not a file.
    service = MemoryMatrixService()
    matrix = DomainEvent.handle(
        CreateMatrix,
        dependencies={'matrix_service': service},
        name='Sales by Region',
        rows=2,
        cols=2,
        cells=[cell()],
    )

    # The record is kept. Create did not return a picture.
    assert isinstance(matrix, PlotMatrixAggregate)
    assert not isinstance(matrix, bytes)
    assert matrix.id == 'sales_by_region'
    assert matrix.cells[0].plot.id == 'revenue_plot'
    assert service.exists('sales_by_region') is True
    assert service.saves == ['sales_by_region']

# ** test: create_keeps_a_supplied_id_and_rejects_a_second
def test_create_keeps_a_supplied_id_and_rejects_a_second():
    '''
    A supplied matrix id is kept. A second create of that id fails.
    '''

    # The first create inserts. The id is not rewritten from the name.
    service = MemoryMatrixService()
    first = DomainEvent.handle(
        CreateMatrix,
        dependencies={'matrix_service': service},
        id='Custom-Id',
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[cell()],
    )
    assert first.id == 'Custom-Id'

    # The second create fails before save. The first record stays.
    with pytest.raises(TiferetError) as caught:
        DomainEvent.handle(
            CreateMatrix,
            dependencies={'matrix_service': service},
            id='Custom-Id',
            name='A different title',
            rows=1,
            cols=1,
            cells=[cell(name='Cost')],
        )
    assert caught.value.error_code == MATRIX_ALREADY_KEPT_ID
    assert service.saves == ['Custom-Id']
    assert service.get('Custom-Id').name == 'Sales by Region'
    assert service.get('Custom-Id').cells[0].plot.name == 'Revenue'

# ** test: create_does_not_save_an_illegal_declaration
def test_create_does_not_save_an_illegal_declaration():
    '''
    A cell plot with no id fails, and save is not called.
    '''

    # The nested plot has a name and no id. Declaration must not fill one.
    service = MemoryMatrixService()
    illegal = cell()
    illegal['plot'].pop('id')
    with pytest.raises(ValidationError):
        DomainEvent.handle(
            CreateMatrix,
            dependencies={'matrix_service': service},
            name='Sales by Region',
            rows=1,
            cols=1,
            cells=[illegal],
        )

    # Nothing was kept.
    assert service.saves == []
    assert service.list() == []

# ** test: get_fails_when_missing_and_does_not_derive
def test_get_fails_when_missing_and_does_not_derive():
    '''
    Get of a missing id fails. A name is not turned into an id.
    '''

    # The kept id is the derived form. The name is not that id.
    service = MemoryMatrixService()
    DomainEvent.handle(
        CreateMatrix,
        dependencies={'matrix_service': service},
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[cell()],
    )
    loaded = DomainEvent.handle(
        GetMatrix,
        dependencies={'matrix_service': service},
        id='sales_by_region',
    )
    assert loaded.cells[0].plot.id == 'revenue_plot'

    # Looking up the name does not derive sales_by_region.
    with pytest.raises(TiferetError) as caught:
        DomainEvent.handle(
            GetMatrix,
            dependencies={'matrix_service': service},
            id='Sales by Region',
        )
    assert caught.value.error_code == MATRIX_NOT_KEPT_ID

# ** test: list_of_an_empty_store_is_an_empty_list
def test_list_of_an_empty_store_is_an_empty_list():
    '''
    List of an empty store returns an empty list, not a string.
    '''

    # No records have been kept.
    service = MemoryMatrixService()
    listed = DomainEvent.handle(
        ListMatrices,
        dependencies={'matrix_service': service},
    )

    # The result is the service list. It is not a sentence.
    assert listed == []
    assert not isinstance(listed, str)
    assert not isinstance(listed, bytes)

# ** test: update_changes_the_name_and_not_the_id
def test_update_changes_the_name_and_not_the_id():
    '''
    Update of a kept id changes the name and does not re-derive any id.
    '''

    # Keep a matrix, then replace the name. The plot id stays supplied.
    service = MemoryMatrixService()
    DomainEvent.handle(
        CreateMatrix,
        dependencies={'matrix_service': service},
        id='Custom-Id',
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[cell()],
    )
    updated = DomainEvent.handle(
        UpdateMatrix,
        dependencies={'matrix_service': service},
        id='Custom-Id',
        name='Quarterly Sales',
        rows=1,
        cols=1,
        cells=[cell()],
    )

    # The key did not follow the new name. The plot id was not derived.
    assert updated.id == 'Custom-Id'
    assert updated.name == 'Quarterly Sales'
    assert updated.cells[0].plot.id == 'revenue_plot'
    assert service.get('quarterly_sales') is None
    assert service.updates == ['Custom-Id']

# ** test: update_of_a_missing_id_does_not_insert
def test_update_of_a_missing_id_does_not_insert():
    '''
    Update of a missing id fails and does not insert.
    '''

    # Nothing is kept. Update must not become create.
    service = MemoryMatrixService()
    with pytest.raises(TiferetError) as caught:
        DomainEvent.handle(
            UpdateMatrix,
            dependencies={'matrix_service': service},
            id='Custom-Id',
            name='Sales by Region',
            rows=1,
            cols=1,
            cells=[cell()],
        )
    assert caught.value.error_code == MATRIX_NOT_KEPT_ID
    assert service.updates == []
    assert service.get('Custom-Id') is None

# ** test: remove_is_idempotent_and_does_not_return_the_matrix
def test_remove_is_idempotent_and_does_not_return_the_matrix():
    '''
    Remove of a kept id makes exists false. Remove of a missing id succeeds.
    '''

    # Remove the kept record. The return is the id, not the matrix.
    service = MemoryMatrixService()
    DomainEvent.handle(
        CreateMatrix,
        dependencies={'matrix_service': service},
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[cell()],
    )
    removed = DomainEvent.handle(
        RemoveMatrix,
        dependencies={'matrix_service': service},
        id='sales_by_region',
    )
    assert removed == 'sales_by_region'
    assert not isinstance(removed, PlotMatrixAggregate)
    assert service.exists('sales_by_region') is False

    # A second remove changes nothing and still does not return a matrix.
    again = DomainEvent.handle(
        RemoveMatrix,
        dependencies={'matrix_service': service},
        id='sales_by_region',
    )
    assert again == 'sales_by_region'
    assert service.list() == []

# ** test: matrix_events_do_not_import_a_drawing_tool_or_a_repository
def test_matrix_events_do_not_import_a_drawing_tool_or_a_repository():
    '''
    Matrix events do not import Matplotlib, a repository, or the plot event base.
    '''

    # The base holds MatrixService. It does not extend a plot event.
    assert issubclass(CreateMatrix, MatrixEvent)
    assert issubclass(GetMatrix, MatrixEvent)
    assert issubclass(ListMatrices, MatrixEvent)
    assert issubclass(UpdateMatrix, MatrixEvent)
    assert issubclass(RemoveMatrix, MatrixEvent)
    imported = ' '.join(imported_modules(events_module))
    assert 'matplotlib' not in imported
    assert 'repos' not in imported
    assert 'utils' not in imported
    source = inspect.getsource(MatrixEvent)
    assert 'PlotEvent' not in source
    assert 'PlotService' not in source
    assert 'png' not in Path(events_module.__file__).read_text().lower()

# ** test: create_plot_carries_title_and_axis_text
def test_create_plot_carries_title_and_axis_text():
    '''
    CreatePlot accepts title and axis text and does not derive an id from them.
    '''

    # The new arguments are keywords. They do not move id or description.
    params = inspect.signature(CreatePlot.execute).parameters
    assert list(params)[:5] == ['self', 'name', 'kind', 'series', 'id']
    assert params['description'].default is None
    assert params['title'].kind is inspect.Parameter.KEYWORD_ONLY
    for name in ('title', 'x_title', 'x_unit', 'y_title', 'y_unit'):
        assert name in params
        assert params[name].default is None

    # Omitted text stays absent. The result is a record, not a picture.
    service = FakePlotService()
    omitted = run(
        CreatePlot,
        service,
        name='Sales by Region',
        kind='line',
        series=line_series(),
        description='Revenue compared across regions.',
    )
    assert omitted.id == 'sales_by_region'
    assert omitted.title is None
    assert omitted.y_title is None
    assert omitted.description == 'Revenue compared across regions.'
    assert not isinstance(omitted, (bytes, str))

    # A supplied id is kept. Title and axis text do not rewrite it.
    kept = run(
        CreatePlot,
        FakePlotService(),
        id='Custom-Id',
        name='Sales by Region',
        kind='line',
        series=line_series(),
        description='A claim.',
        title='Quarterly sales, 2024',
        x_title='Year',
        y_title='Revenue',
        y_unit='USD',
    )
    assert kept.id == 'Custom-Id'
    assert kept.title == 'Quarterly sales, 2024'
    assert kept.x_title == 'Year'
    assert kept.y_unit == 'USD'
    assert kept.description == 'A claim.'

    # A second create of that id fails. The first record stays.
    with pytest.raises(TiferetError) as caught:
        run(
            CreatePlot,
            service,
            name='Sales by Region',
            kind='line',
            series=line_series(),
            title='A different title',
        )
    assert caught.value.error_code == PLOT_ALREADY_KEPT_ID
    assert service.get('sales_by_region').title is None

# ** test: update_plot_can_change_or_clear_figure_text
def test_update_plot_can_change_or_clear_figure_text():
    '''
    Update can change title or a unit. Omitting either clears it.
    '''

    # Keep a record that already has title and axis text.
    service = FakePlotService()
    run(
        CreatePlot,
        service,
        id='Custom-Id',
        name='Sales by Region',
        kind='line',
        series=line_series(),
        title='Quarterly sales, 2024',
        y_title='Revenue',
        y_unit='USD',
    )
    changed = run(
        UpdatePlot,
        service,
        id='Custom-Id',
        name='Quarterly Sales',
        kind='line',
        series=line_series(),
        title='A later title',
        y_title='Revenue',
        y_unit='EUR',
    )

    # The id did not follow the new name, the title, or the unit.
    assert changed.id == 'Custom-Id'
    assert changed.name == 'Quarterly Sales'
    assert changed.title == 'A later title'
    assert changed.y_unit == 'EUR'
    assert service.get('quarterly_sales') is None

    # An omitted title and an omitted unit are cleared, not merged.
    cleared = run(
        UpdatePlot,
        service,
        id='Custom-Id',
        name='Quarterly Sales',
        kind='line',
        series=line_series(),
        y_title='Revenue',
    )
    assert cleared.id == 'Custom-Id'
    assert cleared.title is None
    assert cleared.y_unit is None
    assert cleared.y_title == 'Revenue'

# ** test: create_matrix_accepts_title_and_not_axis_text
def test_create_matrix_accepts_title_and_not_axis_text():
    '''
    CreateMatrix accepts title. It does not gain an axis parameter.
    '''

    # Title is optional. Axis text is not a matrix parameter.
    params = inspect.signature(CreateMatrix.execute).parameters
    assert 'title' in params
    assert params['title'].default is None
    for name in ('x_title', 'x_unit', 'y_title', 'y_unit'):
        assert name not in params
    assert 'x_title' not in inspect.signature(UpdateMatrix.execute).parameters

    # A supplied title is kept. The id still comes from the name.
    service = MemoryMatrixService()
    matrix = DomainEvent.handle(
        CreateMatrix,
        dependencies={'matrix_service': service},
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[cell()],
        title='Quarterly sales by region',
    )
    assert matrix.id == 'sales_by_region'
    assert matrix.title == 'Quarterly sales by region'
    assert not isinstance(matrix, bytes)

    # An omitted title on update clears it and does not change the id.
    updated = DomainEvent.handle(
        UpdateMatrix,
        dependencies={'matrix_service': service},
        id='sales_by_region',
        name='Quarterly Sales',
        rows=1,
        cols=1,
        cells=[cell()],
    )
    assert updated.id == 'sales_by_region'
    assert updated.title is None
    assert service.get('quarterly_sales') is None

# ** test: create_keeps_text_on_a_line_and_rejects_a_second_save
def test_create_keeps_text_on_a_line_and_rejects_a_second_save():
    '''
    Create of a labeled line keeps the marks. A second save of that id fails.
    '''

    # Declare and keep the acceptance record. No plot id is supplied.
    service = FakePlotService()
    series = design_series()
    created = run(
        CreatePlot,
        service,
        name='Design Response',
        kind='line',
        series=series,
    )
    loaded = run(GetPlot, service, id='design_response')

    # The ids come from the names. The marks come back unchanged.
    assert created.id == 'design_response'
    assert created.series[0].id == 'trial'
    assert [mark.role for mark in loaded.series[0].marks] == ['x', 'y', 'label']
    assert loaded.series[0].marks[0].values == ('alpha', 'beta')
    assert loaded.series[0].marks[1].values == (1, 2)
    assert loaded.series[0].marks[2].values == ('run-1', 'run-2')

    # The stored body excludes the plot id. Create and update gain no text fields.
    stored = PlotConfigObject.from_model(created).to_primitive('to_data')
    assert 'id' not in stored
    assert 'rotation' not in stored
    assert 'size' not in stored
    assert 'label' not in inspect.signature(CreatePlot.execute).parameters
    assert 'rotation' not in inspect.signature(CreatePlot.execute).parameters
    assert 'label' not in inspect.signature(UpdatePlot.execute).parameters
    assert 'rotation' not in inspect.signature(UpdatePlot.execute).parameters

    # Saving a second time is still the rejected second save.
    with pytest.raises(TiferetError) as caught:
        run(
            CreatePlot,
            service,
            name='Design Response',
            kind='line',
            series=series,
        )
    assert caught.value.error_code == PLOT_ALREADY_KEPT_ID
    assert service.save_calls == ['design_response']
    assert service.get('design_response').series[0].marks[0].values == ('alpha', 'beta')

# ** test: update_of_label_or_a_design_name_does_not_change_ids
def test_update_of_label_or_a_design_name_does_not_change_ids():
    '''
    Adding or dropping label, or renaming a design, does not change ids.
    '''

    # Keep a line whose x is the design names. No label yet.
    service = FakePlotService()
    run(
        CreatePlot,
        service,
        name='Design Response',
        kind='line',
        series=design_series(label=None),
    )

    # Adding label does not recompute the plot id or the series id.
    added = run(
        UpdatePlot,
        service,
        id='design_response',
        name='Design Response',
        kind='line',
        series=design_series(),
    )
    assert added.id == 'design_response'
    assert added.series[0].id == 'trial'
    assert [mark.role for mark in added.series[0].marks] == ['x', 'y', 'label']

    # Dropping label does not recompute either id.
    dropped = run(
        UpdatePlot,
        service,
        id='design_response',
        name='Design Response',
        kind='line',
        series=design_series(label=None),
    )
    assert dropped.id == 'design_response'
    assert dropped.series[0].id == 'trial'
    assert [mark.role for mark in dropped.series[0].marks] == ['x', 'y']

    # Changing a design name from alpha to gamma does not recompute either id.
    renamed = run(
        UpdatePlot,
        service,
        id='design_response',
        name='Design Response',
        kind='line',
        series=design_series(x=('gamma', 'beta'), label=None),
    )
    assert renamed.id == 'design_response'
    assert renamed.series[0].id == 'trial'
    assert renamed.series[0].marks[0].values == ('gamma', 'beta')
    assert service.get('gamma') is None
    assert service.get('alpha') is None
