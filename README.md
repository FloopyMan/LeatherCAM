# LeatherCAM

Кроссплатформенное CAM-приложение для **CNC 3018 (GRBL 1.1)**, заточенное под изготовление клише для тиснения кожи. Принимает растр (PNG/JPG/BMP) или вектор (SVG/DXF) — выдаёт готовый `.gcode` для станка.

> Проект в активной разработке. Текущий статус — см. [PROGRESS.md](PROGRESS.md).

## Возможности

- **4 стратегии обработки**:
  - **Растровая** — построчный зигзаг по бинаризованному изображению.
  - **Контурная (Profile)** — обход полилиний с компенсацией диаметра фрезы (`on`/`inside`/`outside`).
  - **Карман (Pocket)** — каскадные оффсеты `pyclipper`, корректно обрабатывает дырки внутри букв (Б/О/Р/А/Д). Режим `background` фрезерует фон вокруг рисунка для штампа-клише.
  - **V-carve** — distance transform + level-set контуры для V-фрезы.
- **Зеркалирование по X** для клише-штампа (отпечаток читается правильно).
- **Профили материалов и фрез**: липа, фанера, МДФ, делрин, латунь, алюминий 6061, оргстекло, АМГ3М, Д16 + flat 1/2/3.175 мм, V-bit 30/60/90°, шаровая 1/2 мм, гравёр 0.1 мм, конические сферические TiAlN. Кнопка «Применить рекомендованные параметры» подставляет feed/RPM/step-down.
- **Постпроцессор GRBL 1.1** с модальной оптимизацией (G/F suppression).
- **2D-предпросмотр** со слайдером для прокрутки траектории.
- **Оценка времени работы** и проверка границ рабочего поля (300×180×45 мм).
- **Отправка G-code на станок** через serial (character-counting flow control GRBL), jog, $H, G92, пауза/стоп.
- **Темы** (светлая/тёмная/системная), drag&drop, recent files, логирование.

## Установка

### Готовая сборка

Скачать с [Releases](https://github.com/_owner_/leathercam/releases):
- **Linux**: `LeatherCAM-x86_64.AppImage` — `chmod +x`, запустить двойным кликом.
- **Windows**: `LeatherCAM-Setup-x86_64.exe` — стандартный инсталлятор Inno Setup.

### Из исходников (Linux/macOS)

```bash
git clone https://github.com/_owner_/leathercam
cd leathercam
make dev-install     # .venv с --system-site-packages + pip -e ".[dev]"
make run             # GUI
```

### Из исходников (Windows)

```cmd
git clone https://github.com/_owner_/leathercam
cd leathercam
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m leathercam
```

## Быстрый старт

### Сценарий 1 — Клише для тиснения

1. Открой чёрно-белый PNG (Ctrl+O или drag&drop).
2. Меню **Пресеты → Клише для тиснения** — настроится: растровая стратегия, инверсия (резать фон), зеркало по X.
3. Выбери **Материал** (например, Липа) и **Фрезу** (V-bit 60°) → нажми «Применить рекомендованные параметры».
4. Укажи глубину (например, 0.6 мм) и Safe Z.
5. «Обновить предпросмотр» → проверь bbox и оценку времени.
6. **Файл → Сохранить G-code…** — получишь `.gcode` для UGS/Candle.
7. Или **Файл → Отправить на станок…** (Ctrl+Shift+S) — стрим напрямую по USB.

### Сценарий 2 — Контур из SVG

1. Открой SVG (Ctrl+Shift+O или drag&drop).
2. Стратегия **Контурная (SVG/DXF)**.
3. Выбери фрезу и сторону (`outside` чтобы вырезать деталь, `inside` для отверстия).
4. Глубина = толщине материала + 0.5 мм (на жертвенную доску).

### Сценарий 3 — Карман (выборка фона)

1. Открой SVG с замкнутым контуром (логотип, буквы).
2. Стратегия **Карман (SVG/DXF, выборка фона)**.
3. Установи **Режим (Pocket)** → «фрезеровать фон (оставить рисунок)».
4. Задай **Размер клише, ширина/высота** — границы фрезеруемой области.
5. Step-over обычно = 0.5 × диаметра фрезы.

## Сборка дистрибутивов

### Linux AppImage

Нужны: `appimagetool` ([релизы AppImageKit](https://github.com/AppImage/AppImageKit/releases)) в PATH, установленный `.venv`.

```bash
make dist-install    # установит PyInstaller в .venv
make appimage        # → dist/LeatherCAM-x86_64.AppImage
```

### Windows установщик

Нужны: Python 3.11+, [Inno Setup 6](https://jrsoftware.org/isdl.php).

```cmd
make dist-install
make build
iscc packaging\leathercam.iss
:: → packaging\dist\LeatherCAM-Setup-x86_64.exe
```

### Просто onedir-папка (любая ОС)

```bash
make build
./dist/leathercam/leathercam       # Linux
dist\leathercam\leathercam.exe     # Windows
```

## Архитектура

```
leathercam/
├── gcode/        — постпроцессор GRBL 1.1
├── image/        — растр → бинарная маска
├── vector/       — SVG/DXF → полилинии, группировка с дырками
├── cam/          — стратегии (raster / profile / pocket / vcarve) + метрики
├── profiles/     — материалы/фрезы (JSON в platformdirs)
├── preview/      — рендер траектории на QGraphicsScene
├── grbl/         — serial transport + character-counting flow control
├── ui/           — PySide6 MainWindow и диалог отправки на станок
└── job.py        — оркестратор «вход + параметры → G-code»
```

Ядро (`gcode/`, `image/`, `vector/`, `cam/`, `profiles/`, `grbl/transport.py`) — Qt-free, покрыто unit-тестами. UI — тонкий слой над `job.py`.

## Документация

- [PLAN.md](PLAN.md) — полный план разработки.
- [PROGRESS.md](PROGRESS.md) — журнал выполненных задач.
- [AGENTS.md](AGENTS.md) — инструкции для ИИ-агентов и контрибьюторов.

## Файлы данных

- **Профили**: `~/.config/leathercam/{tools,materials}.json` (Linux) / `%APPDATA%\leathercam\` (Windows). Новые дефолты подтягиваются автоматически.
- **Логи**: `~/.local/state/leathercam/log/leathercam.log` / `%LOCALAPPDATA%\leathercam\Logs\` (rotating, 1 МБ × 5).
- **Recent files / тема**: `QSettings` (стандартное место Qt).

## Лицензия

MIT (будет добавлена при первом релизе).
