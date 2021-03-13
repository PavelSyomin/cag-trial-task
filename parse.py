import psycopg2
import psycopg2.extras as pe
import xmlschema
import os
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

    documents = soup("Документ")

    receivers = {}
    providers = {}
    support_measures = []
    support_kinds = {}

    # Dictionaries to convert numeric codes from the xml file to labels of enumeration types in the database.
    receiver_kinds = {1: "ul", 2: "fl", 3: "npd"}
    receiver_categories = {1: "micro", 2: "small", 3: "medium", 4: "none"}
    size_units = {1: "rouble", 2: "sq_meter", 3: "hour", 4: "percent", 5: "unit"}
    # Dictionary to convert numeric 1-2 code of violations to True/False values.
    bool_codes = {1: True, 2: False}

    for document in documents:
        fl = document("СвФЛ")
        ul = document("СвЮЛ")
        provided_support = document("СвПредПод")

        if len(fl) == 1:
            fl = fl[0]
            receiver_tin = fl["ИННФЛ"]
            name_element = fl.find("ФИО")
            first_name = name_element["Имя"]
            surname = name_element["Фамилия"]
            patronymic = name_element.get("Отчество")
            if patronymic is None:
                patronymic = ""
            receiver_name = " ".join([surname, first_name, patronymic])

        if len(ul) == 1:
            ul = ul[0]
            receiver_tin = ul["ИННЮЛ"]
            receiver_name = ul["НаимОрг"]

        if receiver_tin not in receivers:
            receivers[receiver_tin] = receiver_name

        for support_measure in provided_support:
            provider_name = support_measure["НаимОрг"]
            provider_tin = support_measure["ИННЮЛ"]
            if provider_tin not in providers:
                providers[provider_tin] = provider_name

            receiver_kind_code = int(support_measure["ВидПП"])
            receiver_kind = receiver_kinds[receiver_kind_code]
            receiver_category_code = int(support_measure["КатСуб"])
            receiver_category = receiver_categories[receiver_category_code]
            period = support_measure["СрокПод"].replace(".", "/")
            start_date = support_measure["ДатаПрин"].replace(".", "/")
            end_date = support_measure.get("ДатаПрекр")
            if end_date is not None:
                end_date = end_date.replace(".", "/")
            form = support_measure.find("ФормПод")["КодФорм"]
            kind_code = support_measure.find("ВидПод")["КодВид"]
            kind_name = support_measure.find("ВидПод")["НаимВид"]
            if kind_code not in support_kinds:
                support_kinds[kind_code] = kind_name
            violation = bool_codes[int(support_measure.find("ИнфНаруш")["ИнфНаруш"])]
            misuse = bool_codes[int(support_measure.find("ИнфНаруш")["ИнфНецел"])]
            sizes = support_measure.find_all("РазмПод")
            for item in sizes:
                size = item["РазмПод"]
                unit_code = int(item["ЕдПод"])
                unit = size_units[unit_code]
                support_measures.append((period, start_date, end_date,
                                         size, unit, violation, misuse,
                                         receiver_kind, receiver_category,
                                         receiver_tin, provider_tin,
                                         kind_code, form))

    return receivers, providers, support_measures, support_kinds


# Function to process xml files in a directory.
# Gets a path to a directory and a number of files to process (default number is 10).
# Returns 0 on success.
def process_dir(path, n_files=10):
    connection_args = {"database": "smb_support",
                       "user": "pavel",
                       "password": 12345,
                       "host": "localhost",
                       "port": 5432}
    connection = psycopg2.connect(**connection_args)

    files = os.listdir(path)

    in_receivers = set()
    in_providers = set()
    in_support_kinds = set()

    for file in files[:n_files]:
        if ".xml" not in file:
            continue

        print("File", file, "is being processed")

        r, p, s, k = process_file(path + "/" + file)

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

        cursor = connection.cursor()
        sql = {"receivers": "INSERT INTO receivers VALUES %s",
               "gov_bodies": "INSERT INTO providers VALUES %s",
               "kinds": "INSERT INTO support_kinds VALUES %s",
               "aid": "INSERT INTO support_measures (period, start_date, end_date, size, size_unit, violation, misuse, receiver_kind, receiver_category, receiver, provider, kind, form) VALUES %s"}
        pe.execute_values(cursor, sql["receivers"], r, template=None, page_size=100)
        pe.execute_values(cursor, sql["gov_bodies"], p, template=None, page_size=100)
        pe.execute_values(cursor, sql["kinds"], k, template=None, page_size=100)
        pe.execute_values(cursor, sql["aid"], s, template=None, page_size=100)
        connection.commit()

    connection.close()
    return 0


# All files are not valid: 'ВидСуб' attribute not allowed for element.
# print(validate("data"))
process_dir("data", 200)

