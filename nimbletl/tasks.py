"""Module with prefects utility functions and tasks.

Use `prefect.task` to a function into a task in your dataflow pipeline, for example:

```python
unzip_task = task(unzip)
```
"""

import datetime
from pathlib import Path
from typing import Union, Any
from zipfile import ZipFile

import cbsodata
import pandas as pd
from prefect import task
from prefect.utilities.tasks import defaults_from_attrs
from prefect.engine.signals import SKIP
from prefect.tasks.shell import ShellTask
from prefect.tasks.templates import StringFormatter

from nimbletl.utilities import clean_python_name


@task
def curl_cmd(url: str, filepath: Union[str, Path], **kwargs) -> str:
    """Template for curl command to download file.

    Uses `curl -fL -o` that fails silently and follows redirects. 

    Example:
        from pathlib import Path

        from prefect import Parameter, Flow
        from prefect.tasks.shell import ShellTask

        curl_download = ShellTask(name='curl_download')

        with Flow('test') as flow:
            filepath = Parameter("filepath", required=True)
            curl_command = curl_cmd("https://some/url", filepath)
            curl_download = curl_download(command=curl_command)
    
        flow.run(parameters={'filepath': Path.home() / 'test.zip'})
    
    Args:
        - url (str): url to download
        - file (str): file for saving fecthed url
        - **kwargs: passed to Task constructor
    
    Returns:
        str: curl command
    
    Raises:
        - SKIP: if filepath exists
    """
    if Path(filepath).exists():
        raise SKIP(f"File {filepath} already exists.")
    return f"curl -fL -o {filepath} {url}"


def cbsodata_to_gbq(
    identifier=None, destination_table=None, credentials=None, GCP=None
):
    """Loads table from CBS ODATA into BigQuery.
  
    Column names are converted to `clean_python_name`. Existing tables are replaced.

    Args:
        - identifier (str): CBS ODATA identifier
        - destination_table (str): name of destination table in BigQuery in format `dataset.tablename`
        - credentials (google.auth.credentials.Credentials): credentials for project and BigQuery
        - GCP (dataclass): configuration object with `project` and `location` attributes

    Returns:
        None
  
  """
    # TODO: add kwarg jaar to add verslagjaar as partition or column to allow different versions
    df = (
        pd.DataFrame(cbsodata.get_data(identifier))
        .rename(columns=clean_python_name)
        .to_gbq(
            destination_table,
            project_id=GCP.project,
            credentials=credentials,
            if_exists="replace",
            location=GCP.location,
        )
    )


def excel_to_gbq(io=None, destination_table=None, credentials=None, GCP=None):
    """Load Excel to BigQuery.

    Args:
        - io: str, bytes, ExcelFile, xlrd.Book, path object, or file-like object passed to `pandas.read_excel`
        - destination_table (str): name of destination table in BigQuery in format `dataset.tablename`      
        - credentials (google.auth.credentials.Credentials): credentials for project and BigQuery
        - GCP (dataclass): configuration object with `project` and `location` attributes
    
    Returns:
        - None
    """
    pd.read_excel(io).rename(columns=clean_python_name).to_gbq(
        io,
        destination_table,
        project_id=GCP.project,
        credentials=credentials,
        if_exists="replace",
        location=GCP.location,
    )


def unzip(zipfile):
    """Extracts zipfile from path in the same directory.

    Replaces original zipfile with empty file, so downstream tasks know the file is there.

    Args:
        - path: Path-object to zipfile
        - zipfile

    Returns:
        Path-objects of extracted files
    """
    with ZipFile(zipfile) as zip:
        zip.extractall(path=zipfile.parent)
        files = [zipfile.parent / f for f in zip.namelist()]

    zipfile.unlink()
    zipfile.touch()
    return files


def create_dir(path: Path) -> Path:
    """Checks whether path exists and is directory, and creates it if not.
    
    Args:
        - path (Path): path to check
    
    Returns:
        - Path: new directory
    """
    try:
        path = Path(path)
        if not (path.exists() and path.is_dir()):
            path.mkdir(parents=True)
        return path
    except TypeError as error:
        print(f"Error trying to find {path}: {error!s}")
        return None

