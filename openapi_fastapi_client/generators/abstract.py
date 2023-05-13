from pathlib import Path
import re
from string import Template
from typing import Type, Any

import black
import isort

from ..helpers import operation_id_to_function_name

from .generic import (
    OpenAPIParameterParser,
    OpenAPIRequestObjectParser,
    OpenAPIResponseObjectParser,
    QueryParamTypedictGenerator
)


class AbstractMethodBuilder:

    def build_method_args(self, info: dict[str, Any]) -> list[str]:
        """
        Build the list of args and kwargs for the method signature.

        Args:
            info: the function info dict

        Returns:
            A list of strings with the args and kwargs for the method signature.
        """
        method_args: list[str] = []
        if info["request_obj"]:
            method_args.extend([f'req_data: {info["request_obj"]}'])
        if info["path_parameters"]:
            method_args.append(", ".join(info["path_parameters"]))
        if info["query_parameters"]:
            method_args.append(f"params: {info['query_parameters']}")
        method_args.append("**kwargs")
        return method_args

    def build_request_call_args(self, info: dict[str, Any]) -> list[str]:
        """
        Build the args and kwargs for the ``requests`` or ``aiohttp.client``
        method invocation.

        Args:
            info: the function info dict

        Returns:
            The args and kwargs method call to hit the API endpoint.
        """
        requests_call_args = []
        if info["request_obj"]:
            requests_call_args.append("json=req_data.dict(exclude_unset=True)")
        requests_call_args.extend(["**kwargs"])
        return requests_call_args

    def build_response_type(self, info: dict[str, Any]) -> str:
        if info["response_obj"]:
            if info["is_list"]:
                return f"-> Optional[list[{info['response_obj']}]]"
            else:
                return f"-> Optional[{info['response_obj']}]"
        return "-> Any"

    def build_return_response(self, info: dict[str, Any]) -> str:
        raise NotImplementedError

    def get_template(self, info: dict[str, Any]) -> Template:
        raise NotImplementedError

    def build(self, info: dict[str, Any]) -> str:
        method_str = self.get_template(info)
        return method_str.substitute(
            function_name=info["function_name"],
            function_params=", ".join(self.build_method_args(info)),
            response_type=self.build_response_type(info),
            return_response=self.build_return_response(info),
            url=info["url"],
            method=info["method"],
            call_params=", ".join(self.build_request_call_args(info)),
        )


class AbstractManagerClassGenerator:

    #: The class for the method builder we're using to build our
    #: manager methods Python code
    method_builder: Type[AbstractMethodBuilder]

    def __init__(self, tag: str, paths: dict) -> None:
        #: The OpenAPI tag of the endpoint we're generating the manager for
        self.tag = tag
        #: the schema.yaml path structs
        self.paths: dict = paths
        #: A set of all the imports we need to reference the query parameter
        #: data classes in this class
        self.schema_imports: set = set()
        #: A list of query param data classes that are used by our methods.
        #: These will be added to the ``schemas.py`` file, and imported in the
        #: file this Manager will be generated in.
        self.schema_classes: list = []

    @property
    def class_name(self) -> str:
        """
        Return the name for the manager class.
        """
        return self.tag.title().replace(" ", "").replace("_", "") + "Manager"

    def get_function_name(self, method_def: dict[str, Any]) -> str:
        """
        Build a human friendly function name from the ``operationId`` of the
        method definition.

        Args:
            tag: the tag of the endpoint method we're generating the function
                name for
            method_def: the method definition from the schema file

        Returns:
            A human friendly function name
        """
        function_name: str = operation_id_to_function_name(method_def["operationId"])
        function_name = re.sub(f"^{self.tag}_", "", function_name).lower()
        return function_name

    def get_method(
        self, url: str, method: str, method_def: dict[str, Any]
    ) -> str:
        info = {
            "url": url,
            "method": method,
            "function_name": self.get_function_name(method_def),
            "path_parameters": set(),
            "query_parameters": "",
            "request_obj": OpenAPIRequestObjectParser.parse(method_def),
            "application_type": "application/json",
            "response_obj": "",
            "is_list": False,
        }
        info.update(OpenAPIResponseObjectParser.parse(method_def))
        info.update(self.parse_parameters(url, method_def))
        return self.method_builder().build(info)

    def parse_parameters(
        self, url: str, method_def: dict[str, Any]
    ) -> dict[str, Any]:
        if "parameters" in method_def:
            url, path_parameters, query_parameters = OpenAPIParameterParser().parse(url, method_def)
            info = {
                "url": url,
                "path_parameters": path_parameters,
            }
            if query_parameters:
                schema_class, schema_name = QueryParamTypedictGenerator.generate(
                    self.tag, self.class_name, self.get_function_name(method_def), query_parameters
                )
                self.schema_imports.add(schema_name)
                self.schema_classes.append(schema_class)
                info["query_parameters"] = schema_name
            return info
        return {}

    def tag_name(self, method_def: dict[str, Any]) -> str:
        """
        Extract the raw tag name from ``method_def``.

        Args:
            method_def: the method definition to extract the tag from

        Returns:
            The raw tag name
        """
        return method_def["tags"][0].replace(" ", "")

    def is_tag(self, method_def: dict[str, Any]) -> bool:
        """
        Return ``True`` if we should process this method definition.

        Args:
            method_def: the method definition to check

        Returns:
            ``True`` if ``method_def`` has the tag ``tag``
        """
        return self.tag_name(method_def) == self.tag

    @property
    def session_method(self) -> str:
        raise NotImplementedError

    @property
    def methods(self) -> list[str]:
        """
        Iterate through all the paths, and collect all (path, HTTP method) pairs
        that have the ``tag`` in their ``tags`` key.  Build a Manager class that
        collects all those paths as methods and associates with the schema.

        Args:
            class_name: the name of the Manager class we're generating

        Returns:
            A list of module code strings
        """
        methods: list[str] = []
        methods.append(self.session_method)
        for url, definition in self.paths.items():
            # At this point, url is the path of the API endpoint we're
            # interested in, and definition is the definition of that endpoint,
            # which includes the HTTP method, the parameters, the request body,
            for method, method_def in definition.items():
                if self.is_tag(method_def):
                    methods.append(self.get_method(url, method, method_def))
        return methods

    def generate(self) -> str:
        class_str = Template(
            '''
class $class_name:
    """
    This manager class is used to gather methods that call the API endpoints
    that are associated with the ``$tag`` tag in the OpenAPI specification.

    Args:
        base_url: the base URL of the API

    Keyword Args:
        headers: any headers to send with the requests
        proxies: any proxies to use when making the requests
    """
    #: The OpenAPI tag that this manager is associated with
    openapi_tag: Final[str] = "$tag"

    def __init__(
        self,
        base_url: str,
        headers: Optional[dict[str, str]] = None,
        proxies: Optional[dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url
        self.headers = headers
        self.proxies = proxies

$methods

'''
        )
        cls = class_str.substitute(
            class_name=self.class_name,
            tag=self.tag,
            methods="\n\n".join(self.methods),
        )
        return cls


class AbstractManagerFileGenerator:

    #: The implementation specific class that generates the code for the Manager
    #: class
    manager_class_generator: Type[AbstractManagerClassGenerator]

    def __init__(self, paths: dict, tag: str):
        """
        Generate a python file that contains a Manager class for a the methods
        in ``paths`` which are tagged with ``tag``.

        Args:
            paths: path definitions from the OpenAPI specification
            tag: The OpenAPI tag to use to filter methods
        """
        # The contents of the python file
        self.__file_contents: list[str] = []
        #: The paths from the OpenAPI specification
        self.paths: dict[str, Any] = paths
        #: The OpenAPI tag that this manager is associated with.  This is used
        #: to identify methods in the OpenAPI specification that should be
        #: attached to this manager
        self.tag: str = tag

        # Outputs

        #: Python class definitions for any schema classes that were generated
        #: while parsing the OpenAPI specification for this manager
        self.schema_definitions: list[str] = []

    @property
    def imports(self) -> list[str]:
        return ["from typing import Any, Final, Optional", "\n"]

    def get_component_obj_name(self, data: dict) -> str | None:
        if json_body := data["content"].get("application/json"):
            if "items" in json_body["schema"]:
                return json_body["schema"]["items"].get("$ref", "Any")
            elif "$ref" in json_body["schema"]:
                return json_body["schema"]["$ref"]
        return None

    @property
    def schema_imports(self) -> set[str]:
        schema_imports: set[str] = set()
        for level_0 in self.paths.values():
            for val in level_0.values():
                tag_name = val["tags"][0].replace(" ", "")
                if tag_name != self.tag:
                    continue
                if response := val.get("responses"):
                    for resp_val in response.values():
                        if "content" in resp_val:
                            component_ref = self.get_component_obj_name(resp_val)
                            if component_ref:
                                schema_imports.add(component_ref.split("/")[-1])
                if request_body := val.get("requestBody"):
                    component_ref = self.get_component_obj_name(request_body)
                    if component_ref:
                        schema_imports.add(component_ref.split("/")[-1])
        return schema_imports

    def generate(self, schema_path: str) -> None:
        class_generator = self.manager_class_generator(self.tag, self.paths)
        # The body of our class
        cls = class_generator.generate()
        # The imports for things we're not generating
        self.__file_contents.extend(self.imports)
        # Add the Python code for the schema classes that were generated during
        # manager generation to our list of schema classes to hand upstream.  These
        # will be written to the schema.py file.
        self.schema_definitions.extend(class_generator.schema_classes)
        # Our own imports
        schema_imports = self.schema_imports.union(class_generator.schema_imports)
        objs_str = ",\n".join(
            [
                obj
                for obj in schema_imports
                if obj not in ("AnyType", "Metaclass", "NoneType", "Any")
            ]
        )
        if objs_str:
            data = [
                f"from {schema_path} import ({objs_str})",
                "\n",
            ] + self.__file_contents
            data.append("\n")
            self.__file_contents = data
        self.__file_contents.append(cls)

    def write(self, folder_path: Path):
        text = black.format_str("\n".join(self.__file_contents), mode=black.Mode())
        #text = "\n".join(self.__file_contents)
        file = folder_path / Path(f"{self.tag.lower()}.py")
        file.write_text(text)
        isort.api.sort_file(file)
