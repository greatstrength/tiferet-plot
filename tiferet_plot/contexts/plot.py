"""The plotter session."""

# *** imports

# ** core
from typing import Any, Callable, Dict, List, Tuple

# ** app
from tiferet.contexts.app import AppSessionContext, raise_unwired_handler_error
from tiferet.contexts.cache import CacheContext
from tiferet.domain import AppServiceDependency
from ..domain.plot import Plot, PlotMatrix

# *** constants

# ** constant: plot_flag
PLOT_FLAG = 'plot'

# ** constant: plot_service_cache_prefix
PLOT_SERVICE_CACHE_PREFIX: Tuple[str, ...] = ('plot', 'services')

# ** constant: create_plot_event_id
CREATE_PLOT_EVENT_ID = 'create_plot_evt'

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

# ** function: _record_kind
def _record_kind(record: Any, action: str) -> str:
    '''
    Return which path a finished record takes.

    A matrix is not a plot. A line and a bar are both plots. This does
    not declare a record and does not invent a grid.

    :param record: The finished record.
    :type record: Any
    :param action: The session act that received the record.
    :type action: str
    :return: ``matrix`` or ``plot``.
    :rtype: str
    '''

    # A matrix is its own record. Check it before a plot.
    if isinstance(record, PlotMatrix):
        return 'matrix'

    # A plot aggregate is still a plot. Kind does not split the path.
    if isinstance(record, Plot):
        return 'plot'

    # The caller passes a finished record. This session does not declare one.
    raise ValueError(
        f'{action} requires a plot record or a matrix record.'
    )

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
        if _record_kind(record, 'create') == 'matrix':
            event = get_dependency(CREATE_MATRIX_EVENT_ID, PLOT_FLAG)
            return event.execute(
                name=record.name,
                rows=record.rows,
                cols=record.cols,
                cells=record.cells,
                id=record.id,
                description=record.description,
            )

        # A line and a bar share this event. Kind is an argument, not a method.
        event = get_dependency(CREATE_PLOT_EVENT_ID, PLOT_FLAG)
        return event.execute(
            name=record.name,
            kind=record.kind,
            series=record.series,
            id=record.id,
            description=record.description,
        )

    # Return the closure.
    return handler

# ** function: show_handler
def show_handler(get_dependency: Callable) -> Callable:
    '''
    Build the show handler.

    The handler resolves the renderer on the plot flag and returns the
    picture bytes. It does not write a publication file. A line and a
    bar use the same call.

    :param get_dependency: The DI resolution handler.
    :type get_dependency: Callable
    :return: A handler that returns the picture bytes.
    :rtype: Callable
    '''

    # Return the handler closure bound to the resolver.
    def handler(record: Any) -> bytes:

        # Reject a non-record before resolving the renderer.
        kind = _record_kind(record, 'show')

        # The drawing tool is a service on the plot flag, not an import here.
        renderer = get_dependency(RENDERER_SERVICE_ID, PLOT_FLAG)

        # A matrix is one picture of the grid. A plot is one picture of the record.
        if kind == 'matrix':
            return renderer.render_matrix(record)

        # Kind does not choose a different show.
        return renderer.render(record)

    # Return the closure.
    return handler

# *** contexts

# ** context: plotter_session_context
class PlotterSessionContext(AppSessionContext):
    '''
    The place a person creates a plot or a matrix and sees the picture.

    It extends the session hub and adds create and show as handlers,
    not as a step on every kind. It omits ``domain_type`` so
    ``AppSession`` stays registered to ``AppSessionContext``. The
    generic application entry point cannot select this context.
    Fluent chaining is not this session.
    '''

    # * attribute: resolver
    resolver: Any

    # * attribute: create (private)
    _create: Callable

    # * attribute: show (private)
    _show: Callable

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

    # * method: create
    def create(self, record: Any) -> Any:
        '''
        Create a plot or a matrix and return the kept record.

        The handler calls the plot create event or the matrix create
        event. The result is the record, not a picture.

        :param record: The finished plot or matrix.
        :type record: Any
        :return: The kept record.
        :rtype: Any
        '''

        # An unwired create handler is a composition bug.
        if self._create is None:
            raise_unwired_handler_error(
                'create_handler',
                self.domain.id,
            )

        # The handler calls the create event. This method does not draw.
        return self._create(record)

    # * method: show
    def show(self, record: Any) -> bytes:
        '''
        Present the picture of a plot or a matrix.

        The handler calls ``render`` or ``render_matrix`` and returns
        the bytes. Placing the file is the caller's choice.

        :param record: The finished plot or matrix.
        :type record: Any
        :return: The picture as PNG bytes.
        :rtype: bytes
        '''

        # An unwired show handler is a composition bug.
        if self._show is None:
            raise_unwired_handler_error(
                'show_handler',
                self.domain.id,
            )

        # The handler calls the renderer. This method does not open a store.
        return self._show(record)
