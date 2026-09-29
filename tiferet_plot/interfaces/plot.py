"""Plot service contracts."""

# *** imports

# ** core
from abc import abstractmethod

# ** app
from tiferet.interfaces import Service
from ..mappers.plot import PlotAggregate, PlotMatrixAggregate

# *** constants

# ** constant: plot_already_kept_id
PLOT_ALREADY_KEPT_ID = 'PLOT_ALREADY_KEPT'

# ** constant: plot_not_kept_id
PLOT_NOT_KEPT_ID = 'PLOT_NOT_KEPT'

# ** constant: matrix_already_kept_id
MATRIX_ALREADY_KEPT_ID = 'MATRIX_ALREADY_KEPT'

# ** constant: matrix_not_kept_id
MATRIX_NOT_KEPT_ID = 'MATRIX_NOT_KEPT'

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

    # * method: render_matrix
    @abstractmethod
    def render_matrix(self, matrix: PlotMatrixAggregate) -> bytes:
        '''
        Render a declared grid to one PNG.

        Empty positions are part of that picture. This is not ``render``.
        An unsaved matrix is a valid input. The contract does not open a store.

        :param matrix: The declared matrix.
        :type matrix: PlotMatrixAggregate
        :return: The grid as PNG bytes.
        :rtype: bytes
        '''

        # The implementation supplies the picture. This contract does not.
        raise NotImplementedError(
            'render_matrix method is required for RendererService.'
        )

# ** interface: plot_service
class PlotService(Service):
    '''
    The contract for keeping a plot record so it can be loaded again.

    Events and the session depend on this contract. They do not open a
    store. The contract does not name a file format or where the record
    is kept, and it does not draw a picture.
    '''

    # * method: exists
    @abstractmethod
    def exists(self, id: str) -> bool:
        '''
        Check whether a plot id is kept.

        True only when get would return a record.

        :param id: The plot id.
        :type id: str
        :return: True when the id is kept, otherwise False.
        :rtype: bool
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()

    # * method: get
    @abstractmethod
    def get(self, id: str) -> PlotAggregate | None:
        '''
        Return the kept plot, or nothing when the id is not kept.

        A missing id is not an error.

        :param id: The plot id.
        :type id: str
        :return: The plot aggregate, or None when the id is not kept.
        :rtype: PlotAggregate | None
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()

    # * method: list
    @abstractmethod
    def list(self) -> list[PlotAggregate]:
        '''
        Return the kept plot records.

        The result is records, not a picture and not a display string.

        :return: The kept records.
        :rtype: list[PlotAggregate]
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()

    # * method: save
    @abstractmethod
    def save(self, plot: PlotAggregate) -> None:
        '''
        Keep a plot whose id is not already kept.

        Save inserts. It does not replace an existing record. A second
        save of an id already kept fails, and the first record stays.

        :param plot: The plot aggregate to keep.
        :type plot: PlotAggregate
        :return: None
        :rtype: None
        :raises ServiceError: ``PLOT_ALREADY_KEPT`` when the id is already kept.
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()

    # * method: update
    @abstractmethod
    def update(self, plot: PlotAggregate) -> None:
        '''
        Replace one kept plot with the same id.

        Update does not insert. If the id is not kept, update fails.
        The id is not re-derived from the name.

        :param plot: The plot aggregate that replaces the kept record.
        :type plot: PlotAggregate
        :return: None
        :rtype: None
        :raises ServiceError: ``PLOT_NOT_KEPT`` when the id is not kept.
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()

    # * method: delete
    @abstractmethod
    def delete(self, id: str) -> None:
        '''
        Remove a kept plot and the series stored inside it.

        Deleting an id that is not kept succeeds and changes nothing.

        :param id: The plot id.
        :type id: str
        :return: None
        :rtype: None
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()

# ** interface: matrix_service
class MatrixService(Service):
    '''
    The contract for keeping a matrix so it can be loaded again.

    Events depend on this contract. They do not open a store. The contract
    does not name a file format or where the record is kept, and it does
    not draw a picture.
    '''

    # * method: exists
    @abstractmethod
    def exists(self, id: str) -> bool:
        '''
        Check whether a matrix id is kept.

        True only when get would return a record.

        :param id: The matrix id.
        :type id: str
        :return: True when the id is kept, otherwise False.
        :rtype: bool
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()

    # * method: get
    @abstractmethod
    def get(self, id: str) -> PlotMatrixAggregate | None:
        '''
        Return the kept matrix, or nothing when the id is not kept.

        A missing id is not an error.

        :param id: The matrix id.
        :type id: str
        :return: The matrix aggregate, or None when the id is not kept.
        :rtype: PlotMatrixAggregate | None
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()

    # * method: list
    @abstractmethod
    def list(self) -> list[PlotMatrixAggregate]:
        '''
        Return the kept matrix records.

        The result is records, not a picture and not a display string.

        :return: The kept records.
        :rtype: list[PlotMatrixAggregate]
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()

    # * method: save
    @abstractmethod
    def save(self, matrix: PlotMatrixAggregate) -> None:
        '''
        Keep a matrix whose id is not already kept.

        Save inserts. It does not replace an existing record. A second
        save of an id already kept fails, and the first record stays.

        :param matrix: The matrix aggregate to keep.
        :type matrix: PlotMatrixAggregate
        :return: None
        :rtype: None
        :raises ServiceError: ``MATRIX_ALREADY_KEPT`` when the id is already kept.
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()

    # * method: update
    @abstractmethod
    def update(self, matrix: PlotMatrixAggregate) -> None:
        '''
        Replace one kept matrix with the same id.

        Update does not insert. If the id is not kept, update fails.
        The id is not re-derived from the name.

        :param matrix: The matrix aggregate that replaces the kept record.
        :type matrix: PlotMatrixAggregate
        :return: None
        :rtype: None
        :raises ServiceError: ``MATRIX_NOT_KEPT`` when the id is not kept.
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()

    # * method: delete
    @abstractmethod
    def delete(self, id: str) -> None:
        '''
        Remove a kept matrix and the cells stored inside it.

        Deleting an id that is not kept succeeds and changes nothing.

        :param id: The matrix id.
        :type id: str
        :return: None
        :rtype: None
        '''

        # The implementation decides where the record is kept.
        raise NotImplementedError()
