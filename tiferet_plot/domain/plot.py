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
