from string import Template
from typing import Optional, Any

from openapi_fastapi_client.helpers import TYPE_CONVERTION, operation_id_to_function_name


class OpenAPIParameterParser:
    """
    A class to parse OpenAPI parameters into appropriate python type definitions
    and :py:class:`pydantic.BaseModel` definitions.
    """

    def parse_path_parameter(self, url: str, parameter: dict[str, Any]) -> tuple:
        # Make a python compatible name for the parameter.
        name = operation_id_to_function_name(parameter["name"])
        ptype = parameter["schema"]["type"]
        # Replace the parameter name in the url with the the updated name,
        # above.  This is so that we can map the name we use in the code to
        # the proper path parameter in the url.
        url = url.replace(parameter["name"], name)
        return url, f"{name}: {TYPE_CONVERTION[ptype]}"

    def parse_query_parameter(self, parameter: dict[str, Any]) -> str:
        if parameter.get("required"):
            param_str: str = f"{parameter['name']}: {TYPE_CONVERTION[parameter['schema']['type']]}"
        else:
            param_str = f"{parameter['name']}: Optional[{TYPE_CONVERTION[parameter['schema']['type']]}] = None"
        return Template(
            """#: $description
        $param_str"""
        ).substitute(
            description=parameter.get("description", "The parameter description is missing"),
            param_str=param_str,
        )

    def parse(self, url: str, method_def: dict[str, Any]) -> tuple:
        path_parameters = set()
        query_parameters = set()
        if parameters := method_def.get("parameters"):
            for parameter in parameters:
                if parameter["in"] == "path":
                    url, param_def = self.parse_path_parameter(url, parameter)
                    path_parameters.add(param_def)
                elif parameter["in"] == "query":
                    query_parameters.add(self.parse_query_parameter(parameter))
        return url, path_parameters, query_parameters


class OpenAPIRequestObjectParser:
    @staticmethod
    def parse(method_def: dict[str, Any]) -> str:
        """
        Parse the request object definition from ``method_def``.

        Args:
            method_def: the method definition we're parsing

        Returns:
            The request object definition
        """
        if request_body := method_def.get("requestBody"):
            if json_data := request_body["content"].get("application/json"):
                if "items" in json_data["schema"]:
                    obj_name = json_data["schema"]["items"]["$ref"].split("/")[-1]
                    return f"list[{obj_name}]"
                else:
                    return json_data["schema"].get("$ref", "Any").split("/")[-1]
        return ""


class OpenAPIResponseObjectParser:
    @staticmethod
    def parse(method_def: dict[str, Any]) -> dict[str, Any]:
        response_obj: Optional[str] = ""
        is_list: bool = False
        if responses := method_def.get("responses"):
            for content in responses.values():
                if resp_content := content.get("content"):
                    if "items" in resp_content["application/json"]["schema"]:
                        response_ref = resp_content["application/json"]["schema"]["items"].get(
                            "$ref", "Any"
                        )
                        is_list = True
                    elif "$ref" in resp_content["application/json"]["schema"]:
                        response_ref = resp_content["application/json"]["schema"]["$ref"]
                    elif (
                        "additionalProperties" in resp_content["application/json"]["schema"]
                        and "type"
                        in resp_content["application/json"]["schema"]["additionalProperties"]
                    ):
                        response_ref = TYPE_CONVERTION[
                            resp_content["application/json"]["schema"]["additionalProperties"][
                                "type"
                            ]
                        ]
                    else:
                        try:
                            response_ref = TYPE_CONVERTION[
                                resp_content["application/json"]["schema"]["type"]
                            ]
                        except KeyError:
                            continue

                    if response_ref.split("/")[-1] in ("NoneType", "Metaclass"):
                        response_obj = None
                    else:
                        response_obj = response_ref.split("/")[-1]
        return {"response_obj": response_obj, "is_list": is_list}


class QueryParamTypedictGenerator:
    """
    Generate a :py:class:`pydantic.BaseModel` definition for the query
    parameters of a given endpoint.  This class definition will be saved in the
    schema file.

    Args:
        tag: The tag of the endpoint we're generating the query parameters for
        func_name: The name of the function we're generating the query
            parameters for
        params: The query parameters of the endpoint we're generating the query
            parameters for.

    Returns:
        The string representation of the class definition for the query
        parameters
    """

    @staticmethod
    def generate(
        tag: str, manager_class_name: str, func_name: str, params: set[str]
    ) -> tuple[str, str]:
        # Make a python compatible name for the tag.
        tag_name = tag.title().replace("_", "").replace(" ", "") + "Query"
        # Make a python compatible name for the pydantic class.
        cls_name = tag_name + func_name.title().replace("_", "").replace(" ", "") + "Query"
        description = (
            "A model that holds all the query parameters for the "
            f":py:meth:`{manager_class_name}.{func_name}` method."
        )
        request_str = Template(
            '''class $cls_name(BaseModel):
        """
        $description
        """
        $params'''
        ).substitute(cls_name=cls_name, description=description, params="\n\t".join(params))
        return request_str, cls_name
