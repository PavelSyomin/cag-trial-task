import psycopg2 as p
import psycopg2.extras as pe
import xmlschema
import os
from bs4 import BeautifulSoup


def validate(path):
    count_valid, count_invalid = 0, 0
    files = os.listdir(path)

    schema = xmlschema.XMLSchema("structure.xsd")

    for file in files:
        if ".xml" not in file:
            continue
        try:
            schema.validate(path + "/" + file)
            count_valid = count_valid + 1
        except xmlschema.exceptions.XMLSchemaException as e:
            count_invalid = count_invalid + 1
            print(e)

    return count_valid, count_invalid


def process_file(file, receivers=set(), gov_bodies=set(), aid_list=[], aid_kinds={}):
    with open(file, mode="r", encoding="utf8") as f:
        soup = BeautifulSoup(f, "xml")

    documents = soup("Документ")

    receiver_kinds = {1: "ul", 2: "fl", 3: "npd"}
    receiver_categories = {1: "micro", 2: "small", 3: "medium", 4: "none"}
    size_units = {1: "rouble", 2: "sq_meter", 3: "hour", 4: "percent", 5: "unit"}
    bool_codes = {1: True, 2: False}

    for document in documents:
        fl = document("СвФЛ")
        ul = document("СвЮЛ")
        aid_set = document("СвПредПод")

        if len(fl) == 1:
            fl = fl[0]
            tin = fl["ИННФЛ"]
            name = fl.find("ФИО")
            if name is not None:
                first_name = name["Имя"]
                surname = name["Фамилия"]
                patronymic = name.get("Отчество")
                if patronymic is None:
                    patronymic = ""
                name = " ".join([surname, first_name, patronymic])

        if len(ul) == 1:
            ul = ul[0]
            tin = ul["ИННЮЛ"]
            name = ul["НаимОрг"]

        receivers.add((tin, name))

        for aid in aid_set:
            gov_body_name = aid["НаимОрг"]
            gov_body_tin = aid["ИННЮЛ"]
            receiver_kind = int(aid["ВидПП"])
            receiver_kind = receiver_kinds[receiver_kind]
            receiver_category = int(aid["КатСуб"])
            receiver_category = receiver_categories[receiver_category]
            period = aid["СрокПод"].replace(".", "/")
            start_date = aid["ДатаПрин"].replace(".", "/")
            end_date = aid.get("ДатаПрекр")
            if end_date is not None:
                end_date = end_date.replace(".", "/")
            form = aid.find("ФормПод")["КодФорм"]
            kind_code = aid.find("ВидПод")["КодВид"]
            kind_name = aid.find("ВидПод")["НаимВид"]
            violation = bool_codes[int(aid.find("ИнфНаруш")["ИнфНаруш"])]
            misuse = bool_codes[int(aid.find("ИнфНаруш")["ИнфНецел"])]
            sizes = aid.find_all("РазмПод")
            for size in sizes:
                quantity = size["РазмПод"]
                unit = int(size["ЕдПод"])
                unit = size_units[unit]
                aid_list.append((period, start_date, end_date, quantity, unit, violation, misuse, receiver_kind,
                           receiver_category, tin, gov_body_tin, kind_code, form))

            gov_bodies.add((gov_body_tin, gov_body_name))
            if kind_code not in aid_kinds:
                aid_kinds[kind_code] = kind_name

    return receivers, gov_bodies, aid_list, aid_kinds


def process_dir(connection, path, n_files):
    files = os.listdir(path)
    already_in_receivers, already_in_gov_bodies, already_in_kinds = set(), set(), set()

    for file in files[:n_files]:
        if ".xml" not in file:
            continue

        print("File", file, "is being processed")

        r, g, a, k = process_file(path + "/" + file)

        r = r - already_in_receivers
        g = g - already_in_gov_bodies
        k = k - already_in_kinds
        already_in_receivers = already_in_receivers | r
        already_in_gov_bodies = already_in_gov_bodies | g
        already_in_kinds = already_in_kinds | k

        cursor = connection.cursor()
        sql = {"receivers": "INSERT INTO receivers VALUES %s",
               "gov_bodies": "INSERT INTO gov_bodies VALUES %s",
               "kinds": "INSERT INTO aid_kinds VALUES %s",
               "aid": "INSERT INTO aid (period, start_date, end_date, size, size_unit, violation, misuse, receiver_kind, receiver_category, receiver, gov_body, kind, form) VALUES %s"}
        pe.execute_values(cursor, sql["receivers"], r, template=None, page_size=100)
        pe.execute_values(cursor, sql["gov_bodies"], g, template=None, page_size=100)
        pe.execute_values(cursor, sql["kinds"], k, template=None, page_size=100)
        pe.execute_values(cursor, sql["aid"], a, template=None, page_size=100)
        connection.commit()
    return 0


# All files are not valid: 'ВидСуб' attribute not allowed for element.
# print(validate("data"))
connection = p.connect(database="smp_aid", user="pavel", password="12345", host="localhost", port=5432)
process_dir(connection, "data", 200)
connection.close()

