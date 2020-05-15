"""
Module with prefects utility functions and tasks.

Use `prefect.task` to a function into a task in your dataflow pipeline, for example:

```python
unzip_task = task(unzip)
```
"""

import datetime
from pathlib import Path
from typing import Union, Any
from zipfile import ZipFile

from prefect import task
from prefect.utilities.tasks import defaults_from_attrs
from prefect.engine.signals import SKIP
from prefect.tasks.shell import ShellTask


class CurlDownloadTask(ShellTask):
    """
    Task for downloading file using curl.

    Uses `curl -fL -o` that fails silently and follows redirects. 

    Args:
        - url (str): url to download
        - file (str): file for saving fecthed url
        - **kwargs: additional keyword arguments to pass to the ShellTask constructor

    Returns:
        - Path: path to downloaded file
    
    Raises:
        - SKIP: if file exists
    """

    def __init__(self, url: str = None, filepath: Union[str, Path] = None, **kwargs: Any):
        self.url = url
        self.filepath = filepath
        super().__init__(**kwargs)
        self.run_shelltask = super().run
        

    @defaults_from_attrs("url", "filepath", "env")
    def run(self, url: str, filepath: Union[str, Path], env: dict = None,) -> str:
        """
        Args:
            - url (str): url to download
            - file (str): file for saving fecthed url
        Returns:
            str: result from ShellTask.run
        
        Raises:
            - SKIP: if filepath exists
            - prefect.engine.signals.FAIL: if command has an exit code other
                than 0
        """
        if Path(filepath).exists():
            raise SKIP(f"File {filepath} already exists.")
        curl_cmd = f"curl -fL -o {self.filepath} {self.url}"
        result = self.run_shelltask(command=curl_cmd, env=env)
        return result


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
    