"""The blueprint that selects the plotter session."""

# *** imports

# ** core
from typing import Any, Callable, Dict

# ** app
from tiferet.assets.core import (
    create_app_service_dependency_data,
    create_service_module_path,
)
from tiferet.blueprints import core
from tiferet.contexts.app import AppSession
from tiferet.contexts.cache import CacheContext
from tiferet.di import DIDynamicServiceContainer, ServiceResolver
from tiferet.domain import AppServiceDependency
from ..contexts.plot import (
    CREATE_MATRIX_EVENT_ID,
    CREATE_PLOT_EVENT_ID,
    MATRIX_SERVICE_ID,
    PLOT_FLAG,
    PLOT_SERVICE_ID,
    RENDERER_SERVICE_ID,
    UPDATE_PLOT_EVENT_ID,
    PlotterSessionContext,
    add_default_plot_services,
    create_handler,
    get_default_plot_services,
)

# *** constants

# ** constant: plot_package
PLOT_PACKAGE = 'tiferet_plot'

# ** constant: plot_module
PLOT_MODULE = 'plot'

# ** constant: plotter_session_id
PLOTTER_SESSION_ID = 'plotter'

# ** constant: create_plot_event_data
CREATE_PLOT_EVENT_DATA = create_app_service_dependency_data(
    create_service_module_path(PLOT_PACKAGE, 'events', PLOT_MODULE),
    'CreatePlot',
)

# ** constant: update_plot_event_data
UPDATE_PLOT_EVENT_DATA = create_app_service_dependency_data(
    create_service_module_path(PLOT_PACKAGE, 'events', PLOT_MODULE),
    'UpdatePlot',
)

# ** constant: create_matrix_event_data
CREATE_MATRIX_EVENT_DATA = create_app_service_dependency_data(
    create_service_module_path(PLOT_PACKAGE, 'events', PLOT_MODULE),
    'CreateMatrix',
)

# ** constant: renderer_service_data
RENDERER_SERVICE_DATA = create_app_service_dependency_data(
    create_service_module_path(PLOT_PACKAGE, 'utils', PLOT_MODULE),
    'MatplotlibRenderer',
)

# ** constant: plot_repository_data
PLOT_REPOSITORY_DATA = create_app_service_dependency_data(
    create_service_module_path(PLOT_PACKAGE, 'repos', PLOT_MODULE),
    'PlotConfigRepository',
)

# ** constant: matrix_repository_data
MATRIX_REPOSITORY_DATA = create_app_service_dependency_data(
    create_service_module_path(PLOT_PACKAGE, 'repos', PLOT_MODULE),
    'MatrixConfigRepository',
)

# ** constant: plot_default_services
PLOT_DEFAULT_SERVICES: Dict[str, Dict[str, Any]] = {
    CREATE_MATRIX_EVENT_ID: CREATE_MATRIX_EVENT_DATA,
    CREATE_PLOT_EVENT_ID: CREATE_PLOT_EVENT_DATA,
    RENDERER_SERVICE_ID: RENDERER_SERVICE_DATA,
    UPDATE_PLOT_EVENT_ID: UPDATE_PLOT_EVENT_DATA,
}

# *** blueprints

# ** blueprint: show_handler
def show_handler(get_dependency: Callable) -> Callable:
    '''
    Build the show handler the plotter session is wired with.

    The handler resolves the renderer on the plot flag and returns the
    picture bytes. It passes the caller's width and height through. It
    does not store that pair, default it, or read it from the record.
    It does not write a publication file. A line and a bar use the same
    call.

    :param get_dependency: The DI resolution handler.
    :type get_dependency: Callable
    :return: A handler that returns the picture bytes.
    :rtype: Callable
    '''

    # Return the handler closure bound to the resolver.
    def handler(record: Any, width: float, height: float) -> bytes:

        # The record says whether it is a matrix. A non-record has no such description.
        is_matrix = record.is_matrix

        # The drawing tool is a service on the plot flag, not an import here.
        renderer = get_dependency(RENDERER_SERVICE_ID, PLOT_FLAG)

        # A matrix is one picture of the grid. The size is the caller's pair.
        if is_matrix:
            return renderer.render_matrix(record, width, height)

        # Kind does not choose a different show. The size is not read from the record.
        return renderer.render(record, width, height)

    # Return the closure.
    return handler

# ** blueprint: build_plotter_cache
@add_default_plot_services(PLOT_DEFAULT_SERVICES)
def build_plotter_cache(cache: Dict[str, Any] = None) -> CacheContext:
    '''
    Build the bootstrap cache pre-seeded with framework defaults and the
    plotter's own events and renderer.

    Those defaults are ordinary services. They are not app-level singletons.

    :param cache: An optional initial cache dictionary for the root namespace.
    :type cache: Dict[str, Any] | None
    :return: The pre-seeded cache context.
    :rtype: CacheContext
    '''

    # Delegate to the framework cache builder. The decorator seeds plot services.
    return core.build_cache(cache)

# ** blueprint: build_plot_service_container
def build_plot_service_container(cache: CacheContext,
        plot_config: str,
        matrix_config: str) -> DIDynamicServiceContainer:
    '''
    Build the plotter's dynamic service container.

    The container is factory-scoped. Stores are registered before the
    events so each event factory can wire the service it already names.
    The session does not construct those stores itself.

    :param cache: The bootstrap cache seeded with the plotter's defaults.
    :type cache: CacheContext
    :param plot_config: The publication file path for plot records.
    :type plot_config: str
    :param matrix_config: The publication file path for matrix records.
    :type matrix_config: str
    :return: The built plot service container.
    :rtype: DIDynamicServiceContainer
    '''

    # Register the stores first. Event factories wire providers that already exist.
    services = {
        PLOT_SERVICE_ID: AppServiceDependency.model_validate({
            **PLOT_REPOSITORY_DATA,
            'service_id': PLOT_SERVICE_ID,
            'parameters': {
                'plot_config': plot_config,
            },
        }),
        MATRIX_SERVICE_ID: AppServiceDependency.model_validate({
            **MATRIX_REPOSITORY_DATA,
            'service_id': MATRIX_SERVICE_ID,
            'parameters': {
                'matrix_config': matrix_config,
            },
        }),
    }

    # Events and the renderer ship as defaults. They are not app singletons.
    for service in get_default_plot_services(cache):
        services[service.service_id] = service

    # Factory scope: a new instance per resolution.
    return DIDynamicServiceContainer(services=services)

# ** blueprint: register_plot_container
def register_plot_container(resolver: ServiceResolver,
        cache: CacheContext,
        plot_config: str,
        matrix_config: str) -> None:
    '''
    Register the plotter's service container on the resolver under the plot flag.

    The renderer is resolved on that flag. It is not registered on the
    framework infrastructure flag.

    :param resolver: The feature-level service resolver to register against.
    :type resolver: ServiceResolver
    :param cache: The bootstrap cache seeded with the plotter's defaults.
    :type cache: CacheContext
    :param plot_config: The publication file path for plot records.
    :type plot_config: str
    :param matrix_config: The publication file path for matrix records.
    :type matrix_config: str
    '''

    # Build and register the plot container under the plot flag.
    resolver.add_container(
        build_plot_service_container(
            cache,
            plot_config,
            matrix_config,
        ),
        PLOT_FLAG,
    )

# ** blueprint: build_plotter_session_context
def build_plotter_session_context(app_session: AppSession,
        cache: CacheContext,
        plot_config: str,
        matrix_config: str) -> PlotterSessionContext:
    '''
    Compose a wired plotter session from a resolved app session.

    This selects ``PlotterSessionContext`` here. The generic application
    entry point cannot name this context from configuration.

    :param app_session: The app session bound to the context.
    :type app_session: AppSession
    :param cache: The pre-built shared cache context.
    :type cache: CacheContext
    :param plot_config: The publication file path for plot records.
    :type plot_config: str
    :param matrix_config: The publication file path for matrix records.
    :type matrix_config: str
    :return: The wired plotter session.
    :rtype: PlotterSessionContext
    '''

    # Build the framework container and compose the resolver.
    app_container = core.build_app_service_container(cache, app_session)
    resolver = core.build_service_resolver(app_container)

    # Register the plotter's own container. The renderer lives there.
    register_plot_container(
        resolver,
        cache,
        plot_config,
        matrix_config,
    )

    # Resolve any remaining injectable collaborators the context declares.
    collaborators = core.resolve_collaborators(
        PlotterSessionContext,
        app_container,
    )

    # Construct the plotter session directly. Do not ask the generic entry point.
    return PlotterSessionContext.from_domain(
        app_session,
        get_dependency=resolver.get_dependency,
        cache=cache,
        build_logger_handler=core.build_logger_handler(
            cache,
            resolver.get_dependency,
        ),
        execute_feature_handler=core.execute_feature_handler(
            resolver.get_dependency,
            cache,
        ),
        raise_error_handler=core.raise_error_handler(
            core.get_error(cache, resolver.get_dependency),
        ),
        response_handler=core.response_handler,
        create_request_handler=core.create_session_request,
        create_handler=create_handler(resolver.get_dependency),
        show_handler=show_handler(resolver.get_dependency),
        **collaborators,
        resolver=resolver,
    )

# ** blueprint: create_plotter_session
def create_plotter_session(plot_config: str,
        *,
        matrix_config: str = None) -> PlotterSessionContext:
    '''
    Build a plotter session in one call.

    This is the entry point. It constructs ``PlotterSessionContext``
    itself. There is no command-line mirror. An omitted matrix path
    uses the same publication file as the plot path. The two stores
    write different roots.

    :param plot_config: The publication file path for plot records.
    :type plot_config: str
    :param matrix_config: The publication file path for matrix records.
        Defaults to ``plot_config``.
    :type matrix_config: str
    :return: The wired plotter session.
    :rtype: PlotterSessionContext
    '''

    # Build the cache. Plot events and the renderer are seeded as defaults.
    cache = build_plotter_cache()

    # Bind a session object. Configuration does not name the context class.
    app_session = AppSession(
        id=PLOTTER_SESSION_ID,
        name='Plotter',
        description='The session that creates a plot or a matrix and shows the picture.',
        flags=[
            PLOT_FLAG,
        ],
    )

    # Select the plotter session here.
    return build_plotter_session_context(
        app_session,
        cache,
        plot_config=plot_config,
        matrix_config=matrix_config or plot_config,
    )
