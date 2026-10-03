"""The plotter session."""

# *** imports

# ** core
from typing import Any, Callable, Dict, List, Optional, Tuple

# ** app
from tiferet.contexts.app import AppSessionContext, raise_unwired_handler_error
from tiferet.contexts.cache import CacheContext
from tiferet.domain import AppServiceDependency
from ..domain.plot import (
    Mark,
    Plot,
    Series,
    _is_blank,
    _snake_case,
)

# *** constants

# ** constant: plot_flag
PLOT_FLAG = 'plot'

# ** constant: plot_service_cache_prefix
PLOT_SERVICE_CACHE_PREFIX: Tuple[str, ...] = ('plot', 'services')

# ** constant: create_plot_event_id
CREATE_PLOT_EVENT_ID = 'create_plot_evt'

# ** constant: update_plot_event_id
UPDATE_PLOT_EVENT_ID = 'update_plot_evt'

# ** constant: create_matrix_event_id
CREATE_MATRIX_EVENT_ID = 'create_matrix_evt'

# ** constant: renderer_service_id
RENDERER_SERVICE_ID = 'renderer_service'

# ** constant: plot_service_id
PLOT_SERVICE_ID = 'plot_service'

# ** constant: matrix_service_id
MATRIX_SERVICE_ID = 'matrix_service'

# *** functions

# ** function: add_default_plot_services
def add_default_plot_services(services: Dict[str, Any]) -> Callable:
    '''
    Decorator factory that pre-seeds a cache with the plotter's default services.

    The events and the renderer ship as defaults under the plotter's own
    cache namespace. They are not framework infrastructure.

    :param services: A mapping of service id to raw service dependency dicts.
    :type services: Dict[str, Any]
    :return: A decorator that wraps a cache-builder callable.
    :rtype: Callable
    '''

    # Return the decorator that wraps the cache-builder.
    def decorator(build_fn: Callable) -> Callable:

        # Build the cache, then populate it with the default service dependencies.
        def wrapper(*args, **kwargs) -> CacheContext:

            # Delegate to the wrapped cache-builder.
            cache = build_fn(*args, **kwargs)

            # Reconstitute each raw service dict and cache it by service id.
            for service_id, service_data in services.items():
                cache.set(
                    service_id,
                    AppServiceDependency.model_validate({
                        **service_data,
                        'service_id': service_id,
                    }),
                    *PLOT_SERVICE_CACHE_PREFIX,
                )

            # Return the populated cache context.
            return cache

        # Return the cache-builder wrapper.
        return wrapper

    # Return the decorator.
    return decorator

# ** function: get_default_plot_services
def get_default_plot_services(cache: CacheContext) -> List[AppServiceDependency]:
    '''
    Return the default plotter services seeded on the cache.

    :param cache: The cache context to read.
    :type cache: CacheContext
    :return: The seeded plotter service dependencies.
    :rtype: List[AppServiceDependency]
    '''

    # Return the seeded services as a list.
    return list(cache.get_by_prefix(*PLOT_SERVICE_CACHE_PREFIX).values())

# ** function: create_handler
def create_handler(get_dependency: Callable) -> Callable:
    '''
    Build the create handler.

    The handler calls the plot create event or the matrix create event
    and returns the record. It does not draw, and it does not open a
    publication file.

    :param get_dependency: The DI resolution handler.
    :type get_dependency: Callable
    :return: A handler that keeps a finished record and returns it.
    :rtype: Callable
    '''

    # Return the handler closure bound to the resolver.
    def handler(record: Any) -> Any:

        # A matrix and a plot do not share a create event.
        if record.is_matrix:
            event = get_dependency(CREATE_MATRIX_EVENT_ID, PLOT_FLAG)
            return event.execute(
                name=record.name,
                rows=record.rows,
                cols=record.cols,
                cells=record.cells,
                id=record.id,
                description=record.description,
                title=record.title,
            )

        # A line and a bar share this event. Kind is an argument, not a method.
        event = get_dependency(CREATE_PLOT_EVENT_ID, PLOT_FLAG)
        return event.execute(
            name=record.name,
            kind=record.kind,
            series=record.series,
            id=record.id,
            description=record.description,
            title=record.title,
            x_title=record.x_title,
            x_unit=record.x_unit,
            y_title=record.y_title,
            y_unit=record.y_unit,
        )

    # Return the closure.
    return handler

# ** function: _settled_id
def _settled_id(name: str, supplied: Any) -> str:
    '''
    Keep a supplied id, or derive one once from the name.

    A missing id and a blank id are the same case. An empty derivation
    cannot identify the record.

    :param name: The author's name.
    :type name: str
    :param supplied: The id the caller supplied, if any.
    :type supplied: Any
    :return: The id to keep.
    :rtype: str
    '''

    # A supplied id is kept. Derivation does not rewrite it.
    if not _is_blank(supplied):
        return supplied

    # A blank id is not a supplied id. Derive it once.
    if not isinstance(name, str):
        raise ValueError(
            'The name cannot identify the record and no id was supplied.'
        )
    derived = _snake_case(name)
    if not derived:
        raise ValueError(
            'The name cannot identify the record and no id was supplied.'
        )

    # Return the id settled at this call. Later calls pass it through.
    return derived

# ** function: _copy_series
def _copy_series(series: Series, marks: List[Mark] = None) -> Series:
    '''
    Declare a series again, passing its id through.

    The copy does not recompute the id, and it does not share mark
    objects with the series it copies unless the caller supplies them.

    :param series: The series to copy.
    :type series: Series
    :param marks: Replacement marks. The series marks are copied when omitted.
    :type marks: List[Mark]
    :return: A new series with the same id.
    :rtype: Series
    '''

    # Pass the id through so declaration does not derive it again.
    if marks is None:
        marks = [
            Mark(
                role=mark.role,
                values=tuple(mark.values),
            )
            for mark in series.marks
        ]
    return Series(
        id=series.id,
        name=series.name,
        marks=marks,
    )

# ** function: _declare_plot
def _declare_plot(plot_id: str,
        name: str,
        kind: str,
        description: Any,
        series: List[Series],
        title: Any = None,
        x_title: Any = None,
        x_unit: Any = None,
        y_title: Any = None,
        y_unit: Any = None) -> Plot:
    '''
    Declare the in-memory record again, passing settled ids through.

    Title and axis text are passed through. They are not used to derive
    the id, and a later series does not clear them.

    :param plot_id: The plot id already settled. Not derived again.
    :type plot_id: str
    :param name: The plot name.
    :type name: str
    :param kind: The plot kind.
    :type kind: str
    :param description: The optional claim text.
    :type description: Any
    :param series: The series, each with its id already settled.
    :type series: List[Series]
    :param title: The optional display title. Not used to derive the id.
    :type title: Any
    :param x_title: The optional x-axis title.
    :type x_title: Any
    :param x_unit: The optional x-axis unit.
    :type x_unit: Any
    :param y_title: The optional y-axis title.
    :type y_title: Any
    :param y_unit: The optional y-axis unit.
    :type y_unit: Any
    :return: The declared plot.
    :rtype: Plot
    '''

    # The supplied plot id is kept. Series ids were passed through.
    return Plot(
        id=plot_id,
        name=name,
        kind=kind,
        description=description,
        series=series,
        title=title,
        x_title=x_title,
        x_unit=x_unit,
        y_title=y_title,
        y_unit=y_unit,
    )

# ** function: _own_plot
def _own_plot(plot: Any) -> Plot:
    '''
    Declare a plot the session holds, without mutating the caller's object.

    A matrix is not a plot. A plot that fails the record checks is
    rejected here, before a chain starts.

    :param plot: The plot the caller already holds.
    :type plot: Any
    :return: The session's own record.
    :rtype: Plot
    '''

    # The record says whether it is a matrix. Do not sniff its type.
    if plot.is_matrix:
        raise ValueError('A matrix is not a plot.')

    # Re-declare with the ids already on the record. Do not derive them.
    return _declare_plot(
        plot.id,
        plot.name,
        plot.kind,
        plot.description,
        [
            _copy_series(item)
            for item in plot.series
        ],
        title=plot.title,
        x_title=plot.x_title,
        x_unit=plot.x_unit,
        y_title=plot.y_title,
        y_unit=plot.y_unit,
    )

# ** function: _extended_marks
def _extended_marks(series: Series, addition: Series) -> List[Mark]:
    '''
    Add values to each existing mark without changing roles.

    :param series: The series being extended.
    :type series: Series
    :param addition: The values to add, already checked for the kind.
    :type addition: Series
    :return: New marks with the added values.
    :rtype: List[Mark]
    '''

    # Index the addition by role. The series' roles stay in order.
    added = {
        mark.role: tuple(mark.values)
        for mark in addition.marks
    }
    return [
        Mark(
            role=mark.role,
            values=tuple(mark.values) + added[mark.role],
        )
        for mark in series.marks
    ]

# *** contexts

# ** context: plotter_session_context
class PlotterSessionContext(AppSessionContext):
    '''
    The place a person creates a plot or a matrix and sees the picture.

    It extends the session hub and adds create and show as handlers,
    not as a step on every kind. It omits ``domain_type`` so
    ``AppSession`` stays registered to ``AppSessionContext``. The
    generic application entry point cannot select this context.
    The fluent chain is methods on this session. It is not a second
    context, a second plot, or a second entry point.
    '''

    # * attribute: resolver
    resolver: Any

    # * attribute: create (private)
    _create: Callable

    # * attribute: show (private)
    _show: Callable

    # * attribute: open (private)
    _open: Optional[Dict[str, Any]]

    # * init
    def __init__(self,
            get_dependency: Callable,
            cache: CacheContext = None,
            resolver: Any = None,
            build_logger_handler: Callable = None,
            execute_feature_handler: Callable = None,
            create_request_handler: Callable = None,
            raise_error_handler: Callable = None,
            response_handler: Callable = None,
            create_handler: Callable = None,
            show_handler: Callable = None):
        '''
        Initialize the plotter session.

        :param get_dependency: The DI resolution handler injected by the blueprint.
        :type get_dependency: Callable
        :param cache: The shared bootstrap cache.
        :type cache: CacheContext
        :param resolver: The blueprint-composed service resolver, exposed so a
            later session can resolve additional services without a signature change.
        :type resolver: Any
        :param build_logger_handler: The logger-construction handler.
        :type build_logger_handler: Callable
        :param execute_feature_handler: The feature-execution handler.
        :type execute_feature_handler: Callable
        :param create_request_handler: The request-construction handler.
        :type create_request_handler: Callable
        :param raise_error_handler: The error-handling handler.
        :type raise_error_handler: Callable
        :param response_handler: The response-building handler.
        :type response_handler: Callable
        :param create_handler: The create handler. Unwired, it fails.
        :type create_handler: Callable
        :param show_handler: The show handler. Unwired, it fails.
        :type show_handler: Callable
        '''

        # Initialize the session hub. The five framework handlers stay required.
        super().__init__(
            get_dependency,
            cache=cache,
            build_logger_handler=build_logger_handler,
            execute_feature_handler=execute_feature_handler,
            create_request_handler=create_request_handler,
            raise_error_handler=raise_error_handler,
            response_handler=response_handler,
        )

        # Expose the resolver for a later session that extends this one.
        self.resolver = resolver

        # Store the plotter handlers. They are validated on first use.
        self._create = create_handler
        self._show = show_handler

        # No chain is open until draft or edit.
        self._open = None

    # * method: _refuse_clobber (private)
    def _refuse_clobber(self) -> None:
        '''
        Fail when a plot is already open.

        A second draft or edit does not replace the first plot.

        :return: None
        :rtype: None
        '''

        # Discard is the way out. This is not a delete.
        if self._open is not None:
            raise ValueError('A plot is already open.')

    # * method: _remember (private)
    def _remember(self, record: Plot) -> None:
        '''
        Replace the in-memory record with a newly declared plot.

        :param record: The declared plot.
        :type record: Plot
        :return: None
        :rtype: None
        '''

        # The settled plot id is not rewritten from the name.
        self._open['series'] = list(record.series)
        self._open['record'] = record

    # * method: draft
    def draft(self,
            name: str,
            kind: str,
            id: str = None,
            description: str = None,
            *,
            title: str = None,
            x_title: str = None,
            x_unit: str = None,
            y_title: str = None,
            y_unit: str = None) -> 'PlotterSessionContext':
        '''
        Open one in-memory plot with no series.

        A missing or blank id is derived once from the name. A supplied
        id is kept. An empty derivation opens nothing. Title is a keyword
        and does not shift the id argument.

        :param name: The author's name for the plot.
        :type name: str
        :param kind: The chart kind. One of line, scatter, or bar.
        :type kind: str
        :param id: The plot id. Derived from the name when omitted.
        :type id: str
        :param description: Optional claim text. Not used to derive the id.
        :type description: str
        :param title: Optional display title. Not used to derive the id.
        :type title: str
        :param x_title: Optional title of the x axis.
        :type x_title: str
        :param x_unit: Optional unit of the x axis.
        :type x_unit: str
        :param y_title: Optional title of the y axis.
        :type y_title: str
        :param y_unit: Optional unit of the y axis.
        :type y_unit: str
        :return: This session, for further chaining.
        :rtype: PlotterSessionContext
        '''

        # A second draft does not replace the plot already open.
        self._refuse_clobber()

        # Settle the id and the kind before opening. A failure opens nothing.
        plot_id = _settled_id(name, id)
        settled_kind = Plot.require_kind(kind)
        self._open = {
            'id': plot_id,
            'name': name,
            'kind': settled_kind,
            'description': description,
            'title': title,
            'x_title': x_title,
            'x_unit': x_unit,
            'y_title': y_title,
            'y_unit': y_unit,
            'series': [],
            'record': None,
        }

        # Return the session. The plot is not yet a record with series.
        return self

    # * method: edit
    def edit(self, plot: Any) -> 'PlotterSessionContext':
        '''
        Open the chain from a plot the caller already holds.

        The session keeps that plot's id and each series id. It does
        not derive them again, and it does not mutate the object passed
        in. A matrix is not a plot.

        :param plot: The plot the caller already holds.
        :type plot: Any
        :return: This session, for further chaining.
        :rtype: PlotterSessionContext
        '''

        # A second edit does not replace the plot already open.
        self._refuse_clobber()

        # Hold a new record. Invalid fields fail before a chain starts.
        record = _own_plot(plot)
        self._open = {
            'id': record.id,
            'name': record.name,
            'kind': record.kind,
            'description': record.description,
            'title': record.title,
            'x_title': record.x_title,
            'x_unit': record.x_unit,
            'y_title': record.y_title,
            'y_unit': record.y_unit,
            'series': list(record.series),
            'record': record,
        }

        # Return the session. The caller's object is unchanged.
        return self

    # * method: add_series
    def add_series(self,
            name: str,
            marks: Any,
            id: str = None) -> 'PlotterSessionContext':
        '''
        Add one series to the open plot.

        Marks are a role and its values. A line or a scatter may
        include label, and x or y may be text, when the plot's sort
        rules hold. A missing or blank series id is derived once from
        the series name. A supplied series id is kept. The plot id is
        not recomputed.

        :param name: The author's name for the series.
        :type name: str
        :param marks: The marks for this series. Each mark is a role and values.
        :type marks: Any
        :param id: The series id. Derived from the name when omitted.
        :type id: str
        :return: This session, for further chaining.
        :rtype: PlotterSessionContext
        '''

        # A series needs an open plot. This does not open one.
        if self._open is None:
            raise ValueError('add_series requires an open plot.')

        # Derive a missing series id once. A supplied id is kept.
        added = Series(
            name=name,
            id=id,
            marks=marks,
        )

        # Declare again with the settled plot id and the existing series ids.
        series = [
            _copy_series(item)
            for item in self._open['series']
        ]
        series.append(added)
        record = _declare_plot(
            self._open['id'],
            self._open['name'],
            self._open['kind'],
            self._open['description'],
            series,
            title=self._open['title'],
            x_title=self._open['x_title'],
            x_unit=self._open['x_unit'],
            y_title=self._open['y_title'],
            y_unit=self._open['y_unit'],
        )

        # A failed declaration does not reach here. The series list stays.
        self._remember(record)
        return self

    # * method: append
    def append(self,
            series_id: str,
            marks: Any) -> 'PlotterSessionContext':
        '''
        Add values to an existing series' marks.

        The series is addressed by id, not by name. The addition carries
        exactly the roles that series already carries, including label
        when the series has it. Sorts match that series. The added
        sequences are non-empty and of equal length. A failure leaves
        the marks unchanged.

        :param series_id: The id of the series to extend.
        :type series_id: str
        :param marks: The values to add. The same structure as ``add_series``.
        :type marks: Any
        :return: This session, for further chaining.
        :rtype: PlotterSessionContext
        '''

        # An addition needs an open plot and a series with this id.
        if self._open is None:
            raise ValueError('append requires an open plot.')
        current = None
        for item in self._open['series']:
            if item.id == series_id:
                current = item
                break
        if current is None:
            raise ValueError(f'No series with id {series_id!r}.')

        # The addition must already satisfy the kind. Failure changes nothing.
        addition = Series(
            id=current.id,
            name=current.name,
            marks=marks,
        )
        _declare_plot(
            self._open['id'],
            self._open['name'],
            self._open['kind'],
            self._open['description'],
            [
                addition,
            ],
            title=self._open['title'],
            x_title=self._open['x_title'],
            x_unit=self._open['x_unit'],
            y_title=self._open['y_title'],
            y_unit=self._open['y_unit'],
        )

        # The series describes the addition. Its failure is a model defect.
        current.verify_addition(addition)

        # Rebuild every series. Only the addressed series gains values.
        rebuilt = []
        for item in self._open['series']:
            if item.id == series_id:
                rebuilt.append(_copy_series(
                    item,
                    marks=_extended_marks(item, addition),
                ))
                continue
            rebuilt.append(_copy_series(item))
        record = _declare_plot(
            self._open['id'],
            self._open['name'],
            self._open['kind'],
            self._open['description'],
            rebuilt,
            title=self._open['title'],
            x_title=self._open['x_title'],
            x_unit=self._open['x_unit'],
            y_title=self._open['y_title'],
            y_unit=self._open['y_unit'],
        )

        # A failed declaration does not reach here. Ids stay as settled.
        self._remember(record)
        return self

    # * method: discard
    def discard(self) -> 'PlotterSessionContext':
        '''
        Drop the in-memory plot.

        This calls no event. It is not a removal of a kept record.

        :return: This session.
        :rtype: PlotterSessionContext
        '''

        # Drop the chain. Do not resolve a service and do not open a store.
        self._open = None
        return self

    # * method: create
    def create(self, record: Any = None) -> Any:
        '''
        Create a plot or a matrix and return the kept record.

        An explicit record is the finished-record path. It does not read
        the in-memory plot and does not drop it. With no argument, an
        open plot that has at least one series is passed to the create
        handler. The result is the record, not a picture.

        :param record: The finished plot or matrix. Omit to keep the open plot.
        :type record: Any
        :return: The kept record.
        :rtype: Any
        '''

        # An explicit record always wins. The chain is not sent and not cleared.
        if record is not None:
            if self._create is None:
                raise_unwired_handler_error(
                    'create_handler',
                    self.domain.id,
                )
            return self._create(record)

        # A chain terminal needs an open plot that declaration would accept.
        if self._open is None:
            raise ValueError('create requires an open plot.')
        if not self._open['series']:
            raise ValueError('A draft with no series cannot be kept.')

        # An unwired create handler is a composition bug.
        if self._create is None:
            raise_unwired_handler_error(
                'create_handler',
                self.domain.id,
            )

        # The handler calls the create event. A failure leaves the chain.
        kept = self._create(self._open['record'])

        # Success drops the in-memory plot. The caller holds the kept record.
        self._open = None
        return kept

    # * method: update
    def update(self) -> Any:
        '''
        Keep an edit of the open plot and return the record.

        The call resolves ``UpdatePlot`` on the plot flag. It does not
        re-derive the id, does not insert, and does not fall through to
        create. A failure leaves the in-memory plot.

        :return: The kept record.
        :rtype: Any
        '''

        # Update needs an open plot that declaration would accept.
        if self._open is None:
            raise ValueError('update requires an open plot.')
        if not self._open['series']:
            raise ValueError('A draft with no series cannot be kept.')

        # Resolve the existing event. Do not construct it and do not open a store.
        plot = self._open['record']
        event = self.get_dependency(UPDATE_PLOT_EVENT_ID, PLOT_FLAG)
        kept = event.execute(
            id=plot.id,
            name=plot.name,
            kind=plot.kind,
            series=plot.series,
            description=plot.description,
            title=plot.title,
            x_title=plot.x_title,
            x_unit=plot.x_unit,
            y_title=plot.y_title,
            y_unit=plot.y_unit,
        )

        # Success drops the in-memory plot. A failure does not reach here.
        self._open = None
        return kept

    # * method: show
    def show(self,
            record: Any,
            width: float,
            height: float) -> bytes:
        '''
        Present the picture of a plot or a matrix at the given size.

        The handler calls ``render`` or ``render_matrix`` and passes the
        width and height through. The session does not store the pair,
        default it, or read it from the record. Placing the file is the
        caller's choice.

        :param record: The finished plot or matrix.
        :type record: Any
        :param width: The picture width, in inches.
        :type width: float
        :param height: The picture height, in inches.
        :type height: float
        :return: The picture as PNG bytes.
        :rtype: bytes
        '''

        # An unwired show handler is a composition bug.
        if self._show is None:
            raise_unwired_handler_error(
                'show_handler',
                self.domain.id,
            )

        # Forward the pair. This method does not open a store or keep a size.
        return self._show(record, width, height)
