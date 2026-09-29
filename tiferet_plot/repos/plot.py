"""Plot publication-file repository."""

# *** imports

# ** core
from __future__ import annotations
from pathlib import Path

# ** app
from tiferet.interfaces import ServiceError
from tiferet.repos.core import ConfigurationRepository
from ..interfaces.plot import (
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
    PlotService,
)
from ..mappers.plot import (
    PlotAggregate,
    PlotConfigObject,
)

# *** repos

# ** repo: plot_config_repository
class PlotConfigRepository(PlotService, ConfigurationRepository):
    '''
    The first store for a plot record: a publication file beside the paper.

    ``.yaml`` and ``.yml`` are YAML. ``.json`` is JSON. Any other extension
    fails. Records live under a ``plots`` root, keyed by plot id. Series
    live inside that entry, keyed by series id, so deleting a plot takes
    its series with it. The ids are the keys. They are not fields in the
    stored body. This store does not draw and does not derive ids.
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

        # Return the plots root, defaulting to an empty mapping.
        return self._load_full().get('plots') or {}

    # * method: _entry
    def _entry(self, plot: PlotAggregate) -> dict:
        '''
        Serialize a plot to the stored body.

        The body excludes the plot id. Series are keyed by series id.

        :param plot: The plot aggregate to store.
        :type plot: PlotAggregate
        :return: The file body for this plot.
        :rtype: dict
        '''

        # The transfer object writes the file shape. The repository does not derive an id.
        return PlotConfigObject.from_model(plot).to_primitive(self.default_role)

    # * method: _to_aggregate
    def _to_aggregate(self, plot_id: str, body: dict) -> PlotAggregate:
        '''
        Map a stored plot entry back to the aggregate.

        The plot id and each series id come from keys, not from the body.

        :param plot_id: The plot key.
        :type plot_id: str
        :param body: The stored plot body.
        :type body: dict
        :return: The plot aggregate.
        :rtype: PlotAggregate
        '''

        # Series live inside this plot, keyed by series id.
        series = [
            {
                **series_body,
                'id': series_id,
            }
            for series_id, series_body in (body.get('series') or {}).items()
        ]

        # The plot id comes from the file key. The key wins over any body field.
        return PlotConfigObject.model_validate({
            **body,
            'id': plot_id,
            'series': series,
        }).map()

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

        # Put the id back from the key and return the record.
        return self._to_aggregate(id, body)

    # * method: list
    def list(self) -> list[PlotAggregate]:
        '''
        Return the kept plot records.

        :return: The kept plots. Not a picture and not a display string.
        :rtype: list[PlotAggregate]
        '''

        # Map each kept entry. An empty or missing file returns no records.
        return [
            self._to_aggregate(plot_id, body)
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

        # Insert the body under the plot id. The id is the key, not a body field.
        plots[plot.id] = self._entry(plot)
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
        plots[plot.id] = self._entry(plot)
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
