"""
Utility functions. 
"""

import datetime

def ask_yes_no(question, default="yes"):

    """
    Ask a yes/no question and return the answer.

    Parameters:
    -----------
    question (str): The question to ask the user. 
    default: The presumed answer if the user hits only <Enter>. 
        Can be either "yes", "no", or None. Default is "yes".
    Returns:
    ---------
    bool
    """

    valid = {"yes": True, "y": True,
             "no": False, "n": False}

    if default is None:
        prompt = "[y/n]\n"
    elif default == "yes":
        prompt = "[Y/n]\n"
    elif default == "no":
        prompt = "[y/N]\n"
    else:
        raise ValueError(f"invalid default answer: {default}")

    while True:

        print(f"{question} {prompt}")
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            print("Please respond with 'yes'/'y' or 'no'/'n'. \n")


def datetime_to_elapsed(df, col_name="datetime"):

    """
    Generates a pd.series (column) of elapsed times in seconds,
    from a column of datetime objs

    Parameters:
    -----------
    df: A dataframe.
    col_name (str): Name of the column of datetime objects. 

    Returns:
    ---------
    A dataframe with an additional column of elapsed seconds.
    ("elapsed secs")
    """

    col = df[col_name]- df[col_name].iloc[0]
    df["elapsed secs"] = [row.total_seconds() for row in col]
    
    return df


def parse_readme_for_docstrings(readme_path):
    
    """
    Extract docstrings for functions from the `README.md` file.
    From the path to the `README.md`, returns a list of docstrings. 
    """

    with open(readme_path, "r") as f:
        readme = f.readlines()
    
    # Extract docstring start and end lines from README.md:
    start_lines = []
    end_lines = []
    for i, line in enumerate(readme):

        if line.startswith("<details>"):
            start_lines.append(i+2)

        if line.startswith("</details>"):
            end_lines.append(i-1)
    
    # Generate docstrings from start and end lines:
    docstrings = ["".join(readme[start_line:end_line+1])
                  for start_line, end_line in zip(start_lines, end_lines)]
            
    return docstrings


def docstring_parameter(*sub):

    """
    Modify the __doc__ object so I can pass in variables 
    to the docsring
    """

    def dec(obj):
        obj.__doc__ = obj.__doc__.format(*sub)
        return obj
    return dec