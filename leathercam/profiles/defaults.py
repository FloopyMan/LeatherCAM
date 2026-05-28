"""Built-in default profiles shipped with the app.

Values are conservative starting points for a CNC 3018 (low rigidity,
500W spindle) cutting on a workpiece that's well clamped. Always
sanity-check on a test piece before running production work.
"""

from __future__ import annotations

from leathercam.profiles.models import Material, Recommendation, Tool

DEFAULT_TOOLS: tuple[Tool, ...] = (
    Tool(id="flat_1mm", name="Прямая фреза 1 мм", kind="flat", diameter_mm=1.0),
    Tool(id="flat_2mm", name="Прямая фреза 2 мм", kind="flat", diameter_mm=2.0),
    Tool(
        id="flat_3.175mm",
        name='Прямая фреза 3.175 мм (1/8")',
        kind="flat",
        diameter_mm=3.175,
    ),
    Tool(
        id="vbit_30",
        name="V-bit 30°",
        kind="vbit",
        diameter_mm=3.175,
        angle_deg=30.0,
        flute_length_mm=12.0,
    ),
    Tool(
        id="vbit_60",
        name="V-bit 60°",
        kind="vbit",
        diameter_mm=3.175,
        angle_deg=60.0,
        flute_length_mm=12.0,
    ),
    Tool(
        id="vbit_90",
        name="V-bit 90°",
        kind="vbit",
        diameter_mm=3.175,
        angle_deg=90.0,
        flute_length_mm=12.0,
    ),
    Tool(id="ball_1mm", name="Шаровая фреза 1 мм", kind="ball", diameter_mm=1.0),
    Tool(id="ball_2mm", name="Шаровая фреза 2 мм", kind="ball", diameter_mm=2.0),
    Tool(
        id="engraver_0.1mm",
        name="Гравёр 0.1 мм",
        kind="engraver",
        diameter_mm=0.1,
        angle_deg=20.0,
    ),
    # Tapered ball-nose engravers (treated as "ball" kind with a taper angle).
    # diameter_mm is the tip diameter (2*R); the angle is the full taper.
    Tool(
        id="tapered_ball_R0.25",
        name="Конический сферический R0.25 L15 D3.175 TiAlN (A=5.1°)",
        kind="ball",
        diameter_mm=0.5,
        angle_deg=5.1,
        flute_length_mm=15.0,
    ),
    Tool(
        id="tapered_ball_R0.1",
        name="Конический сферический R0.1 L15 D3.175 (A=5.66°)",
        kind="ball",
        diameter_mm=0.2,
        angle_deg=5.66,
        flute_length_mm=15.0,
    ),
    Tool(
        id="tapered_ball_R0.5",
        name="Конический сферический R0.5 L15 D3.175 TiAlN (A=4.15°)",
        kind="ball",
        diameter_mm=1.0,
        angle_deg=4.15,
        flute_length_mm=15.0,
    ),
)


DEFAULT_MATERIALS: tuple[Material, ...] = (
    Material(
        id="linden",
        name="Липа",
        description="Мягкая древесина, идеальна для клише.",
        recommendations=(
            Recommendation(
                "flat_1mm", feed_xy=500, feed_z=150, spindle_rpm=10000, step_down_mm=0.3
            ),
            Recommendation(
                "flat_2mm", feed_xy=700, feed_z=200, spindle_rpm=10000, step_down_mm=0.5
            ),
            Recommendation("vbit_60", feed_xy=800, feed_z=250, spindle_rpm=12000, step_down_mm=0.3),
            Recommendation("vbit_30", feed_xy=600, feed_z=200, spindle_rpm=12000, step_down_mm=0.2),
            Recommendation(
                "engraver_0.1mm",
                feed_xy=300,
                feed_z=100,
                spindle_rpm=12000,
                step_down_mm=0.1,
            ),
        ),
    ),
    Material(
        id="birch_plywood",
        name="Берёзовая фанера",
        description="Слоистая структура, заметные перепады плотности.",
        recommendations=(
            Recommendation(
                "flat_1mm", feed_xy=400, feed_z=120, spindle_rpm=12000, step_down_mm=0.2
            ),
            Recommendation(
                "flat_2mm", feed_xy=600, feed_z=180, spindle_rpm=12000, step_down_mm=0.4
            ),
            Recommendation(
                "vbit_60", feed_xy=600, feed_z=200, spindle_rpm=12000, step_down_mm=0.25
            ),
        ),
    ),
    Material(
        id="mdf",
        name="МДФ / ЛДФ",
        description="Равномерная плотность, пылит — нужен пылесос.",
        recommendations=(
            Recommendation(
                "flat_1mm", feed_xy=600, feed_z=180, spindle_rpm=10000, step_down_mm=0.4
            ),
            Recommendation(
                "flat_2mm", feed_xy=900, feed_z=250, spindle_rpm=10000, step_down_mm=0.7
            ),
            Recommendation("vbit_60", feed_xy=900, feed_z=300, spindle_rpm=12000, step_down_mm=0.4),
        ),
    ),
    Material(
        id="delrin",
        name="Делрин (POM)",
        description="Полиоксиметилен, отлично режется, малый износ фрезы.",
        recommendations=(
            Recommendation(
                "flat_1mm", feed_xy=400, feed_z=120, spindle_rpm=12000, step_down_mm=0.2
            ),
            Recommendation(
                "flat_2mm", feed_xy=600, feed_z=180, spindle_rpm=12000, step_down_mm=0.4
            ),
            Recommendation(
                "vbit_60", feed_xy=500, feed_z=180, spindle_rpm=12000, step_down_mm=0.25
            ),
        ),
    ),
    Material(
        id="brass",
        name="Латунь (мягкая)",
        description="Только однозубые фрезы или гравёры, обязательно смазка.",
        recommendations=(
            Recommendation(
                "flat_1mm", feed_xy=120, feed_z=40, spindle_rpm=10000, step_down_mm=0.05
            ),
            Recommendation(
                "engraver_0.1mm",
                feed_xy=150,
                feed_z=50,
                spindle_rpm=12000,
                step_down_mm=0.05,
            ),
        ),
    ),
    Material(
        id="aluminium",
        name="Алюминий (мягкий, типа 6061)",
        description="Только лёгкие проходы, обязательно смазка/охлаждение.",
        recommendations=(
            Recommendation(
                "flat_1mm", feed_xy=100, feed_z=30, spindle_rpm=12000, step_down_mm=0.05
            ),
            Recommendation("flat_2mm", feed_xy=180, feed_z=60, spindle_rpm=12000, step_down_mm=0.1),
        ),
    ),
    Material(
        id="pmma_10mm",
        name="Оргстекло (ПММА) 10 мм",
        description="Низкие подачи и обороты, иначе плавится. Желателен обдув.",
        recommendations=(
            Recommendation(
                "flat_1mm", feed_xy=400, feed_z=120, spindle_rpm=10000, step_down_mm=0.3
            ),
            Recommendation(
                "flat_2mm", feed_xy=600, feed_z=180, spindle_rpm=10000, step_down_mm=0.5
            ),
            Recommendation("vbit_60", feed_xy=500, feed_z=180, spindle_rpm=12000, step_down_mm=0.3),
            Recommendation(
                "tapered_ball_R0.25",
                feed_xy=350,
                feed_z=120,
                spindle_rpm=12000,
                step_down_mm=0.15,
            ),
            Recommendation(
                "tapered_ball_R0.1",
                feed_xy=250,
                feed_z=80,
                spindle_rpm=12000,
                step_down_mm=0.05,
            ),
            Recommendation(
                "tapered_ball_R0.5",
                feed_xy=500,
                feed_z=160,
                spindle_rpm=12000,
                step_down_mm=0.2,
            ),
        ),
    ),
    Material(
        id="aluminium_amg3m_8mm",
        name="Лист алюминиевый АМГ3М 8 мм",
        description="Мягкий сплав Al-Mg, обязательно смазка (WD-40 или керосин).",
        recommendations=(
            Recommendation(
                "flat_1mm", feed_xy=120, feed_z=40, spindle_rpm=12000, step_down_mm=0.05
            ),
            Recommendation("flat_2mm", feed_xy=200, feed_z=60, spindle_rpm=12000, step_down_mm=0.1),
            Recommendation(
                "tapered_ball_R0.25",
                feed_xy=120,
                feed_z=40,
                spindle_rpm=12000,
                step_down_mm=0.05,
            ),
            Recommendation(
                "tapered_ball_R0.1",
                feed_xy=80,
                feed_z=30,
                spindle_rpm=12000,
                step_down_mm=0.03,
            ),
            Recommendation(
                "tapered_ball_R0.5",
                feed_xy=180,
                feed_z=60,
                spindle_rpm=12000,
                step_down_mm=0.08,
            ),
        ),
    ),
    Material(
        id="aluminium_d16_14mm",
        name="Алюминий Д16 14 мм (квадрат)",
        description="Дюраль (Al-Cu), плотный — самые лёгкие проходы. Смазка обязательна.",
        recommendations=(
            Recommendation("flat_1mm", feed_xy=80, feed_z=25, spindle_rpm=12000, step_down_mm=0.03),
            Recommendation(
                "flat_2mm", feed_xy=150, feed_z=45, spindle_rpm=12000, step_down_mm=0.07
            ),
            Recommendation(
                "tapered_ball_R0.25",
                feed_xy=80,
                feed_z=25,
                spindle_rpm=12000,
                step_down_mm=0.03,
            ),
            Recommendation(
                "tapered_ball_R0.1",
                feed_xy=50,
                feed_z=18,
                spindle_rpm=12000,
                step_down_mm=0.02,
            ),
            Recommendation(
                "tapered_ball_R0.5",
                feed_xy=120,
                feed_z=40,
                spindle_rpm=12000,
                step_down_mm=0.05,
            ),
        ),
    ),
)
