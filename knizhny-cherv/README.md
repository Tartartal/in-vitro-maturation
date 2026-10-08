# Книжный червь

Поиск и выгрузка научной литературы для обзора **in vitro maturation** в этом репозитории. Источник — [Europe PMC](https://europepmc.org/) (PubMed, PMC и смежные записи). Сторонние пакеты не нужны: достаточно Python 3.11+.

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
