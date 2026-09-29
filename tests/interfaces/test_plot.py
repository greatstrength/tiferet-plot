"""Tests for the renderer service contract."""

# *** imports

# ** core
import ast
import inspect
from pathlib import Path

# ** infra
import pytest

# ** app
from tiferet_plot.interfaces.plot import RendererService
import tiferet_plot.interfaces.plot as interface_module

# *** functions

# ** function: imported_modules
def imported_modules(module) -> list:
    '''
    List modules imported by a source file.

    :param module: The imported module to inspect.
    :type module: module
    :return: Imported module names.
    :rtype: list
    '''

    # Parse the module source rather than trusting a substring search.
    source = Path(module.__file__).read_text()
    tree = ast.parse(source)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)

    # Return the imported module names.
    return names

# *** tests

# ** test: renderer_service_does_not_import_matplotlib
def test_renderer_service_does_not_import_matplotlib():
    '''
    The renderer contract does not import a drawing tool.
    '''

    # The interface names a picture, not a figure class or a library.
    imported = ' '.join(imported_modules(interface_module))
    assert 'matplotlib' not in imported
    assert 'domain' not in imported
    assert 'repos' not in imported
    source = Path(interface_module.__file__).read_text()
    assert 'Figure' not in source
    assert 'PlotService' not in source

# ** test: render_returns_bytes_and_takes_only_a_plot
def test_render_returns_bytes_and_takes_only_a_plot():
    '''
    render(plot) returns bytes. It does not take a path or a store.
    '''

    # The contract is one plot in, PNG bytes out.
    signature = inspect.signature(RendererService.render)
    assert list(signature.parameters) == ['self', 'plot']
    assert signature.return_annotation is bytes

    # The contract is not a usable renderer by itself.
    with pytest.raises(TypeError):
        RendererService()
