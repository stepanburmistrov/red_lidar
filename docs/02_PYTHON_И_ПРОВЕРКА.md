# Python: проверка железа и визуализация

Python-утилиты позволяют полностью проверить ESP32 и лидар без ROS 2. Это лучший первый шаг диагностики.

## Установка зависимостей

Из корня репозитория:

```bash
pip install -r requirements.txt
```

Если хотите отдельное окружение:

### Windows

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Аппаратный smoke-test

Windows:

```powershell
python tools\hardware_smoke.py COM6 --seconds 10
```

Linux:

```bash
python3 tools/hardware_smoke.py /dev/ttyUSB0 --seconds 10
```

Пример нормального результата:

```text
scan packets:       52
scan rate:          5.20 Hz
intensity packets:  52
matched intensity:  52/52
without intensity:  0
sequence gaps:      0
CRC errors:         0
header errors:      0
[PASS] distance scan transport is stable.
[PASS] intensity companion packets are stable.
```

### Что означают поля

- `scan packets` — число полных сканов расстояний;
- `scan rate` — частота полных оборотов/сканов;
- `intensity packets` — число companion-пакетов intensity;
- `matched intensity` — сколько intensity-пакетов удалось связать с соответствующим сканом;
- `sequence gaps` — пропуски номеров сканов;
- `CRC errors` — ошибки контрольной суммы;
- `header errors` — повреждённые/неожиданные заголовки;
- `native intensity` — диапазон реально полученной отражательной способности.

## Python-визуализатор

### Окраска по intensity

```powershell
python tools\lidar_viewer.py COM6 --color-by intensity
```

### Окраска по расстоянию

```powershell
python tools\lidar_viewer.py COM6 --color-by distance
```

Linux:

```bash
python3 tools/lidar_viewer.py /dev/ttyUSB0 --color-by intensity
```

## Дополнительные параметры

```bash
python3 tools/lidar_viewer.py /dev/ttyUSB0 --max-range 6
python3 tools/lidar_viewer.py /dev/ttyUSB0 --offset 180
python3 tools/lidar_viewer.py /dev/ttyUSB0 --no-mirror
```

## Важно

Перед запуском Python закройте:

- Arduino Serial Monitor;
- ROS-ноду;
- другую копию viewer;
- любую программу, которая держит тот же COM/TTY-порт.

## Если Python работает, а ROS нет

Это хороший признак: аппаратный тракт уже исправен. Тогда проверяйте сборку ROS workspace, `local_setup`, QoS и настройки RViz по `docs/08_ДИАГНОСТИКА.md`.
