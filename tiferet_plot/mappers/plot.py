"""Plot aggregates."""

# *** imports

# ** core
from __future__ import annotations
from typing import Sequence

# ** app
from tiferet.mappers import Aggregate
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
