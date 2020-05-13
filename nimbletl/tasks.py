"""Module with prefects utilities tasks."""

import datetime
from pathlib import Path
from zipfile import ZipFile

from prefect import task
from prefect.engine.signals import SKIP
from prefect.tasks.shell import ShellTask


@task
def curl_cmd(url: str, file: str) -> str:
    """
    Generate the curl command for downloading url to file.

    Uses `curl -fL -o` that fails silently and follows redirects. 

    Args:
        - url (str): url to download
        - file (str): file for saving fecthed url

    Returns:
        str: curl cmd
    
    Raises:
        - SKIP: if file exists
    """
    if Path(file).exists():
        raise SKIP("File already exists.")
    return f"curl -fL -o {file} {url}"


# ShellTask is a task from the Task library which will execute a given command in a subprocess
# and fail if the command returns a non-zero exit code
download = ShellTask(
    name="curl_task", max_retries=2, retry_delay=datetime.timedelta(seconds=10)
)


@task
def unzip(zipfile):
    """
    Extracts zipfile from path in the same directory.

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


@task
def create_dir(path: Path) -> Path:
    """
    Checks whether path exists and is directory, and creates it if not.
    
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
    