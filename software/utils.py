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