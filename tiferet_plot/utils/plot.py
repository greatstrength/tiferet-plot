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
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FixedLocator, FormatStrFormatter
from matplotlib.transforms import ScaledTranslation

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

# ** constant: optional_mark_roles_by_kind
OPTIONAL_MARK_ROLES_BY_KIND = {
    'line': (
        'label',
    ),
    'scatter': (
        'label',
    ),
    'bar': (),
}

# ** constant: numeric_mark_roles
NUMERIC_MARK_ROLES = (
    'height',
)

# ** constant: text_mark_roles
TEXT_MARK_ROLES = (
    'category',
    'label',
)

# ** constant: axis_mark_roles
AXIS_MARK_ROLES = (
    'x',
    'y',
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

# ** constant: color_cycle
COLOR_CYCLE = (
    '#1f77b4',
    '#ff7f0e',
    '#2ca02c',
    '#d62728',
    '#9467bd',
    '#8c564b',
    '#e377c2',
    '#7f7f7f',
    '#bcbd22',
    '#17becf',
)

# ** constant: marker_codes
MARKER_CODES = {
    'circle': 'o',
    'square': 's',
    'triangle': '^',
    'diamond': 'D',
    'x': 'x',
    'plus': '+',
    'point': '.',
}

# ** constant: legend_tool_loc
LEGEND_TOOL_LOC = {
    'upper_right': 'upper right',
    'upper_left': 'upper left',
    'lower_left': 'lower left',
    'lower_right': 'lower right',
}

# ** constant: default_title_size
DEFAULT_TITLE_SIZE = 12

# ** constant: default_subtitle_size
DEFAULT_SUBTITLE_SIZE = 10

# ** constant: default_axis_label_size
DEFAULT_AXIS_LABEL_SIZE = 10

# ** constant: default_tick_label_size
DEFAULT_TICK_LABEL_SIZE = 8

# ** constant: default_legend_size
DEFAULT_LEGEND_SIZE = 10

# ** constant: default_font_family
DEFAULT_FONT_FAMILY = 'sans-serif'

# ** constant: default_linestyle
DEFAULT_LINESTYLE = 'solid'

# ** constant: default_linewidth
DEFAULT_LINEWIDTH = 1.5

# ** constant: default_markersize
DEFAULT_MARKERSIZE = 6

# ** constant: default_scatter_marker
DEFAULT_SCATTER_MARKER = 'circle'

# ** constant: bar_group_span
BAR_GROUP_SPAN = 0.8

# ** constant: point_label_size
POINT_LABEL_SIZE = 8

# ** constant: point_label_offset
POINT_LABEL_OFFSET = (
    4,
    4,
)

# ** constant: outside_legend_gap
OUTSIDE_LEGEND_GAP = 4

# ** constant: text_tick_rotation
TEXT_TICK_ROTATION = 45

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

# ** function: _present
def _present(value):
    '''
    Return text that is present, or nothing when it is absent or blank.

    An empty string and a whitespace-only string are the same case as
    an omitted field. The reading is not written back.

    :param value: The stored text.
    :type value: Any
    :return: The text, or None when there is nothing to draw.
    :rtype: str | None
    '''

    # A non-string is not figure text. Do not coerce it.
    if not isinstance(value, str) or not value.strip():
        return None

    # A supplied string is kept for the picture. It is not rewritten.
    return value

# ** function: _supplied
def _supplied(value, default):
    '''
    Return a stored number, or the drawing default when it was omitted.

    A stored zero is a supplied value. It is not the absent case, and
    the default is not written back onto the record.

    :param value: The stored number, if any.
    :type value: Any
    :param default: The drawing default.
    :type default: Any
    :return: The stored number, or the default when it was omitted.
    :rtype: Any
    '''

    # None is the only absent case. Zero stays zero.
    if value is None:
        return default

    # Return the supplied value. Do not store the default.
    return value

# ** function: _font_family
def _font_family(plot) -> str:
    '''
    Return the family that covers every text artist in the picture.

    Absent is sans-serif. A present value is used as stored. It is not
    written back.

    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :return: The font family for this picture.
    :rtype: str
    '''

    # A blank family is the same case as an omitted one.
    family = _present(getattr(plot, 'font_family', None))
    if family is None:
        return DEFAULT_FONT_FAMILY

    # One family covers the picture. A second family is not introduced.
    return family

# ** function: _figure_title
def _figure_title(plot) -> str:
    '''
    Return the axes title this picture draws.

    The reading is ``title`` when it is present and not blank, otherwise
    the catalog name. The name is not written into ``title``. The id is
    not the title.

    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :return: The title text.
    :rtype: str
    '''

    # A present title is the text. The catalog name is not also a title.
    title = _present(getattr(plot, 'title', None))
    if title is not None:
        return title

    # Absent title falls back for the picture only. The record stays absent.
    return plot.name

# ** function: _composed_label
def _composed_label(title, unit):
    '''
    Compose an axis label from a title and a unit, at draw time.

    Both present: the title, a space, and the unit in parentheses. The
    title alone is the title. The unit alone is the unit, not wrapped.
    Neither present draws no label. The string is not stored.

    :param title: The axis title, if any.
    :type title: Any
    :param unit: The axis unit, if any.
    :type unit: Any
    :return: The label, or None when that axis has no label.
    :rtype: str | None
    '''

    # Blank is not present. Do not invent a separator field.
    title = _present(title)
    unit = _present(unit)
    if title and unit:
        return f'{title} ({unit})'
    if title:
        return title
    if unit:
        return unit

    # Neither present. Do not draw an empty label.
    return None

# ** function: _legend_entry
def _legend_entry(series) -> str:
    '''
    Return one series' legend text.

    A present label is that text. An absent or blank label is the series
    name. The name is not written into the label. A point label is not
    an entry.

    :param series: The series.
    :type series: SeriesAggregate
    :return: The entry text.
    :rtype: str
    '''

    # A present label is the entry. The series name is not written back.
    label = _present(getattr(series, 'legend_label', None))
    if label is not None:
        return label

    # The series name is the reading. It is not stored as the label.
    return series.name

# ** function: _role_sort
def _role_sort(role: str, values) -> str:
    '''
    Return the sort of one role, or refuse the picture.

    Height is numeric. Category and label are text. An empty label is
    an unlabeled point. x and y are each one sort: all numeric, or all
    non-blank text. Text that looks like a number is not coerced.

    :param role: The mark role.
    :type role: str
    :param values: The values that play the role.
    :type values: Sequence
    :return: ``numeric`` or ``text``.
    :rtype: str
    '''

    # Height stays numeric. Do not accept text that looks like a number.
    if role in NUMERIC_MARK_ROLES:
        if any(not _is_numeric(value) for value in values):
            raise ValueError(
                f'Mark role {role!r} requires numeric values.'
            )
        return 'numeric'

    # Category and label are text. A blank label is still text.
    if role in TEXT_MARK_ROLES:
        if any(not isinstance(value, str) for value in values):
            raise ValueError(
                f'Mark role {role!r} requires text values.'
            )
        return 'text'

    # An axis is one sort. A blank name is not a position.
    if role in AXIS_MARK_ROLES:
        if all(_is_numeric(value) for value in values):
            return 'numeric'
        if all(isinstance(value, str) for value in values):
            if any(not value.strip() for value in values):
                raise ValueError(
                    f'Mark role {role!r} requires a non-blank name '
                    'when the values are text.'
                )
            return 'text'
        raise ValueError(
            f'Mark role {role!r} requires values of one sort, numeric or text.'
        )

    # A role outside the closed list is not a sort this check names.
    raise ValueError(f'Mark role {role!r} is not a declared role.')

# ** function: _drawable_marks
def _drawable_marks(kind: str, marks) -> dict:
    '''
    Return mark values when they match the kind, else refuse the picture.

    Label is allowed on line and scatter. It is not allowed on a bar.
    Text x or text y is allowed when the other axis is numeric. Text on
    both axes is not a picture. This is not a declaration. It does not
    derive an id or rewrite a role.

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

    # The kind selects the roles. Label is optional. Any other extra role fails.
    required = MARK_ROLES_BY_KIND[kind]
    allowed = required + OPTIONAL_MARK_ROLES_BY_KIND[kind]
    extra = [role for role in by_role if role not in allowed]
    if extra:
        raise ValueError(
            f'Kind {kind!r} does not allow mark role {extra[0]!r}.'
        )

    # Every role the drawing path reads must be present. Label may be absent.
    missing = [role for role in required if role not in by_role]
    if missing:
        raise ValueError(
            f'Kind {kind!r} requires mark role {missing[0]!r}.'
        )

    # Present values must be one sort, non-empty, and the same length.
    lengths = []
    sorts = {}
    for role in allowed:
        if role not in by_role:
            continue
        values = by_role[role]
        if len(values) < 1:
            raise ValueError(
                f'Mark role {role!r} requires at least one value.'
            )
        sorts[role] = _role_sort(role, values)
        lengths.append(len(values))

    # Equal length is part of being drawable for the kind.
    if len(set(lengths)) != 1:
        raise ValueError('Mark value sequences must have equal length.')

    # A line or a scatter still marks a quantity. Two text axes do not.
    both_text = (
        kind in ('line', 'scatter')
        and sorts.get('x') == 'text'
        and sorts.get('y') == 'text'
    )
    if both_text:
        raise ValueError(
            f'Kind {kind!r} requires at least one of x and y to be numeric.'
        )

    # Return the values. Roles are unchanged.
    return by_role

# ** function: _refuse_inapplicable_style
def _refuse_inapplicable_style(kind: str, series) -> None:
    '''
    Refuse a present style field the kind does not show.

    An absent value is legal on every kind. A stored value the picture
    does not show is not. The field is not cleared. No picture is returned.

    :param kind: The plot kind.
    :type kind: str
    :param series: The series.
    :type series: SeriesAggregate
    :return: None
    :rtype: None
    '''

    # The first inapplicable field fails. The value stays on the series.
    field = None
    if kind != 'line' and getattr(series, 'linestyle', None) is not None:
        field = 'linestyle'
    elif kind != 'line' and getattr(series, 'linewidth', None) is not None:
        field = 'linewidth'
    elif kind == 'bar' and getattr(series, 'marker', None) is not None:
        field = 'marker'
    elif kind == 'bar' and getattr(series, 'markersize', None) is not None:
        field = 'markersize'
    elif kind != 'bar' and getattr(series, 'bar_width', None) is not None:
        field = 'bar_width'
    if field is None:
        return

    # The kind is what makes the field illegal. Do not start a picture.
    raise ValueError(f'Kind {kind!r} does not use {field}.')

# ** function: _tool_marker
def _tool_marker(token: str):
    '''
    Map a stored marker token to the drawing tool's code.

    The record is not rewritten to that code. ``no_marker`` draws nothing.

    :param token: The stored marker token.
    :type token: str
    :return: The tool code, or None when no marker is drawn.
    :rtype: str | None
    '''

    # A stored no_marker stays no_marker on the record and draws nothing.
    if token == 'no_marker':
        return None

    # The tool spelling is not stored. An unknown token is not a picture.
    code = MARKER_CODES.get(token)
    if code is None:
        raise ValueError(f'Marker {token!r} is not a declared marker.')

    # Return the tool code. Do not write it back.
    return code

# ** function: _drawn_color
def _drawn_color(series, index: int) -> str:
    '''
    Return the color this series is drawn with.

    An absent color is the cycle hex for this series' index, counting
    from zero, modulo 10. A hex is used as stored. A name is mapped
    through the dictionary beside this renderer. Nothing is written back.

    :param series: The series.
    :type series: SeriesAggregate
    :param index: The series position in this plot, from zero.
    :type index: int
    :return: The color the tool draws.
    :rtype: str
    '''

    # The index is the series position, not the count of omitted colors.
    color = getattr(series, 'color', None)
    if color is None or (isinstance(color, str) and not color.strip()):
        return COLOR_CYCLE[index % len(COLOR_CYCLE)]

    # A hex is used as stored. It is not rewritten to a name.
    if isinstance(color, str) and color.startswith('#'):
        return color

    # A name is mapped here. The hex is not written back. grey is not a key.
    mapped = CSS_COLOR_HEX.get(color)
    if mapped is None:
        raise ValueError(
            f'Color {color!r} is not a six-digit hex or a CSS Level 1 name.'
        )

    # Return the mapped hex. The record keeps the name.
    return mapped

# ** function: _series_style
def _series_style(kind: str, series, index: int) -> dict:
    '''
    Read the style this series is drawn with.

    Defaults are applied here and are not written back. A size does not
    invent a marker. A present style the kind does not show fails.

    :param kind: The plot kind.
    :type kind: str
    :param series: The series.
    :type series: SeriesAggregate
    :param index: The series position in this plot, from zero.
    :type index: int
    :return: The drawing style. Not a field of the record.
    :rtype: dict
    '''

    # An inapplicable field fails before a picture starts.
    _refuse_inapplicable_style(kind, series)

    # Color is the cycle, the stored hex, or the mapped name.
    style = {
        'color': _drawn_color(series, index),
        'linestyle': None,
        'linewidth': None,
        'marker': None,
        'markersize': None,
        'bar_scale': None,
    }

    # A line's absent stroke is solid at 1.5, with no marker.
    if kind == 'line':
        style['linestyle'] = _supplied(
            getattr(series, 'linestyle', None),
            DEFAULT_LINESTYLE,
        )
        style['linewidth'] = _supplied(
            getattr(series, 'linewidth', None),
            DEFAULT_LINEWIDTH,
        )
        marker = getattr(series, 'marker', None)
        if marker is not None:
            style['marker'] = _tool_marker(marker)

    # A scatter's absent marker is circle. no_marker draws nothing.
    if kind == 'scatter':
        marker = getattr(series, 'marker', None)
        if marker is None:
            marker = DEFAULT_SCATTER_MARKER
        style['marker'] = _tool_marker(marker)

    # A size does not invent a marker. It applies only when one is drawn.
    if style['marker'] is not None:
        style['markersize'] = _supplied(
            getattr(series, 'markersize', None),
            DEFAULT_MARKERSIZE,
        )

    # Bar width is a scale of the slot. Absent is not stored as 1.
    if kind == 'bar':
        style['bar_scale'] = getattr(series, 'bar_width', None)

    # Return the reading. The series fields are unchanged.
    return style

# ** function: _prepare
def _prepare(plot: PlotAggregate) -> tuple:
    '''
    Read a record that can be drawn, or refuse it before a picture starts.

    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :return: Mark values and drawing styles, one pair per series.
    :rtype: tuple
    '''

    # A kind outside the three drawing paths is not a picture.
    kind = plot.kind
    if kind not in RENDER_KINDS:
        allowed = ', '.join(RENDER_KINDS)
        raise ValueError(f'Kind {kind!r} is not one of {allowed}.')

    # Nothing to draw is not an empty picture.
    if not plot.series:
        raise ValueError('A plot requires at least one series.')

    # An unknown legend place is not a picture. best is not a fallback.
    location = getattr(plot, 'legend_location', None)
    if (location is not None
            and location != 'outside_right'
            and location not in LEGEND_TOOL_LOC):
        raise ValueError(
            f'Legend location {location!r} is not a declared place.'
        )

    # Check marks and style before a figure exists. Do not rename a role.
    series_values = []
    styles = []
    for index, series in enumerate(plot.series):
        series_values.append(_drawable_marks(kind, series.marks))
        styles.append(_series_style(kind, series, index))

    # Return the readings. Nothing has been written back.
    return series_values, styles

# ** function: _text_order
def _text_order(series_values: list, role: str) -> list:
    '''
    Return text-axis names in first appearance, across series.

    The order is computed at draw time. It is not stored. Duplicate
    names share that tick. No category list is added to the record.

    :param series_values: Role-to-values mappings, one per series.
    :type series_values: list
    :param role: The text role.
    :type role: str
    :return: Names in first-appearance order.
    :rtype: list
    '''

    # Walk series in record order. The first time a name appears is its tick.
    order = []
    seen = set()
    for values in series_values:
        for value in values[role]:
            if value in seen:
                continue
            seen.add(value)
            order.append(value)

    # Return the order. Do not write it onto the record.
    return order

# ** function: _coordinates
def _coordinates(values: dict, role: str, order) -> list:
    '''
    Return positions for one role.

    A numeric role is drawn as stored. A text role is the index of each
    name in the first-appearance order. The text values are not replaced
    on the record.

    :param values: One series' mark values.
    :type values: dict
    :param role: The role to place.
    :type role: str
    :param order: The text order, or None when the role is numeric.
    :type order: list | None
    :return: Positions for the drawing tool.
    :rtype: list
    '''

    # Numeric values are already positions. Do not rename the role.
    if order is None:
        return list(values[role])

    # Text shares a tick by name. The index is not stored.
    index = {name: position for position, name in enumerate(order)}
    return [index[value] for value in values[role]]

# ** function: _set_margins
def _set_margins(figure,
        axes,
        top: float,
        right: float,
        bottom: float,
        left: float) -> None:
    '''
    Inset the axes so text can fall inside the requested figure.

    The inset is not a margin field. It does not change the requested
    inches. A figure smaller than the inset keeps a positive axes box.

    :param figure: The picture.
    :type figure: Figure
    :param axes: The axes to place.
    :type axes: Axes
    :param top: The top inset, in inches.
    :type top: float
    :param right: The right inset, in inches.
    :type right: float
    :param bottom: The bottom inset, in inches.
    :type bottom: float
    :param left: The left inset, in inches.
    :type left: float
    :return: None
    :rtype: None
    '''

    # Shrink the inset when the figure cannot hold it. Do not change the figure.
    width = figure.get_figwidth()
    height = figure.get_figheight()
    if left + right > width * 0.8:
        scale = (width * 0.8) / (left + right)
        left *= scale
        right *= scale
    if top + bottom > height * 0.8:
        scale = (height * 0.8) / (top + bottom)
        top *= scale
        bottom *= scale

    # Place the axes inside the figure. The figure size is unchanged.
    axes.set_position([
        left / width,
        bottom / height,
        1 - (left + right) / width,
        1 - (top + bottom) / height,
    ])

# ** function: _place_axes
def _place_axes(figure,
        axes,
        plot,
        has_subtitle: bool,
        x_label,
        y_label,
        x_rotation) -> None:
    '''
    Leave room for the title, the subtitle, the axis labels, and the ticks.

    The room is computed at draw time. It is not a field.

    :param figure: The picture.
    :type figure: Figure
    :param axes: The axes to place.
    :type axes: Axes
    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :param has_subtitle: Whether a subtitle is drawn.
    :type has_subtitle: bool
    :param x_label: The x axis label, if any.
    :type x_label: str | None
    :param y_label: The y axis label, if any.
    :type y_label: str | None
    :param x_rotation: The drawn x tick rotation, in degrees.
    :type x_rotation: Any
    :return: None
    :rtype: None
    '''

    # Sizes are readings. An absent size is not written back.
    title_size = _supplied(getattr(plot, 'title_size', None), DEFAULT_TITLE_SIZE)
    subtitle_size = _supplied(
        getattr(plot, 'subtitle_size', None),
        DEFAULT_SUBTITLE_SIZE,
    )
    axis_size = _supplied(
        getattr(plot, 'axis_label_size', None),
        DEFAULT_AXIS_LABEL_SIZE,
    )
    tick_size = _supplied(
        getattr(plot, 'tick_label_size', None),
        DEFAULT_TICK_LABEL_SIZE,
    )

    # The title sits above the axes. A subtitle needs room under that title.
    top = (title_size + 14) / 72
    if has_subtitle:
        top += (subtitle_size + 10) / 72

    # Rotated tick text needs more room than a horizontal tick.
    bottom = (tick_size + 12) / 72
    if x_label:
        bottom += (axis_size + 8) / 72
    if x_rotation:
        bottom += abs(x_rotation) / 360 * 1.1 + (tick_size * 2) / 72

    # The y label sits left of the tick text.
    left = (tick_size * 4 + 18) / 72
    if y_label:
        left += (axis_size + 10) / 72

    # The right inset grows later when the legend is outside the axes.
    _set_margins(figure, axes, top, 0.22, bottom, left)

# ** function: _draw_line
def _draw_line(axes,
        values: dict,
        style: dict,
        x_order,
        y_order) -> tuple:
    '''
    Draw one line series. An absent marker draws no marker.

    Linestyle words are passed as stored. They are not rewritten to the
    tool's short codes.

    :param axes: The axes to draw on.
    :type axes: Axes
    :param values: The series' mark values.
    :type values: dict
    :param style: The drawing style.
    :type style: dict
    :param x_order: The text order of x, or None when x is numeric.
    :type x_order: list | None
    :param y_order: The text order of y, or None when y is numeric.
    :type y_order: list | None
    :return: The positions the points were drawn at.
    :rtype: tuple
    '''

    # Positions are computed here. Text values stay on the record.
    xs = _coordinates(values, 'x', x_order)
    ys = _coordinates(values, 'y', y_order)

    # No marker key when the line has no marker. A size does not invent one.
    if style['marker'] is None:
        axes.plot(
            xs,
            ys,
            color=style['color'],
            linestyle=style['linestyle'],
            linewidth=style['linewidth'],
        )
        return xs, ys

    # A present marker uses the tool code. The record keeps its token.
    axes.plot(
        xs,
        ys,
        color=style['color'],
        linestyle=style['linestyle'],
        linewidth=style['linewidth'],
        marker=style['marker'],
        markersize=style['markersize'],
    )
    return xs, ys

# ** function: _draw_scatter
def _draw_scatter(axes,
        values: dict,
        style: dict,
        x_order,
        y_order) -> tuple:
    '''
    Draw one scatter series.

    An absent marker is circle. ``no_marker`` draws no marker and is not
    rewritten. The scatter size is the square of the point size, which is
    how this tool names a marker of that many points across.

    :param axes: The axes to draw on.
    :type axes: Axes
    :param values: The series' mark values.
    :type values: dict
    :param style: The drawing style.
    :type style: dict
    :param x_order: The text order of x, or None when x is numeric.
    :type x_order: list | None
    :param y_order: The text order of y, or None when y is numeric.
    :type y_order: list | None
    :return: The positions the points were drawn at.
    :rtype: tuple
    '''

    # Positions are computed here. Text values stay on the record.
    xs = _coordinates(values, 'x', x_order)
    ys = _coordinates(values, 'y', y_order)

    # no_marker draws no marker. The points still place the axis.
    if style['marker'] is None:
        axes.scatter(xs, ys, c=style['color'], marker='none')
        return xs, ys

    # The tool's size is an area. The record's size is points across.
    axes.scatter(
        xs,
        ys,
        c=style['color'],
        marker=style['marker'],
        s=style['markersize'] ** 2,
    )
    return xs, ys

# ** function: _draw_bars
def _draw_bars(axes, series_values: list, styles: list) -> list:
    '''
    Draw grouped bars. Category order is first appearance.

    For n series the slot width is 0.8 / n. The group is centered on the
    category tick. A present bar width scales the drawn width and does
    not change the shift. A series that lacks a category draws no bar
    there. The picture does not invent a zero.

    :param axes: The axes to draw on.
    :type axes: Axes
    :param series_values: Role-to-values mappings, one per series.
    :type series_values: list
    :param styles: Drawing styles, one per series.
    :type styles: list
    :return: Category names in first-appearance order.
    :rtype: list
    '''

    # The order is not stored. Duplicate names share a tick.
    order = _text_order(series_values, 'category')
    index = {name: position for position, name in enumerate(order)}
    count = len(series_values)
    slot = BAR_GROUP_SPAN / count

    # Each series keeps its slot. A missing category is a missing bar.
    for position, (values, style) in enumerate(zip(series_values, styles)):
        shift = (position - (count - 1) / 2) * slot
        scale = 1 if style['bar_scale'] is None else style['bar_scale']
        xs = []
        heights = []
        for category, height in zip(values['category'], values['height']):
            xs.append(index[category] + shift)
            heights.append(height)
        axes.bar(
            xs,
            heights,
            width=slot * scale,
            color=style['color'],
            align='center',
        )

    # Return the tick names. category and height are not renamed.
    return order

# ** function: _draw_point_labels
def _draw_point_labels(axes,
        kind: str,
        values: dict,
        xs: list,
        ys: list,
        family: str) -> None:
    '''
    Draw point labels beside line and scatter points.

    The size is 8 points. The label is horizontal, offset 4 points right
    and 4 points up. Those two are not fields. An empty string draws no
    label. Tick rotation does not rotate it. A bar does not gain this.

    :param axes: The axes to draw on.
    :type axes: Axes
    :param kind: The plot kind.
    :type kind: str
    :param values: The series' mark values.
    :type values: dict
    :param xs: The drawn x positions.
    :type xs: list
    :param ys: The drawn y positions.
    :type ys: list
    :param family: The picture's font family.
    :type family: str
    :return: None
    :rtype: None
    '''

    # Bar has no point label. A series without the role draws none.
    if kind == 'bar' or 'label' not in values:
        return

    # An empty string is an unlabeled point. It is not the series name.
    for x, y, text in zip(xs, ys, values['label']):
        if text == '':
            continue
        axes.annotate(
            text,
            xy=(x, y),
            xytext=POINT_LABEL_OFFSET,
            textcoords='offset points',
            fontsize=POINT_LABEL_SIZE,
            fontfamily=family,
            rotation=0,
            ha='left',
            va='bottom',
            annotation_clip=False,
        )

# ** function: _draw_figure_text
def _draw_figure_text(figure, axes, plot) -> bool:
    '''
    Draw the axes title and, when present, the subtitle under it.

    The subtitle is description. There is no subtitle field. A missing
    or blank description draws no subtitle.

    :param figure: The picture.
    :type figure: Figure
    :param axes: The axes to title.
    :type axes: Axes
    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :return: True when a subtitle was drawn.
    :rtype: bool
    '''

    # One family and the declared sizes. Absent sizes are not stored.
    family = _font_family(plot)
    title_size = _supplied(getattr(plot, 'title_size', None), DEFAULT_TITLE_SIZE)
    subtitle = _present(getattr(plot, 'description', None))
    subtitle_size = _supplied(
        getattr(plot, 'subtitle_size', None),
        DEFAULT_SUBTITLE_SIZE,
    )
    pad = 6
    if subtitle is not None:
        pad = subtitle_size + 14

    # The title is the axes title. The id is not drawn.
    axes.set_title(
        _figure_title(plot),
        fontsize=title_size,
        fontfamily=family,
        pad=pad,
    )
    if subtitle is None:
        return False

    # The subtitle sits just above the axes, under the title.
    transform = axes.transAxes + ScaledTranslation(
        0,
        2 / 72,
        figure.dpi_scale_trans,
    )
    axes.text(
        0.5,
        1.0,
        subtitle,
        transform=transform,
        ha='center',
        va='bottom',
        fontsize=subtitle_size,
        fontfamily=family,
        clip_on=False,
    )
    return True

# ** function: _draw_axis_labels
def _draw_axis_labels(axes, plot) -> tuple:
    '''
    Draw the composed axis labels. Tick rotation does not rotate them.

    For a bar, x labels the category axis and y labels the height axis.
    Those roles are not renamed.

    :param axes: The axes to label.
    :type axes: Axes
    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :return: The x label and the y label, either of which may be absent.
    :rtype: tuple
    '''

    # Compose at draw time. The record keeps title and unit apart.
    family = _font_family(plot)
    size = _supplied(
        getattr(plot, 'axis_label_size', None),
        DEFAULT_AXIS_LABEL_SIZE,
    )
    x_label = _composed_label(
        getattr(plot, 'x_title', None),
        getattr(plot, 'x_unit', None),
    )
    y_label = _composed_label(
        getattr(plot, 'y_title', None),
        getattr(plot, 'y_unit', None),
    )
    if x_label is not None:
        axes.set_xlabel(x_label, fontsize=size, fontfamily=family)
    if y_label is not None:
        axes.set_ylabel(y_label, fontsize=size, fontfamily=family)

    # Return the readings so the inset can leave room for them.
    return x_label, y_label

# ** function: _x_rotation
def _x_rotation(plot, x_is_text: bool):
    '''
    Return the x tick rotation this picture uses.

    Absent is 45 degrees when the x tick text is text, including bar
    category, and 0 degrees when it is numeric. A stored 0 stays 0.
    The value is not rewritten modulo 360, and it is not written back.

    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :param x_is_text: Whether the x tick text is text.
    :type x_is_text: bool
    :return: The rotation in degrees.
    :rtype: Any
    '''

    # A stored value is passed as stored, including zero.
    stored = getattr(plot, 'x_tick_rotation', None)
    if stored is not None:
        return stored

    # Text ticks, including bar category, default to 45. Numeric ticks do not.
    if x_is_text:
        return TEXT_TICK_ROTATION

    # A numeric axis is horizontal when the rotation was omitted.
    return 0

# ** function: _y_rotation
def _y_rotation(plot):
    '''
    Return the y tick rotation this picture uses.

    Absent is 0 degrees. A present value is passed as stored. It is not
    written back and not rewritten modulo 360.

    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :return: The rotation in degrees.
    :rtype: Any
    '''

    # A stored value is passed as stored, including a non-zero rotation.
    stored = getattr(plot, 'y_tick_rotation', None)
    if stored is not None:
        return stored

    # Absent y rotation is horizontal. It is not stored as 0.
    return 0

# ** function: _apply_ticks
def _apply_ticks(axes,
        plot,
        x_order,
        y_order):
    '''
    Set tick text, size, rotation, and a numeric format when one was stored.

    Absent decimal fields do not set a format. A stored count is a
    fixed-point pattern derived here. It is not a format-string field.
    Category text is not formatted by ``x_tick_decimals``.

    :param axes: The axes whose ticks are set.
    :type axes: Axes
    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :param x_order: The x tick names, or None when x is numeric.
    :type x_order: list | None
    :param y_order: The y tick names, or None when y is numeric.
    :type y_order: list | None
    :return: The drawn x rotation.
    :rtype: Any
    '''

    # Text ticks are the values. They are not renamed to category.
    if x_order is not None:
        axes.xaxis.set_major_locator(FixedLocator(list(range(len(x_order)))))
        axes.set_xticklabels(list(x_order))
    elif getattr(plot, 'x_tick_decimals', None) is not None:
        places = plot.x_tick_decimals
        axes.xaxis.set_major_formatter(FormatStrFormatter(f'%.{places}f'))

    # The same rule on y. A text y axis ignores y_tick_decimals.
    if y_order is not None:
        axes.yaxis.set_major_locator(FixedLocator(list(range(len(y_order)))))
        axes.set_yticklabels(list(y_order))
    elif getattr(plot, 'y_tick_decimals', None) is not None:
        places = plot.y_tick_decimals
        axes.yaxis.set_major_formatter(FormatStrFormatter(f'%.{places}f'))

    # One size for every tick. Rotation does not rotate the axis label.
    tick_size = _supplied(
        getattr(plot, 'tick_label_size', None),
        DEFAULT_TICK_LABEL_SIZE,
    )
    x_rotation = _x_rotation(plot, x_order is not None)
    y_rotation = _y_rotation(plot)
    axes.tick_params(
        axis='x',
        labelsize=tick_size,
        labelrotation=x_rotation,
    )
    axes.tick_params(
        axis='y',
        labelsize=tick_size,
        labelrotation=y_rotation,
    )

    # Return the rotation so a non-zero x rotation can be right-aligned.
    return x_rotation

# ** function: _style_tick_labels
def _style_tick_labels(figure,
        axes,
        family: str,
        x_rotation) -> None:
    '''
    Cover tick labels with the picture's font family.

    When the drawn x rotation is not 0, the x tick labels are
    right-aligned. That alignment is not a field. The family is not
    written back.

    :param figure: The picture.
    :type figure: Figure
    :param axes: The axes whose tick labels are styled.
    :type axes: Axes
    :param family: The picture's font family.
    :type family: str
    :param x_rotation: The drawn x tick rotation.
    :type x_rotation: Any
    :return: None
    :rtype: None
    '''

    # Realize the tick labels, then set the family on those artists.
    figure.canvas.draw()
    for label in axes.get_xticklabels():
        label.set_fontfamily(family)
        if x_rotation != 0:
            label.set_ha('right')
    for label in axes.get_yticklabels():
        label.set_fontfamily(family)

# ** function: _legend_handle
def _legend_handle(kind: str, style: dict):
    '''
    Build the legend handle from the series as drawn.

    The handle is not a separate field. Hatch, edge color, and alpha
    are not passed.

    :param kind: The plot kind.
    :type kind: str
    :param style: The drawing style.
    :type style: dict
    :return: The handle.
    :rtype: Artist
    '''

    # A bar swatch is the bar's color. It has no marker shape.
    if kind == 'bar':
        return Patch(facecolor=style['color'])

    # A scatter swatch is the marker. A line swatch is the stroke and marker.
    marker = 'None' if style['marker'] is None else style['marker']
    if kind == 'scatter':
        return Line2D(
            [0],
            [0],
            color=style['color'],
            linestyle='None',
            marker=marker,
            markersize=_supplied(style['markersize'], DEFAULT_MARKERSIZE),
        )

    # The line handle uses the same stroke the series was drawn with.
    return Line2D(
        [0],
        [0],
        color=style['color'],
        linestyle=style['linestyle'],
        linewidth=style['linewidth'],
        marker=marker,
        markersize=_supplied(style['markersize'], DEFAULT_MARKERSIZE),
    )

# ** function: _style_legend_title
def _style_legend_title(legend,
        title,
        size,
        family: str) -> None:
    '''
    Draw a present legend title at the legend size, in the picture's family.

    An absent title is not filled from the plot name.

    :param legend: The legend artist.
    :type legend: Legend
    :param title: The legend title, or None.
    :type title: str | None
    :param size: The legend size, in points.
    :type size: Any
    :param family: The picture's font family.
    :type family: str
    :return: None
    :rtype: None
    '''

    # No title means the artist is left empty. Do not borrow the plot name.
    if title is None:
        return

    # The title uses the same size as the entries. It is not a second field.
    legend.get_title().set_fontsize(size)
    legend.get_title().set_fontfamily(family)

# ** function: _place_outside_right
def _place_outside_right(figure, axes, legend) -> None:
    '''
    Place the legend outside the axes and inside the figure.

    The legend's top aligns with the axes' top. Its left edge sits 4
    points to the right of the axes. The axes are inset on the right by
    the legend's width plus those 4 points. The figure's inches do not
    change. The inset is not stored.

    :param figure: The picture.
    :type figure: Figure
    :param axes: The axes the legend sits beside.
    :type axes: Axes
    :param legend: The legend artist.
    :type legend: Legend
    :return: None
    :rtype: None
    '''

    # Measure the legend, then give it that width plus the 4-point gap.
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    legend_width = legend.get_window_extent(renderer).width / figure.dpi
    gap = OUTSIDE_LEGEND_GAP / 72
    pos = axes.get_position()
    shrink = (legend_width + gap) / figure.get_figwidth()
    new_width = pos.width - shrink
    if new_width < 0.05:
        new_width = 0.05
    axes.set_position([pos.x0, pos.y0, new_width, pos.height])

    # Anchor the legend, then correct it so the drawn box matches the rule.
    pos = axes.get_position()
    anchor_x = pos.x1 + gap / figure.get_figwidth()
    anchor_y = pos.y1
    legend.set_loc('upper left')
    legend.set_bbox_to_anchor(
        (anchor_x, anchor_y),
        transform=figure.transFigure,
    )
    legend.set_clip_on(False)
    for _ in range(3):
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        legend_box = legend.get_window_extent(renderer)
        axes_box = axes.get_window_extent(renderer)
        dx = (legend_box.x0 - axes_box.x1) / figure.dpi - gap
        dy = (legend_box.y1 - axes_box.y1) / figure.dpi
        anchor_x -= dx / figure.get_figwidth()
        anchor_y -= dy / figure.get_figheight()
        legend.set_bbox_to_anchor(
            (anchor_x, anchor_y),
            transform=figure.transFigure,
        )

# ** function: _add_legend
def _add_legend(axes,
        handles,
        labels,
        loc: str,
        prop: dict,
        title):
    '''
    Add the legend. An absent title is not passed, so none is drawn.

    :param axes: The axes the legend belongs to.
    :type axes: Axes
    :param handles: One handle per series, in record order.
    :type handles: list
    :param labels: One entry per series, in record order.
    :type labels: list
    :param loc: The tool location.
    :type loc: str
    :param prop: The font family and size.
    :type prop: dict
    :param title: The legend title, or None.
    :type title: str | None
    :return: The legend artist.
    :rtype: Legend
    '''

    # Omit the title argument. An empty title is not filled from the name.
    if title is None:
        return axes.legend(
            handles,
            labels,
            loc=loc,
            prop=prop,
            ncol=1,
        )

    # A present title is drawn. It is not a column-count field.
    return axes.legend(
        handles,
        labels,
        loc=loc,
        prop=prop,
        ncol=1,
        title=title,
    )

# ** function: _draw_legend
def _draw_legend(figure,
        axes,
        plot,
        kind: str,
        styles: list) -> None:
    '''
    Draw one legend entry per series, in record order, or draw none.

    Absent ``show_legend`` draws the legend, including for one series.
    False hides it and does not clear a stored location or title. Absent
    location is upper right, inside the axes. The legend is one column.
    There is no column-count field.

    :param figure: The picture.
    :type figure: Figure
    :param axes: The axes the legend belongs to.
    :type axes: Axes
    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :param kind: The plot kind.
    :type kind: str
    :param styles: Drawing styles, one per series.
    :type styles: list
    :return: None
    :rtype: None
    '''

    # False hides the legend. Absent is not stored as true, and still draws.
    if getattr(plot, 'show_legend', None) is False:
        return

    # One entry per series. The same text is still two entries. Not a union.
    handles = [_legend_handle(kind, style) for style in styles]
    labels = [_legend_entry(series) for series in plot.series]
    size = _supplied(getattr(plot, 'legend_size', None), DEFAULT_LEGEND_SIZE)
    family = _font_family(plot)
    title = _present(getattr(plot, 'legend_title', None))
    location = getattr(plot, 'legend_location', None) or 'upper_right'
    prop = {
        'family': family,
        'size': size,
    }

    # outside_right is outside the axes. The other tokens stay inside.
    if location == 'outside_right':
        legend = _add_legend(axes, handles, labels, 'upper left', prop, title)
        _style_legend_title(legend, title, size, family)
        _place_outside_right(figure, axes, legend)
        return

    # An inside place stays inside the axes. best is not a fallback.
    legend = _add_legend(
        axes,
        handles,
        labels,
        LEGEND_TOOL_LOC[location],
        prop,
        title,
    )
    _style_legend_title(legend, title, size, family)
    legend.set_clip_on(False)

# ** function: _draw
def _draw(figure,
        plot: PlotAggregate,
        series_values: list,
        styles: list) -> None:
    '''
    Draw one declared plot on a figure of the caller's size.

    The figure's inches are already set. This does not write the picture
    back onto the record, and it does not fill an omitted field.

    :param figure: The picture, already sized.
    :type figure: Figure
    :param plot: The declared plot record.
    :type plot: PlotAggregate
    :param series_values: Role-to-values mappings, one per series.
    :type series_values: list
    :param styles: Drawing styles, one per series.
    :type styles: list
    :return: None
    :rtype: None
    '''

    # Text positions are first appearance. They are not stored.
    axes = figure.add_subplot(111)
    kind = plot.kind
    family = _font_family(plot)
    x_order = None
    y_order = None
    if kind == 'bar':
        x_order = _text_order(series_values, 'category')
    else:
        if not _is_numeric(series_values[0]['x'][0]):
            x_order = _text_order(series_values, 'x')
        if not _is_numeric(series_values[0]['y'][0]):
            y_order = _text_order(series_values, 'y')

    # Marks first, so the axes know their data before the text is placed.
    points = []
    if kind == 'line':
        for values, style in zip(series_values, styles):
            points.append(_draw_line(axes, values, style, x_order, y_order))
    elif kind == 'scatter':
        for values, style in zip(series_values, styles):
            points.append(_draw_scatter(axes, values, style, x_order, y_order))
    else:
        _draw_bars(axes, series_values, styles)

    # Figure text and axis labels are readings. They are not stored composed.
    has_subtitle = _draw_figure_text(figure, axes, plot)
    x_label, y_label = _draw_axis_labels(axes, plot)
    x_rotation = _apply_ticks(axes, plot, x_order, y_order)
    _place_axes(figure, axes, plot, has_subtitle, x_label, y_label, x_rotation)

    # Point labels use the drawing policy. Tick rotation does not move them.
    if kind != 'bar':
        for values, (xs, ys) in zip(series_values, points):
            _draw_point_labels(axes, kind, values, xs, ys, family)

    # The legend reads the record. A hidden legend is not drawn.
    _draw_legend(figure, axes, plot, kind, styles)
    _style_tick_labels(figure, axes, family, x_rotation)

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
    and columns place the cells. They do not choose the size. This is
    not a subplot matrix.

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

    The picture is a reading of the record. It is not written back, and
    an omitted appearance field is not filled with the default that was
    drawn. A later drawing library is another class on the renderer service.
    '''

    # * method: render
    def render(self,
            plot: PlotAggregate,
            width: float,
            height: float) -> bytes:
        '''
        Render a plot record to PNG bytes of the given size.

        An unsaved record is a valid input. An illegal size, an illegal
        kind, illegal marks, or a style the kind does not show raises,
        and no picture is returned. Width and height are inches. They
        are not fields of the plot. There is no dpi argument, no path,
        and no palette. The caller places the file.

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
        series_values, styles = _prepare(plot)

        # Draw at the requested size. Nothing is written to a path or the record.
        figure = Figure(figsize=(width, height))
        FigureCanvasAgg(figure)
        _draw(figure, plot, series_values, styles)

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
        This does not draw a subplot matrix, a grid title, or a grid legend.

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
