"""Tests for plot service contracts."""

# *** imports

# ** core
import ast
import importlib
import inspect
from pathlib import Path

# ** infra
import pytest

# ** app
from tiferet.interfaces import ServiceError
from tiferet_plot.domain.plot import Mark
from tiferet_plot.interfaces.plot import (
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
    PlotService,
    RendererService,
)
from tiferet_plot.mappers.plot import PlotAggregate, SeriesAggregate
import tiferet_plot.interfaces.plot as interface_module

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

# ** test: renderer_service_does_not_import_matplotlib
def test_renderer_service_does_not_import_matplotlib():
    '''
    The renderer contract does not import a drawing tool.
    '''

    # The interface names a picture, not a figure class or a library.
    imported = ' '.join(imported_modules(interface_module))
    assert 'matplotlib' not in imported
    assert 'domain' not in imported
    assert 'repos' not in imported
    source = inspect.getsource(RendererService)
    assert 'Figure' not in source
    assert 'PlotService' not in source

# ** test: render_returns_bytes_and_takes_only_a_plot
def test_render_returns_bytes_and_takes_only_a_plot():
    '''
    render(plot) returns bytes. It does not take a path or a store.
    '''

    # The contract is one plot in, PNG bytes out.
    signature = inspect.signature(RendererService.render)
    assert list(signature.parameters) == ['self', 'plot']
    assert signature.return_annotation is bytes

    # The contract is not a usable renderer by itself.
    with pytest.raises(TypeError):
        RendererService()

# ** test: plot_service_names_no_file_format_or_root
def test_plot_service_names_no_file_format_or_root():
    '''
    The plot service can be read without a file extension or a root node.
    '''

    # Read the keep contract, not the renderer that shares the module.
    source = inspect.getsource(PlotService)
    lowered = source.lower()
    for token in ('.yaml', '.yml', '.json', '.txt', 'matplotlib', 'database'):
        assert token not in lowered
    assert "'plots'" not in source
    assert '"plots"' not in source
    assert 'RendererService' not in source

    # The module does not import a repository or Matplotlib.
    module = importlib.import_module(PlotService.__module__)
    imported = ' '.join(imported_modules(module))
    assert 'matplotlib' not in imported
    assert 'repos' not in imported

# ** test: plot_service_can_be_implemented_without_a_file
def test_plot_service_can_be_implemented_without_a_file():
    '''
    A second implementation can keep records without naming a file extension.
    '''

    # An in-memory store satisfies the contract. It names no file format.
    class MemoryPlotService(PlotService):
        '''
        An in-memory plot service used to prove the contract.
        '''

        # * init
        def __init__(self) -> None:
            '''
            Start with no kept records.
            '''

            # The records are keyed by plot id.
            self.records = {}

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
        def get(self, id: str):
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
        def list(self):
            '''
            Return the kept records.

            :return: The kept plots.
            :rtype: list
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

            # A second save does not replace the first record.
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

            # Update does not insert.
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

            # Pop is idempotent.
            self.records.pop(id, None)

    # Declare a record and keep it without a file.
    service = MemoryPlotService()
    plot = PlotAggregate(
        id='Custom-Id',
        name='Sales by Region',
        kind='line',
        series=[
            SeriesAggregate(id='rev-1', name='Revenue', marks=line_marks()),
        ],
    )
    service.save(plot)

    # The first record is kept. A second save of that id fails.
    assert service.exists('Custom-Id') is True
    assert service.get('Custom-Id').name == 'Sales by Region'
    assert service.list()[0].id == 'Custom-Id'
    with pytest.raises(ServiceError) as caught:
        service.save(plot)
    assert caught.value.error_code == PLOT_ALREADY_KEPT_ID
    assert service.get('Custom-Id').series[0].id == 'rev-1'

    # Update replaces. A missing id does not insert.
    plot.rename('Quarterly Sales')
    service.update(plot)
    assert service.get('Custom-Id').name == 'Quarterly Sales'
    missing = PlotAggregate(
        id='other',
        name='Other',
        kind='line',
        series=[
            SeriesAggregate(name='Revenue', marks=line_marks()),
        ],
    )
    with pytest.raises(ServiceError) as caught:
        service.update(missing)
    assert caught.value.error_code == PLOT_NOT_KEPT_ID
    assert service.get('other') is None

    # Delete of a missing id changes nothing.
    service.delete('missing')
    assert service.get('Custom-Id') is not None
