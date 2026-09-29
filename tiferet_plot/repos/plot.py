"""Plot publication-file repository."""

# *** imports

# ** core
from __future__ import annotations
from pathlib import Path

# ** app
from tiferet.interfaces import ServiceError
from tiferet.repos.core import ConfigurationRepository
from ..interfaces.plot import (
    MATRIX_ALREADY_KEPT_ID,
    MATRIX_NOT_KEPT_ID,
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
    MatrixService,
    PlotService,
)
from ..mappers import (
    MatrixConfigObject,
    PlotAggregate,
    PlotConfigObject,
    PlotMatrixAggregate,
)

# *** repos

# ** repo: plot_config_repository
class PlotConfigRepository(PlotService, ConfigurationRepository):
    '''
    The first store for a plot record: a publication file beside the paper.

    ``.yaml`` and ``.yml`` are YAML. ``.json`` is JSON. Any other extension
    fails. Records live under a ``plots`` root, keyed by plot id. The
    transfer object writes the body and excludes that id. Series are nested
    in the plot entry, so deleting a plot takes them with it. This store
    does not draw and does not derive ids.
    '''

    # * init
    def __init__(self, plot_config: str, encoding: str = 'utf-8') -> None:
        '''
        Initialize the plot configuration repository.

        :param plot_config: The publication file path.
        :type plot_config: str
        :param encoding: The file encoding.
        :type encoding: str
        '''

        # Initialize the configuration repository base.
        ConfigurationRepository.__init__(
            self,
            config_file=plot_config,
            encoding=encoding,
        )

    # * method: _require_supported_file
    def _require_supported_file(self) -> None:
        '''
        Fail when the path is not a publication file.

        :return: None
        :rtype: None
        :raises ServiceError: When the extension is not YAML or JSON.
        '''

        # Resolving the loader rejects any extension other than YAML or JSON.
        self._get_loader()

    # * method: _load_full
    def _load_full(self) -> dict:
        '''
        Load the full publication, treating a missing file as empty.

        :return: The full file mapping, or an empty mapping.
        :rtype: dict
        '''

        # An unsupported extension fails before a missing file is treated as empty.
        self._require_supported_file()

        # A missing file is an empty store, not a corrupt publication.
        if not Path(self.config_file).exists():
            return {}

        # Load and return the full publication.
        return self._load() or {}

    # * method: _load_plots
    def _load_plots(self) -> dict:
        '''
        Load the plots mapping, tolerating a missing file or root.

        :return: The plots mapping keyed by plot id.
        :rtype: dict
        '''

        # An unsupported extension fails before a missing file is empty.
        self._require_supported_file()
        if not Path(self.config_file).exists():
            return {}

        # Select the plots node. An empty root is an empty store.
        return self._load(
            start_node=lambda data: (data or {}).get('plots') or {},
        ) or {}

    # * method: exists
    def exists(self, id: str) -> bool:
        '''
        Check whether a plot id is kept.

        :param id: The plot id.
        :type id: str
        :return: True when get would return a record, otherwise False.
        :rtype: bool
        '''

        # True only when get would return a record.
        return self.get(id) is not None

    # * method: get
    def get(self, id: str) -> PlotAggregate | None:
        '''
        Return the kept plot, or nothing when the id is not kept.

        :param id: The plot id.
        :type id: str
        :return: The plot aggregate, or None when the id is not kept.
        :rtype: PlotAggregate | None
        '''

        # Load the plot body. A missing id is not an error.
        body = self._load_plots().get(id)
        if not body:
            return None

        # Inject the file key as id, then map the transfer object.
        return PlotConfigObject.model_validate({
            **body,
            'id': id,
        }).map()

    # * method: list
    def list(self) -> list[PlotAggregate]:
        '''
        Return the kept plot records.

        :return: The kept plots. Not a picture and not a display string.
        :rtype: list[PlotAggregate]
        '''

        # Map each kept entry. An empty or missing file returns no records.
        return [
            PlotConfigObject.model_validate({
                **body,
                'id': plot_id,
            }).map()
            for plot_id, body in self._load_plots().items()
        ]

    # * method: save
    def save(self, plot: PlotAggregate) -> None:
        '''
        Insert a plot whose id is not already kept.

        :param plot: The plot aggregate to keep.
        :type plot: PlotAggregate
        :return: None
        :rtype: None
        :raises ServiceError: ``PLOT_ALREADY_KEPT`` when the id is already kept.
        '''

        # Convert the plot to the file shape. The role excludes the plot id.
        plot_data = PlotConfigObject.from_model(plot)

        # Load the publication. A missing file is an empty store.
        full_data = self._load_full()
        plots = full_data.get('plots') or {}

        # A second save must not replace the first publication.
        if plot.id in plots:
            ServiceError.raise_for(
                self,
                PLOT_ALREADY_KEPT_ID,
                message=f'Plot {plot.id!r} is already kept.',
                plot_id=plot.id,
            )

        # Insert the body under the plot id.
        plots[plot.id] = plot_data.to_primitive(self.default_role)
        full_data['plots'] = plots
        self._save(full_data)

    # * method: update
    def update(self, plot: PlotAggregate) -> None:
        '''
        Replace a kept plot with the same id.

        :param plot: The plot aggregate that replaces the kept record.
        :type plot: PlotAggregate
        :return: None
        :rtype: None
        :raises ServiceError: ``PLOT_NOT_KEPT`` when the id is not kept.
        '''

        # Convert the plot to the file shape. The role excludes the plot id.
        plot_data = PlotConfigObject.from_model(plot)

        # Load the publication. A missing file has nothing to replace.
        full_data = self._load_full()
        plots = full_data.get('plots') or {}

        # Update does not insert, and it does not re-derive the id from the name.
        if plot.id not in plots:
            ServiceError.raise_for(
                self,
                PLOT_NOT_KEPT_ID,
                message=f'Plot {plot.id!r} is not kept.',
                plot_id=plot.id,
            )

        # Replace that entry. The key stays the id the caller already kept.
        plots[plot.id] = plot_data.to_primitive(self.default_role)
        full_data['plots'] = plots
        self._save(full_data)

    # * method: delete
    def delete(self, id: str) -> None:
        '''
        Remove a kept plot and the series stored inside it.

        :param id: The plot id.
        :type id: str
        :return: None
        :rtype: None
        '''

        # An unsupported extension fails. A missing file is already empty.
        self._require_supported_file()
        if not Path(self.config_file).exists():
            return

        # A missing id changes nothing, including the file bytes.
        full_data = self._load() or {}
        plots = full_data.get('plots') or {}
        if id not in plots:
            return

        # Remove the plot entry. Its series live inside it, not at a second root.
        plots.pop(id, None)
        full_data['plots'] = plots
        self._save(full_data)

# ** repo: matrix_config_repository
class MatrixConfigRepository(MatrixService, ConfigurationRepository):
    '''
    The first store for a matrix record: a publication file beside the paper.

    ``.yaml`` and ``.yml`` are YAML. ``.json`` is JSON. Any other extension
    fails. Records live under a ``matrices`` root, keyed by matrix id. The
    transfer object writes the body and excludes that id. Cells, including
    their plot records, are nested in the matrix entry. This store does not
    draw, does not derive ids, and does not write those plots under ``plots``.
    '''

    # * init
    def __init__(self, matrix_config: str, encoding: str = 'utf-8') -> None:
        '''
        Initialize the matrix configuration repository.

        :param matrix_config: The publication file path.
        :type matrix_config: str
        :param encoding: The file encoding.
        :type encoding: str
        '''

        # Initialize the configuration repository base.
        ConfigurationRepository.__init__(
            self,
            config_file=matrix_config,
            encoding=encoding,
        )

    # * method: _require_supported_file
    def _require_supported_file(self) -> None:
        '''
        Fail when the path is not a publication file.

        :return: None
        :rtype: None
        :raises ServiceError: When the extension is not YAML or JSON.
        '''

        # Resolving the loader rejects any extension other than YAML or JSON.
        self._get_loader()

    # * method: _load_full
    def _load_full(self) -> dict:
        '''
        Load the full publication, treating a missing file as empty.

        :return: The full file mapping, or an empty mapping.
        :rtype: dict
        '''

        # An unsupported extension fails before a missing file is treated as empty.
        self._require_supported_file()

        # A missing file is an empty store, not a corrupt publication.
        if not Path(self.config_file).exists():
            return {}

        # Load and return the full publication.
        return self._load() or {}

    # * method: _load_matrices
    def _load_matrices(self) -> dict:
        '''
        Load the matrices mapping, tolerating a missing file or root.

        :return: The matrices mapping keyed by matrix id.
        :rtype: dict
        '''

        # An unsupported extension fails before a missing file is empty.
        self._require_supported_file()
        if not Path(self.config_file).exists():
            return {}

        # Select the matrices node. An empty root is an empty store.
        return self._load(
            start_node=lambda data: (data or {}).get('matrices') or {},
        ) or {}

    # * method: exists
    def exists(self, id: str) -> bool:
        '''
        Check whether a matrix id is kept.

        :param id: The matrix id.
        :type id: str
        :return: True when get would return a record, otherwise False.
        :rtype: bool
        '''

        # True only when get would return a record.
        return self.get(id) is not None

    # * method: get
    def get(self, id: str) -> PlotMatrixAggregate | None:
        '''
        Return the kept matrix, or nothing when the id is not kept.

        :param id: The matrix id.
        :type id: str
        :return: The matrix aggregate, or None when the id is not kept.
        :rtype: PlotMatrixAggregate | None
        '''

        # Load the matrix body. A missing id is not an error.
        body = self._load_matrices().get(id)
        if not body:
            return None

        # Inject the file key as id, then map the transfer object.
        return MatrixConfigObject.model_validate({
            **body,
            'id': id,
        }).map()

    # * method: list
    def list(self) -> list[PlotMatrixAggregate]:
        '''
        Return the kept matrix records.

        :return: The kept matrices. Not a picture and not a display string.
        :rtype: list[PlotMatrixAggregate]
        '''

        # Map each kept entry. An empty or missing file returns no records.
        return [
            MatrixConfigObject.model_validate({
                **body,
                'id': matrix_id,
            }).map()
            for matrix_id, body in self._load_matrices().items()
        ]

    # * method: save
    def save(self, matrix: PlotMatrixAggregate) -> None:
        '''
        Insert a matrix whose id is not already kept.

        :param matrix: The matrix aggregate to keep.
        :type matrix: PlotMatrixAggregate
        :return: None
        :rtype: None
        :raises ServiceError: ``MATRIX_ALREADY_KEPT`` when the id is already kept.
        '''

        # Convert the matrix to the file shape. The role excludes the matrix id.
        matrix_data = MatrixConfigObject.from_model(matrix)

        # Load the publication. A missing file is an empty store.
        full_data = self._load_full()
        matrices = full_data.get('matrices') or {}

        # A second save must not replace the first publication.
        if matrix.id in matrices:
            ServiceError.raise_for(
                self,
                MATRIX_ALREADY_KEPT_ID,
                message=f'Matrix {matrix.id!r} is already kept.',
                matrix_id=matrix.id,
            )

        # Insert the body under the matrix id. Leave every other root in place.
        matrices[matrix.id] = matrix_data.to_primitive(self.default_role)
        full_data['matrices'] = matrices
        self._save(full_data)

    # * method: update
    def update(self, matrix: PlotMatrixAggregate) -> None:
        '''
        Replace a kept matrix with the same id.

        :param matrix: The matrix aggregate that replaces the kept record.
        :type matrix: PlotMatrixAggregate
        :return: None
        :rtype: None
        :raises ServiceError: ``MATRIX_NOT_KEPT`` when the id is not kept.
        '''

        # Convert the matrix to the file shape. The role excludes the matrix id.
        matrix_data = MatrixConfigObject.from_model(matrix)

        # Load the publication. A missing file has nothing to replace.
        full_data = self._load_full()
        matrices = full_data.get('matrices') or {}

        # Update does not insert, and it does not re-derive the id from the name.
        if matrix.id not in matrices:
            ServiceError.raise_for(
                self,
                MATRIX_NOT_KEPT_ID,
                message=f'Matrix {matrix.id!r} is not kept.',
                matrix_id=matrix.id,
            )

        # Replace that entry. The key stays the id the caller already kept.
        matrices[matrix.id] = matrix_data.to_primitive(self.default_role)
        full_data['matrices'] = matrices
        self._save(full_data)

    # * method: delete
    def delete(self, id: str) -> None:
        '''
        Remove a kept matrix and the cells stored inside it.

        :param id: The matrix id.
        :type id: str
        :return: None
        :rtype: None
        '''

        # An unsupported extension fails. A missing file is already empty.
        self._require_supported_file()
        if not Path(self.config_file).exists():
            return

        # A missing id changes nothing, including the file bytes.
        full_data = self._load() or {}
        matrices = full_data.get('matrices') or {}
        if id not in matrices:
            return

        # Remove the matrix entry. Its cells live inside it, not at a second root.
        matrices.pop(id, None)
        full_data['matrices'] = matrices
        self._save(full_data)
