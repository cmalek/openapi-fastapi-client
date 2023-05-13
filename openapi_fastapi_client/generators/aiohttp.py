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
                """    async def $function_name(self, $function_params)$response_type:

        async with self.session as session:
            async with session.$method(f"{self.base_url}$url", params=params.dict(exclude_unset=True), $call_params) as resp:
                if resp.ok:
                    $return_response
                else:
                    return None
"""
            )
        elif info["path_parameters"] and not info["query_parameters"]:
            function_str = Template(
                """    async def $function_name(self, $function_params)$response_type:

        url = f"{self.base_url}$url"
        async with self.session as session:
            async with session.$method(url, $call_params) as resp:
                if resp.ok:
                    $return_response
                else:
                    return None
"""
            )
        elif info["path_parameters"] and info["query_parameters"]:
            function_str = Template(
                """    async def $function_name(self, $function_params)$response_type:

        url = f"{self.base_url}$url"
        async with self.session as session:
            async with session.$method(url, params=params.dict(exclude_unset=True), $call_params) as resp:
                if resp.ok:
                    $return_response
                else:
                    return None
"""
            )
        else:
            function_str = Template(
                """    async def $function_name(self, $function_params)$response_type:

        async with self.session as session:
            async with session.$method(f"{self.base_url}$url", $call_params) as resp:
                if resp.ok:
                    $return_response
                else:
                    return None
"""
            )
        return function_str

    def build_return_response(self, info: dict[str, Any]) -> str:
        if info["response_obj"]:
            if info["is_list"]:
                return Template(
                    """data = await resp.json()
                    return [$resp_obj(**obj) for obj in data]"""
                ).substitute(resp_obj=info["response_obj"])
            else:
                return Template(
                    """data = await resp.json()
                    return $resp_obj(**data)"""
                ).substitute(resp_obj=info["response_obj"])
        return Template("""return await resp.json()""").substitute()


class ManagerClassGenerator(AbstractManagerClassGenerator):

    method_builder: Type[AbstractMethodBuilder] = MethodBuilder

    @property
    def session_method(self) -> str:
        return Template('''
    @property
    def session(self) -> aiohttp.ClientSession:
        """
        Build a :py:class:`aiohttp.ClientSession` object with the headers and
        proxies that were passed to the constructor.  This is used to make the
        requests to the API.

        Returns:
            A configured :py:class:`aiohttp.ClientSession` object
        """
        return aiohttp.ClientSession(headers=self.headers)
        ''').substitute()


class ManagerFileGenerator(AbstractManagerFileGenerator):

    manager_class_generator: Type[AbstractManagerClassGenerator] = ManagerClassGenerator

    @property
    def imports(self) -> list[str]:
        _imports = super().imports
        _imports.append("import aiohttp")
        return _imports
