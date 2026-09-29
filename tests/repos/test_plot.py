"""Tests for saving a plot to a publication file."""

# *** imports

# ** core
import ast
from pathlib import Path

# ** infra
import pytest

# ** app
from tiferet import use_tester
from tiferet.interfaces import ServiceError
from tiferet.repos.core import UNSUPPORTED_CONFIG_FILE_TYPE_ID
from tiferet_plot import (
    PLOT_ALREADY_KEPT_ID,
    PLOT_NOT_KEPT_ID,
    PlotService,
)
from tiferet_plot.domain.plot import Mark
from tiferet_plot.mappers.plot import PlotAggregate, SeriesAggregate
from tiferet_plot.repos.plot import PlotConfigRepository
import tiferet_plot
import tiferet_plot.repos as repos_package

# *** constants

# ** constant: seeded_plot_yaml
SEEDED_PLOT_YAML = '''\
plots:
  sales_by_region:
    name: Sales by Region
    kind: line
    description: Revenue compared across regions.
    series:
      - id: revenue
        name: Revenue
        marks:
          - role: x
            values: [1, 2]
          - role: y
            values: [3, 4]
'''

# *** functions

# ** function: line_marks
def line_marks(x=(1, 2), y=(3, 4)):
    '''
    Build numeric x and y marks.

    :param x: The x values.
    :type x: tuple
    :param y: The y values.
    :type y: tuple
    :return: Marks for a line or scatter series.
    :rtype: list
    '''

    # Return the two required roles.
    return [
        Mark(role='x', values=x),
        Mark(role='y', values=y),
    ]

# ** function: bar_marks
def bar_marks(category=('North', 'South'), height=(10, 12)):
    '''
    Build category and height marks.

    :param category: The category labels.
    :type category: tuple
    :param height: The bar heights.
    :type height: tuple
    :return: Marks for a bar series.
    :rtype: list
    '''

    # Return the two required roles.
    return [
        Mark(role='category', values=category),
        Mark(role='height', values=height),
    ]

# ** function: line_plot
def line_plot() -> PlotAggregate:
    '''
    A line plot with a supplied id that is not the snake_case of its name.

    :return: The plot aggregate.
    :rtype: PlotAggregate
    '''

    # Supply both ids. The store must not derive them.
    return PlotAggregate(
        id='Custom-Id',
        name='Sales by Region',
        description='Revenue compared across regions.',
        kind='line',
        series=[
            SeriesAggregate(id='rev-1', name='Revenue', marks=line_marks()),
            SeriesAggregate(
                id='cost-1',
                name='Cost',
                marks=line_marks((5, 6), (7, 8)),
            ),
        ],
    )

# ** function: bar_plot
def bar_plot() -> PlotAggregate:
    '''
    A bar plot with no description and a derived id.

    :return: The plot aggregate.
    :rtype: PlotAggregate
    '''

    # Omit the description. The store must not invent one.
    return PlotAggregate(
        name='Q3 Revenue',
        kind='bar',
        series=[
            SeriesAggregate(name='Revenue', marks=bar_marks()),
        ],
    )

# ** function: open_repo
def open_repo(tmp_path: Path, suffix: str) -> tuple:
    '''
    Point a repository at a publication path that does not exist yet.

    :param tmp_path: The pytest temporary directory.
    :type tmp_path: Path
    :param suffix: The file extension, including the dot.
    :type suffix: str
    :return: The repository and the path.
    :rtype: tuple
    '''

    # The file is created by the first successful save.
    path = tmp_path / f'publication{suffix}'
    return PlotConfigRepository(str(path)), path

# ** function: assert_same_record
def assert_same_record(loaded: PlotAggregate, original: PlotAggregate) -> None:
    '''
    Assert a loaded plot is the same record that was saved.

    :param loaded: The plot returned by the store.
    :type loaded: PlotAggregate
    :param original: The plot that was saved.
    :type original: PlotAggregate
    :return: None
    :rtype: None
    '''

    # Identity, claim, kind, and description come back unchanged.
    assert loaded.id == original.id
    assert loaded.name == original.name
    assert loaded.kind == original.kind
    assert loaded.description == original.description
    assert len(loaded.series) == len(original.series)

    # Series ids, names, and marks come back in declaration order.
    for loaded_series, original_series in zip(loaded.series, original.series):
        assert loaded_series.id == original_series.id
        assert loaded_series.name == original_series.name
        assert len(loaded_series.marks) == len(original_series.marks)
        for loaded_mark, original_mark in zip(
                loaded_series.marks,
                original_series.marks):
            assert loaded_mark.role == original_mark.role
            assert loaded_mark.values == original_mark.values

# *** fixtures

# ** fixture: seeded_plot_file
@pytest.fixture
def seeded_plot_file(tmp_path) -> str:
    '''
    Write a publication that already keeps one plot.

    :param tmp_path: The pytest temporary directory.
    :type tmp_path: Path
    :return: The YAML file path.
    :rtype: str
    '''

    # Seed the file shape: plot id is the key, series are nested in the body.
    path = tmp_path / 'seeded.yml'
    path.write_text(SEEDED_PLOT_YAML, encoding='utf-8')
    return str(path)

# *** tests

# ** test: save_round_trips_line_and_bar
@pytest.mark.parametrize('suffix', ['.yml', '.yaml', '.json'])
def test_save_round_trips_line_and_bar(tmp_path, suffix):
    '''
    Saving a new id writes it, and loading returns the same record.
    '''

    # Keep a line plot and a bar plot in the same publication.
    repo, path = open_repo(tmp_path, suffix)
    line = line_plot()
    bar = bar_plot()
    repo.save(line)
    repo.save(bar)

    # Both records come back. List returns records, not a picture.
    assert_same_record(repo.get(line.id), line)
    assert_same_record(repo.get(bar.id), bar)
    listed = repo.list()
    assert {item.id for item in listed} == {line.id, bar.id}
    assert all(isinstance(item, PlotAggregate) for item in listed)
    assert not isinstance(listed, str)

    # The stored body has no plot id, renderer, or database handle.
    raw = repo._load()
    assert 'series' not in raw
    for plot in (line, bar):
        body = raw['plots'][plot.id]
        assert 'id' not in body
        assert 'renderer' not in body
        assert 'database' not in body
        assert 'file_path' not in body
        assert set(body) <= {'name', 'kind', 'description', 'series'}
        assert isinstance(body['series'], list)
        assert [item['id'] for item in body['series']] == [
            series.id for series in plot.series
        ]
        for series, series_body in zip(plot.series, body['series']):
            assert series_body['name'] == series.name
            assert 'renderer' not in series_body

    # The publication file exists only because save wrote it.
    assert path.exists()

# ** test: second_save_fails_and_leaves_the_first_record
def test_second_save_fails_and_leaves_the_first_record(tmp_path):
    '''
    A second plot with an id already kept fails, and the first record is unchanged.
    '''

    # Keep two different ids. That must not be an overwrite.
    repo, path = open_repo(tmp_path, '.yml')
    first = line_plot()
    other = bar_plot()
    repo.save(first)
    repo.save(other)
    before = path.read_bytes()

    # A later declaration that resolves to the first id is rejected.
    duplicate = PlotAggregate(
        id=first.id,
        name='A different title',
        kind='scatter',
        series=[
            SeriesAggregate(name='Other', marks=line_marks((9, 8), (7, 6))),
        ],
    )
    with pytest.raises(ServiceError) as caught:
        repo.save(duplicate)

    # The first publication is byte-for-byte unchanged.
    assert caught.value.error_code == PLOT_ALREADY_KEPT_ID
    assert path.read_bytes() == before
    assert_same_record(repo.get(first.id), first)
    assert_same_record(repo.get(other.id), other)

# ** test: update_replaces_kept_record_without_changing_id
def test_update_replaces_kept_record_without_changing_id(tmp_path):
    '''
    Updating a kept id replaces that record and does not re-derive its id.
    '''

    # Keep a record, then edit the name and the marks.
    repo, _path = open_repo(tmp_path, '.yaml')
    plot = line_plot()
    repo.save(plot)
    plot.rename('Quarterly Sales')
    plot.rename_series('rev-1', 'Cost of Goods')
    plot.replace_marks('rev-1', line_marks((9, 8), (7, 6)))
    repo.update(plot)

    # The key is still the original id. The name and marks changed.
    loaded = repo.get('Custom-Id')
    assert loaded.id == 'Custom-Id'
    assert loaded.name == 'Quarterly Sales'
    assert loaded.series[0].id == 'rev-1'
    assert loaded.series[0].name == 'Cost of Goods'
    assert loaded.series[0].marks[0].values == (9, 8)
    assert repo.get('quarterly_sales') is None
    assert repo.get('cost_of_goods') is None

    # The file key did not follow the new name. The series id was not re-derived.
    body = repo._load()['plots']['Custom-Id']
    series_ids = [item['id'] for item in body['series']]
    assert body['name'] == 'Quarterly Sales'
    assert 'id' not in body
    assert series_ids == ['rev-1', 'cost-1']
    assert 'cost_of_goods' not in series_ids
    assert body['series'][0]['name'] == 'Cost of Goods'

# ** test: update_of_missing_id_fails_and_does_not_insert
def test_update_of_missing_id_fails_and_does_not_insert(tmp_path):
    '''
    Updating an id that is not kept fails and does not insert.
    '''

    # A missing file has nothing to replace.
    repo, path = open_repo(tmp_path, '.json')
    plot = line_plot()
    with pytest.raises(ServiceError) as caught:
        repo.update(plot)

    # The failure does not create the publication.
    assert caught.value.error_code == PLOT_NOT_KEPT_ID
    assert not path.exists()
    assert repo.exists(plot.id) is False
    assert repo.get(plot.id) is None

    # After a different id is kept, updating the missing id still does not insert.
    repo.save(bar_plot())
    before = path.read_bytes()
    with pytest.raises(ServiceError) as caught:
        repo.update(plot)
    assert caught.value.error_code == PLOT_NOT_KEPT_ID
    assert path.read_bytes() == before
    assert repo.get(plot.id) is None

# ** test: missing_file_is_empty_and_delete_changes_nothing
def test_missing_file_is_empty_and_delete_changes_nothing(tmp_path):
    '''
    Getting a missing id returns nothing. Deleting a missing id succeeds.
    '''

    # A missing file is an empty store.
    repo, path = open_repo(tmp_path, '.yml')
    assert repo.exists('sales_by_region') is False
    assert repo.get('sales_by_region') is None
    listed = repo.list()
    assert listed == []
    assert not isinstance(listed, str)

    # Delete of a missing id does not create the file.
    repo.delete('sales_by_region')
    assert not path.exists()

    # An empty file is also an empty store.
    path.write_text('', encoding='utf-8')
    assert repo.list() == []
    assert repo.get('sales_by_region') is None
    before = path.read_bytes()
    repo.delete('sales_by_region')
    assert path.read_bytes() == before

# ** test: delete_removes_the_plot_and_its_series
def test_delete_removes_the_plot_and_its_series(tmp_path):
    '''
    Delete removes the plot and the series stored inside it.
    '''

    # Keep a plot, then remove it.
    repo, path = open_repo(tmp_path, '.yml')
    plot = line_plot()
    repo.save(plot)
    repo.delete(plot.id)

    # The record is gone. A second delete changes nothing.
    assert repo.get(plot.id) is None
    assert repo.exists(plot.id) is False
    raw = repo._load()
    assert plot.id not in raw.get('plots', {})
    assert 'series' not in raw
    before = path.read_bytes()
    repo.delete(plot.id)
    assert path.read_bytes() == before

# ** test: txt_path_fails
def test_txt_path_fails(tmp_path):
    '''
    A .txt path fails.
    '''

    # The extension is rejected before the store is treated as empty.
    path = tmp_path / 'publication.txt'
    repo = PlotConfigRepository(str(path))
    with pytest.raises(ServiceError) as caught:
        repo.exists('sales_by_region')
    assert caught.value.error_code == UNSUPPORTED_CONFIG_FILE_TYPE_ID
    assert not path.exists()

    # Save does not create a text file either.
    with pytest.raises(ServiceError) as caught:
        repo.save(line_plot())
    assert caught.value.error_code == UNSUPPORTED_CONFIG_FILE_TYPE_ID
    assert not path.exists()

# ** test: save_preserves_unrelated_file_keys
def test_save_preserves_unrelated_file_keys(tmp_path):
    '''
    Saving a plot does not drop unrelated keys already in the file.
    '''

    # A note beside the publication is not a plot field.
    path = tmp_path / 'publication.yml'
    path.write_text('note: keep\n', encoding='utf-8')
    repo = PlotConfigRepository(str(path))
    plot = line_plot()
    repo.save(plot)

    # The note remains. The plot is under the plots root.
    raw = repo._load()
    assert raw['note'] == 'keep'
    assert plot.id in raw['plots']
    assert 'id' not in raw['plots'][plot.id]

# ** test: repository_is_not_exported_and_does_not_import_matplotlib
def test_repository_is_not_exported_and_does_not_import_matplotlib():
    '''
    The repository is not a package export and does not import Matplotlib.
    '''

    # The package and the repos package do not export the repository.
    assert 'PlotConfigRepository' not in tiferet_plot.__all__
    assert not hasattr(tiferet_plot, 'PlotConfigRepository')
    assert not hasattr(repos_package, 'PlotConfigRepository')
    assert issubclass(PlotConfigRepository, PlotService)

    # No plot module imports Matplotlib or derives an id.
    root = Path(tiferet_plot.__file__).parent
    for path in root.rglob('*.py'):
        source = path.read_text()
        names = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
        imported = ' '.join(names)
        assert 'matplotlib' not in imported
        if path.name == 'plot.py' and path.parent.name == 'repos':
            assert '_snake_case' not in source
            assert '_fill_id' not in source

# *** testers

# ** tester: test_plot_config_repository
@use_tester(
    type='repo',
    target_cls=PlotConfigRepository,
    config_parameter='plot_config',
    equality_fields=[
        'id',
        'name',
        'kind',
        'description',
    ],
    aggregate_cls=PlotAggregate,
    aggregate_sample_data={
        'id': 'q3_revenue',
        'name': 'Q3 Revenue',
        'kind': 'scatter',
        'description': 'A scatter claim.',
        'series': [
            {
                'id': 'rev-1',
                'name': 'Revenue',
                'marks': [
                    {
                        'role': 'x',
                        'values': (1, 2),
                    },
                    {
                        'role': 'y',
                        'values': (3, 4),
                    },
                ],
            },
        ],
    },
    exists_cases=[
        ('sales_by_region', True),
        ('missing', False),
    ],
    get_cases=[
        ('sales_by_region', {
            'id': 'sales_by_region',
            'name': 'Sales by Region',
            'kind': 'line',
            'description': 'Revenue compared across regions.',
        }),
        ('missing', None),
    ],
    list_ids=[
        'sales_by_region',
    ],
    delete_ids=[
        'sales_by_region',
        'missing',
    ],
)
class TestPlotConfigRepository:
    '''
    Tests for PlotConfigRepository using the repo tester.
    '''

    # * test: exists
    def test_exists(self, test_ctx, seeded_plot_file: str):
        '''
        Exists is true only for a kept id.

        :param test_ctx: The bound repo tester context.
        :type test_ctx: object
        :param seeded_plot_file: The seeded publication path.
        :type seeded_plot_file: str
        '''

        # Construct the repository against the seeded file.
        repo = test_ctx.make_target(config_file=seeded_plot_file)

        # Assert the seeded id and a missing id.
        test_ctx.assert_exists(repo)

    # * test: get
    def test_get(self, test_ctx, seeded_plot_file: str):
        '''
        Get returns the record, or nothing when the id is not kept.

        :param test_ctx: The bound repo tester context.
        :type test_ctx: object
        :param seeded_plot_file: The seeded publication path.
        :type seeded_plot_file: str
        '''

        # Construct the repository against the seeded file.
        repo = test_ctx.make_target(config_file=seeded_plot_file)

        # Assert the seeded record and a missing id.
        test_ctx.assert_get(repo)
        loaded = repo.get('sales_by_region')
        assert loaded.series[0].id == 'revenue'
        assert loaded.series[0].marks[0].values == (1, 2)

    # * test: list
    def test_list(self, test_ctx, seeded_plot_file: str):
        '''
        List returns the kept records.

        :param test_ctx: The bound repo tester context.
        :type test_ctx: object
        :param seeded_plot_file: The seeded publication path.
        :type seeded_plot_file: str
        '''

        # Construct the repository against the seeded file.
        repo = test_ctx.make_target(config_file=seeded_plot_file)

        # Assert the kept ids. The result is not a display string.
        test_ctx.assert_list(repo)
        assert all(isinstance(item, PlotAggregate) for item in repo.list())

    # * test: save
    def test_save(self, test_ctx, tmp_path):
        '''
        Save inserts a record that was not kept.

        :param test_ctx: The bound repo tester context.
        :type test_ctx: object
        :param tmp_path: The pytest temporary directory.
        :type tmp_path: Path
        '''

        # Save into a file that does not exist yet.
        repo = test_ctx.make_target(config_file=str(tmp_path / 'saved.yml'))
        test_ctx.assert_save(repo)

    # * test: delete
    def test_delete(self, test_ctx, seeded_plot_file: str):
        '''
        Delete removes a kept id and succeeds for a missing id.

        :param test_ctx: The bound repo tester context.
        :type test_ctx: object
        :param seeded_plot_file: The seeded publication path.
        :type seeded_plot_file: str
        '''

        # Delete the seeded id, then a missing id.
        repo = test_ctx.make_target(config_file=seeded_plot_file)
        test_ctx.assert_delete(repo)
