from pathlib import Path
from typing import Optional

import typer
import yaml

from .project import ProjectGenerator

app = typer.Typer()


@app.command()
def main(
    openapi_file: Path,
    destination: Path,
    module_name: str,
    async_req: Optional[bool] = typer.Option(
        False, "--async", help="All requests to the client are asynchronous with aiohttp."
    ),
):
    if not openapi_file.exists():
        raise FileNotFoundError(f"{openapi_file} does not exists.")

    with openapi_file.open("r") as yaml_file:
        openapi_schema = yaml.load(yaml_file, Loader=yaml.CFullLoader)

    project = ProjectGenerator(
        destination,
        module_name,
        openapi_schema,
        "aiohttp" if async_req else "requests",
    )
    project.generate()
