"""Plot and matrix events."""

# *** imports

# ** app
from tiferet.events import DomainEvent
from ..interfaces.plot import (
    MATRIX_ALREADY_KEPT_ID,
    MATRIX_NOT_KEPT_ID,
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
    MatrixService,
    PlotService,
)
from ..mappers.plot import PlotAggregate, PlotMatrixAggregate

# *** events

# ** event: plot_event
class PlotEvent(DomainEvent):
    '''
    The path that declares a plot and keeps it.

    Create, get, list, update, and remove share the plot service. They do
    not open a file, construct a repository, or draw.
    '''

    # * attribute: plot_service
    plot_service: PlotService

    # * init
    def __init__(self, plot_service: PlotService) -> None:
        '''
        Initialize the plot event with its shared service.

        :param plot_service: The plot service shared across plot events.
        :type plot_service: PlotService
        '''

        # Hold the service. Do not open a store.
        self.plot_service = plot_service

# ** event: create_plot
class CreatePlot(PlotEvent):
    '''
    Declare a plot and keep it, as one operation.

    An id already kept fails, and the first record stays. The event returns
    the record. It does not return a picture.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['name', 'kind', 'series'])
    def execute(self,
            name: str,
            kind: str,
            series: list,
            id: str | None = None,
            description: str | None = None,
            *,
            title: str | None = None,
            x_title: str | None = None,
            x_unit: str | None = None,
            y_title: str | None = None,
            y_unit: str | None = None,
            show_legend: bool | None = None,
            legend_location: str | None = None,
            legend_title: str | None = None,
            title_size: int | float | None = None,
            subtitle_size: int | float | None = None,
            axis_label_size: int | float | None = None,
            tick_label_size: int | float | None = None,
            legend_size: int | float | None = None,
            x_tick_rotation: int | float | None = None,
            y_tick_rotation: int | float | None = None,
            x_tick_decimals: int | None = None,
            y_tick_decimals: int | None = None,
            font_family: str | None = None,
            **kwargs,
        ) -> PlotAggregate:
        '''
        Declare a plot and keep it.

        A missing id is the snake_case of the name. A supplied id is kept.
        Kind and marks are checked by that declaration. An id already kept
        fails before save. Title and axis text are not identity.
        Appearance rides on these keywords and on the series. It does
        not derive an id, and it does not draw.

        :param name: The author's name for the plot.
        :type name: str
        :param kind: The chart kind. One of line, scatter, or bar.
        :type kind: str
        :param series: The series to declare. Each item is a series record or its fields.
        :type series: list
        :param id: The plot id. Derived from the name when omitted.
        :type id: str | None
        :param description: Optional claim text. Not used to derive the id.
        :type description: str | None
        :param title: Optional display title. Not used to derive the id.
        :type title: str | None
        :param x_title: Optional title of the x axis. Not used to derive the id.
        :type x_title: str | None
        :param x_unit: Optional unit of the x axis. Not used to derive the id.
        :type x_unit: str | None
        :param y_title: Optional title of the y axis. Not used to derive the id.
        :type y_title: str | None
        :param y_unit: Optional unit of the y axis. Not used to derive the id.
        :type y_unit: str | None
        :param show_legend: Optional legend flag. Omitted is not stored as true.
        :type show_legend: bool | None
        :param legend_location: Optional legend place.
        :type legend_location: str | None
        :param legend_title: Optional legend title. Blank is absent.
        :type legend_title: str | None
        :param title_size: Optional title size in points.
        :type title_size: int | float | None
        :param subtitle_size: Optional subtitle size in points.
        :type subtitle_size: int | float | None
        :param axis_label_size: Optional axis-label size in points.
        :type axis_label_size: int | float | None
        :param tick_label_size: Optional tick-label size in points.
        :type tick_label_size: int | float | None
        :param legend_size: Optional legend size in points.
        :type legend_size: int | float | None
        :param x_tick_rotation: Optional x tick rotation in degrees.
        :type x_tick_rotation: int | float | None
        :param y_tick_rotation: Optional y tick rotation in degrees.
        :type y_tick_rotation: int | float | None
        :param x_tick_decimals: Optional x decimal count. Zero is supplied.
        :type x_tick_decimals: int | None
        :param y_tick_decimals: Optional y decimal count. Zero is supplied.
        :type y_tick_decimals: int | None
        :param font_family: Optional font family.
        :type font_family: str | None
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The kept plot record.
        :rtype: PlotAggregate
        :raises TiferetError: ``PLOT_ALREADY_KEPT`` when the id is already kept.
        '''

        # Declare the record. Invalid kind, marks, or appearance fail here.
        plot = PlotAggregate(
            name=name,
            kind=kind,
            series=series,
            id=id,
            description=description,
            title=title,
            x_title=x_title,
            x_unit=x_unit,
            y_title=y_title,
            y_unit=y_unit,
            show_legend=show_legend,
            legend_location=legend_location,
            legend_title=legend_title,
            title_size=title_size,
            subtitle_size=subtitle_size,
            axis_label_size=axis_label_size,
            tick_label_size=tick_label_size,
            legend_size=legend_size,
            x_tick_rotation=x_tick_rotation,
            y_tick_rotation=y_tick_rotation,
            x_tick_decimals=x_tick_decimals,
            y_tick_decimals=y_tick_decimals,
            font_family=font_family,
        )

        # An id already kept is the rejected second save. Do not call save.
        self.verify(
            not self.plot_service.exists(plot.id),
            PLOT_ALREADY_KEPT_ID,
            message=f'Plot {plot.id!r} is already kept.',
            plot_id=plot.id,
        )

        # Keep the declared record.
        self.plot_service.save(plot)

        # Return the record. Not a picture.
        return plot

# ** event: get_plot
class GetPlot(PlotEvent):
    '''
    Load one kept plot record.

    A missing id fails. The event does not derive an id from a name, and
    it does not draw.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['id'])
    def execute(self, id: str, **kwargs) -> PlotAggregate:
        '''
        Return one kept plot.

        :param id: The plot id. Not derived from a name.
        :type id: str
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The kept plot record.
        :rtype: PlotAggregate
        :raises TiferetError: ``PLOT_NOT_KEPT`` when the id is not kept.
        '''

        # Load the record. A missing id is nothing, not a derived name.
        plot = self.plot_service.get(id)

        # A missing record fails. This event does not draw.
        self.verify(
            plot is not None,
            PLOT_NOT_KEPT_ID,
            message=f'Plot {id!r} is not kept.',
            plot_id=id,
        )

        # Return the record.
        return plot

# ** event: list_plots
class ListPlots(PlotEvent):
    '''
    Return the kept plot records.

    An empty store is an empty list. A list of plots is not a display
    string and not a picture.
    '''

    # * method: execute
    def execute(self, **kwargs) -> list[PlotAggregate]:
        '''
        Return the kept plots.

        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The kept records. An empty store returns an empty list.
        :rtype: list[PlotAggregate]
        '''

        # Return records. An empty store is an empty list, not a sentence.
        return self.plot_service.list()

# ** event: update_plot
class UpdatePlot(PlotEvent):
    '''
    Keep an edit of a plot that is already saved.

    The id is not derived from the name again. A missing id fails and
    nothing is inserted. Rename and replacing marks are the edit.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['id', 'name', 'kind', 'series'])
    def execute(self,
            id: str,
            name: str,
            kind: str,
            series: list,
            description: str | None = None,
            *,
            title: str | None = None,
            x_title: str | None = None,
            x_unit: str | None = None,
            y_title: str | None = None,
            y_unit: str | None = None,
            show_legend: bool | None = None,
            legend_location: str | None = None,
            legend_title: str | None = None,
            title_size: int | float | None = None,
            subtitle_size: int | float | None = None,
            axis_label_size: int | float | None = None,
            tick_label_size: int | float | None = None,
            legend_size: int | float | None = None,
            x_tick_rotation: int | float | None = None,
            y_tick_rotation: int | float | None = None,
            x_tick_decimals: int | None = None,
            y_tick_decimals: int | None = None,
            font_family: str | None = None,
            **kwargs,
        ) -> PlotAggregate:
        '''
        Replace a kept plot without changing its id.

        Kind and marks are checked again. An omitted description is no
        description, not a merge with the kept record. An omitted title,
        axis field, or appearance field is absent, not a merge. The id
        is the one the caller already kept. It is not derived from
        appearance.

        :param id: The kept plot id. Not derived from the name.
        :type id: str
        :param name: The replacement name.
        :type name: str
        :param kind: The replacement kind.
        :type kind: str
        :param series: The replacement series. Style rides on each series.
        :type series: list
        :param description: The replacement claim text, if any.
        :type description: str | None
        :param title: The replacement display title, if any. Not identity.
        :type title: str | None
        :param x_title: The replacement x-axis title, if any.
        :type x_title: str | None
        :param x_unit: The replacement x-axis unit, if any.
        :type x_unit: str | None
        :param y_title: The replacement y-axis title, if any.
        :type y_title: str | None
        :param y_unit: The replacement y-axis unit, if any.
        :type y_unit: str | None
        :param show_legend: The replacement legend flag. Omitted clears it.
        :type show_legend: bool | None
        :param legend_location: The replacement legend place. Omitted clears it.
        :type legend_location: str | None
        :param legend_title: The replacement legend title. Omitted clears it.
        :type legend_title: str | None
        :param title_size: The replacement title size. Omitted clears it.
        :type title_size: int | float | None
        :param subtitle_size: The replacement subtitle size. Omitted clears it.
        :type subtitle_size: int | float | None
        :param axis_label_size: The replacement axis-label size. Omitted clears it.
        :type axis_label_size: int | float | None
        :param tick_label_size: The replacement tick-label size. Omitted clears it.
        :type tick_label_size: int | float | None
        :param legend_size: The replacement legend size. Omitted clears it.
        :type legend_size: int | float | None
        :param x_tick_rotation: The replacement x rotation. Omitted clears it.
        :type x_tick_rotation: int | float | None
        :param y_tick_rotation: The replacement y rotation. Omitted clears it.
        :type y_tick_rotation: int | float | None
        :param x_tick_decimals: The replacement x decimals. Omitted clears it.
        :type x_tick_decimals: int | None
        :param y_tick_decimals: The replacement y decimals. Omitted clears it.
        :type y_tick_decimals: int | None
        :param font_family: The replacement font family. Omitted clears it.
        :type font_family: str | None
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The replacement record.
        :rtype: PlotAggregate
        :raises ServiceError: ``PLOT_NOT_KEPT`` when the id is not kept.
        '''

        # Re-declare the replacement. The supplied id is not rewritten.
        plot = PlotAggregate(
            id=id,
            name=name,
            kind=kind,
            series=series,
            description=description,
            title=title,
            x_title=x_title,
            x_unit=x_unit,
            y_title=y_title,
            y_unit=y_unit,
            show_legend=show_legend,
            legend_location=legend_location,
            legend_title=legend_title,
            title_size=title_size,
            subtitle_size=subtitle_size,
            axis_label_size=axis_label_size,
            tick_label_size=tick_label_size,
            legend_size=legend_size,
            x_tick_rotation=x_tick_rotation,
            y_tick_rotation=y_tick_rotation,
            x_tick_decimals=x_tick_decimals,
            y_tick_decimals=y_tick_decimals,
            font_family=font_family,
        )

        # Replace the kept record. A missing id fails and does not insert.
        self.plot_service.update(plot)

        # Return the edited record. The id is unchanged.
        return plot

# ** event: remove_plot
class RemovePlot(PlotEvent):
    '''
    Remove a plot by id.

    A missing id succeeds. The series stored inside that plot go with it.
    The event does not return the deleted record and does not draw.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['id'])
    def execute(self, id: str, **kwargs) -> str:
        '''
        Remove a plot by id.

        :param id: The plot id.
        :type id: str
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The plot id. Not the deleted record.
        :rtype: str
        '''

        # Delete by id. A missing id succeeds and changes nothing.
        self.plot_service.delete(id)

        # Return the id. Not the deleted record, and not a picture.
        return id

# ** event: matrix_event
class MatrixEvent(DomainEvent):
    '''
    Base event for keeping a declared grid.

    It holds the matrix service and nothing else. It does not hold the
    plot service, and it does not open a file.
    '''

    # * attribute: matrix_service
    matrix_service: MatrixService

    # * init
    def __init__(self, matrix_service: MatrixService) -> None:
        '''
        Initialize the matrix event with its service.

        :param matrix_service: The matrix service.
        :type matrix_service: MatrixService
        '''

        # Set the matrix service dependency.
        self.matrix_service = matrix_service

# ** event: create_matrix
class CreateMatrix(MatrixEvent):
    '''
    Declare a matrix and keep it.

    Create returns the record. It does not return a picture.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['name', 'rows', 'cols', 'cells'])
    def execute(self,
            name: str,
            rows: int,
            cols: int,
            cells: list,
            id: str | None = None,
            description: str | None = None,
            *,
            title: str | None = None,
            show_legend: bool | None = None,
            legend_location: str | None = None,
            legend_title: str | None = None,
            title_size: int | float | None = None,
            subtitle_size: int | float | None = None,
            legend_size: int | float | None = None,
            font_family: str | None = None,
            row_spacing: int | float | None = None,
            col_spacing: int | float | None = None,
            **kwargs,
        ) -> PlotMatrixAggregate:
        '''
        Declare a matrix, then insert it.

        An id already kept fails before save and leaves the first matrix
        unchanged. Save failing because the id exists is that same failure.
        Title is not identity. A matrix has no axis text.
        Grid appearance rides on these keywords. Series style stays on
        the cell plots. This event does not take a color.

        :param name: The author's name for the matrix.
        :type name: str
        :param rows: The declared row count.
        :type rows: int
        :param cols: The declared column count.
        :type cols: int
        :param cells: The occupied cells, each carrying a plot record.
        :type cells: list
        :param id: The matrix id. Derived from the name when omitted.
        :type id: str | None
        :param description: Optional claim text. Not identity.
        :type description: str | None
        :param title: Optional display title of the grid. Not used to derive the id.
        :type title: str | None
        :param show_legend: Optional grid-legend flag. Omitted is not false.
        :type show_legend: bool | None
        :param legend_location: Optional grid-legend place.
        :type legend_location: str | None
        :param legend_title: Optional grid-legend title. Blank is absent.
        :type legend_title: str | None
        :param title_size: Optional grid-title size in points.
        :type title_size: int | float | None
        :param subtitle_size: Optional grid-subtitle size in points.
        :type subtitle_size: int | float | None
        :param legend_size: Optional grid-legend size in points.
        :type legend_size: int | float | None
        :param font_family: Optional grid font family.
        :type font_family: str | None
        :param row_spacing: Optional row gap. Zero is supplied.
        :type row_spacing: int | float | None
        :param col_spacing: Optional column gap. Zero is supplied.
        :type col_spacing: int | float | None
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The kept matrix.
        :rtype: PlotMatrixAggregate
        '''

        # Declare the grid. A bad cell or a disagreeing legend fails here.
        matrix = PlotMatrixAggregate(
            name=name,
            rows=rows,
            cols=cols,
            cells=cells,
            id=id,
            description=description,
            title=title,
            show_legend=show_legend,
            legend_location=legend_location,
            legend_title=legend_title,
            title_size=title_size,
            subtitle_size=subtitle_size,
            legend_size=legend_size,
            font_family=font_family,
            row_spacing=row_spacing,
            col_spacing=col_spacing,
        )

        # An id already kept is the same failure as a rejected save.
        self.verify(
            not self.matrix_service.exists(matrix.id),
            MATRIX_ALREADY_KEPT_ID,
            message=f'Matrix {matrix.id!r} is already kept.',
            matrix_id=matrix.id,
        )

        # Insert the declared record. Do not draw it.
        self.matrix_service.save(matrix)

        # Return the matrix. The picture is a later call.
        return matrix

# ** event: get_matrix
class GetMatrix(MatrixEvent):
    '''
    Load one kept matrix by the id it already has.

    A missing id fails. The name is not an id.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['id'])
    def execute(self, id: str, **kwargs) -> PlotMatrixAggregate:
        '''
        Return the kept matrix.

        :param id: The matrix id. Not derived from a name.
        :type id: str
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The kept matrix.
        :rtype: PlotMatrixAggregate
        '''

        # Load through the service. Do not derive an id from a name.
        matrix = self.matrix_service.get(id)

        # A missing id fails. The caller does not interpret nothing.
        self.verify(
            matrix is not None,
            MATRIX_NOT_KEPT_ID,
            message=f'Matrix {id!r} is not kept.',
            matrix_id=id,
        )

        # Return the record. Not a picture.
        return matrix

# ** event: list_matrices
class ListMatrices(MatrixEvent):
    '''
    Return the kept matrices.

    An empty store is an empty list, not a sentence and not a picture.
    '''

    # * method: execute
    def execute(self, **kwargs) -> list[PlotMatrixAggregate]:
        '''
        Return the service list.

        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The kept matrices.
        :rtype: list[PlotMatrixAggregate]
        '''

        # Return records. Do not format them for display.
        return self.matrix_service.list()

# ** event: update_matrix
class UpdateMatrix(MatrixEvent):
    '''
    Replace one kept matrix.

    Update re-checks the declaration rules and does not re-derive the
    matrix id or any plot id. A missing id fails and does not insert.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['id', 'name', 'rows', 'cols', 'cells'])
    def execute(self,
            id: str,
            name: str,
            rows: int,
            cols: int,
            cells: list,
            description: str | None = None,
            *,
            title: str | None = None,
            show_legend: bool | None = None,
            legend_location: str | None = None,
            legend_title: str | None = None,
            title_size: int | float | None = None,
            subtitle_size: int | float | None = None,
            legend_size: int | float | None = None,
            font_family: str | None = None,
            row_spacing: int | float | None = None,
            col_spacing: int | float | None = None,
            **kwargs,
        ) -> PlotMatrixAggregate:
        '''
        Re-declare a kept matrix and replace it.

        An omitted title is no title, not a merge with the kept record.
        The id is not derived from the title. An omitted appearance
        field clears it. Setting the grid legend re-declares the union.
        A disagreement fails before update, so the kept matrix is
        unchanged.

        :param id: The matrix id already kept. Not recomputed from the name.
        :type id: str
        :param name: The replacement name.
        :type name: str
        :param rows: The declared row count.
        :type rows: int
        :param cols: The declared column count.
        :type cols: int
        :param cells: The replacement cells. Each plot id must already be set.
        :type cells: list
        :param description: Optional claim text. Not identity.
        :type description: str | None
        :param title: The replacement display title, if any. Not identity.
        :type title: str | None
        :param show_legend: The replacement grid-legend flag. Omitted clears it.
        :type show_legend: bool | None
        :param legend_location: The replacement legend place. Omitted clears it.
        :type legend_location: str | None
        :param legend_title: The replacement legend title. Omitted clears it.
        :type legend_title: str | None
        :param title_size: The replacement grid-title size. Omitted clears it.
        :type title_size: int | float | None
        :param subtitle_size: The replacement grid-subtitle size. Omitted clears it.
        :type subtitle_size: int | float | None
        :param legend_size: The replacement grid-legend size. Omitted clears it.
        :type legend_size: int | float | None
        :param font_family: The replacement font family. Omitted clears it.
        :type font_family: str | None
        :param row_spacing: The replacement row gap. Omitted clears it.
        :type row_spacing: int | float | None
        :param col_spacing: The replacement column gap. Omitted clears it.
        :type col_spacing: int | float | None
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The replacement matrix.
        :rtype: PlotMatrixAggregate
        '''

        # Re-check the declaration. The supplied id is kept.
        matrix = PlotMatrixAggregate(
            id=id,
            name=name,
            rows=rows,
            cols=cols,
            cells=cells,
            description=description,
            title=title,
            show_legend=show_legend,
            legend_location=legend_location,
            legend_title=legend_title,
            title_size=title_size,
            subtitle_size=subtitle_size,
            legend_size=legend_size,
            font_family=font_family,
            row_spacing=row_spacing,
            col_spacing=col_spacing,
        )

        # A missing id fails before update and does not insert.
        self.verify(
            self.matrix_service.exists(matrix.id),
            MATRIX_NOT_KEPT_ID,
            message=f'Matrix {matrix.id!r} is not kept.',
            matrix_id=matrix.id,
        )

        # Replace the kept record. Do not draw it.
        self.matrix_service.update(matrix)

        # Return the replacement. Not a picture.
        return matrix

# ** event: remove_matrix
class RemoveMatrix(MatrixEvent):
    '''
    Remove a matrix by id.

    Remove is idempotent. It does not return the deleted matrix.
    '''

    # * method: execute
    @DomainEvent.parameters_required(['id'])
    def execute(self, id: str, **kwargs) -> str:
        '''
        Delete a matrix by id.

        :param id: The matrix id.
        :type id: str
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The id that was removed, or that was already absent.
        :rtype: str
        '''

        # Delete is idempotent. A missing id changes nothing.
        self.matrix_service.delete(id)

        # Return the id. Not the deleted matrix, and not a picture.
        return id
