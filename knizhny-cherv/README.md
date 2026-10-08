# Книжный червь

Поиск и выгрузка научной литературы для обзора **in vitro maturation** в этом репозитории. Источник — [Europe PMC](https://europepmc.org/) (PubMed, PMC и смежные записи). Текст уже найденной статьи разбирает **Прозектор**. Сторонние пакеты не нужны: достаточно Python 3.11+.

Проект лежит на ветке литературного обзора и закрывает пять вопросов, из которых собран краткий обзор IVM: биология, показания, протоколы, эффективность, безопасность.

## Запросы

Готовые запросы — в [`queries/ivm.json`](queries/ivm.json). Их можно править, не трогая код.

```bash
python3 knizhny-cherv/bookworm.py list-presets
```

## Собрать библиографию

Из корня репозитория:

```bash
python3 knizhny-cherv/bookworm.py presets --limit 20 --out-dir literature/ivm
```

Появятся:

- `literature/ivm/<вопрос>.csv` — статьи одного вопроса, с аннотациями
- `literature/ivm/all.csv` — все строки
- `literature/ivm/unique.csv` — те же статьи без повторов; в `query_id` перечислены вопросы через `;`
- `literature/ivm/bibliography.md` — читаемый список

Сортировка по умолчанию — релевантность Europe PMC. Другие варианты: `--sort cited` и `--sort date`.

## Прозектор

Поиск отдаёт аннотации и ссылки. Прозектор разбирает уже скачанный текст: что сделали авторы, чем был контроль, какие положения взяты из чужих работ, какие получились результаты. Если в статье есть протокол, его шаги вынимаются из общего текста.

Цитаты дословные и остаются на языке статьи. Английский не переводится. Колонка «Без ссылок» только снимает маркеры `[1]`, `[9–11]` и `(Smith et al., 2020)`. Список литературы в конце статьи в таблицы не попадает.

```bash
python3 knizhny-cherv/bookworm.py prozektor article.xml --out literature/ivm/prozektor/article.md
python3 knizhny-cherv/bookworm.py prozektor article.txt --out literature/ivm/prozektor/article.md --csv literature/ivm/prozektor/article.csv
python3 knizhny-cherv/bookworm.py prozektor --pmcid PMC13200467 --docx literature/ivm/prozektor/article.docx
```

`--docx` кладёт те же таблицы в файл Word. Достаточно одного из `--out`, `--csv`, `--docx`.

Файл может быть обычным текстом с заголовками разделов или JATS XML из Europe PMC. Полный текст скачивается только если он есть в PMC. Иначе сохраните статью в файл и передайте его первым аргументом.

Пустая таблица значит, что правило не нашло таких предложений. Это не вывод, что в статье их не было.

## Свой запрос

Синтаксис — [Europe PMC](https://europepmc.org/searchsyntax).

```bash
python3 knizhny-cherv/bookworm.py search \
  'TITLE:"in vitro maturation" AND oocyte AND PUB_TYPE:review' \
  --limit 30 \
  --out literature/ivm/custom.csv
```

## Тесты

```bash
cd knizhny-cherv && python3 -m unittest discover -s tests -v
```
