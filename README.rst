========
nimbletl
========


.. image:: https://img.shields.io/pypi/v/nimbletl.svg
        :target: https://pypi.python.org/pypi/nimbletl

.. image:: https://img.shields.io/travis/dkapitan/nimbletl.svg
        :target: https://travis-ci.com/dkapitan/nimbletl

.. image:: https://readthedocs.org/projects/nimbletl/badge/?version=latest
        :target: https://nimbletl.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status




Lightweight Python ETL toolkit using Prefect.


* Free software: MIT license
* Documentation: https://nimbletl.readthedocs.io.

Introduction
------------

Flexible Python ETL toolkit for datawarehousing framework based on Dask, Prefect and the pydata stack. It follows the `original design principles`_ from these libraries, combined with a `functional programming approach to data engineering`_.

`Google Cloud Platform (GCP)`_ is used as the core infrastructure, particularly `BigQuery (GBQ)`_ and `Cloud Storage (GCS)`_ as the main storage engines. We follow Google's recommendations on how to use `BigQuery for data warehouse applications`_ with four layers:

- source data, in production environment or file-based
- staging, on GCS
- datavaault, on GBQ
- datamarts, on GBQ using `ARRAY_AGG, STRUCT, UNNEST SQL-pattern`_

*nimble (/ˈnɪmb(ə)l/): quick and light in movement or action; agile*, wink at the godfather of the star-schema, Kimball_


Usage
-----

.. code:: shell

        pip install -e git+https://github.com/dkapitan/nimbletl.git


A conda environment is included for convenience, containing most commonly use packages.

.. code:: shell

        conda env create -f environment.yml


Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _`original design principles`: https://stories.dask.org/en/latest/prefect-workflows.html
.. _`functional programming approach to data engineering`: https://medium.com/@maximebeauchemin/functional-data-engineering-a-modern-paradigm-for-batch-data-processing-2327ec32c42a
.. _`Google Cloud Platform (GCP)`: https://cloud.google.com/docs/
.. _`BigQuery (GBQ)`: https://cloud.google.com/bigquery/docs/
.. _`Cloud Storage (GCS)`: https://cloud.google.com/storage/
.. _`BigQuery for data warehouse applications`: https://cloud.google.com/solutions/bigquery-data-warehouse
.. _`ARRAY_AGG, STRUCT, UNNEST SQL-pattern`: https://medium.freecodecamp.org/exploring-a-powerful-sql-pattern-array-agg-struct-and-unnest-b7dcc6263e36
.. _Kimball: https://en.wikipedia.org/wiki/Ralph_Kimball
.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
