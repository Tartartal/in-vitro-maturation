# In vitro maturation (IVM)

Краткий обзор метода **in vitro maturation** для вспомогательных репродуктивных технологий.

## Документ

- [`In_vitro_maturation_overview.docx`](./In_vitro_maturation_overview.docx) — обзор на ≈2 страницы (русский язык)

## Содержание обзора

1. Определение и биологическая суть  
2. Клинические показания  
3. Протоколы и лабораторные подходы  
4. Эффективность и безопасность  
5. Ограничения и перспективы  

## Литературный обзор

Поиск статей и рабочая библиография живут в каталоге [`literature/`](literature/SEARCH_STRATEGY.md). Ищет их проект [Книжный червь](knizhny-cherv/README.md) по Europe PMC.

```bash
python3 knizhny-cherv/bookworm.py presets --limit 20 --out-dir literature/ivm
```

Полные тексты в этот репозиторий не кладутся. Открытые `.pdf`, `.docx` и `.djvu` Книжный червь складывает в отдельный репозиторий статей, по папке на тему обзора. Если файл скачать нельзя, это написано в [`literature/ivm/bibliography.md`](literature/ivm/bibliography.md).

```bash
python3 knizhny-cherv/bookworm.py fetch \
  --out-dir literature/ivm \
  --library ../ivm-articles \
  --library-url https://github.com/Tartartal/ivm-articles
```

## Пересборка DOCX

```bash
python create_docx.py
```
