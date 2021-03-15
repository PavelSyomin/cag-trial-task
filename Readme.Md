# Краткая документация

## Что есть что

* schema.dbm — схема базы данных
* schema.sql — то же самое, но в sql
* structure.xsd — xsd-схема для валидации xml-файлов, скачанная с (https://www.nalog.ru/opendata/7707329152-rsmppp/)
* parse.py — скрипт, который парсит данные
* dump.sql — дамп базы после обработки первых двухсот xml-файлов с данными

## Чего здесь нет

Здесь нет самих данных. Предполагается, что они лежат в ./data в распакованном виде.

## Что к чему в схеме БД

* support_measures — это основная таблица с мерами поддержки
* receivers — это таблица с получателями поддержки. Они там все вместе: и юридические лица, и ИП с самозанятыми. В качестве первичного ключа взял ИНН, потому что по идее он уникальный. На практике, конечно, нельзя исключать, что он окажется не уникальным, но в конкретном наборе данных я такого не встретил. На receivers ссылаются support_measures.
* providers — таблица с органами, предоставившими поддержку. Аналогична таблице receivers.
* support_forms — таблица с кодами и названиями форм поддержки. Там всего 7 форм: 0100…0600 и ещё 0000 — это на тот случай, если где-то форма указана неправильно. По сути такой словарик с кодами и названиями, на который ссылается одно из полей support_measures. Наверное, можно было просто писать коды и названия форм поддержки напрямую в support_measures или сделать пользовательский тип данных, но вот решил заморочиться с отдельной таблицей.
* support_kinds — аналогичная таблица, только с видами поддержки. В отличие от предыдущей, коды и названия в неё вставляются в процессе парсинга файлов. Почему так: потому что я нигде не нашёл нормальный справочник форм и видов поддержки, и в итоге у меня парсер стал «ломаться» после нескольких десятков файлов из-за того, что нужного кода поддержки не было в support_kinds. Тогда я сделал автоматическое заполнение этой таблицы в процессе парсинга. Наверное, можно было вообще убрать эту таблицу и вставлять коды напрямую в support_measures.

В схеме для полей таблиц есть комментарии, в которых написано, что именно это за поле. В большинстве случаев комментарии брал прямо из https://file.nalog.ru/opendata/7707329152-rsmppp/VO_SVMSP_2_213_23_04_01.docx

## Как (примерно) работает парсер

Парсер берёт каждый xml-файл, открывает его с помощью BeautifulSoup, берёт в файле элементы «Документ», перебирает их, выбирает нужные элементы и атрибуты, заполняет данными три словаря и один список, после чего делает некоторые проверки, чтобы первичные ключи в receivers, providers и support_kinds не повторялись, и вставляет данные в четыре таблицы БД.

По идее он ещё должен делать валидацию всех xml-файлов, используя structure.xsd в качестве схемы. Но оказалось, что абсолютно все файлы с данными невалидные, так как там есть непонятный атрибут ВидСуб, которого нет в схеме (и в  
https://file.nalog.ru/opendata/7707329152-rsmppp/VO_SVMSP_2_213_23_04_01.docx — тоже нет). Поскольку все файлы невалидные, то пришлось закомментировать бесполезную валидацию и по сути ходить по минному полю и проверять элементы вручную.

## Что с производительностью

Первые двести файлов обработал за 129.5 c (это на Intel Core i5-3317U в один поток при 12Гб оперативной памяти). Все 5162 файла обработал где-то часа за 2 (но точно я не замерял). Расход памяти специально не замерял, но сам процесс с python ест от силы 300 Мб.

(Да, я в итоге обработал все 5162 файла, но поскольку дамп такой БД весит почти 600 Мб и поскольку в задании было достаточно обработать 100–200 файлов, то загрузил сюда дамп после первых 200 файлов).

## Что ещё можно улучшить

Много что :) Подключить другие БД — я так и не успел это сделать, к сожалению. Придумать что-то, чтобы физические и юридические лица в получателях были в разных таблицах (пробовал несколько вариантов это сделать, но в итоге решил, что проще всего сгрузить все данные в одну таблицу). Улучшить код парсера: разбить process_file на функции, улучшить проверку типов и обработку возможных ошибок (потому что в принципе там ещё много мест осталось, в которых во время выполнения может выскочить ошибка, если входные данные будут некорректными). Написать тесты.