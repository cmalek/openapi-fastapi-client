from pathlib import Path
from typing import Any, Type, Literal

from .schema import Schema
from .generators import requests, aiohttp
from .generators.abstract import AbstractManagerFileGenerator


class ProjectGenerator:
    """
    This class is the top level generator for the entire Python API
    client project.  It is responsible for generating the module folder
    and all of its contents.

    Args:
        module_name: what to name the Python module
        openapi_schema: the contents of our OpenAPI schema file as a python dict
    """

    generators: dict[str, Type[AbstractManagerFileGenerator]] = {
        'requests': requests.ManagerFileGenerator,
        'aiohttp': aiohttp.ManagerFileGenerator,
    }

    def __init__(
        self,
        destination: Path,
        module_name: str,
        openapi_schema: dict[str, Any],
        client_type: Literal["requests", "aiohttp"] = 'requests',
    ) -> None:
        self.module_name = module_name
        self.destination = destination
        self.module_path = destination / Path(module_name)
        self.managers_path = self.module_path / Path("managers")
        self.models_path = self.module_path / Path("models.py")
        self.openapi_schema = openapi_schema
        self.client_type = client_type

        self.schema_definitions: list[str] = []

    @property
    def openapi_tags(self) -> list[str]:
        """
        Return the all unique tags from all paths in the OpenAPI schema.

        Returns:
            A list of unique tags from all paths in the OpenAPI schema
        """
        return list(set(
            [
                val_obj["tags"][0].replace(" ", "")
                for url, val in self.paths.items()
                for key, val_obj in val.items()
            ]
        ))

    @property
    def paths(self) -> dict[str, Any]:
        """
        Return the paths object from the OpenAPI schema.

        Returns:
            The paths object from the OpenAPI schema
        """
        return self.openapi_schema["paths"]

    @property
    def schemas(self) -> dict[str, Any]:
        """
        Return the schemas object from the OpenAPI schema.

        Returns:
            The schemas object from the OpenAPI schema
        """
        return self.openapi_schema["components"]["schemas"]

    @property
    def manager_generator_class(self) -> Type[AbstractManagerFileGenerator]:
        """
        Return the manager generator class for the client type.

        Returns:
            The manager generator class for the client type
        """
        return self.generators[self.client_type]

    def make_python_module(self, path: Path) -> None:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            init_py = path / Path("__init__.py")
            with init_py.open("w") as file:
                file.write("\n")

    def generate_module(self) -> None:
        """
        Geenrate the top level module file structure.
        """
        self.make_python_module(self.module_path)
        self.make_python_module(self.managers_path)

    def generate_managers(self) -> None:
        """
        Generate all our manager files.
        """
        for tag in self.openapi_tags:
            manager_file = self.manager_generator_class(self.paths, tag=tag)
            manager_file.generate(schema_path="..models")  # type: ignore
            self.schema_definitions.extend(manager_file.schema_definitions)
            manager_file.write(self.managers_path)

    def generate_models(self) -> None:
        """
        Generate our ``models.py`` file

        .. note::

            This needs to come after generating the managers with
            :py:meth:`generate_managers`, because in building the managers
            we will discover more schemas that need to be included.
        """
        schema = Schema(self.schemas)
        schema.generate()
        schema.schema_definitions.extend(self.schema_definitions)
        schema.write(self.models_path)

    def generate(self) -> None:
        """
        Generate the Python API client project.
        """
        self.generate_module()
        # This needs to come before generating the models.py file, because
        # in building the managers we will discover mode schemas that need
        # to be included
        self.generate_managers()
        self.generate_models()
