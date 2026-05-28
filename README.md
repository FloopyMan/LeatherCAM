# LeatherCAM

CAM-приложение для CNC 3018 (GRBL 1.1), ориентированное на изготовление клише для тиснения кожи. Из растрового изображения (PNG/JPG) или вектора (SVG/DXF) генерирует G-code для фрезеровки.

> Проект в активной разработке. Текущий статус — см. [PROGRESS.md](PROGRESS.md).

## Возможности (целевые)

- Импорт PNG, JPG, BMP, SVG, DXF.
- Профили материалов (липа, фанера, ЛДФ, делрин, латунь и др.) и фрез (flat, V-bit, шаровая, гравёр).
- Стратегии: растровая гравировка (zigzag), контурная обработка (profile), выборка кармана (pocket), V-carving, heightmap → рельеф.
- Компенсация диаметра фрезы, многопроходная обработка с step-down.
- 2D и псевдо-3D предпросмотр траектории, оценка времени.
- Постпроцессор G-code для GRBL 1.1.
- Кроссплатформенность: Linux и Windows.

## Стек

- Python 3.11+, PySide6 (Qt 6).
- Pillow, OpenCV, NumPy, SciPy.
- Shapely, pyclipper.
- svgelements, ezdxf.
- pytest, ruff.

## Установка для разработки

Вариант через Makefile (Linux/macOS):

```bash
make dev-install        # создаст .venv c --system-site-packages и поставит -e ".[dev]"
make run                # запустит GUI
make test-headless      # прогонит тесты под offscreen Qt
make check              # ruff lint + ruff format --check + tests
```

Ручной вариант (или Windows):

```bash
python -m venv .venv
source .venv/bin/activate         # Linux
.venv\Scripts\activate            # Windows
pip install -e ".[dev]"
python -m leathercam              # запуск GUI
pytest -q                         # тесты
```

## Документация

- [PLAN.md](PLAN.md) — полный план разработки по этапам.
- [PROGRESS.md](PROGRESS.md) — журнал выполненных задач.
- [AGENTS.md](AGENTS.md) — инструкции для ИИ-агентов и контрибьюторов.

## Лицензия

MIT (будет добавлена при первом релизе).
