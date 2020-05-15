def clean_python_name(s):
    """
    https://gist.github.com/dkapitan/89ff20eeed38e6d9757fef9e09e23c3d
    Method to convert string to clean string for use
    in dataframe column names such :
        i) it complies to python 2.x object name standard:
           (letter|'_')(letter|digit|'_')
        ii) my preference to use lowercase and adhere
            to practice of case-insensitive column names for data
    Based on
    https://stackoverflow.com/questions/3303312/how-do-i-convert-a-string-to-a-valid-variable-name-in-python
    """
    import re

    # Remove leading characters until we find a letter or underscore, and remove trailing spaces
    s = re.sub('^[^a-zA-Z_]+', '', s.strip())

    # Replace invalid characters with underscores
    s = re.sub('[^0-9a-zA-Z_]', '_', s)

    return s.lower()