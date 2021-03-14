import psycopg2
import psycopg2.extras as pe
import xmlschema
import os
from datetime import date
from bs4 import BeautifulSoup


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
    with open(file, mode="r", encoding="utf8") as f:
        soup = BeautifulSoup(f, "xml")

    data = {"receivers": {},
            "providers": {},
            "support_measures": [],
            "support_kinds": {}}
    error = False

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

    for document in documents:
        doc_id = document.get("ИдДок", "")
        individual = document.find("СвФЛ")
        organization = document.find("СвЮЛ")
        provided_support = document.find_all("СвПредПод")
        error_message_base = "Error in file {0}, document {1}:".format(file, doc_id)

        receiver_tin = ""
        receiver_name = ""

        if individual is not None:
            receiver_tin = individual.get("ИННФЛ", "")
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

        if receiver_tin not in data["receivers"]:
            data["receivers"][receiver_tin] = receiver_name

        if len(provided_support) == 0:
            print(error_message_base, "no information on support measures.")
            error = True
            continue

        for support_measure in provided_support:
            provider_name = support_measure.get("НаимОрг", "")
            if provider_name == "":
                error = True
                print(error_message_base, "no «НаимОрг» (provider) attribute.")
            provider_tin = support_measure.get("ИННЮЛ", "")
            if provider_tin == "":
                error = True
                print(error_message_base, "no «ИННЮЛ» (provider) attribute.")
                continue
            if provider_tin not in data["providers"]:
                data["providers"][provider_tin] = provider_name

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

            def string_to_date(string):
                parts = list(map(int, string.split(".")))
                if len(parts) == 3:
                    return date(year=parts[2], month=parts[1], day=parts[0])
                else:
                    return None

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
            if len(sizes) == 0:
                print(error_message_base, "no «РазмПод» element.")
                error = True
                size = 0.0
                unit = "unit"
                data["support_measures"].append((period, start_date, end_date,
                                         size, unit, violation, misuse,
                                         receiver_kind, receiver_category,
                                         receiver_tin, provider_tin,
                                         kind_code, form))
            for item in sizes:
                try:
                    size = float(item.get("РазмПод", 0.0))
                except ValueError:
                    print(error_message_base, "«РазмПод» can't be converted to float.")
                    error = True
                    size = 0.0
                if size >= 1e9:
                    size = 0.0
                    error = True
                    print(error_message_base, "«РазмПод» is bigger than 1 billion")
                unit_code = int(item.get("ЕдПод", 5))
                unit = size_units[unit_code]
                data["support_measures"].append((period, start_date, end_date,
                                         size, unit, violation, misuse,
                                         receiver_kind, receiver_category,
                                         receiver_tin, provider_tin,
                                         kind_code, form))

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

    files = os.listdir(path)

    def get_pk_set(column, table):
        query = "SELECT {0} FROM {1}".format(column, table)
        cursor.execute(query)
        query_result = cursor.fetchall()
        values_set = {i[0] for i in query_result}
        return values_set

    in_receivers = get_pk_set("tin", "receivers")
    in_providers = get_pk_set("tin", "providers")
    in_support_kinds = get_pk_set("code", "support_kinds")

    total_errors = 0

    for i, file in enumerate(files[start:end]):
        if ".xml" not in file:
            continue

        print("Start processing file # {0}: {1}".format(i, file))

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

        def check_and_update(existing, new):
            common = existing & new.keys()
            for key in common:
                del new[key]

            existing = existing | new.keys()
            return existing, new

        in_receivers, r = check_and_update(in_receivers, r)
        in_providers, p = check_and_update(in_providers, p)
        in_support_kinds, k = check_and_update(in_support_kinds, k)

        r = list(r.items())
        p = list(p.items())
        k = list(k.items())

        sql = {"receivers": "INSERT INTO receivers VALUES %s",
               "providers": "INSERT INTO providers VALUES %s",
               "kinds": "INSERT INTO support_kinds VALUES %s",
               "measures": "INSERT INTO support_measures (period, start_date, end_date, size, size_unit, violation, misuse, receiver_kind, receiver_category, receiver, provider, kind, form) VALUES %s"}
        try:
            pe.execute_values(cursor, sql["receivers"], r, template=None, page_size=100)
            pe.execute_values(cursor, sql["providers"], p, template=None, page_size=100)
            pe.execute_values(cursor, sql["kinds"], k, template=None, page_size=100)
            pe.execute_values(cursor, sql["measures"], s, template=None, page_size=100)
            connection.commit()
        except psycopg2.Error as e:
            print(e.pgerror)
            total_errors = total_errors + 1
            connection.rollback()

    connection.close()
    i = i + 1
    print("{0} files processed, {1} of them are with errors.".format(i, total_errors))
    return 0


# All files are not valid: 'ВидСуб' attribute not allowed for element.
# print(validate("data"))
process_dir("data")
