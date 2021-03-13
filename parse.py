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
# Returns:
# - a dict of receivers,
# - a dict of providers,
# - a list of support measures,
# - a dict of support kinds.
def process_file(file):
    with open(file, mode="r", encoding="utf8") as f:
        soup = BeautifulSoup(f, "xml")

    data = {"receivers": {},
            "providers": {},
            "support_measures": [],
            "support_kinds": {}}

    documents = soup.find_all("Документ")
    if documents is None:
        print("File {0} doesn't have a «Документ» element.".format(file))
        return False

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

        receiver_tin = ""
        receiver_name = ""

        if individual is not None:
            receiver_tin = individual.get("ИННФЛ", "")
            if receiver_tin == "":
                print("ERROR: Document {0} in file {1} doesn't have «ИННФЛ» attribute and will be skipped.".format(doc_id, file))
                continue
            name_element = individual.find("ФИО")
            if name_element is None:
                print("WARNING: Document {0} in file {1} doesn't have «ФИО» element.".format(doc_id, file))
            else:
                first_name = name_element.get("Имя", "")
                surname = name_element.get("Фамилия", "")
                patronymic = name_element.get("Отчество", "")
                receiver_name = " ".join([surname, first_name, patronymic]).strip()
        elif organization is not None:
            receiver_tin = organization.get("ИННЮЛ", "")
            if receiver_tin == "":
                print("ERROR: Document {0} in file {1} doesn't have «ИННЮЛ» attribute and will be skipped.".format(doc_id, file))
                continue
            receiver_name = organization.get("НаимОрг", "")
            if receiver_name == "":
                print("WARNING: Document {0} in file {1} doesn't have «НаимОрг» element.".format(doc_id, file))
        else:
            print("ERROR: Document {0} in file {1} doesn't have information on receiver and will be skipped".format(doc_id, file))
            continue

        if receiver_tin not in data["receivers"]:
            data["receivers"][receiver_tin] = receiver_name

        if len(provided_support) == 0:
            print("ERROR: Document {0} in file {1} has no information on support measures and will be skipped".format(doc_id, file))
            continue

        for support_measure in provided_support:
            provider_name = support_measure.get("НаимОрг", "")
            if provider_name == "":
                print("WARNING: Document {0} doesn't have «НаимОрг» attribute.".format(doc_id))
            provider_tin = support_measure.get("ИННЮЛ", "")
            if provider_tin == "":
                print("ERROR: No «ИННЮЛ» attribute of «СвПредПод» element in document {0}. This support measure will be skipped.".format(doc_id))
                continue
            if provider_tin not in data["providers"]:
                data["providers"][provider_tin] = provider_name

            receiver_kind_code = int(support_measure.get("ВидПП", ""))
            if receiver_kind_code == "":
                print("WARNING: no «ВидПП» attribute.")
                receiver_kind = None
            else:
                receiver_kind = receiver_kinds[receiver_kind_code]
            receiver_category_code = int(support_measure.get("КатСуб", ""))
            if receiver_category_code == "":
                print("WARNING: no «КатСуб» attribute.")
                receiver_category = None
            else:
                receiver_category = receiver_categories[receiver_category_code]

            def string_to_date(string):
                parts = string.split(".")
                if len(parts) == 3:
                    return date(year=parts[2], month=parts[1], day=parts[0])
                else:
                    return None

            period = support_measure.get("СрокПод", "00.00.0000")
            period = string_to_date(period)
            if period is None:
                period = date(1, 1, 1)
            start_date = support_measure.get("ДатаПрин", "00.00.0000")
            start_date = string_to_date(start_date)
            if start_date is None:
                start_date = date (1, 1, 1)
            end_date = support_measure.get("ДатаПрекр", None)
            if end_date is not None:
                end_date = string_to_date(end_date)
            form = support_measure.find("ФормПод").get("КодФорм", "0000")
            if form not in ["0000", "0100", "0200", "0300", "0400", "0500", "0600"]:
                form = "0000"
            kind_code = support_measure.find("ВидПод").get("КодВид")
            kind_name = support_measure.find("ВидПод").get("НаимВид")
            if kind_code not in data["support_kinds"]:
                data["support_kinds"][kind_code] = kind_name
            violations_element = support_measure.find("ИнфНаруш")
            if violations_element is not None:
                violation = bool_codes[int(violations_element.get("ИнфНаруш", "2"))]
                misuse = bool_codes[int(violations_element.get("ИнфНецел", "2"))]
            else:
                violation, misuse = False, False
            sizes = support_measure.find_all("РазмПод")
            if len(sizes) == 0:
                size = 0.0
                unit = "unit"
                data["support_measures"].append((period, start_date, end_date,
                                         size, unit, violation, misuse,
                                         receiver_kind, receiver_category,
                                         receiver_tin, provider_tin,
                                         kind_code, form))
            for item in sizes:
                size = item.get("РазмПод", 0.0)
                unit_code = int(item.get("ЕдПод", 5))
                unit = size_units[unit_code]
                data["support_measures"].append((period, start_date, end_date,
                                         size, unit, violation, misuse,
                                         receiver_kind, receiver_category,
                                         receiver_tin, provider_tin,
                                         kind_code, form))

    return data


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

    for i, file in enumerate(files[start:end]):
        if ".xml" not in file:
            continue

        print("Start processing file # {0}: {1}".format(i, file))

        d, e = process_file(path + "/" + file)
        if len(e) > 0:
            print(*e)
        r = d["receivers"].copy()
        p = d["providers"].copy()
        s = d["support_measures"].copy()
        k = d["support_kinds"].copy()

        if len(s) == 0:
            continue

        def check_and_update(existing, new):
            for key in existing:
                if key in new:
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
        pe.execute_values(cursor, sql["receivers"], r, template=None, page_size=100)
        pe.execute_values(cursor, sql["providers"], p, template=None, page_size=100)
        pe.execute_values(cursor, sql["kinds"], k, template=None, page_size=100)
        pe.execute_values(cursor, sql["measures"], s, template=None, page_size=100)
        connection.commit()

    connection.close()
    return 0


# All files are not valid: 'ВидСуб' attribute not allowed for element.
# print(validate("data"))
process_dir("data", 800, None)
