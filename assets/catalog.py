#!/bin/python3

import os
import re
import logging
import json
import psycopg2
import yaml
from string import Template

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
FORMATTER = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')

# Create handler that will redirect log entries to STDOUT
STDOUT_HANDLER = logging.StreamHandler()
STDOUT_HANDLER.setLevel(logging.DEBUG)
STDOUT_HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(STDOUT_HANDLER)

# Path to prepared operators
OP_PATH = "/app/op"

# postgres database connection infos
DB = {
    'USER': os.environ['DB_USER'],
    'PASSWORD': os.environ['DB_PWD'],
    'HOST': os.environ['DB_HOST'],
    'PORT': int(os.environ['DB_PORT'])
}

insert_family = Template("""
INSERT INTO catalogue_functionalfamilydao
("name", "desc", "label")
VALUES
  ('$name', '$description', '$label');
""")

algorithm = Template("""
INSERT INTO catalogue_algorithmdao
("name", "label", "desc", "family_id")
VALUES 
  ('$name', '$label', '$description', (SELECT id FROM catalogue_functionalfamilydao WHERE name = '$family'));
""")

implementation = Template("""
INSERT INTO catalogue_implementationdao
("name", "label", "desc", "algo_id", "execution_plugin", "library_address", "visibility")
VALUES
  ('$name', '$label', '$description', (SELECT id FROM catalogue_algorithmdao WHERE name = '$name'), 'apps.algo.execute.models.business.python_local_exec_engine::PythonLocalExecEngine', '$entry_point', '$visibility');
""")

profile_item_IN = Template("""
INSERT INTO catalogue_profileitemdao
("name", "label", "desc", "direction", "dtype", "order_index", "data_format")
VALUES
  ('$name', '$label', '$description', $direction, $dtype, $index, '$type');
INSERT INTO catalogue_implementationdao_input_desc_items ("implementationdao_id", "profileitemdao_id")
VALUES
   ((SELECT id FROM catalogue_implementationdao WHERE "name" = '$name_algo'), 
    (SELECT id FROM catalogue_profileitemdao WHERE "name" = '$name'));
""")

profile_item_PARAM = Template("""
INSERT INTO catalogue_profileitemdao
("name", "label", "desc", "direction", "dtype", "order_index", "data_format", "domain_of_values", "default_value")
VALUES
  ('$name', '$label', '$description', $direction, $dtype, $index, '$type', '$domain', '$default_value');
INSERT INTO catalogue_implementationdao_input_desc_items ("implementationdao_id", "profileitemdao_id")
VALUES
   ((SELECT id FROM catalogue_implementationdao WHERE "name" = '$name_algo'), 
    (SELECT id FROM catalogue_profileitemdao WHERE "name" = '$name'));
""")

profile_item_OUT = Template("""
INSERT INTO catalogue_profileitemdao
("name", "label", "desc", "direction", "dtype", "order_index", "data_format")
VALUES
  ('$name', '$label', '$description', $direction, $dtype, $index, '$type');
INSERT INTO catalogue_implementationdao_output_desc_items ("implementationdao_id", "profileitemdao_id")
VALUES
   ((SELECT id FROM catalogue_implementationdao WHERE name = '$name_algo'), 
    (SELECT id FROM catalogue_profileitemdao WHERE "name" = '$name'));
""")


def read_families_list():
    """
    Reads the families.json file to get name, label and description of operators families
    :return: the dict containing the JSON information
    """
    with open('families.json') as f:
        return json.load(f)


# Get families name,label and descriptions from families.json
FAMILIES = read_families_list()


def extract_catalog(op_name):
    """
    Retrieves list of catalog_def for given operator
    """
    catalog_list = []

    # Check if catalog definition is present in repository
    pattern = re.compile("catalog_def(_[0-9]{,2})?.json")
    for file_path in os.listdir("%s/%s" % (OP_PATH, op_name)):
        if pattern.match(file_path):
            with open("%s/%s/%s" % (OP_PATH, op_name, file_path)) as cat_def:
                try:
                    catalog_list.append(json.load(cat_def))
                except:
                    LOGGER.error("JSON bad format for op-%s/%s", op_name, file_path)
                    LOGGER.warning("Operator %s is ignored", op_name)

    return catalog_list


def format_catalog(catalog):
    """
    Add missing optional keys with default values in catalog
    """

    catalog['entry_point'] = "ikats.algo.%s" % catalog.get('entry_point', 'missing')

    if "visibility" not in catalog:
        catalog["visibility"] = True

    # create optional keys with default values if missing
    if 'family' not in catalog or catalog['family'] not in [x.get('name') for x in FAMILIES]:
        catalog['family'] = 'Uncategorized'
    if 'label' not in catalog:
        catalog['label'] = catalog['name']
        LOGGER.warning("Label is missing for operator %s", catalog.get('name'))
    if 'description' not in catalog:
        catalog['description'] = 'no description'

    def format_item(item):
        # create optional keys with default values if missing
        if 'label' not in item:
            item['label'] = item.get('name')
            LOGGER.warning("Label is missing for item %s", item.get('name'))
        if 'description' not in item:
            item['description'] = 'no description'

    if 'inputs' in catalog:
        for input in catalog.get('inputs'):
            format_item(input)
    if 'outputs' in catalog:
        for output in catalog.get('outputs'):
            format_item(output)
    if 'parameters' in catalog:
        for parameter in catalog.get('parameters'):
            format_item(parameter)
            if 'domain' not in parameter:
                parameter['domain'] = None
            else:
                # domain is considered as a list of string contained in a list
                parameter['domain'] = parameter.get('domain').replace("'", "\"")
            if 'default_value' not in parameter:
                parameter['default_value'] = None
            else:
                # string case
                if type(parameter.get('default_value')) is str:
                    parameter['default_value'] = "\"{0}\"".format(
                        parameter.get('default_value'))
                elif type(parameter.get('default_value')) is bool:
                    # boolean case
                    if parameter.get('default_value'):
                        parameter['default_value'] = 'true'
                    else:
                        parameter['default_value'] = 'false'

    return catalog


def replace_quotes(catalog):
    """
    Function that replace simple quote by double quotes in string values of a catalog recursively
    """
    for k, v in catalog.items():
        if isinstance(v, list):
            new_list = []
            for obj in v:
                new_list.append(replace_quotes(obj))
            catalog[k] = new_list
        elif isinstance(v, str):
            catalog[k] = v.replace("'", "''")
    return catalog


def catalog_json_to_SQL(catalog):
    """
    Convert algorithm catalog definition from json to sql query
    """
    catalog = replace_quotes(catalog)
    sql = algorithm.substitute(catalog)
    sql += implementation.substitute(catalog)
    index_profileitem = 0
    if 'inputs' in catalog:
        for input in catalog.get('inputs'):
            sql += profile_item_IN.substitute(
                input,
                name='{}_{}_{}'.format(catalog.get('name'), '_i_', input.get('name')),
                direction=0,
                dtype=1,
                index=index_profileitem,
                name_algo=catalog.get('name'))
            index_profileitem += 1
    if 'parameters' in catalog:
        for parameter in catalog.get('parameters'):
            sql += profile_item_PARAM.substitute(
                parameter,
                name='{}_{}_{}'.format(catalog.get('name'), '_p_', parameter.get('name')),
                direction=0,
                dtype=0,
                index=index_profileitem,
                name_algo=catalog.get('name'))
            index_profileitem += 1
    if 'outputs' in catalog:
        for output in catalog.get('outputs'):
            sql += profile_item_OUT.substitute(
                output,
                name='{}_{}_{}'.format(catalog.get('name'), '_o_', output.get('name')),
                direction=1,
                dtype=1,
                index=index_profileitem,
                name_algo=catalog.get('name'))
            index_profileitem += 1

    return sql.replace("\'None\'", "NULL")


def delete_catalog_postgres():
    """
    Delete data from catalogue databases
    """
    CATALOG_DATABASES_LIST = [
        'custom_customizedparameterdao',
        'custom_customizedalgodao',
        'catalogue_implementationdao_input_desc_items',
        'catalogue_implementationdao_output_desc_items',
        'catalogue_profileitemdao',
        'catalogue_implementationdao',
        'catalogue_algorithmdao',
        'catalogue_functionalfamilydao']
    for db in CATALOG_DATABASES_LIST:
        # delete all data and reset associated id sequence
        request_to_postgres("TRUNCATE TABLE %s RESTART IDENTITY CASCADE;" % db)


def populate_catalog_families():
    """
    Insert families in catalog
    """
    for family in FAMILIES:
        sql = insert_family.substitute(family)
        request_to_postgres(sql)


def request_to_postgres(query):
    """
    Request postgresql with sql query as a string
    """

    conn_string = 'host={} port={} user={} password={}'.format(DB.get('HOST'), DB.get('PORT'),
                                                               DB.get('USER'), DB.get('PASSWORD'))
    connection = None
    try:
        connection = psycopg2.connect(conn_string)
        cursor = connection.cursor()
        cursor.execute(query)
        connection.commit()
        cursor.close()
    except Exception as error:
        LOGGER.error(error)
    finally:
        if connection is not None:
            connection.close()


def process_operator_catalog(op):
    """
    Processing the catalog for a given operator (main)
    :param op: name of the operator processed
    :type op: str
    """

    # extract catalog from catalog_def.json in given repo
    catalog_list_json = extract_catalog(op)

    if catalog_list_json:

        LOGGER.info(
            "Processing catalog definition for operator : %s ...", op)

        # to handle the case : several operators in same directory
        for catalog_json in catalog_list_json:
            format_catalog(catalog_json)

            # generate SQL request from catalog definition in JSON format
            sql = catalog_json_to_SQL(catalog_json)

            # postgresql request
            request_to_postgres(sql)

        LOGGER.info("Operator %s catalog processed with success.", op)

    else:
        LOGGER.info("No catalog definition found for repo : %s", op)
