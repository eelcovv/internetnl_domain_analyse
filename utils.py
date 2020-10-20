import re
import numpy as np
from tldextract import tldextract
import logging
import pandas as pd
import sqlite3
from ict_analyser.utils import (reorganise_stat_df, standard_output)

_logger = logging.getLogger(__name__)


def read_tables_from_sqlite(filename: str, table_names, index_name) -> pd.DataFrame:
    if isinstance(table_names, str):
        table_names = [table_names]

    _logger.info(f"Reading from {filename}")
    connection = sqlite3.connect(filename)
    tables = list()
    for table_name in table_names:
        df = pd.read_sql(f"select * from {table_name}", con=connection, index_col=index_name)
        tables.append(df)
    if len(tables) > 1:
        tables_df = pd.concat(tables, axis=1)
    else:
        tables_df = tables[0]

    connection.close()

    return tables_df


def get_domain(url):
    try:
        tld = tldextract.extract(url)
    except TypeError:
        domain = None
    else:
        domain = tld.domain.lower()
    return domain


def fill_booleans(tables, translations, variables):
    for col in tables.columns:
        convert_to_bool = True
        try:
            var_type = variables.loc[col, "type"]
        except KeyError:
            pass
        else:
            if var_type == "dict":
                convert_to_bool = False

        if convert_to_bool:
            unique_values = tables[col].unique()
            if len(unique_values) <= 3:
                for trans_key, trans_prop in translations.items():
                    bool_keys = set(trans_prop.keys())
                    intersection = bool_keys.intersection(unique_values)
                    if intersection:
                        nan_val = set(unique_values).difference(bool_keys)
                        if nan_val:
                            trans_prop[list(nan_val)[0]] = np.nan
                        for key, val in trans_prop.items():
                            mask = tables[col] == key
                            if any(mask):
                                tables.loc[mask, col] = float(val)
    return tables


def prepare_stat_data_for_write(all_stats, file_base, variables, module_key, variable_key,
                                breakdown_labels=None, n_digits=3, connection=None):
    data = pd.DataFrame.from_dict(all_stats)
    if connection is not None:
        data.to_sql(name=file_base, con=connection, if_exists="replace")

    stat_df = reorganise_stat_df(records_stats=data, variables=variables,
                                 module_key=module_key,
                                 variable_key=variable_key,
                                 n_digits=n_digits)
    if breakdown_labels is not None:
        try:
            labels = breakdown_labels[file_base]
        except KeyError:
            _logger.info(f"No breakdown labels for {file_base}")
        else:
            stat_df.rename(columns=labels, inplace=True)

    return stat_df


def get_option_mask(question_df, variables):
    """  get the mask to filter the positive options from a question """
    original_name = re.sub(r"_\d\.0$", "", question_df["variable"].values[0])
    question_type = variables.loc[original_name, "type"]
    mask_total = None
    if question_type == "dict":
        for optie in ("Passed", "Yes", "Good"):
            mask = question_df.index.get_level_values(2) == optie
            if mask_total is None:
                mask_total = mask
            else:
                mask_total = mask | mask_total
    else:
        mask_total = pd.Series(True, index=question_df.index)

    return mask_total

