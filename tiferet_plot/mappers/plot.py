"""Plot aggregates and publication-file shapes."""

# *** imports

# ** core
from __future__ import annotations
from typing import Any, ClassVar, Dict, Sequence

# ** infra
from pydantic import Field

# ** app
from tiferet.mappers import Aggregate, TransferObject
from ..domain.plot import Mark, Plot, Series

# *** mappers

# ** mapper: series_aggregate
class SeriesAggregate(Series, Aggregate):
    '''
    The mutable face of a series.

    Renaming a series changes what the author calls it. It does not
    recompute the id that identifies the series.
    '''

    # * method: rename
    def rename(self, name: str) -> None:
        '''
        Rename the series without recomputing its id.

        :param name: The new series name.
        :type name: str
        :return: None
        :rtype: None
        '''

        # Assign the name. Identity was fixed at declaration.
        self.name = name

    # * method: replace_marks
    def replace_marks(self, marks: Sequence[Mark]) -> None:
        '''
        Replace the marks on this series without recomputing its id.

        Kind rules are checked when the series is declared on a plot, and
        again when the plot aggregate replaces marks.

        :param marks: The replacement marks.
        :type marks: Sequence[Mark]
        :return: None
        :rtype: None
        '''

        # Replace the mark sequence. The series id stays as declared.
        self.marks = list(marks)

# ** mapper: plot_aggregate
class PlotAggregate(Plot, Aggregate):
    '''
    The mutable face of a declared plot.

    A rename changes the author's name for the figure. It does not
    recompute the id, and it does not draw or save.
    '''

    # * method: rename
    def rename(self, name: str) -> None:
        '''
        Rename the plot without recomputing its id.

        :param name: The new plot name.
        :type name: str
        :return: None
        :rtype: None
        '''

        # Assign the name. Identity was fixed at declaration.
        self.name = name

    # * method: rename_series
    def rename_series(self, series_id: str, name: str) -> None:
        '''
        Rename one series on this plot without recomputing that series id.

        :param series_id: The id of the series to rename.
        :type series_id: str
        :param name: The new series name.
        :type name: str
        :return: None
        :rtype: None
        '''

        # Copy the series list, changing only the named series' name.
        updated = []
        found = False
        for series in self.series:
            if series.id == series_id:
                found = True
                updated.append(series.model_copy(update={'name': name}))
            else:
                updated.append(series)

        # A missing series is a bad edit, not a new declaration.
        if not found:
            raise ValueError(f'No series with id {series_id!r}.')

        # Assign the edited series. Ids were fixed at declaration.
        self.series = updated

    # * method: replace_marks
    def replace_marks(self, series_id: str, marks: Sequence[Mark]) -> None:
        '''
        Replace one series' marks and re-check them against the plot kind.

        The series id is not recomputed. Invalid marks are rejected before
        the record changes.

        :param series_id: The id of the series whose marks are replaced.
        :type series_id: str
        :param marks: The replacement marks.
        :type marks: Sequence[Mark]
        :return: None
        :rtype: None
        '''

        # Build a declaration payload that keeps every id as already stored.
        series_data = []
        found = False
        for series in self.series:
            item = series.model_dump()
            if series.id == series_id:
                found = True
                item['marks'] = list(marks)
            series_data.append(item)

        # A missing series is a bad edit, not a new declaration.
        if not found:
            raise ValueError(f'No series with id {series_id!r}.')

        # Re-declare the record so kind rules still hold before assignment.
        data = self.model_dump()
        data['series'] = series_data
        checked = type(self).model_validate(data)

        # Keep the validated series. Identity is unchanged.
        self.series = checked.series

# ** mapper: series_config_object
class SeriesConfigObject(Series, TransferObject):
    '''
    The file shape of one series inside its plot.

    A series is nested in the plot body, not a second store. Its id stays
    on the series so a rename does not recompute it.
    '''

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_model': {},
        'to_data': {
            'by_alias': True,
            'mode': 'json',
        },
    }

    # * method: map
    def map(self, **overrides) -> SeriesAggregate:
        '''
        Map the series file shape to a series aggregate.

        :param overrides: Field values that replace the serialized shape.
        :type overrides: dict
        :return: The series aggregate.
        :rtype: SeriesAggregate
        '''

        # Map to the aggregate. A supplied id is not derived again.
        return super().map(SeriesAggregate, **overrides)

# ** mapper: plot_config_object
class PlotConfigObject(Plot, TransferObject):
    '''
    The file shape of a plot record, not a second record and not a picture.

    The plot id is the file key, so ``to_data`` excludes it. Series are
    nested transfer objects in the body. The body does not keep a renderer
    or a store handle.
    '''

    # * attribute: _ROLES
    _ROLES: ClassVar[Dict[str, Dict[str, Any]]] = {
        'to_model': {
            'exclude': {'series'},
        },
        'to_data': {
            'by_alias': True,
            'exclude': {'id'},
            'mode': 'json',
        },
    }

    # * attribute: series
    series: list[SeriesConfigObject] = Field(
        ...,
        min_length=1,
        description='The series nested in this plot entry.',
    )

    # * method: map
    def map(self, **overrides) -> PlotAggregate:
        '''
        Map the plot file shape to a plot aggregate.

        :param overrides: Field values that replace the serialized shape.
        :type overrides: dict
        :return: The plot aggregate.
        :rtype: PlotAggregate
        '''

        # Map nested series, then the plot. Ids already on the objects are kept.
        return super().map(
            PlotAggregate,
            series=[series.map() for series in self.series],
            **overrides,
        )

    # * method: from_model
    @classmethod
    def from_model(cls, plot: Plot, **overrides) -> 'PlotConfigObject':
        '''
        Create a plot file shape from a plot record.

        :param plot: The plot record.
        :type plot: Plot
        :param overrides: Field values that replace the record.
        :type overrides: dict
        :return: The plot file shape.
        :rtype: PlotConfigObject
        '''

        # Convert each series, then the plot. This does not derive an id.
        return super().from_model(
            plot,
            series=[
                SeriesConfigObject.from_model(series)
                for series in plot.series
            ],
            **overrides,
        )
