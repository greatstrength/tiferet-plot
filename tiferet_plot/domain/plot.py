"""Plot domain models."""

# *** imports

# ** core
from __future__ import annotations
from typing import Any, Sequence

# ** infra
from pydantic import Field, field_validator, model_validator

# ** app
from tiferet import DomainObject

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

# ** function: _validate_marks
def _validate_marks(kind: str, marks: Sequence[Mark]) -> None:
    '''
    Require the mark roles a kind selects, and no others.

    :param kind: The plot kind.
    :type kind: str
    :param marks: The series marks.
    :type marks: Sequence[Mark]
    :return: None
    :rtype: None
    '''

    # Index marks by role and reject a repeated role.
    by_role = {}
    for mark in marks:
        if mark.role in by_role:
            raise ValueError(f'Duplicate mark role {mark.role!r}.')
        by_role[mark.role] = mark

    # The kind selects the legal roles. Extra roles are invalid.
    required = MARK_ROLES_BY_KIND[kind]
    extra = [role for role in by_role if role not in required]
    if extra:
        raise ValueError(
            f'Kind {kind!r} does not allow mark role {extra[0]!r}.'
        )

    # Every required role must be present.
    missing = [role for role in required if role not in by_role]
    if missing:
        raise ValueError(
            f'Kind {kind!r} requires mark role {missing[0]!r}.'
        )

    # Required values must be the right sort, non-empty, and the same length.
    lengths = []
    for role in required:
        values = by_role[role].values
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

    # Equal length is part of being well-formed for the kind.
    if len(set(lengths)) != 1:
        raise ValueError('Mark value sequences must have equal length.')

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

    :param kind: The plot kind.
    :type kind: str
    :param series: The declared series.
    :type series: Sequence[Series]
    :return: None
    :rtype: None
    '''

    # Two series in one plot may not resolve to the same id.
    seen = set()
    for item in series:
        if item.id in seen:
            raise ValueError(
                f'Two series resolved to the same id {item.id!r}.'
            )
        seen.add(item.id)

        # The kind rectifies this series' marks. It does not add plot fields.
        _validate_marks(kind, item.marks)

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

    It is part of the plot record. It is not a drawing instruction, and it
    has no description in this round.
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
    marks. It does not know which tool will draw it or where it will be kept.
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
        description='Optional claim text. Not used to derive id or kind.',
    )

    # * attribute: series
    series: list[Series] = Field(
        ...,
        min_length=1,
        description='The series in this plot. A plot has at least one.',
    )

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

        # Kind is an input. It is not normalized and not inferred.
        if value not in PLOT_KINDS:
            allowed = ', '.join(PLOT_KINDS)
            raise ValueError(
                f'Kind {value!r} is not one of {allowed}.'
            )

        # Return the supplied kind.
        return value

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

    It names which plots occupy which row and column. The picture of that
    grid is not part of the record, and neither is the tool that draws it.
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
        description='Optional claim text. Not used to derive the id.',
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
