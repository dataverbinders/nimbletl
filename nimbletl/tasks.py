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

import pyarrow as pa
import pyarrow.parquet as pq
import re
from time import sleep

from google.cloud import bigquery
from google.cloud import storage
import pandas as pd
import prefect
from prefect import task
from prefect.utilities.tasks import defaults_from_attrs
from prefect.tasks.gcp.bigquery import BigQueryLoadFile
from prefect.engine.signals import SKIP
from prefect.tasks.shell import ShellTask
from prefect.tasks.templates import StringFormatter
from prefect.triggers import all_successful
from prefect.engine.results import PrefectResult

from nimbletl.utilities import clean_python_name


@task
def curl_cmd(url: str, filepath: Union[str, Path], **kwargs) -> str:
    """Template for curl command to download file.

    Uses `curl -fL -o` that fails silently and follows redirects. 

    Example:
    ```
    from pathlib import Path

    from prefect import Parameter, Flow
    from prefect.tasks.shell import ShellTask

    curl_download = ShellTask(name='curl_download')

    with Flow('test') as flow:
        filepath = Parameter("filepath", required=True)
        curl_command = curl_cmd("https://some/url", filepath)
        curl_download = curl_download(command=curl_command)

    flow.run(parameters={'filepath': Path.home() / 'test.zip'})
    ```

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


def get_description(url_data_definition):
    """Getting the descriptions of columns from a data set given in url_data_definition.

    Args:
        - url_data_definition (str): url of DataProperties data set as String.

    Return:
        - dict{'column_name':'description'}
    """
    # Get JSON format of data set.
    url_data_info = "?".join((url_data_definition, "$format=json"))
    # print("Data Property:", url_data_info)

    data_info = requests.get(url_data_info).json() # Is of type dict()

    data_info_values = data_info["value"] # Is of type list

    dict_description = {}

    # Only dict's containing the key 'Key' has information about table columns.
    for i in data_info_values:
        if i["Key"] != "":
            # Make description shorter, since BigQuery only allows 1024 characters
            if i["Description"] is not None and len(i["Description"]) > 1024:
                i["Description"] = i["Description"][:1021] + "..."

            dict_description[i["Key"]] = i["Description"]


    return dict_description


@task(trigger=all_successful)
def column_descriptions(table_id, third_party=False, schema_bq="cbs", GCP=None):
    """Updates schema defined in schema_bq by adding column descriptions to 'TypedDataSet' tables in Google BigQuery.

    Args:
        - table_id (str): table ID like `83583NED`
        - third_party (boolean): 'opendata.cbs.nl' is used by default (False). Set to true for dataderden.cbs.nl
        - schema_bq (str): schema to load data into
        - GCP: config object
    """
    bq = bigquery.Client(project=GCP.project)

    base_url = {
        True: f"https://dataderden.cbs.nl/ODataFeed/odata/{table_id}?$format=json",
        False: f"https://opendata.cbs.nl/ODataFeed/odata/{table_id}?$format=json",
    }

    for i in requests.get(base_url[third_party]).json()["value"]:
        if "DataProperties" in i.values():
            url_data_properties = i["url"]

    table_typed = bq.get_table(f"{GCP.project}.{schema_bq}.{table_id}_TypedDataSet")

    new_schema = []
    descriptions = get_description(url_data_properties)

    # for i in table_schema:
    for i in table_typed.schema:
        # print("Name:", i.to_api_repr()['name'])
        # print("Field_type:", i.to_api_repr()['type'])
        # print("Description:", i.to_api_repr()['description'])

        if i.to_api_repr()['name'] not in descriptions:
            new_description = ""
        else:
            new_description = descriptions[i.to_api_repr()['name']]

        new_schema.append(
            bigquery.SchemaField(
                name=i.to_api_repr()['name'],
                field_type=i.to_api_repr()['type'],
                description=new_description
            )
        )

    table_typed.schema = new_schema
    bq.update_table(table_typed, ["schema"])


def table_description(url_table_infos):
    """Load table description to corresponding table in BigQuery.

    Args:
        - url_table_infos (str): url of the data set `TableInfos`
    
    Returns:
        - String: table_description
    """

    # Using TableInfos for the description of the tables.
    url_table_info = "?".join((url_table_infos, "$format=json"))
    table_info = requests.get(url_table_info).json()

    # Get the complete description from TableInfos.
    table_description = table_info["value"][0]["Description"]
    
    return table_description


@task
def cbsodatav3_to_gbq(id, third_party=False, schema="cbs", credentials=None, GCP=None):
    """Load CBS odata v3 into Google BigQuery.

    For given dataset id, following tables are uploaded into schema (taking `cbs` as default and `83583NED` as example):

    - cbs.83583NED_DataProperties: description of topics and dimensions contained in table
    - cbs.83583NED_DimensionName: separate dimension tables
    - cbs.83583NED_TypedDataSet: the TypedDataset
    - cbs.83583NED_CategoryGroups: grouping of dimensions

    See Handleiding CBS Open Data Services (v3)[^odatav3] for details.
    
    Args:
        - id (str): table ID like `83583NED`
        - third_party (boolean): 'opendata.cbs.nl' is used by default (False). Set to true for dataderden.cbs.nl
        - schema (str): schema to load data into
        - credentials: GCP credentials
        - GCP: config object

    Return:
        - List[google.cloud.bigquery.job.LoadJob] 

    [^odatav3]: https://www.cbs.nl/-/media/statline/documenten/handleiding-cbs-opendata-services.pdf
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

    # Need to append because API may return more than 1 rowset (max 10.000 rows per call)
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


@task(name="get_cbs_data", result=PrefectResult())
def cbsodatav3_to_gcs(id, third_party=False, schema="cbs", credentials=None, GCP=None, paths=None):
    """Load CBS odata v3 into Google Cloud Storage as Parquet.

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
        - Paths: config object for output directory

    Return:
        - Set: Paths to Parquet files
        - String: table_description
    """
    
    base_url = {
        True: f"https://dataderden.cbs.nl/ODataFeed/odata/{id}?$format=json",
        False: f"https://opendata.cbs.nl/ODataFeed/odata/{id}?$format=json",
    }
    urls = {
        item["name"]: item["url"]
        for item in requests.get(base_url[third_party]).json()["value"]
    }

    output = {
        True: paths.root / paths.tmp,
        False: paths.root / paths.cbs,
    }

    # Getting the description of the data set.
    data_set_description = table_description(urls["TableInfos"])

    gcs = storage.Client(project="dataverbinders")
    gcs_bucket = gcs.bucket(GCP.bucket)

    files_parquet = set()

    # TableInfos is redundant --> use https://opendata.cbs.nl/ODataCatalog/Tables?$format=json
    # UntypedDataSet is redundant --> use TypedDataSet
    for key, url in [
        (k, v) for k, v in urls.items() if k not in ("TableInfos", "UntypedDataSet")
    ]:
        url = "?".join((url, "$format=json"))
        table_name = f"{schema}.{id}_{key}"

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
                
                pq_dir = f"{output[third_party]}/{table_name}.parquet"

                # Add path of file to set, when data set contains information
                files_parquet.add(f"{table_name}.parquet")

                cbs_table = pa.Table.from_pandas(df)

                if i == 0:
                    # Have to append the lines, instead of overwrite.
                    # https://stackoverflow.com/questions/47113813/using-pyarrow-how-do-you-append-to-parquet-file/47114713
                    # Use gzip as compression, is one of the accepted compression types. With default level = 6.
                    pq_writer = pq.ParquetWriter(where=pq_dir, schema=cbs_table.schema, compression="gzip", compression_level=6)
                    
                # Write transformed df to the given file (pq_dir)
                pq_writer.write_table(cbs_table)
            
            # each request limited to 10,000 cells
            if "odata.nextLink" in r:
                i += 1
                url = r["odata.nextLink"]
            else:
                # Add upload to GCS here!!!
                pq_writer.close() # Close the Parquet Writer

                # Name of file in GCS.
                gcs_blob = gcs_bucket.blob(pq_dir.split("/")[-1])

                # Upload file to GCS from given location.
                gcs_blob.upload_from_filename(filename=pq_dir)
                
                url = None

    return files_parquet, data_set_description


def create_dataset(name, bq_client):
    """Creates new data set in Google BigQuery if this data set does not exist yet.

    Args:
        - name (str): Name of the data set
        - bq_client (google.cloud.bigquery.client.Client): Google BigQuery Client
    """
    dataset_id = f"{bq_client.project}.{name}"

    dataset_info = bigquery.Dataset(dataset_id)
    dataset_info.description="Test for creating new Data Set"

    bq_client.create_dataset(dataset_info, exists_ok=True)


@task(name="gcs_to_bq")
def gcs_to_bq(prefect_output, third_party=False, credentials=None, GCP=None):
    """Load Parquet files from Google Cloud Storage into Google BigQuery.

    Args:
        - prefect_output (tuple): Output of Task "cbsodatav3_to_gcs"
        - third_party (boolean): 'opendata.cbs.nl' is used by default (False). Set to true for dataderden.cbs.nl
        - credentials: GCP credentials
        - GCP: config object
    """

    awaiting_jobs = set()

    def callback(future):
        awaiting_jobs.discard(future.job_id)

    logger = prefect.context.get("logger")
    parquet_list = prefect_output[0]

    bq = bigquery.Client(project=GCP.project, location=GCP.location)

    # Create new Data Set if not already present.
    data_set_id = re.split(r'[._]', list(prefect_output[0])[0])[0]
    create_dataset(name=data_set_id, bq_client=bq)

    job_config = bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.PARQUET)
    job_config.destination_table_description=prefect_output[1]
    jobs = []

    for parquet_file in parquet_list:

        gcs_url = f"gs://{GCP.bucket}/{parquet_file}"
        table_name = parquet_file[:-8]
        bq.delete_table(table=table_name, not_found_ok=True)

        load_job = bq.load_table_from_uri(
            gcs_url,
            destination=table_name,
            project=GCP.project,
            job_config=job_config,
        )

        jobs.append(load_job)

        awaiting_jobs.add(load_job.job_id)
        load_job.add_done_callback(callback)
    

    while awaiting_jobs:
        logger.info(f"{len(awaiting_jobs)} remaining data set(s) loading into BQ.... ")
        sleep(1)
    

    logger.info("The data sets have been loaded into BQ")
    
