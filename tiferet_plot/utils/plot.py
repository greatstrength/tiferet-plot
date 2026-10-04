"""Matplotlib renderer for a declared plot."""

# *** imports

# ** core
import io
import os

# Select a headless backend before the drawing tool loads.
os.environ.setdefault('MPLBACKEND', 'Agg')

# ** infra
from matplotlib import image as mpl_image
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

# ** app
from ..interfaces.plot import RendererService
from ..mappers.plot import PlotAggregate, PlotMatrixAggregate

# *** constants

# ** constant: render_kinds
RENDER_KINDS = (
    'line',
    'scatter',
    'bar',
)

# ** constant: mark_roles_by_kind
MARK_ROLES_BY_KIND = {
    'line': (
        'x',
        'y',
    ),
    'scatter': (
        'x',
        'y',
    ),
    'bar': (
        'category',
        'height',
    ),
}

# ** constant: numeric_mark_roles
NUMERIC_MARK_ROLES = (
    'x',
    'y',
    'height',
)

# ** constant: text_mark_roles
TEXT_MARK_ROLES = (
    'category',
)

# ** constant: css_color_hex
CSS_COLOR_HEX = {
    'aqua': '#00ffff',
    'black': '#000000',
    'blue': '#0000ff',
    'fuchsia': '#ff00ff',
    'gray': '#808080',
    'green': '#008000',
    'lime': '#00ff00',
    'maroon': '#800000',
    'navy': '#000080',
    'olive': '#808000',
    'purple': '#800080',
    'red': '#ff0000',
    'silver': '#c0c0c0',
    'teal': '#008080',
    'white': '#ffffff',
    'yellow': '#ffff00',
}

# *** functions

# ** function: _require_picture_size
def _require_picture_size(width, height) -> None:
    '''
    Require a positive width and height in inches.

    A bool is not a width of 1. Text that looks like a number is not a
    size. Zero and a negative number are not a picture. There is no
    default. The pair the caller named is not changed.

    :param width: The picture width.
    :type width: Any
    :param height: The picture height.
    :type height: Any
    :return: None
    :rtype: None
    '''

    # Check each extent. Do not coerce text, and do not fill a missing one.
    for name, value in (('width', width), ('height', height)):
        if (isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value <= 0):
            raise ValueError(
                f'{name.capitalize()} must be a positive number of inches.'
            )

# ** function: _is_numeric
def _is_numeric(value) -> bool:
    '''
    Return whether a mark value can be drawn as a number.

    Booleans are not numeric. Text that looks like a number is not numeric.

    :param value: The mark value to classify.
    :type value: Any
    :return: True when the value is an int or a float.
    :rtype: bool
    '''

    # Reject bool before int, because bool is a subclass of int.
    if isinstance(value, bool):
        return False

    # Accept only real numbers. Do not coerce text.
    return isinstance(value, (int, float))

# ** function: _drawable_marks
def _drawable_marks(kind: str, marks) -> dict:
    '''
    Return mark values when they match the kind, else refuse the picture.

    This is not a declaration. It does not derive an id or rewrite a role.
    It stops an illegal record from becoming a picture.

    :param kind: The plot kind.
    :type kind: str
    :param marks: The series marks.
    :type marks: Sequence
    :return: Mark values keyed by role.
    :rtype: dict
    '''

    # Index marks by role and reject a repeated role.
    by_role = {}
    for mark in marks:
        if mark.role in by_role:
            raise ValueError(f'Duplicate mark role {mark.role!r}.')
        by_role[mark.role] = mark.values

    # The kind selects the roles this renderer draws. Extra roles are illegal.
    required = MARK_ROLES_BY_KIND[kind]
    extra = [role for role in by_role if role not in required]
    if extra:
        raise ValueError(
            f'Kind {kind!r} does not allow mark role {extra[0]!r}.'
        )

    # Every role the drawing path reads must be present.
    missing = [role for role in required if role not in by_role]
    if missing:
        raise ValueError(
            f'Kind {kind!r} requires mark role {missing[0]!r}.'
        )

    # Required values must be the right sort, non-empty, and the same length.
    lengths = []
    for role in required:
        values = by_role[role]
        if len(values) < 1:
            raise ValueError(
                f'Mark role {role!r} requires at least one value.'
            )
        if role in NUMERIC_MARK_ROLES and any(
                not _is_numeric(value) for value in values):
            raise ValueError(
                f'Mark role {role!r} requires numeric values.'
            )
        if role in TEXT_MARK_ROLES and any(
                not isinstance(value, str) for value in values):
            raise ValueError(
                f'Mark role {role!r} requires text values.'
            )
        lengths.append(len(values))

    # Equal length is part of being drawable for the kind.
    if len(set(lengths)) != 1:
        raise ValueError('Mark value sequences must have equal length.')

    # Return the values. Roles are unchanged.
    return by_role

# ** function: _drawable_series
def _drawable_series(plot: PlotAggregate) -> list:
    '''
    Return each series' mark values when the record can be drawn.

    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :return: One role-to-values mapping per series.
    :rtype: list
    '''

    # A kind outside the three drawing paths is not a picture.
    kind = plot.kind
    if kind not in RENDER_KINDS:
        allowed = ', '.join(RENDER_KINDS)
        raise ValueError(f'Kind {kind!r} is not one of {allowed}.')

    # Nothing to draw is not an empty picture.
    if not plot.series:
        raise ValueError('A plot requires at least one series.')

    # Check each series. Do not rename category or height.
    return [
        _drawable_marks(kind, series.marks)
        for series in plot.series
    ]

# ** function: _draw
def _draw(axes, kind: str, series_values: list) -> None:
    '''
    Draw each series on one plain axes.

    Line and scatter read x and y. Bar reads category and height.

    :param axes: The axes to draw on.
    :type axes: Axes
    :param kind: The plot kind.
    :type kind: str
    :param series_values: Role-to-values mappings, one per series.
    :type series_values: list
    :return: None
    :rtype: None
    '''

    # Line draws x and y. It does not read category.
    if kind == 'line':
        for values in series_values:
            axes.plot(values['x'], values['y'])
        return

    # Scatter draws x and y. It is not a second service.
    if kind == 'scatter':
        for values in series_values:
            axes.scatter(values['x'], values['y'])
        return

    # Bar draws category and height. Those roles are not renamed.
    if kind == 'bar':
        for values in series_values:
            axes.bar(values['category'], values['height'])
        return

    # A kind with no drawing path does not become a picture.
    allowed = ', '.join(RENDER_KINDS)
    raise ValueError(f'Kind {kind!r} is not one of {allowed}.')

# ** function: _read_png
def _read_png(png: bytes):
    '''
    Read picture bytes into an image array.

    The bytes came from ``render``. They are not written to a path.

    :param png: The picture bytes.
    :type png: bytes
    :return: The image array.
    :rtype: Any
    '''

    # Read the picture from memory. Do not place it on disk.
    return mpl_image.imread(io.BytesIO(png), format='png')

# ** function: _compose_grid
def _compose_grid(rows: int,
        cols: int,
        pictures: list,
        width: float,
        height: float) -> bytes:
    '''
    Place occupied-cell pictures on the declared grid.

    Empty positions stay empty. The result is one picture, not one
    picture per cell. Width and height are that picture's size. Rows
    and columns place the cells. They do not choose the size.

    :param rows: The declared row count.
    :type rows: int
    :param cols: The declared column count.
    :type cols: int
    :param pictures: ``(row, col, png)`` for each occupied cell.
    :type pictures: list
    :param width: The picture width, in inches.
    :type width: float
    :param height: The picture height, in inches.
    :type height: float
    :return: The grid as PNG bytes.
    :rtype: bytes
    '''

    # Size the figure by the requested pair. An empty corner still takes a cell.
    figure = Figure(figsize=(width, height))
    FigureCanvasAgg(figure)
    axes_grid = figure.subplots(nrows=rows, ncols=cols, squeeze=False)
    for row in range(rows):
        for col in range(cols):
            axes_grid[row][col].set_axis_off()

    # Place each occupied picture. Do not draw an empty position.
    for row, col, png in pictures:
        axes = axes_grid[row][col]
        axes.imshow(_read_png(png))
        axes.set_axis_off()

    # The bytes are the grid. Where they are placed is not this service.
    buffer = io.BytesIO()
    figure.savefig(buffer, format='png')
    return buffer.getvalue()

# *** utils

# ** util: matplotlib_renderer
class MatplotlibRenderer(RendererService):
    '''
    The first renderer. It turns a plot record into PNG bytes.

    It does not keep the record, derive an id, or write a publication file.
    A later drawing library is another class on the renderer service.
    '''

    # * method: render
    def render(self,
            plot: PlotAggregate,
            width: float,
            height: float) -> bytes:
        '''
        Render a plot record to PNG bytes of the given size.

        An unsaved record is a valid input. An illegal size, an illegal
        kind, or illegal marks raise, and no picture is returned. Width
        and height are inches. They are not fields of the plot.

        :param plot: The declared plot record.
        :type plot: PlotAggregate
        :param width: The picture width, in inches.
        :type width: float
        :param height: The picture height, in inches.
        :type height: float
        :return: The picture as PNG bytes.
        :rtype: bytes
        '''

        # Refuse a size that is not a picture. Do not start a figure.
        _require_picture_size(width, height)

        # Refuse a record this renderer cannot draw. Do not start a picture.
        series_values = _drawable_series(plot)

        # Draw at the requested size. Nothing is written to a path.
        figure = Figure(figsize=(width, height))
        FigureCanvasAgg(figure)
        _draw(figure.add_subplot(111), plot.kind, series_values)

        # The bytes are the picture. Where they are placed is not this service.
        buffer = io.BytesIO()
        figure.savefig(buffer, format='png')
        return buffer.getvalue()

    # * method: render_matrix
    def render_matrix(self,
            matrix: PlotMatrixAggregate,
            width: float,
            height: float) -> bytes:
        '''
        Render a declared grid to one PNG of the given size.

        Each occupied cell is drawn by ``render`` with that same width
        and height, and placed at its row and column. An empty position
        is not drawn. The pair is the grid picture's size, not a size
        per cell. An unsaved matrix is a valid input. If the size is
        illegal, or any occupied cell fails, no picture is returned.

        :param matrix: The declared matrix.
        :type matrix: PlotMatrixAggregate
        :param width: The picture width, in inches.
        :type width: float
        :param height: The picture height, in inches.
        :type height: float
        :return: The grid as PNG bytes.
        :rtype: bytes
        '''

        # Refuse a size that is not a picture. Do not draw a cell.
        _require_picture_size(width, height)

        # Draw every occupied cell at that same size. A failure returns no grid.
        pictures = []
        for cell in matrix.cells:
            pictures.append((
                cell.row,
                cell.col,
                self.render(cell.plot, width, height),
            ))

        # Place those pictures on one figure of the requested size.
        return _compose_grid(
            matrix.rows,
            matrix.cols,
            pictures,
            width,
            height,
        )
