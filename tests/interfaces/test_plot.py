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
    MATRIX_ALREADY_KEPT_ID,
    MATRIX_NOT_KEPT_ID,
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
    MatrixService,
    PlotService,
    RendererService,
)
from tiferet_plot.mappers.plot import (
    PlotAggregate,
    PlotMatrixAggregate,
    SeriesAggregate,
)
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

# ** test: render_returns_bytes_for_a_sized_picture
def test_render_returns_bytes_for_a_sized_picture():
    '''
    render(plot, width, height) returns bytes. It does not take a path or a store.
    '''

    # The contract is one plot and one size in, PNG bytes out.
    signature = inspect.signature(RendererService.render)
    assert list(signature.parameters) == ['self', 'plot', 'width', 'height']
    assert signature.parameters['width'].default is inspect.Parameter.empty
    assert signature.parameters['height'].default is inspect.Parameter.empty
    assert signature.return_annotation is bytes
    source = inspect.getsource(RendererService.render)
    for name in ('dpi', 'figsize', 'pixels'):
        assert name not in source

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

# ** test: render_matrix_is_a_second_method
def test_render_matrix_is_a_second_method():
    '''
    render_matrix returns bytes. render does not gain a matrix parameter.
    '''

    # The single-plot method takes the record, then the size. Not a cell size.
    render = inspect.signature(RendererService.render)
    assert list(render.parameters) == ['self', 'plot', 'width', 'height']
    assert render.return_annotation is bytes

    # The grid is a second method. One pair covers that picture.
    render_matrix = inspect.signature(RendererService.render_matrix)
    assert list(render_matrix.parameters) == [
        'self',
        'matrix',
        'width',
        'height',
    ]
    assert render_matrix.parameters['width'].default is inspect.Parameter.empty
    assert render_matrix.parameters['height'].default is inspect.Parameter.empty
    assert render_matrix.return_annotation is bytes
    source = inspect.getsource(RendererService)
    for name in ('dpi', 'figsize', 'pixels', 'cell_width', 'cell_height'):
        assert name not in source
    assert not hasattr(RendererService, 'heatmap')
    assert not hasattr(MatrixService, 'heatmap')
    source = inspect.getsource(RendererService)
    assert 'PlotService' not in source
    assert 'MatrixService' not in source

# ** test: matrix_service_names_no_file_format_or_root
def test_matrix_service_names_no_file_format_or_root():
    '''
    The matrix service can be read without a file extension or a root node.
    '''

    # Read the keep contract, not the repository that implements it.
    source = inspect.getsource(MatrixService)
    lowered = source.lower()
    for token in ('.yaml', '.yml', '.json', '.txt', 'matplotlib', 'database'):
        assert token not in lowered
    assert "'matrices'" not in source
    assert '"matrices"' not in source
    assert 'PlotService' not in source

# ** test: matrix_service_can_be_implemented_without_a_file
def test_matrix_service_can_be_implemented_without_a_file():
    '''
    A second implementation can keep a matrix without naming a file extension.
    '''

    # An in-memory store satisfies the contract. It names no file format.
    class MemoryMatrixService(MatrixService):
        '''
        An in-memory matrix service used to prove the contract.
        '''

        # * init
        def __init__(self) -> None:
            '''
            Start with no kept records.
            '''

            # The records are keyed by matrix id.
            self.records = {}

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

    # Declare a record and keep it without a file.
    service = MemoryMatrixService()
    matrix = PlotMatrixAggregate(
        id='Custom-Id',
        name='Sales by Region',
        rows=1,
        cols=1,
        cells=[
            {
                'row': 0,
                'col': 0,
                'plot': {
                    'id': 'revenue_plot',
                    'name': 'Revenue',
                    'kind': 'line',
                    'series': [
                        SeriesAggregate(
                            id='rev-1',
                            name='Revenue',
                            marks=line_marks(),
                        ),
                    ],
                },
            },
        ],
    )
    service.save(matrix)

    # The first record is kept. A second save of that id fails.
    assert service.exists('Custom-Id') is True
    assert service.get('Custom-Id').name == 'Sales by Region'
    assert service.list()[0].id == 'Custom-Id'
    assert not isinstance(service.list(), str)
    with pytest.raises(ServiceError) as caught:
        service.save(matrix)
    assert caught.value.error_code == MATRIX_ALREADY_KEPT_ID
    assert service.get('Custom-Id').cells[0].plot.id == 'revenue_plot'

    # Update replaces. A missing id does not insert.
    matrix.rename('Quarterly Sales')
    service.update(matrix)
    assert service.get('Custom-Id').name == 'Quarterly Sales'
    assert service.get('Custom-Id').id == 'Custom-Id'
    missing = PlotMatrixAggregate(
        id='other',
        name='Other',
        rows=1,
        cols=1,
        cells=matrix.cells,
    )
    with pytest.raises(ServiceError) as caught:
        service.update(missing)
    assert caught.value.error_code == MATRIX_NOT_KEPT_ID
    assert service.get('other') is None

    # Delete of a missing id changes nothing.
    service.delete('missing')
    assert service.get('Custom-Id') is not None
