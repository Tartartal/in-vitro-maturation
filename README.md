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

Поиск статей и рабочая библиография живут в каталоге [`literature/`](literature/SEARCH_STRATEGY.md). Ищет их проект [Книжный червь](knizhny-cherv/README.md) по Europe PMC. Текст отобранной статьи разбирает Прозектор.

```bash
python3 knizhny-cherv/bookworm.py presets --limit 20 --out-dir literature/ivm
python3 knizhny-cherv/bookworm.py prozektor article.xml --out literature/ivm/prozektor/article.md
python3 knizhny-cherv/bookworm.py prozektor --pmcid PMC10664544 --docx literature/ivm/prozektor/Das_Son_2023_IVM.docx
```

Разбор Das M, Son WY, 2023: [`literature/ivm/prozektor/Das_Son_2023_IVM.docx`](literature/ivm/prozektor/Das_Son_2023_IVM.docx).

## Пересборка DOCX

```bash
python create_docx.py
```
