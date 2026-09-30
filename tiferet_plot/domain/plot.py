"""Plot domain models."""

# *** imports

# ** core
from __future__ import annotations
import re
from typing import Any, Sequence

# ** infra
from pydantic import Field, field_validator, model_validator

# ** app
from tiferet import DomainObject
from tiferet.domain import ModelError

# *** constants

# ** constant: plot_kinds
PLOT_KINDS = (
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

# *** constants (error)

# ** constant: addition_role_not_in_series_id
ADDITION_ROLE_NOT_IN_SERIES_ID = 'ADDITION_ROLE_NOT_IN_SERIES'

# ** constant: addition_role_not_in_series_message
ADDITION_ROLE_NOT_IN_SERIES_MESSAGE = (
    'The addition carries mark role {role}, which this series does not carry.'
)

# ** constant: addition_role_missing_id
ADDITION_ROLE_MISSING_ID = 'ADDITION_ROLE_MISSING'

# ** constant: addition_role_missing_message
ADDITION_ROLE_MISSING_MESSAGE = (
    'The addition omits mark role {role}, which this series carries.'
)

# ** constant: addition_sort_mismatch_id
ADDITION_SORT_MISMATCH_ID = 'ADDITION_SORT_MISMATCH'

# ** constant: addition_sort_mismatch_message
ADDITION_SORT_MISMATCH_MESSAGE = (
    'The addition plays mark role {role} as {addition_sort} values, '
    'and this series plays it as {series_sort} values.'
)

# ** constant: css_color_names
CSS_COLOR_NAMES = (
    'aqua',
    'black',
    'blue',
    'fuchsia',
    'gray',
    'green',
    'lime',
    'maroon',
    'navy',
    'olive',
    'purple',
    'red',
    'silver',
    'teal',
    'white',
    'yellow',
)

# ** constant: hex_color
HEX_COLOR = re.compile(r'^#[0-9A-Fa-f]{6}$')

# ** constant: linestyles
LINESTYLES = (
    'solid',
    'dashed',
    'dotted',
    'dashdot',
)

# ** constant: markers
MARKERS = (
    'no_marker',
    'circle',
    'square',
    'triangle',
    'diamond',
    'x',
    'plus',
    'point',
)

# ** constant: legend_locations
LEGEND_LOCATIONS = (
    'upper_right',
    'upper_left',
    'lower_left',
    'lower_right',
    'outside_right',
)

# ** constant: font_families
FONT_FAMILIES = (
    'serif',
    'sans-serif',
    'monospace',
)

# ** constant: absent_color_cycle
ABSENT_COLOR_CYCLE = (
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

# *** functions

# ** function: _is_blank
def _is_blank(value: Any) -> bool:
    '''
    Return whether an id was omitted.

    A missing id and a blank id are the same case. A supplied id, including
    one that does not match the name, is not blank.

    :param value: The raw id value.
    :type value: Any
    :return: True when the id is missing or blank.
    :rtype: bool
    '''

    # None means the caller did not supply an id.
    if value is None:
        return True

    # A whitespace-only string is blank, not a supplied id.
    if isinstance(value, str) and not value.strip():
        return True

    # Any other value was supplied and must be kept.
    return False

# ** function: _absent_text
def _absent_text(value: Any) -> Any:
    '''
    Store omitted and blank figure text as absent.

    An empty string and a whitespace-only string are the same case as
    an omitted field. A supplied string is kept as given. This does
    not fill the text from the name.

    :param value: The raw text.
    :type value: Any
    :return: None when the text was omitted or blank, otherwise the value.
    :rtype: Any
    '''

    # Blank text is no text. Do not store an empty string.
    if _is_blank(value):
        return None

    # A supplied string is kept. It is not rewritten from the name.
    return value

# ** function: _title_text
def _title_text(title: Any, name: str) -> str:
    '''
    Return the title text a later drawer reads.

    The reading is ``title`` when that field is present and not blank,
    otherwise the catalog name. It is not stored back into ``title``.

    :param title: The display title, if any.
    :type title: Any
    :param name: The catalog name.
    :type name: str
    :return: The title text a later drawer reads.
    :rtype: str
    '''

    # Absent title is not filled from the name in the record.
    if _is_blank(title):
        return name

    # A present title is the text. The name is not the display title.
    return title

# ** function: _subtitle_text
def _subtitle_text(description: Any) -> str | None:
    '''
    Return the subtitle text a later drawer reads.

    The subtitle is ``description`` when that field is present and not
    blank. There is no subtitle field. This does not rewrite description.

    :param description: The claim text, if any.
    :type description: Any
    :return: The subtitle text, or None when there is none to read.
    :rtype: str | None
    '''

    # A blank description is no subtitle for the later drawer.
    if _is_blank(description):
        return None

    # The stored sentence is the subtitle. It is not copied to another field.
    return description

# ** function: _snake_case
def _snake_case(name: str) -> str:
    '''
    Derive an id from an author's name.

    Trim, lowercase, turn each run of characters that are not letters or
    digits into one underscore, and strip underscores from the ends.

    :param name: The author's name.
    :type name: str
    :return: The snake_case id, or an empty string when the name cannot identify a record.
    :rtype: str
    '''

    # Collect letter and digit runs. Anything else is a separator.
    pieces = []
    current = []
    for char in name.strip().lower():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            pieces.append(''.join(current))
            current = []

    # Flush the trailing run, then join. Ends never keep a separator.
    if current:
        pieces.append(''.join(current))

    # Return the derived id. An empty result cannot identify the record.
    return '_'.join(pieces)

# ** function: _fill_id
def _fill_id(data: Any) -> Any:
    '''
    Set id from the name when the caller did not supply one.

    Derivation happens once, here, at declaration. A supplied id is stored
    as given and is not rewritten from the name.

    :param data: The raw model input.
    :type data: Any
    :return: The input, with id filled when it was omitted.
    :rtype: Any
    '''

    # Leave non-mapping input for Pydantic to reject.
    if not isinstance(data, dict):
        return data

    # Copy before filling a missing id. Do not rewrite a supplied id.
    data = dict(data)
    if not _is_blank(data.get('id')):
        return data

    # A blank id is not a supplied id.
    data.pop('id', None)

    # Without a name, the required-field check names the omission.
    name = data.get('name')
    if not isinstance(name, str):
        return data

    # Derive the id. An empty derivation cannot identify the record.
    derived = _snake_case(name)
    if not derived:
        raise ValueError(
            'The name cannot identify the record and no id was supplied.'
        )
    data['id'] = derived

    # Return the declaration with its id filled once.
    return data

# ** function: _is_numeric
def _is_numeric(value: Any) -> bool:
    '''
    Return whether a mark value is numeric.

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

# ** function: _role_sort
def _role_sort(role: str, values: Sequence[Any]) -> str:
    '''
    Return the sort of one role, or fail when the values are not that sort.

    Height is numeric. Category and label are text. An empty label is an
    unlabeled point. x and y are each one sort for the whole role: all
    numeric, or all non-blank text. Text that looks like a number is not
    coerced.

    :param role: The mark role.
    :type role: str
    :param values: The values that play the role.
    :type values: Sequence[Any]
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
            if any(_is_blank(value) for value in values):
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

# ** function: _validate_marks
def _validate_marks(kind: str, marks: Sequence[Mark]) -> dict:
    '''
    Require the mark roles a kind selects, and no others.

    Line and scatter may also carry label. On those kinds, x and y are
    each one sort, and at least one of them is numeric.

    :param kind: The plot kind.
    :type kind: str
    :param marks: The series marks.
    :type marks: Sequence[Mark]
    :return: The sort of x and of y, when this kind has those roles.
    :rtype: dict
    '''

    # Index marks by role and reject a repeated role.
    by_role = {}
    for mark in marks:
        if mark.role in by_role:
            raise ValueError(f'Duplicate mark role {mark.role!r}.')
        by_role[mark.role] = mark

    # The kind selects the legal roles. Label is optional. Extra roles fail.
    required = MARK_ROLES_BY_KIND[kind]
    allowed = required + OPTIONAL_MARK_ROLES_BY_KIND[kind]
    extra = [role for role in by_role if role not in allowed]
    if extra:
        raise ValueError(
            f'Kind {kind!r} does not allow mark role {extra[0]!r}.'
        )

    # Every required role must be present. Label may be absent.
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
        values = by_role[role].values
        if len(values) < 1:
            raise ValueError(
                f'Mark role {role!r} requires at least one value.'
            )
        sorts[role] = _role_sort(role, values)
        lengths.append(len(values))

    # Equal length is part of being well-formed for the kind.
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

    # Return the axis sorts so series on one plot can be compared.
    return {
        role: sorts[role]
        for role in AXIS_MARK_ROLES
        if role in sorts
    }

# ** function: _require_plot_id
def _require_plot_id(plot: Any) -> None:
    '''
    Fail when a cell plot has no id.

    Matrix declaration does not derive a plot id from the plot name.
    A missing id and a blank id are the same failure.

    :param plot: The raw cell plot.
    :type plot: Any
    :return: None
    :rtype: None
    '''

    # A mapping is the declaration form. Do not fill a missing id.
    if isinstance(plot, dict):
        if _is_blank(plot.get('id')):
            raise ValueError(
                'A cell plot requires an id. Declaration does not derive one.'
            )
        return

    # A record that already exists must already carry an id.
    if plot is not None and not isinstance(plot, str) and hasattr(plot, 'id'):
        if _is_blank(plot.id):
            raise ValueError(
                'A cell plot requires an id. Declaration does not derive one.'
            )
        return

    # A bare id is not a plot record. Leave other shapes for field validation.
    if isinstance(plot, str):
        raise ValueError('A cell carries a plot record, not an id.')

# ** function: _validate_cell_positions
def _validate_cell_positions(
        rows: int,
        cols: int,
        cells: Sequence[MatrixCell],
    ) -> None:
    '''
    Require every cell to sit in the declared grid, and not on another cell.

    An empty corner is the absence of a cell. The author declared the grid.
    Rows and columns are not computed from the occupied cells.

    :param rows: The declared row count.
    :type rows: int
    :param cols: The declared column count.
    :type cols: int
    :param cells: The occupied cells.
    :type cells: Sequence[MatrixCell]
    :return: None
    :rtype: None
    '''

    # Two placements may share a plot id. They may not share a position.
    seen = set()
    for cell in cells:
        if cell.row >= rows or cell.col >= cols:
            raise ValueError(
                f'Cell at row {cell.row}, column {cell.col} is outside '
                f'a {rows} by {cols} grid.'
            )
        position = (cell.row, cell.col)
        if position in seen:
            raise ValueError(
                f'Two cells share row {cell.row} and column {cell.col}.'
            )
        seen.add(position)

# ** function: _validate_series
def _validate_series(kind: str, series: Sequence[Series]) -> None:
    '''
    Reject duplicate series ids and marks that do not match the kind.

    Series on a line or a scatter agree on the sort of x and on the sort
    of y. They need not agree on whether label is present.

    :param kind: The plot kind.
    :type kind: str
    :param series: The declared series.
    :type series: Sequence[Series]
    :return: None
    :rtype: None
    '''

    # Two series in one plot may not resolve to the same id.
    seen = set()
    axis_sorts = {}
    for item in series:
        if item.id in seen:
            raise ValueError(
                f'Two series resolved to the same id {item.id!r}.'
            )
        seen.add(item.id)

        # The kind rectifies this series' marks. It does not add plot fields.
        sorts = _validate_marks(kind, item.marks)

        # Every series agrees on the sort of each axis. Label may differ.
        for role, sort in sorts.items():
            agreed = axis_sorts.get(role)
            if agreed is None:
                axis_sorts[role] = sort
                continue
            if agreed != sort:
                raise ValueError(
                    f'Series disagree on the sort of mark role {role!r}.'
                )

        # A present style the kind does not show fails. An absent one does not.
        _validate_series_style(kind, item)

# ** function: _optional_bool
def _optional_bool(value: Any) -> Any:
    '''
    Keep a supplied bool. Do not coerce text or a number.

    Omitted is absent. ``false`` as text is not the bool ``False``.

    :param value: The raw bool.
    :type value: Any
    :return: The bool, or None when it was omitted.
    :rtype: Any
    '''

    # Omitted stays absent. It is not stored as true or false.
    if value is None:
        return None

    # A string is not coerced. A bool is not a width of 1.
    if not isinstance(value, bool):
        raise ValueError('A bool is required.')

    # Return the supplied bool. False is a value, not a blank.
    return value

# ** function: _optional_number
def _optional_number(value: Any,
        *,
        positive: bool = False,
        nonnegative: bool = False) -> Any:
    '''
    Keep a supplied number. Reject a bool and text.

    Text that looks like a number is not a number. A bool is not a
    width of 1. The supplied int or float is not rewritten.

    :param value: The raw number.
    :type value: Any
    :param positive: When true, zero and negatives fail.
    :type positive: bool
    :param nonnegative: When true, negatives fail and zero is kept.
    :type nonnegative: bool
    :return: The supplied number, or None when it was omitted.
    :rtype: Any
    '''

    # Omitted stays absent. A default is not written back.
    if value is None:
        return None

    # Reject bool before int, because bool is a subclass of int.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('A number is required.')

    # A size is positive. Zero is not a width.
    if positive and not value > 0:
        raise ValueError('The number must be positive.')

    # Spacing may be zero. A negative gap is not a fraction of the cell.
    if nonnegative and value < 0:
        raise ValueError('The number must not be negative.')

    # Return the supplied number. Do not coerce an int to a float.
    return value

# ** function: _optional_decimals
def _optional_decimals(value: Any) -> Any:
    '''
    Keep a supplied non-negative integer decimal count.

    A float, a bool, a negative number, and text fail. Zero is a
    supplied value, not an omitted one.

    :param value: The raw decimal count.
    :type value: Any
    :return: The integer, or None when it was omitted.
    :rtype: Any
    '''

    # Omitted means the drawer does not set a numeric format.
    if value is None:
        return None

    # A float is not an integer. A bool is not a count of 1.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError('A non-negative integer is required.')

    # Zero shows no digits after the decimal. A negative count fails.
    if value < 0:
        raise ValueError('A decimal count must not be negative.')

    # Return the supplied count. Do not treat zero as absent.
    return value

# ** function: _optional_token
def _optional_token(value: Any, allowed: Sequence[str]) -> Any:
    '''
    Keep a token from a closed set. Do not coerce a near spelling.

    :param value: The raw token.
    :type value: Any
    :param allowed: The closed set.
    :type allowed: Sequence[str]
    :return: The token, or None when it was omitted.
    :rtype: Any
    '''

    # Omitted stays absent. The drawer default is not written back.
    if value is None:
        return None

    # The tool's own spelling is not this token.
    if not isinstance(value, str) or value not in allowed:
        choices = ', '.join(allowed)
        raise ValueError(f'{value!r} is not one of {choices}.')

    # Return the supplied token. Do not rewrite it.
    return value

# ** function: _normalize_color
def _normalize_color(value: Any) -> Any:
    '''
    Store a series color as lowercase hex or a CSS Level 1 name.

    ``grey`` is stored as ``gray``. A name is not rewritten to hex,
    and a hex is not rewritten to a name. An unknown name fails here,
    without a drawing tool.

    :param value: The raw color.
    :type value: Any
    :return: The stored color, or None when it was omitted or blank.
    :rtype: Any
    '''

    # Omitted and blank are absent. A cycle hex is not written back.
    if _is_blank(value):
        return None

    # A color is text. A number is not a color.
    if not isinstance(value, str):
        raise ValueError('A color must be text.')

    # A hex is six digits. Short and eight-digit forms fail.
    if value.startswith('#'):
        if HEX_COLOR.fullmatch(value) is None:
            raise ValueError(
                f'Color {value!r} is not # plus six hex digits '
                'or a CSS Level 1 name.'
            )
        return value.lower()

    # Lowercase before the grey alias, so GREY is stored as gray.
    name = value.lower()
    if name == 'grey':
        name = 'gray'
    if name not in CSS_COLOR_NAMES:
        raise ValueError(
            f'Color {value!r} is not # plus six hex digits '
            'or a CSS Level 1 name.'
        )

    # A name stays a name. It is not replaced by a hex.
    return name

# ** function: _validate_series_style
def _validate_series_style(kind: str, series: Series) -> None:
    '''
    Reject a present style field the kind does not show.

    Kind does not add or remove the field. An absent value is legal
    on every kind. A stored value the picture does not show is not.

    :param kind: The plot kind.
    :type kind: str
    :param series: The series whose style is checked.
    :type series: Series
    :return: None
    :rtype: None
    '''

    # Line is the only kind that shows a stroke.
    if kind != 'line':
        if series.linestyle is not None:
            raise ValueError(f'Kind {kind!r} does not use linestyle.')
        if series.linewidth is not None:
            raise ValueError(f'Kind {kind!r} does not use linewidth.')

    # A bar has no marker. A present marker or size would not be shown.
    if kind == 'bar':
        if series.marker is not None:
            raise ValueError(f'Kind {kind!r} does not use marker.')
        if series.markersize is not None:
            raise ValueError(f'Kind {kind!r} does not use markersize.')

    # Bar width is a bar scale. A line or a scatter does not show it.
    if kind != 'bar' and series.bar_width is not None:
        raise ValueError(f'Kind {kind!r} does not use bar_width.')

# ** function: _legend_text
def _legend_text(series: Series) -> str:
    '''
    Return the legend text a later drawer reads.

    The text is ``legend_label`` when it is present. Otherwise it is
    the series name. This does not write the name back onto the label.

    :param series: The series.
    :type series: Series
    :return: The legend text.
    :rtype: str
    '''

    # A present label is the text. An absent label falls back, unread back.
    if series.legend_label:
        return series.legend_label
    return series.name

# ** function: _effective_color
def _effective_color(series: Series, index: int) -> str:
    '''
    Return the color a grid swatch compares.

    A stored color is used as stored. A name is not rewritten to hex.
    An absent color is the cycle hex for this series' index in its own
    cell, and that hex is not written back.

    :param series: The series.
    :type series: Series
    :param index: The series index in its own cell, from zero.
    :type index: int
    :return: The effective color.
    :rtype: str
    '''

    # A present color is not replaced by the cycle, and not rewritten.
    if series.color is not None:
        return series.color

    # The cycle is the absent-color rule. It is not a theme field.
    return ABSENT_COLOR_CYCLE[index % len(ABSENT_COLOR_CYCLE)]

# ** function: _swatch
def _swatch(kind: str, series: Series, index: int) -> tuple:
    '''
    Return the swatch a grid legend compares.

    Linewidth, marker size, and bar width are not part of the swatch.
    Absent linestyle is solid. Absent line marker is no marker. Absent
    scatter marker is circle. A bar has no marker shape.

    :param kind: The cell plot kind.
    :type kind: str
    :param series: The series.
    :type series: Series
    :param index: The series index in its own cell, from zero.
    :type index: int
    :return: The swatch.
    :rtype: tuple
    '''

    # Color is stored as given, or the cycle hex when absent.
    color = _effective_color(series, index)

    # A bar swatch is its color. It has no marker shape.
    if kind == 'bar':
        return (kind, color)

    # A scatter swatch is the marker. Absent means circle, not stored.
    if kind == 'scatter':
        marker = 'circle' if series.marker is None else series.marker
        return (kind, color, marker)

    # A line swatch is the stroke and the marker. Absences are not stored.
    linestyle = 'solid' if series.linestyle is None else series.linestyle
    marker = 'no_marker' if series.marker is None else series.marker
    return (kind, color, linestyle, marker)

# ** function: _validate_grid_legend
def _validate_grid_legend(matrix: PlotMatrix) -> None:
    '''
    Fail when a requested grid legend cannot agree on a swatch.

    The check runs only when the matrix asks for a legend. The union
    is not stored. A cell's own legend flag does not filter it.

    :param matrix: The declared matrix.
    :type matrix: PlotMatrix
    :return: None
    :rtype: None
    '''

    # Absent and false do not ask. The cells stay legal either way.
    if matrix.show_legend is not True:
        return

    # Order is row, then column, then series order inside the cell.
    owned = {}
    cells = sorted(matrix.cells, key=lambda cell: (cell.row, cell.col))
    for cell in cells:
        for index, series in enumerate(cell.plot.series):
            text = _legend_text(series)
            swatch = _swatch(cell.plot.kind, series, index)
            previous = owned.get(text)
            if previous is not None and previous != swatch:
                raise ValueError(
                    f'Grid legend text {text!r} has disagreeing swatches.'
                )
            owned.setdefault(text, swatch)

# *** models

# ** model: mark
class Mark(DomainObject):
    '''
    A mark is a role and the values that play that role.

    The kind decides which roles are legal. Drawing those roles is not
    part of the record.
    '''

    # * attribute: role
    role: str = Field(
        ...,
        description='The role these values play, such as x, y, category, or height.',
    )

    # * attribute: values
    values: tuple[Any, ...] = Field(
        ...,
        min_length=1,
        description='The values that play the role. Empty sequences are invalid.',
    )

# ** model: series
class Series(DomainObject):
    '''
    A series binds one named set of data to the marks a kind requires.

    It is part of the plot record. It is not a drawing instruction. It
    has no description, no title, and no axis text.
    '''

    # * attribute: id
    id: str = Field(
        ...,
        description='The series identity. Derived from name when omitted.',
    )

    # * attribute: name
    name: str = Field(
        ...,
        description='The author\'s name for the series.',
    )

    # * attribute: marks
    marks: list[Mark] = Field(
        ...,
        description='The role-and-values marks this series carries.',
    )

    # * attribute: legend_label
    legend_label: str | None = Field(
        default=None,
        description='Optional legend text. Blank is absent. Not derived from the name.',
    )

    # * attribute: color
    color: str | None = Field(
        default=None,
        description='Optional series color. Six-digit hex or a CSS Level 1 name.',
    )

    # * attribute: linestyle
    linestyle: str | None = Field(
        default=None,
        description='Optional line style. One of solid, dashed, dotted, or dashdot.',
    )

    # * attribute: linewidth
    linewidth: int | float | None = Field(
        default=None,
        description='Optional line width in points. Positive. Line only.',
    )

    # * attribute: marker
    marker: str | None = Field(
        default=None,
        description='Optional marker token. Line and scatter only. Not a tool code.',
    )

    # * attribute: markersize
    markersize: int | float | None = Field(
        default=None,
        description='Optional marker size in points. Positive. Line and scatter only.',
    )

    # * attribute: bar_width
    bar_width: int | float | None = Field(
        default=None,
        description='Optional scale of the grouped-bar slot width. Positive. Bar only.',
    )

    # * method: verify_addition
    def verify_addition(self, addition: Series) -> None:
        '''
        Describe another series as an addition to this one, and fail
        when it is not one.

        An addition carries exactly the roles this series carries,
        including ``label`` when this series has it, and plays each of
        them as the same sort. A legal series on its own is not an
        addition to this series. Neither series is changed.

        :param addition: The series whose values would extend this one.
        :type addition: Series
        :return: None
        :rtype: None
        :raises ModelError: ``ADDITION_ROLE_NOT_IN_SERIES`` for a role this
            series does not carry, ``ADDITION_ROLE_MISSING`` for one it
            carries that the addition omits, and ``ADDITION_SORT_MISMATCH``
            when a shared role is played as the other sort.
        '''

        # The addition carries these roles, not a fresh required pair.
        roles = [mark.role for mark in self.marks]
        added_roles = [mark.role for mark in addition.marks]
        extra = [role for role in added_roles if role not in roles]
        if extra:
            ModelError.raise_error(
                ADDITION_ROLE_NOT_IN_SERIES_ID,
                message=ADDITION_ROLE_NOT_IN_SERIES_MESSAGE.format(
                    role=extra[0],
                ),
                model=self,
                role=extra[0],
            )

        # A role this series carries is not optional in the addition.
        missing = [role for role in roles if role not in added_roles]
        if missing:
            ModelError.raise_error(
                ADDITION_ROLE_MISSING_ID,
                message=ADDITION_ROLE_MISSING_MESSAGE.format(
                    role=missing[0],
                ),
                model=self,
                role=missing[0],
            )

        # Sorts match this series. A legal sort on its own is not enough.
        values = {mark.role: mark.values for mark in self.marks}
        for mark in addition.marks:
            series_sort = _role_sort(mark.role, values[mark.role])
            addition_sort = _role_sort(mark.role, mark.values)
            if addition_sort != series_sort:
                ModelError.raise_error(
                    ADDITION_SORT_MISMATCH_ID,
                    message=ADDITION_SORT_MISMATCH_MESSAGE.format(
                        role=mark.role,
                        addition_sort=addition_sort,
                        series_sort=series_sort,
                    ),
                    model=self,
                    role=mark.role,
                )

    # * method: legend_text (property)
    legend_label: str | None = Field(
        default=None,
        description='Optional legend text. Blank is absent. Not derived from the name.',
    )

    # * attribute: color
    color: str | None = Field(
        default=None,
        description='Optional series color. Six-digit hex or a CSS Level 1 name.',
    )

    # * attribute: linestyle
    linestyle: str | None = Field(
        default=None,
        description='Optional line style. One of solid, dashed, dotted, or dashdot.',
    )

    # * attribute: linewidth
    linewidth: int | float | None = Field(
        default=None,
        description='Optional line width in points. Positive. Line only.',
    )

    # * attribute: marker
    marker: str | None = Field(
        default=None,
        description='Optional marker token. Line and scatter only. Not a tool code.',
    )

    # * attribute: markersize
    markersize: int | float | None = Field(
        default=None,
        description='Optional marker size in points. Positive. Line and scatter only.',
    )

    # * attribute: bar_width
    bar_width: int | float | None = Field(
        default=None,
        description='Optional scale of the grouped-bar slot width. Positive. Bar only.',
    )

    # * method: legend_text (property)
    @property
    def legend_text(self) -> str:
        '''
        Return the legend text a later drawer reads.

        A present label is that text. An absent label is the series name.
        The name is not written back onto the label.

        :return: The legend text.
        :rtype: str
        '''

        # The fallback is a reading. It is not a stored default.
        return _legend_text(self)

    # * method: _normalize_legend_label (field validator)
    @field_validator('legend_label', mode='before')
    @classmethod
    def _normalize_legend_label(cls, value: Any) -> Any:
        '''
        Store a blank legend label as absent.

        :param value: The raw label.
        :type value: Any
        :return: The label, or None when it was omitted or blank.
        :rtype: Any
        '''

        # Do not fill the label from the series name.
        return _absent_text(value)

    # * method: _normalize_color (field validator)
    @field_validator('color', mode='before')
    @classmethod
    def _normalize_color(cls, value: Any) -> Any:
        '''
        Store a legal color, or fail without a drawing tool.

        :param value: The raw color.
        :type value: Any
        :return: The stored color, or None when it was omitted or blank.
        :rtype: Any
        '''

        # Names and hex are checked here. Matplotlib is not imported.
        return _normalize_color(value)

    # * method: _validate_linestyle (field validator)
    @field_validator('linestyle', mode='before')
    @classmethod
    def _validate_linestyle(cls, value: Any) -> Any:
        '''
        Reject a linestyle outside the closed set.

        :param value: The raw linestyle.
        :type value: Any
        :return: The linestyle, or None when it was omitted.
        :rtype: Any
        '''

        # The tool spelling is not this token.
        return _optional_token(value, LINESTYLES)

    # * method: _validate_linewidth (field validator)
    @field_validator('linewidth', mode='before')
    @classmethod
    def _validate_linewidth(cls, value: Any) -> Any:
        '''
        Reject a linewidth that is not a positive number.

        :param value: The raw linewidth.
        :type value: Any
        :return: The linewidth, or None when it was omitted.
        :rtype: Any
        '''

        # A bool is not a width of 1. Text is not a width.
        return _optional_number(value, positive=True)

    # * method: _validate_marker (field validator)
    @field_validator('marker', mode='before')
    @classmethod
    def _validate_marker(cls, value: Any) -> Any:
        '''
        Reject a marker outside the closed set.

        :param value: The raw marker.
        :type value: Any
        :return: The marker, or None when it was omitted.
        :rtype: Any
        '''

        # A tool code is not a stored marker.
        return _optional_token(value, MARKERS)

    # * method: _validate_markersize (field validator)
    @field_validator('markersize', mode='before')
    @classmethod
    def _validate_markersize(cls, value: Any) -> Any:
        '''
        Reject a marker size that is not a positive number.

        :param value: The raw marker size.
        :type value: Any
        :return: The marker size, or None when it was omitted.
        :rtype: Any
        '''

        # A size does not invent a marker. It is only a number.
        return _optional_number(value, positive=True)

    # * method: _validate_bar_width (field validator)
    @field_validator('bar_width', mode='before')
    @classmethod
    def _validate_bar_width(cls, value: Any) -> Any:
        '''
        Reject a bar width that is not a positive scale.

        :param value: The raw bar width.
        :type value: Any
        :return: The scale, or None when it was omitted.
        :rtype: Any
        '''

        # The scale is not rewritten to the slot width.
        return _optional_number(value, positive=True)

    # * method: _derive_id (model validator)
    @model_validator(mode='before')
    @classmethod
    def _derive_id(cls, data: Any) -> Any:
        '''
        Derive a missing series id from its name.

        :param data: The raw series input.
        :type data: Any
        :return: The series input, with id filled when it was omitted.
        :rtype: Any
        '''

        # Fill a missing id once. A supplied id is kept as given.
        return _fill_id(data)

# ** model: plot
class Plot(DomainObject):
    '''
    A plot is a declared record of a claim, not a picture.

    It names the figure, the kind of chart, and the series that carry the
    marks. The catalog name is not the display title. It does not know
    which tool will draw it or where it will be kept.
    '''

    # * attribute: id
    id: str = Field(
        ...,
        description='The plot identity. Derived from name when omitted.',
    )

    # * attribute: name
    name: str = Field(
        ...,
        description='The author\'s name for the plot.',
    )

    # * attribute: kind
    kind: str = Field(
        ...,
        description='The chart kind. One of line, scatter, or bar. Not inferred.',
    )

    # * attribute: description
    description: str | None = Field(
        default=None,
        description='Optional claim text, read later as the subtitle. Not used to derive id or kind.',
    )

    # * attribute: title
    title: str | None = Field(
        default=None,
        description='Optional display title. Not the catalog name, and not used to derive id.',
    )

    # * attribute: x_title
    x_title: str | None = Field(
        default=None,
        description='Optional title of the x axis. Not a mark role, and not used to derive id.',
    )

    # * attribute: x_unit
    x_unit: str | None = Field(
        default=None,
        description='Optional unit of the x axis. Not written into the axis title.',
    )

    # * attribute: y_title
    y_title: str | None = Field(
        default=None,
        description='Optional title of the y axis. Not a mark role, and not used to derive id.',
    )

    # * attribute: y_unit
    y_unit: str | None = Field(
        default=None,
        description='Optional unit of the y axis. Not written into the axis title.',
    )

    # * attribute: series
    series: list[Series] = Field(
        ...,
        min_length=1,
        description='The series in this plot. A plot has at least one.',
    )

    # * attribute: show_legend
    show_legend: bool | None = Field(
        default=None,
        description='Optional legend flag. Omitted is not stored as true.',
    )

    # * attribute: legend_location
    legend_location: str | None = Field(
        default=None,
        description='Optional legend place. Not best, and not a coordinate pair.',
    )

    # * attribute: legend_title
    legend_title: str | None = Field(
        default=None,
        description='Optional legend title. Blank is absent. Not filled from the name.',
    )

    # * attribute: title_size
    title_size: int | float | None = Field(
        default=None,
        description='Optional title size in points. Positive. Absent is not stored as 12.',
    )

    # * attribute: subtitle_size
    subtitle_size: int | float | None = Field(
        default=None,
        description='Optional subtitle size in points. Positive. Absent is not stored as 10.',
    )

    # * attribute: axis_label_size
    axis_label_size: int | float | None = Field(
        default=None,
        description='Optional axis-label size in points. One size for both axes.',
    )

    # * attribute: tick_label_size
    tick_label_size: int | float | None = Field(
        default=None,
        description='Optional tick-label size in points. One size for every tick.',
    )

    # * attribute: legend_size
    legend_size: int | float | None = Field(
        default=None,
        description='Optional legend size in points. Positive. Absent is not stored as 10.',
    )

    # * attribute: x_tick_rotation
    x_tick_rotation: int | float | None = Field(
        default=None,
        description='Optional x tick rotation in degrees. Not rewritten modulo 360.',
    )

    # * attribute: y_tick_rotation
    y_tick_rotation: int | float | None = Field(
        default=None,
        description='Optional y tick rotation in degrees. Not rewritten modulo 360.',
    )

    # * attribute: x_tick_decimals
    x_tick_decimals: int | None = Field(
        default=None,
        description='Optional x decimal count. Zero is supplied. Absent is not zero.',
    )

    # * attribute: y_tick_decimals
    y_tick_decimals: int | None = Field(
        default=None,
        description='Optional y decimal count. Zero is supplied. Absent is not zero.',
    )

    # * attribute: font_family
    font_family: str | None = Field(
        default=None,
        description='Optional font family. One of serif, sans-serif, or monospace.',
    )

    # * method: is_matrix (property)
    @property
    def is_matrix(self) -> bool:
        '''
        Return whether this record is a matrix.

        A line, a scatter, and a bar are plots. Kind does not make a
        plot into a matrix.

        :return: False. A plot is not a matrix.
        :rtype: bool
        '''

        # A plot is the record with a kind. It is not a grid.
        return False

    # * method: title_text (property)
    @property
    def title_text(self) -> str:
        '''
        Return the title text a later drawer reads.

        The reading is ``title`` when it is present and not blank,
        otherwise the catalog name. The reading is not stored.

        :return: The title text a later drawer reads.
        :rtype: str
        '''

        # Do not copy the name into title. The drawer reads one or the other.
        return _title_text(self.title, self.name)

    # * method: subtitle_text (property)
    @property
    def subtitle_text(self) -> str | None:
        '''
        Return the subtitle text a later drawer reads.

        The subtitle is ``description`` when it is present and not blank.
        There is no subtitle field. A blank description is no subtitle.

        :return: The subtitle text, or None when there is none to read.
        :rtype: str | None
        '''

        # Description stays as stored. Blank text is not a subtitle.
        return _subtitle_text(self.description)

    # * method: require_kind (static)
    @staticmethod
    def require_kind(kind: str) -> str:
        '''
        Reject a kind that is not one of the declared kinds.

        Kind is an input. It is not inferred from the values, and it is
        not guessed from case.

        :param kind: The supplied kind.
        :type kind: str
        :return: The kind, unchanged.
        :rtype: str
        '''

        # Kind is not normalized. The declared kinds are the description.
        if kind not in PLOT_KINDS:
            allowed = ', '.join(PLOT_KINDS)
            raise ValueError(
                f'Kind {kind!r} is not one of {allowed}.'
            )

        # Return the supplied kind.
        return kind

    # * method: _derive_id (model validator)
    @model_validator(mode='before')
    @classmethod
    def _derive_id(cls, data: Any) -> Any:
        '''
        Derive a missing plot id from its name.

        Description is not identity. Kind is not inferred from the values.

        :param data: The raw plot input.
        :type data: Any
        :return: The plot input, with id filled when it was omitted.
        :rtype: Any
        '''

        # Fill a missing id once. A supplied id is kept as given.
        return _fill_id(data)

    # * method: _validate_kind (field validator)
    @field_validator('kind')
    @classmethod
    def _validate_kind(cls, value: str) -> str:
        '''
        Reject a kind that is not one of the declared kinds.

        :param value: The supplied kind.
        :type value: str
        :return: The kind, unchanged.
        :rtype: str
        '''

        # The plot describes a legal kind. Do not restate that rule here.
        return cls.require_kind(value)

    # * method: _normalize_figure_text (field validator)
    @field_validator('title', 'x_title', 'x_unit', 'y_title', 'y_unit')
    @classmethod
    def _normalize_figure_text(cls, value: str | None) -> str | None:
        '''
        Store omitted and blank figure text as absent.

        Declaration does not fill ``title`` from the name, and it does
        not write a unit into a title.

        :param value: The supplied text.
        :type value: str | None
        :return: None when the text was omitted or blank, otherwise the string.
        :rtype: str | None
        '''

        # Blank and omitted are the same case. Do not store an empty string.
        return _absent_text(value)

    # * method: _validate_show_legend (field validator)
    @field_validator('show_legend', mode='before')
    @classmethod
    def _validate_show_legend(cls, value: Any) -> Any:
        '''
        Reject a legend flag that is not a bool.

        :param value: The raw flag.
        :type value: Any
        :return: The bool, or None when it was omitted.
        :rtype: Any
        '''

        # Text is not coerced. Omitted is not stored as true.
        return _optional_bool(value)

    # * method: _validate_legend_location (field validator)
    @field_validator('legend_location', mode='before')
    @classmethod
    def _validate_legend_location(cls, value: Any) -> Any:
        '''
        Reject a legend place outside the closed set.

        :param value: The raw location.
        :type value: Any
        :return: The location, or None when it was omitted.
        :rtype: Any
        '''

        # best and the tool's spelling are not this token.
        return _optional_token(value, LEGEND_LOCATIONS)

    # * method: _validate_legend_title (field validator)
    @field_validator('legend_title', mode='before')
    @classmethod
    def _validate_legend_title(cls, value: Any) -> Any:
        '''
        Store a blank legend title as absent.

        :param value: The raw title.
        :type value: Any
        :return: The title, or None when it was omitted or blank.
        :rtype: Any
        '''

        # Do not fill the title from the plot name.
        return _absent_text(value)

    # * method: _validate_text_size (field validator)
    @field_validator(
        'title_size',
        'subtitle_size',
        'axis_label_size',
        'tick_label_size',
        'legend_size',
        mode='before',
    )
    @classmethod
    def _validate_text_size(cls, value: Any) -> Any:
        '''
        Reject a text size that is not a positive number.

        :param value: The raw size.
        :type value: Any
        :return: The size, or None when it was omitted.
        :rtype: Any
        '''

        # A named size is a catalog. Text that looks like a number is not a size.
        return _optional_number(value, positive=True)

    # * method: _validate_tick_rotation (field validator)
    @field_validator('x_tick_rotation', 'y_tick_rotation', mode='before')
    @classmethod
    def _validate_tick_rotation(cls, value: Any) -> Any:
        '''
        Reject a tick rotation that is not a number.

        :param value: The raw rotation.
        :type value: Any
        :return: The rotation, or None when it was omitted.
        :rtype: Any
        '''

        # A float is legal. The value is not rewritten modulo 360.
        return _optional_number(value)

    # * method: _validate_tick_decimals (field validator)
    @field_validator('x_tick_decimals', 'y_tick_decimals', mode='before')
    @classmethod
    def _validate_tick_decimals(cls, value: Any) -> Any:
        '''
        Reject a decimal count that is not a non-negative integer.

        :param value: The raw count.
        :type value: Any
        :return: The count, or None when it was omitted.
        :rtype: Any
        '''

        # Zero is supplied. A float is not an integer count.
        return _optional_decimals(value)

    # * method: _validate_font_family (field validator)
    @field_validator('font_family', mode='before')
    @classmethod
    def _validate_font_family(cls, value: Any) -> Any:
        '''
        Reject a font family outside the closed set.

        :param value: The raw family.
        :type value: Any
        :return: The family, or None when it was omitted.
        :rtype: Any
        '''

        # A raw family name is not this token.
        return _optional_token(value, FONT_FAMILIES)

    # * method: _validate_declaration (model validator)
    @model_validator(mode='after')
    def _validate_declaration(self) -> Plot:
        '''
        Check that the series are well-formed for the kind.

        :return: The validated plot.
        :rtype: Plot
        '''

        # Duplicate series ids and illegal marks fail at declaration.
        _validate_series(self.kind, self.series)

        # Return the declared record. Nothing has been drawn or saved.
        return self

# ** model: matrix_cell
class MatrixCell(DomainObject):
    '''
    A cell places one plot on a declared grid.

    The plot is the declared record, carried on the cell. An empty position
    is the absence of a cell, not a cell with nothing in it.
    '''

    # * attribute: row
    row: int = Field(
        ...,
        ge=0,
        description='The zero-based row this plot occupies.',
    )

    # * attribute: col
    col: int = Field(
        ...,
        ge=0,
        description='The zero-based column this plot occupies.',
    )

    # * attribute: plot
    plot: Plot = Field(
        ...,
        description='The plot record placed in this cell. Not a bare id.',
    )

    # * method: _require_plot_id (model validator)
    @model_validator(mode='before')
    @classmethod
    def _require_plot_id(cls, data: Any) -> Any:
        '''
        Reject a cell plot whose id is missing or blank.

        Declaration does not fill that id from the plot name.

        :param data: The raw cell input.
        :type data: Any
        :return: The cell input, unchanged when the plot id is present.
        :rtype: Any
        '''

        # Leave non-mapping input for Pydantic to reject.
        if not isinstance(data, dict):
            return data

        # A missing plot is a required-field failure, not an id failure.
        if 'plot' not in data:
            return data

        # Do not derive a plot id. A blank id is not a supplied id.
        _require_plot_id(data.get('plot'))
        return data

# ** model: plot_matrix
class PlotMatrix(DomainObject):
    '''
    A plot matrix is a declared grid of plots, not a fourth chart kind.

    It names which plots occupy which row and column. Its display title
    is not a cell's title. The picture of that grid is not part of the
    record, and neither is the tool that draws it.
    '''

    # * attribute: id
    id: str = Field(
        ...,
        description='The matrix identity. Derived from name when omitted.',
    )

    # * attribute: name
    name: str = Field(
        ...,
        description='The author\'s name for the matrix.',
    )

    # * attribute: description
    description: str | None = Field(
        default=None,
        description='Optional claim text, read later as the grid subtitle. Not used to derive the id.',
    )

    # * attribute: title
    title: str | None = Field(
        default=None,
        description='Optional display title of the grid. Not a cell title, and not used to derive id.',
    )

    # * attribute: rows
    rows: int = Field(
        ...,
        ge=1,
        description='The declared number of rows. At least one. Not inferred.',
    )

    # * attribute: cols
    cols: int = Field(
        ...,
        ge=1,
        description='The declared number of columns. At least one. Not inferred.',
    )

    # * attribute: cells
    cells: list[MatrixCell] = Field(
        ...,
        min_length=1,
        description='The occupied cells. An empty corner is not a cell.',
    )

    # * attribute: show_legend
    show_legend: bool | None = Field(
        default=None,
        description='Optional grid-legend flag. Omitted is not stored as false.',
    )

    # * attribute: legend_location
    legend_location: str | None = Field(
        default=None,
        description='Optional grid-legend place. Not best, and not a coordinate pair.',
    )

    # * attribute: legend_title
    legend_title: str | None = Field(
        default=None,
        description='Optional grid-legend title. Blank is absent. Not filled from the name.',
    )

    # * attribute: title_size
    title_size: int | float | None = Field(
        default=None,
        description='Optional grid-title size in points. Positive. Absent is not stored as 12.',
    )

    # * attribute: subtitle_size
    subtitle_size: int | float | None = Field(
        default=None,
        description='Optional grid-subtitle size in points. Positive. Absent is not stored as 10.',
    )

    # * attribute: legend_size
    legend_size: int | float | None = Field(
        default=None,
        description='Optional grid-legend size in points. Positive. Absent is not stored as 10.',
    )

    # * attribute: font_family
    font_family: str | None = Field(
        default=None,
        description='Optional grid font family. One of serif, sans-serif, or monospace.',
    )

    # * attribute: row_spacing
    row_spacing: int | float | None = Field(
        default=None,
        description='Optional row gap as a fraction of average cell height. Zero is legal.',
    )

    # * attribute: col_spacing
    col_spacing: int | float | None = Field(
        default=None,
        description='Optional column gap as a fraction of average cell width. Zero is legal.',
    )

    # * method: is_matrix (property)
    @property
    def is_matrix(self) -> bool:
        '''
        Return whether this record is a matrix.

        A matrix is a declared grid. It is not a fourth chart kind, and
        it has no kind of its own.

        :return: True. A matrix is not a plot.
        :rtype: bool
        '''

        # A matrix is its own record. Kind does not describe it.
        return True

    # * method: title_text (property)
    @property
    def title_text(self) -> str:
        '''
        Return the grid title text a later drawer reads.

        The reading is the matrix ``title`` when it is present and not
        blank, otherwise the matrix name. A cell title is not this text.

        :return: The grid title text a later drawer reads.
        :rtype: str
        '''

        # Do not copy the name into title. A cell title is not the grid title.
        return _title_text(self.title, self.name)

    # * method: subtitle_text (property)
    @property
    def subtitle_text(self) -> str | None:
        '''
        Return the grid subtitle a later drawer reads.

        The subtitle is the matrix ``description`` when it is present
        and not blank. A cell description is not this text.

        :return: The grid subtitle, or None when there is none to read.
        :rtype: str | None
        '''

        # Description stays as stored. Blank text is not a subtitle.
        return _subtitle_text(self.description)

    # * method: _normalize_title (field validator)
    @field_validator('title')
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        '''
        Store an omitted or blank grid title as absent.

        Declaration does not fill ``title`` from the name.

        :param value: The supplied title.
        :type value: str | None
        :return: None when the title was omitted or blank, otherwise the string.
        :rtype: str | None
        '''

        # Blank and omitted are the same case. Do not store an empty string.
        return _absent_text(value)

    # * method: _derive_id (model validator)
    @model_validator(mode='before')
    @classmethod
    def _derive_id(cls, data: Any) -> Any:
        '''
        Derive a missing matrix id from its name.

        The rule is the plot id rule. A supplied id is kept. A cell plot
        id is not derived here.

        :param data: The raw matrix input.
        :type data: Any
        :return: The matrix input, with id filled when it was omitted.
        :rtype: Any
        '''

        # Fill a missing id once. A supplied id is kept as given.
        return _fill_id(data)

    # * method: _validate_show_legend (field validator)
    @field_validator('show_legend', mode='before')
    @classmethod
    def _validate_show_legend(cls, value: Any) -> Any:
        '''
        Reject a grid-legend flag that is not a bool.

        :param value: The raw flag.
        :type value: Any
        :return: The bool, or None when it was omitted.
        :rtype: Any
        '''

        # Text is not coerced. Omitted is not stored as false.
        return _optional_bool(value)

    # * method: _validate_legend_location (field validator)
    @field_validator('legend_location', mode='before')
    @classmethod
    def _validate_legend_location(cls, value: Any) -> Any:
        '''
        Reject a grid-legend place outside the closed set.

        :param value: The raw location.
        :type value: Any
        :return: The location, or None when it was omitted.
        :rtype: Any
        '''

        # best and the tool's spelling are not this token.
        return _optional_token(value, LEGEND_LOCATIONS)

    # * method: _validate_legend_title (field validator)
    @field_validator('legend_title', mode='before')
    @classmethod
    def _validate_legend_title(cls, value: Any) -> Any:
        '''
        Store a blank grid-legend title as absent.

        :param value: The raw title.
        :type value: Any
        :return: The title, or None when it was omitted or blank.
        :rtype: Any
        '''

        # Do not fill the title from the matrix name.
        return _absent_text(value)

    # * method: _validate_text_size (field validator)
    @field_validator(
        'title_size',
        'subtitle_size',
        'legend_size',
        mode='before',
    )
    @classmethod
    def _validate_text_size(cls, value: Any) -> Any:
        '''
        Reject a grid text size that is not a positive number.

        :param value: The raw size.
        :type value: Any
        :return: The size, or None when it was omitted.
        :rtype: Any
        '''

        # A named size is a catalog. Text that looks like a number is not a size.
        return _optional_number(value, positive=True)

    # * method: _validate_font_family (field validator)
    @field_validator('font_family', mode='before')
    @classmethod
    def _validate_font_family(cls, value: Any) -> Any:
        '''
        Reject a grid font family outside the closed set.

        :param value: The raw family.
        :type value: Any
        :return: The family, or None when it was omitted.
        :rtype: Any
        '''

        # A raw family name is not this token.
        return _optional_token(value, FONT_FAMILIES)

    # * method: _validate_spacing (field validator)
    @field_validator('row_spacing', 'col_spacing', mode='before')
    @classmethod
    def _validate_spacing(cls, value: Any) -> Any:
        '''
        Reject a spacing that is not a non-negative number.

        :param value: The raw spacing.
        :type value: Any
        :return: The spacing, or None when it was omitted.
        :rtype: Any
        '''

        # Zero is a supplied gap. A bool is not a gap of 1.
        return _optional_number(value, nonnegative=True)

    # * method: _validate_grid (model validator)
    @model_validator(mode='after')
    def _validate_grid(self) -> PlotMatrix:
        '''
        Check that each cell sits in the declared grid and on its own position.

        A requested grid legend fails when two series share legend text
        and disagree on the swatch. The union is not stored.

        :return: The validated matrix.
        :rtype: PlotMatrix
        '''

        # The author declared the grid. Do not shrink it to the occupied cells.
        _validate_cell_positions(self.rows, self.cols, self.cells)

        # Ask only when the matrix asks. A cell flag does not filter the union.
        _validate_grid_legend(self)

        # Return the declared record. Nothing has been drawn or saved.
        return self
