def clean_python_name(s):
    """Method to convert string to Python 2 object name.
    
    Inteded for use in dataframe column names such :
        i) it complies to python 2.x object name standard:
           (letter|'_')(letter|digit|'_')
        ii) my preference to use lowercase and adhere
            to practice of case-insensitive column names for data
    
    Based on
    https://stackoverflow.com/questions/3303312/how-do-i-convert-a-string-to-a-valid-variable-name-in-python

    Example:
    
    .. code:: python
        df.rename(columns=clean_python_name)
    
    Args:
        - s (str): string to be converted
    
    Returns:
        str: cleaned string
    """
    
    import re

    # Remove leading characters until we find a letter or underscore, and remove trailing spaces
    s = re.sub('^[^a-zA-Z_]+', '', s.strip())

    # Replace invalid characters with underscores
    s = re.sub('[^0-9a-zA-Z_]', '_', s)

    return s.lower()