"""Module with prefects utility functions and tasks.

Use `prefect.task` to a function into a task in your dataflow pipeline, for example:

.. code:: python

    unzip_task = task(unzip)

"""

import datetime
from pathlib import Path
import requests
from typing import Union, Any
from zipfile import ZipFile

from google.cloud import bigquery
import pandas as pd
import prefect
from prefect import task
from prefect.utilities.tasks import defaults_from_attrs
from prefect.tasks.gcp.bigquery import BigQueryLoadFile
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


def excel_to_gbq(io=None, destination=None, credentials=None, GCP=None):
    """Load Excel to BigQuery.

    Args:
        - io: str, bytes, ExcelFile, xlrd.Book, path object, or file-like object passed to `pandas.read_excel`
        - destination_table (str): name of destination table in BigQuery in format `dataset.tablename`      
        - credentials (google.auth.credentials.Credentials): credentials for project and BigQuery
        - GCP (dataclass): configuration object with `project` and `location` attributes
    
    Returns:
        - google.cloud.bigquery.job.LoadJob
    """
    df = pd.read_excel(io).rename(columns=clean_python_name)
    bq = bigquery.Client(credentials=credentials, project=GCP.project)
    job_config = bigquery.LoadJobConfig()
    job_config.write_disposition= "WRITE_TRUNCATE"
    job = bq.load_table_from_dataframe(
        dataframe=df,
        destination=destination_table,
        job_config=job_config,
        credentials=credentials,
        project=GCP.project,
        location=GCP.location,
    )
    return job


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


def table_description(url_table_infos):
    # Using TableInfos for the description of the tables.
    url_table_info = "?".join((url_table_infos, "$format=json"))
    table_info = requests.get(url_table_info).json()

    # Get the short description from TableInfos.
    table_description = table_info["value"][0]["ShortDescription"]

    # Get the complete description from TableInfos.
    # big_table_description = table_info["value"][0]["Description"]
    
    return table_description


def cbsodatav3_to_gbq(id, third_party=False, schema="cbs", credentials=None, GCP=None):
    """Load CBS odata v3 into Google BigQuery.

    For given dataset id, following tables are uploaded into schema (taking `cbs` as default and `83583NED` as example):
        - ``cbs.83583NED_DataProperties``: description of topics and dimensions contained in table
        - ``cbs.83583NED_DimensionName``: separate dimension tables
        - ``cbs.83583NED_TypedDataSet``: the TypedDataset
        - ``cbs.83583NED_CategoryGroups``: grouping of dimensions

    See `Handleiding CBS Ope Data Services (v3) <https://www.cbs.nl/-/media/statline/documenten/handleiding-cbs-opendata-services.pdf>`_ for details.
    
    Args:
        - id (str): table ID like `83583NED`
        - third_party (boolean): 'opendata.cbs.nl' is used by default (False). Set to true for dataderden.cbs.nl
        - schema (str): schema to load data into
        - credentials: GCP credentials
        - GCP: config object

    Return:
        - List[google.cloud.bigquery.job.LoadJob] 
    """
    
    base_url = {
        True: f"https://dataderden.cbs.nl/ODataFeed/odata/{id}?$format=json",
        False: f"https://opendata.cbs.nl/ODataFeed/odata/{id}?$format=json",
    }
    urls = {
        item["name"]: item["url"]
        for item in requests.get(base_url[third_party]).json()["value"]
    }

    bq = bigquery.Client(project=GCP.project)
    job_config = bigquery.LoadJobConfig()
    job_config.write_disposition = "WRITE_APPEND"
    job_config.destination_table_description=table_description(urls["TableInfos"])
    jobs = []

    # TableInfos is redundant --> use https://opendata.cbs.nl/ODataCatalog/Tables?$format=json
    # UntypedDataSet is redundant --> use TypedDataSet
    for key, url in [
        (k, v) for k, v in urls.items() if k not in ("TableInfos", "UntypedDataSet")
    ]:
        url = "?".join((url, "$format=json"))
        table_name = f"{schema}.{id}_{key}"
        bq.delete_table(table=table_name, not_found_ok=True)

        i = 0
        while url:
            logger = prefect.context.get("logger")
            logger.info(f"Processing {key} (i = {i}) from {url}")
            r = requests.get(url).json()

            # odata api contains empty lists as values --> skip these
            if r["value"]:
                # DataProperties contains column odata.type --> odata_type
                df = pd.DataFrame(r["value"]).rename(
                    columns=lambda s: s.replace(".", "_")
                )
                jobs.append(
                    bq.load_table_from_dataframe(
                        df,
                        destination=table_name,
                        project=GCP.project,
                        job_config=job_config,
                    )
                )

            # each request limited to 10,000 cells
            if "odata.nextLink" in r:
                i += 1
                url = r["odata.nextLink"]
            else:
                url = None
    return jobs
