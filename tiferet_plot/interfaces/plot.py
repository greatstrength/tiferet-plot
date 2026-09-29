"""Plot service contracts."""

# *** imports

# ** core
from abc import abstractmethod

# ** app
from tiferet.interfaces import Service
from ..mappers.plot import PlotAggregate

# *** interfaces

# ** interface: renderer_service
class RendererService(Service):
    '''
    Vertical contract for turning a plot record into a picture.

    The picture is PNG bytes. The contract does not name a drawing tool.
    An unsaved record is a valid input. Keeping the record and writing
    a publication file are not this service.
    '''

    # * method: render
    @abstractmethod
    def render(self, plot: PlotAggregate) -> bytes:
        '''
        Render a plot record to PNG bytes.

        :param plot: The declared plot record.
        :type plot: PlotAggregate
        :return: The picture as PNG bytes.
        :rtype: bytes
        '''

        # The implementation supplies the picture. This contract does not.
        raise NotImplementedError(
            'render method is required for RendererService.'
        )
