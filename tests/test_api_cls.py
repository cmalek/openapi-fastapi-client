from pathlib import Path

import pytest

from openapi_fastapi_client.api import ManagerFileGenerator


def test_create_api_instance(openapi_paths):
    api = ManagerFileGenerator(openapi_paths, "http://localhost:8080", "pet")
    assert not api._file_contents  # empty on creation
    assert not api.schema_imports  # empty on creation
    assert not api.schema_classes  # empty on creation

    assert api.paths == openapi_paths
    assert api.base_url == "http://localhost:8080"


def test_create_api_instance_with_url_ending_with_slash_removes_slash(openapi_paths):
    api = ManagerFileGenerator(openapi_paths, "http://localhost:8080/", "pet")
    assert api.base_url == "http://localhost:8080"


@pytest.mark.parametrize("client_kind", (None, "sync", "async"))
def test_base_imports(example_api, client_kind):

    if client_kind:
        assert example_api.generate_base_imports(client_kind) is None
    else:
        assert example_api.generate_base_imports() is None

    if client_kind is None or client_kind == "sync":
        # default is synchronous
        assert "import requests" in example_api.data
    else:
        assert "import aiohttp" in example_api.data

    assert "from typing import Any, Optional" in example_api.data
    assert "BASE_URL = 'http://localhost:8080'" in example_api.data


@pytest.mark.parametrize("client_kind", ("sync", "async"))
def test_create_valid_api_file(example_api, test_folder, create_dummy_schema_cls, client_kind):
    example_api.generate_apis(".pet_test_store.schema", client_kind=client_kind)
    example_api.write_api(test_folder)
    assert (test_folder / Path("pet.py")).exists()
    with (test_folder / Path("pet.py")).open("r") as file:
        exec(file.read(), globals(), {})
