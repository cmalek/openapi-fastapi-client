from string import Template
from typing import Any, Type

from .abstract import (
    AbstractManagerClassGenerator,
    AbstractManagerFileGenerator,
    AbstractMethodBuilder
)


class MethodBuilder(AbstractMethodBuilder):

    def get_template(self, info: dict[str, Any]) -> Template:
        if info["query_parameters"] and not info["path_parameters"]:
            function_str = Template(
                """    def $function_name(self, $function_params)$response_type:

        with self.session as session:
            response_obj = session.$method(url=f"{self.base_url}$url", params=params.dict(exclude_unset=True), $call_params)

        if response_obj.ok:
            return $return_response
        return None
"""
            )
        elif info["path_parameters"] and not info["query_parameters"]:
            function_str = Template(
                """    def $function_name(self, $function_params)$response_type:
        url = f"{self.base_url}$url"

        with self.session as session:
            response_obj = session.$method(url=url, $call_params)

        if response_obj.ok:
            return $return_response
        return None
"""
            )
        elif info["path_parameters"] and info["query_parameters"]:
            function_str = Template(
                """    def $function_name(self, $function_params)$response_type:
        url = f"{self.base_url}$url"

        with self.session as session:
            response_obj = session.$method(url=url, params=params.dict(exclude_unset=True), $call_params)

        if response_obj.ok:
            return $return_response
        return None
"""
            )
        else:
            function_str = Template(
                """    def $function_name(self, $function_params)$response_type:

        with self.session as session:
            response_obj = session.$method(url=f"{self.base_url}$url", $call_params)

        if response_obj.ok:
            return $return_response
        return None
"""
            )
        return function_str

    def build_response_type(self, info: dict[str, Any]) -> str:
        if info["response_obj"]:
            if info["is_list"]:
                return f"-> Optional[list[{info['response_obj']}]]"
            else:
                return f"-> Optional[{info['response_obj']}]"
        return "-> Any"

    def build_return_response(self, info: dict[str, Any]) -> str:
        if info["response_obj"]:
            if info["is_list"]:
                return f"[{info['response_obj']}(**obj) for obj in response_obj.json()]"
            else:
                return f"{info['response_obj']}(**response_obj.json())"
        return "response_obj.json()"


class ManagerClassGenerator(AbstractManagerClassGenerator):

    method_builder: Type[AbstractMethodBuilder] = MethodBuilder

    @property
    def session_method(self) -> str:
        return Template('''
    @property
    def session(self) -> requests.Session:
        """
        Build a :py:class:`requests.Session` object with the headers and
        proxies that were passed to the constructor.  This is used to make the
        requests to the API.

        Returns:
            A configured :py:class:`requests.Session` object
        """
        s = requests.Session()
        s.headers.update(self.headers or {})
        s.proxies.update(self.proxies or {})
        return s
        ''').substitute()


class ManagerFileGenerator(AbstractManagerFileGenerator):

    manager_class_generator: Type[AbstractManagerClassGenerator] = ManagerClassGenerator

    @property
    def imports(self) -> list[str]:
        _imports = super().imports
        _imports.append("import requests")
        return _imports
