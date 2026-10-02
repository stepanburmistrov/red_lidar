# ROS2-пакет `rosik_lidar`

Пакет принимает бинарный поток ESP32 и публикует круговой скан в стандартном ROS2-сообщении:

```text
/scan → sensor_msgs/msg/LaserScan
```

Поля `ranges[]` содержат расстояния в метрах, `intensities[]` — нативную интенсивность отражения лидара.

## Сборка

Из каталога `ros2_ws`:

```bash
colcon build --symlink-install
source install/setup.bash
```

Для Windows / PowerShell используйте подробную инструкцию: [`../../../docs/03_ROS2_WINDOWS10.md`](../../../docs/03_ROS2_WINDOWS10.md).

## Запуск ноды

Ubuntu / WSL:

```bash
ros2 run rosik_lidar rosik_lidar_node --ros-args -p port:=/dev/ttyUSB0
```

Windows:

```powershell
ros2 run rosik_lidar rosik_lidar_node --ros-args -p port:=COM6
```

## Запуск с RViz2

```bash
ros2 launch rosik_lidar lidar.launch.py port:=/dev/ttyUSB0 rviz:=true
```

Windows:

```powershell
ros2 launch rosik_lidar lidar.launch.py port:=COM6 rviz:=true
```

## Основные параметры

Значения по умолчанию находятся в [`config/lidar.yaml`](config/lidar.yaml).

| Параметр | По умолчанию | Назначение |
|---|---:|---|
| `port` | `/dev/ttyUSB0` | COM/TTY-порт ESP32 |
| `baud` | `460800` | скорость связи с ESP32 |
| `topic` | `/scan` | имя LaserScan-топика |
| `frame_id` | `laser` | frame лидара |
| `base_frame` | `base_link` | базовый frame робота |
| `publish_static_tf` | `true` | публиковать `base_link → laser` |
| `angle_offset_deg` | `180.0` | поворот скана |
| `mirror` | `true` | зеркальное преобразование направления |
| `range_min` | `0.05` | минимальная дальность, м |
| `range_max` | `16.0` | максимальная дальность, м |
| `scan_bins` | `360` | число угловых ячеек выходного LaserScan |

## Проверка

```bash
ros2 topic hz /scan
```

```bash
ros2 topic echo /scan --once \
  --qos-reliability best_effort \
  --qos-durability volatile
```

Только интенсивность:

```bash
ros2 topic echo /scan --once --field intensities \
  --qos-reliability best_effort \
  --qos-durability volatile
```

## RViz2

Готовый конфиг: [`rviz/lidar.rviz`](rviz/lidar.rviz).

Дополнительная инструкция: [`../../../docs/06_RVIZ.md`](../../../docs/06_RVIZ.md).
