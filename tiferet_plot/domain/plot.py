"""Plot domain models."""

# *** imports

# ** core
from __future__ import annotations
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

    # * method: _validate_grid (model validator)
    @model_validator(mode='after')
    def _validate_grid(self) -> PlotMatrix:
        '''
        Check that each cell sits in the declared grid and on its own position.

        :return: The validated matrix.
        :rtype: PlotMatrix
        '''

        # The author declared the grid. Do not shrink it to the occupied cells.
        _validate_cell_positions(self.rows, self.cols, self.cells)

        # Return the declared record. Nothing has been drawn or saved.
        return self
