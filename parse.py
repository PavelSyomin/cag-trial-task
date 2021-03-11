import psycopg2 as p


connection = p.connect(database="smp_aid", user="pavel", password="12345", host="localhost", port=5432)
