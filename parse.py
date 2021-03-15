import psycopg2
import psycopg2.extras as pe
import xmlschema
import os
from datetime import date
from bs4 import BeautifulSoup


# A function to convert string date representation to Python date object.
# Gets string in a format "dd.mm.yyyy".
# Returns date object or none if the conversion didn't succeed.
def string_to_date(string):
    parts = list(map(int, string.split(".")))
    if len(parts) == 3:
        return date(year=parts[2], month=parts[1], day=parts[0])
    else:
        return None


# A function to get a column from a table.
# Gets a cursor object, a column name and a table name.
# Returns a set of values.
def get_pk_set(cursor, column, table):
    query = "SELECT {0} FROM {1}".format(column, table)
    cursor.execute(query)
    query_result = cursor.fetchall()
    values_set = {i[0] for i in query_result}
    return values_set


# A function to remove keys from a dict which are already present in a set of keys.
# Gets set of existing keys and a dict which contains new keys.
# Returns dict with new keys only.
def check_keys(existing, new):
    common = existing & new.keys()
    for key in common:
        del new[key]
    return new


# A function to update a set of existing keys.
# Gets a set of keys and a dict to get the new keys from.
# Returns updated set.
def update_keys(existing, new):
    existing = existing | new.keys()
    return existing


# A validation function.
# Gets path to the directory and a path to xsd file.
# Returns a tuple with the number of valid and invalid files.
# Catches and prints all errors happened during the validation.
# In fact, ALL the files are NOT valid, so the function is nearly useless.
def validate(path, schema_file="structure.xsd"):
    count_valid, count_invalid = 0, 0
    files = os.listdir(path)
    schema = xmlschema.XMLSchema(schema_file)

    for file in files:
        # We shouldn't validate non-xml files.
        if ".xml" not in file:
            continue

        # Try to validate the file.
        try:
            schema.validate(path + "/" + file)
            count_valid = count_valid + 1
        # Catch any error and print it, if the file is not valid.
        except xmlschema.exceptions.XMLSchemaException as e:
            count_invalid = count_invalid + 1
            print(e)

    return count_valid, count_invalid


# File processing function.
# Gets an xml file with data.
# Returns a dict of data including:
# - a dict of receivers,
# - a dict of providers,
# - a list of support measures,
# - a dict of support kinds,
# - and a boolean error value indicating if any errors occurred.
def process_file(file):
    # Open the file.
    with open(file, mode="r", encoding="utf8") as f:
        soup = BeautifulSoup(f, "xml")

    # Dict for data and variable for error indication.
    data = {"receivers": {},
            "providers": {},
            "support_measures": [],
            "support_kinds": {}}
    error = False

    # Get all «Документ» elements.
    documents = soup.find_all("Документ")
    if documents is None:
        print("Error in file {0}: no «Документ» element.".format(file))
        error = True
        return data, error

    # Dictionaries to convert numeric codes from the xml file to labels of enumeration types in the database.
    receiver_kinds = {1: "ul", 2: "fl", 3: "npd"}
    receiver_categories = {1: "micro", 2: "small", 3: "medium", 4: "none"}
    size_units = {1: "rouble", 2: "sq_meter", 3: "hour", 4: "percent", 5: "unit"}
    # Dictionary to convert numeric 1-2 code of violations to True/False values.
    bool_codes = {1: True, 2: False}

    # Iterate over a set of documents.
    for document in documents:
        # Get three main elements and a document id.
        doc_id = document.get("ИдДок", "")
        individual = document.find("СвФЛ")
        organization = document.find("СвЮЛ")
        provided_support = document.find_all("СвПредПод")
        # Base string for error messages.
        error_message_base = "Error in file {0}, document {1}:".format(file, doc_id)

        # Variables for receiver tin and name.
        receiver_tin = ""
        receiver_name = ""

        # We need either «СвФЛ» or «СвЮЛ» to get receiver's tin and name.
        # If we don't have any, we continue to the next document.
        if individual is not None:
            receiver_tin = individual.get("ИННФЛ", "")
            # If we don't have receiver's tin, we won't be able to insert data.
            # So print error message and go to the next document.
            if receiver_tin == "":
                print(error_message_base, "no «ИННФЛ» attribute.")
                error = True
                continue
            name_element = individual.find("ФИО")
            if name_element is None:
                print(error_message_base, "no «ФИО» element.")
                error = True
            else:
                first_name = name_element.get("Имя", "")
                if first_name == "":
                    print(error_message_base, "no «Имя» attribute.")
                    error = True
                surname = name_element.get("Фамилия", "")
                if surname == "":
                    print(error_message_base, "no «Фамилия» attribute.")
                    error = True
                # Patronymic is not required.
                patronymic = name_element.get("Отчество", "")
                receiver_name = " ".join([surname, first_name, patronymic]).strip()
        elif organization is not None:
            receiver_tin = organization.get("ИННЮЛ", "")
            if receiver_tin == "":
                print(error_message_base, "no «ИННЮЛ» (receiver) attribute.")
                error = True
                continue
            receiver_name = organization.get("НаимОрг", "")
            if receiver_name == "":
                error = True
                print(error_message_base, "no «НаимОрг» (receiver) attribute.")
        else:
            print(error_message_base, "no information on receiver.")
            error = True
            continue

        # It is possible that one receiver will be mentioned in different documents.
        # So we have to check this using tin.
        # Otherwise kay error will happen on insert.
        if receiver_tin not in data["receivers"]:
            data["receivers"][receiver_tin] = receiver_name

        # If there are no «СвПредПод» elements in a document, go to the next document.
        if len(provided_support) == 0:
            print(error_message_base, "no information on support measures.")
            error = True
            continue

        # Otherwise cycle through the support measures.
        for support_measure in provided_support:
            # Get data on support provider.
            provider_name = support_measure.get("НаимОрг", "")
            if provider_name == "":
                error = True
                print(error_message_base, "no «НаимОрг» (provider) attribute.")
            provider_tin = support_measure.get("ИННЮЛ", "")
            if provider_tin == "":
                error = True
                print(error_message_base, "no «ИННЮЛ» (provider) attribute.")
                continue
            # It's highly likely that one receiver may de present in many documents.
            # So we have to check whether we already have the current one to avoid duplication.
            # Otherwise key error will happen on insert.
            if provider_tin not in data["providers"]:
                data["providers"][provider_tin] = provider_name

            # Get data on support measure.
            # Would be great to have more type-check and error handling.
            # But with the given dataset it's not very important.
            receiver_kind_code = int(support_measure.get("ВидПП", ""))
            if receiver_kind_code == "":
                error = True
                print(error_message_base, "no «ВидПП» attribute.")
                continue
            else:
                receiver_kind = receiver_kinds[receiver_kind_code]
            receiver_category_code = int(support_measure.get("КатСуб", ""))
            if receiver_category_code == "":
                print(error_message_base, "no «КатСуб» attribute.")
                error = True
                receiver_category = 4
            else:
                receiver_category = receiver_categories[receiver_category_code]

            period = support_measure.get("СрокПод", "00.00.0000")
            period = string_to_date(period)
            if period is None:
                print(error_message_base, "no «СрокПод» attribute")
                error = True
                period = date(1, 1, 1)
            start_date = support_measure.get("ДатаПрин", "00.00.0000")
            start_date = string_to_date(start_date)
            if start_date is None:
                print(error_message_base, "no «ДатаПрин» attribute.")
                error = True
                start_date = date(1, 1, 1)
            end_date = support_measure.get("ДатаПрекр", None)
            if end_date is not None:
                end_date = string_to_date(end_date)
            form = support_measure.find("ФормПод").get("КодФорм", "")
            if form not in ["0100", "0200", "0300", "0400", "0500", "0600"]:
                print(error_message_base, "no «КодФорм» attribute.")
                error = True
                form = "0000"
            kind_code_element = support_measure.find("ВидПод")
            if kind_code_element is None:
                print(error_message_base, "no «ВидПод» element.")
                error = True
                kind_code = "0000"
                kind_name = "Нет данных"
            else:
                kind_code = kind_code_element.get("КодВид", "")
                kind_name = kind_code_element.get("НаимВид", "")
            # Unfortunately, I couldn't find a complete list of support kinds.
            # So the best way is to build it from files data.
            # If we have a new kind code and name, add them to the data and then insert into a table.
            if kind_code not in data["support_kinds"]:
                data["support_kinds"][kind_code] = kind_name
            violations_element = support_measure.find("ИнфНаруш")
            if violations_element is not None:
                violation = bool_codes[int(violations_element.get("ИнфНаруш", "2"))]
                misuse = bool_codes[int(violations_element.get("ИнфНецел", "2"))]
            else:
                print(error_message_base, "no «ИнфНаруш» element.")
                error = True
                violation, misuse = False, False
            sizes = support_measure.find_all("РазмПод")
            # Special case for no «РазмПод» element.
            # Assume that the size is 0.0
            # Would be great to combine with the next for cycle to avoid code duplication.
            if len(sizes) == 0:
                print(error_message_base, "no «РазмПод» element.")
                error = True
                size = 0.0
                unit = "unit"
                data["support_measures"].append((period, start_date, end_date,
                                         size, unit, violation, misuse,
                                         receiver_kind, receiver_category,
                                         receiver_tin, provider_tin,
                                         kind_code, form, file, doc_id))
            # Iterate over sizes.
            for item in sizes:
                try:
                    size = float(item.get("РазмПод", 0.0))
                except ValueError:
                    print(error_message_base, "«РазмПод» can't be converted to float.")
                    error = True
                    size = 0.0
                # If support size is more than 1e9, it won't be inserted into the database due to column specification.
                if size >= 1e9:
                    size = 0.0
                    error = True
                    print(error_message_base, "«РазмПод» is bigger than 1 billion")
                unit_code = int(item.get("ЕдПод", 5))
                unit = size_units[unit_code]
                # Finally, append data to the list.
                # Here we don't need to check for duplication.
                data["support_measures"].append((period, start_date, end_date,
                                         size, unit, violation, misuse,
                                         receiver_kind, receiver_category,
                                         receiver_tin, provider_tin,
                                         kind_code, form, file, doc_id))

    return data, error


# Function to process xml files in a directory.
# Gets:
# - a path to a directory,
# - a number of file to start (default is 0),
# - a number of file to end (default is 10).
# Returns 0 on success.
def process_dir(path, start=0, end=10):
    # Connect to the database and get a cursor.
    connection_args = {"database": "smb_support",
                       "user": "pavel",
                       "password": 12345,
                       "host": "localhost",
                       "port": 5432}
    connection = psycopg2.connect(**connection_args)
    cursor = connection.cursor()

    # Get files list.
    files = os.listdir(path)

    # Each new file may contain tins and codes which are already present in the corresponding tables.
    # Tins and codes are primary keys.
    # If we try to insert them, an error will happen.
    # So we need to remove existing keys from the data.
    # First, get existing keys from the database.
    # Also, this help us to run the script multiple times with different chunks of files.
    in_receivers = get_pk_set(cursor, "tin", "receivers")
    in_providers = get_pk_set(cursor, "tin", "providers")
    in_support_kinds = get_pk_set(cursor, "code", "support_kinds")

    # Error counter.
    total_errors = 0

    # Iterate over files.
    i = 0
    for i, file in enumerate(files[start:end]):
        # Non-xml files are not processed.
        if ".xml" not in file:
            continue

        print("Start processing file # {0}: {1}".format(i, file))

        # Parse data from the file.
        d, err = process_file(path + "/" + file)
        if d:
            r = d["receivers"].copy()
            p = d["providers"].copy()
            s = d["support_measures"].copy()
            k = d["support_kinds"].copy()
        else:
            continue

        if err:
            total_errors = total_errors + 1

        # Remove keys and associated data if keys are already in the database.
        r = check_keys(in_receivers, r)
        p = check_keys(in_providers, p)
        k = check_keys(in_support_kinds, k)

        # Queries.
        sql = {"receivers": "INSERT INTO receivers VALUES %s",
               "providers": "INSERT INTO providers VALUES %s",
               "kinds": "INSERT INTO support_kinds VALUES %s",
               "measures": "INSERT INTO support_measures (period, start_date, end_date, size, size_unit, violation, misuse, receiver_kind, receiver_category, receiver, provider, kind, form, source_file, doc_id) VALUES %s"}
        # Try to insert data.
        try:
            pe.execute_values(cursor, sql["receivers"], list(r.items()), template=None, page_size=100)
            pe.execute_values(cursor, sql["providers"], list(p.items()), template=None, page_size=100)
            pe.execute_values(cursor, sql["kinds"], list(k.items()), template=None, page_size=100)
            pe.execute_values(cursor, sql["measures"], s, template=None, page_size=100)
            connection.commit()
            # Update the set of keys which are present in the database.
            in_receivers = update_keys(in_receivers, r)
            in_providers = update_keys(in_providers, p)
            in_support_kinds = update_keys(in_support_kinds, k)
        # Catch all errors.
        except psycopg2.Error as e:
            print(e.pgerror)
            total_errors = total_errors + 1
            connection.rollback()

    # Close the connection.
    connection.close()
    # Increment i for accurate count of processed files.
    i = i + 1
    print("{0} files processed, {1} of them are with errors.".format(i, total_errors))
    return 0


# All files are not valid: 'ВидСуб' attribute not allowed for element.
# print(validate("data"))
process_dir("data", 200, 400)
