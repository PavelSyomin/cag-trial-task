-- Database generated with pgModeler (PostgreSQL Database Modeler).
-- pgModeler  version: 0.9.2
-- PostgreSQL version: 12.0
-- Project Site: pgmodeler.io
-- Model Author: ---


-- Database creation must be done outside a multicommand file.
-- These commands were put in this file only as a convenience.
-- -- object: smb_support | type: DATABASE --
-- -- DROP DATABASE IF EXISTS smb_support;
-- CREATE DATABASE smb_support;
-- -- ddl-end --
-- 

-- object: public.receivers | type: TABLE --
-- DROP TABLE IF EXISTS public.receivers CASCADE;
CREATE TABLE public.receivers (
	tin varchar(12) NOT NULL,
	name varchar(1000) NOT NULL,
	CONSTRAINT receivers_pk PRIMARY KEY (tin)

);
-- ddl-end --
COMMENT ON TABLE public.receivers IS E'Получатели поддержки (как физические, так и юридические лица)';
-- ddl-end --
COMMENT ON COLUMN public.receivers.tin IS E'ИНН';
-- ddl-end --
COMMENT ON COLUMN public.receivers.name IS E'ФИО (для физических лиц) или наименование (для юридических лиц)';
-- ddl-end --
-- ALTER TABLE public.receivers OWNER TO postgres;
-- ddl-end --

-- object: public.size_unit | type: TYPE --
-- DROP TYPE IF EXISTS public.size_unit CASCADE;
CREATE TYPE public.size_unit AS
 ENUM ('rouble','sq_meter','hour','percent','unit');
-- ddl-end --
-- ALTER TYPE public.size_unit OWNER TO postgres;
-- ddl-end --

-- object: public.support_forms | type: TABLE --
-- DROP TABLE IF EXISTS public.support_forms CASCADE;
CREATE TABLE public.support_forms (
	code char(4) NOT NULL,
	name varchar(200) NOT NULL,
	CONSTRAINT support_forms_pk PRIMARY KEY (code)

);
-- ddl-end --
COMMENT ON TABLE public.support_forms IS E'Коды и названия форм поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_forms.code IS E'Код';
-- ddl-end --
COMMENT ON COLUMN public.support_forms.name IS E'Название';
-- ddl-end --
-- ALTER TABLE public.support_forms OWNER TO postgres;
-- ddl-end --

-- Appended SQL commands --
insert into support_forms (code, name) values
	('0000', 'Нет данных'),
	('0100', 'Финансовая поддержка'),
	('0200', 'Информационная поддержка'),
	('0300', 'Образовательная поддержка'),
	('0400', 'Консультационная поддержка'),
	('0500', 'Имущественная поддержка'),
	('0600', 'Инновационная поддержка');
-- ddl-end --

-- object: public.providers | type: TABLE --
-- DROP TABLE IF EXISTS public.providers CASCADE;
CREATE TABLE public.providers (
	tin varchar(10) NOT NULL,
	name varchar(1000) NOT NULL,
	CONSTRAINT providers_pk PRIMARY KEY (tin)

);
-- ddl-end --
COMMENT ON TABLE public.providers IS E'Органы, предоставившие поддержку';
-- ddl-end --
COMMENT ON COLUMN public.providers.tin IS E'ИНН';
-- ddl-end --
COMMENT ON COLUMN public.providers.name IS E'Наименование органа власти';
-- ddl-end --
-- ALTER TABLE public.providers OWNER TO postgres;
-- ddl-end --

-- object: public.receiver_kinds | type: TYPE --
-- DROP TYPE IF EXISTS public.receiver_kinds CASCADE;
CREATE TYPE public.receiver_kinds AS
 ENUM ('ul','fl','npd');
-- ddl-end --
-- ALTER TYPE public.receiver_kinds OWNER TO postgres;
-- ddl-end --

-- object: public.receiver_categories | type: TYPE --
-- DROP TYPE IF EXISTS public.receiver_categories CASCADE;
CREATE TYPE public.receiver_categories AS
 ENUM ('micro','small','medium','none');
-- ddl-end --
-- ALTER TYPE public.receiver_categories OWNER TO postgres;
-- ddl-end --

-- object: public.support_measures | type: TABLE --
-- DROP TABLE IF EXISTS public.support_measures CASCADE;
CREATE TABLE public.support_measures (
	id serial NOT NULL,
	period date NOT NULL,
	start_date date NOT NULL,
	end_date date,
	size numeric(11,2) NOT NULL,
	size_unit public.size_unit NOT NULL,
	violation bool NOT NULL,
	misuse bool NOT NULL,
	receiver_kind public.receiver_kinds NOT NULL,
	receiver_category public.receiver_categories NOT NULL,
	source_file varchar(100),
	doc_id varchar(60),
	receiver varchar(12),
	provider varchar(10),
	form char(4),
	kind char(4),
	CONSTRAINT support_measures_pk PRIMARY KEY (id)

);
-- ddl-end --
COMMENT ON TABLE public.support_measures IS E'Меры поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_measures.period IS E'Срок оказания поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_measures.start_date IS E'Дата принятия решения о предоставлении поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_measures.end_date IS E'Дата принятия решения о прекращении оказания поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_measures.size IS E'Размер поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_measures.size_unit IS E'Единица измерения поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_measures.violation IS E'Информация о наличии нарушения порядка и условий предоставления поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_measures.misuse IS E'Информация о нецелевом использовании средств поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_measures.receiver_kind IS E'Вид получателя поддержки на дату принятия решения о предоставлении поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_measures.receiver_category IS E'Категория субъекта малого и среднего предпринимательства на дату принятия решения о предоставлении поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_measures.source_file IS E'Название файла, из которого взята запись';
-- ddl-end --
COMMENT ON COLUMN public.support_measures.doc_id IS E'Идентификатор документа (ИдДок) в файле';
-- ddl-end --
-- ALTER TABLE public.support_measures OWNER TO postgres;
-- ddl-end --

-- object: providers_fk | type: CONSTRAINT --
-- ALTER TABLE public.support_measures DROP CONSTRAINT IF EXISTS providers_fk CASCADE;
ALTER TABLE public.support_measures ADD CONSTRAINT providers_fk FOREIGN KEY (provider)
REFERENCES public.providers (tin) MATCH FULL
ON DELETE SET NULL ON UPDATE CASCADE;
-- ddl-end --

-- object: receivers_fk | type: CONSTRAINT --
-- ALTER TABLE public.support_measures DROP CONSTRAINT IF EXISTS receivers_fk CASCADE;
ALTER TABLE public.support_measures ADD CONSTRAINT receivers_fk FOREIGN KEY (receiver)
REFERENCES public.receivers (tin) MATCH FULL
ON DELETE SET NULL ON UPDATE CASCADE;
-- ddl-end --

-- object: public.support_kinds | type: TABLE --
-- DROP TABLE IF EXISTS public.support_kinds CASCADE;
CREATE TABLE public.support_kinds (
	code char(4) NOT NULL,
	name varchar(400) NOT NULL,
	CONSTRAINT support_kinds_pk PRIMARY KEY (code)

);
-- ddl-end --
COMMENT ON TABLE public.support_kinds IS E'Коды и названия видов поддержки';
-- ddl-end --
COMMENT ON COLUMN public.support_kinds.code IS E'Код';
-- ddl-end --
COMMENT ON COLUMN public.support_kinds.name IS E'Название';
-- ddl-end --
-- ALTER TABLE public.support_kinds OWNER TO postgres;
-- ddl-end --

-- object: support_forms_fk | type: CONSTRAINT --
-- ALTER TABLE public.support_measures DROP CONSTRAINT IF EXISTS support_forms_fk CASCADE;
ALTER TABLE public.support_measures ADD CONSTRAINT support_forms_fk FOREIGN KEY (form)
REFERENCES public.support_forms (code) MATCH FULL
ON DELETE SET NULL ON UPDATE CASCADE;
-- ddl-end --

-- object: support_kinds_fk | type: CONSTRAINT --
-- ALTER TABLE public.support_measures DROP CONSTRAINT IF EXISTS support_kinds_fk CASCADE;
ALTER TABLE public.support_measures ADD CONSTRAINT support_kinds_fk FOREIGN KEY (kind)
REFERENCES public.support_kinds (code) MATCH FULL
ON DELETE SET NULL ON UPDATE CASCADE;
-- ddl-end --


