"""Plot events."""

# *** imports

# ** app
from tiferet.events import DomainEvent
from ..interfaces.plot import (
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
    PlotService,
)
from ..mappers.plot import PlotAggregate

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
            **kwargs,
        ) -> PlotAggregate:
        '''
        Declare a plot and keep it.

        A missing id is the snake_case of the name. A supplied id is kept.
        Kind and marks are checked by that declaration. An id already kept
        fails before save.

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
        :param kwargs: Additional keyword arguments.
        :type kwargs: dict
        :return: The kept plot record.
        :rtype: PlotAggregate
        :raises TiferetError: ``PLOT_ALREADY_KEPT`` when the id is already kept.
        '''

        # Declare the record. Invalid kind or marks fail here, before save.
        plot = PlotAggregate(
            name=name,
            kind=kind,
            series=series,
            id=id,
            description=description,
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
            **kwargs,
        ) -> PlotAggregate:
        '''
        Replace a kept plot without changing its id.

        Kind and marks are checked again. An omitted description is no
        description, not a merge with the kept record. The id is the one
        the caller already kept.

        :param id: The kept plot id. Not derived from the name.
        :type id: str
        :param name: The replacement name.
        :type name: str
        :param kind: The replacement kind.
        :type kind: str
        :param series: The replacement series.
        :type series: list
        :param description: The replacement claim text, if any.
        :type description: str | None
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
