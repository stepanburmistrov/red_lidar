# Запуск под Ubuntu 24.04 + ROS 2 Jazzy

Эта инструкция подходит для обычной установки Ubuntu 24.04, когда ROS 2 Jazzy запускается прямо в Linux.

## 1. Что нужно заранее

- Ubuntu 24.04
- установленный ROS 2 Jazzy (`ros-jazzy-desktop`)
- подключённый ESP32 с прошивкой `rosik_lidar_uart.ino`
- LiDAR, подключённый к ESP32

Если ROS 2 ещё не установлен, минимально:

```bash
sudo apt update
sudo apt install -y ros-jazzy-desktop python3-colcon-common-extensions python3-rosdep python3-serial
```

Если `rosdep` ещё не инициализирован:

```bash
sudo rosdep init
rosdep update
```

## 2. Дать доступ к последовательному порту

Чаще всего устройство появится как:

- `/dev/ttyUSB0`
- или `/dev/ttyACM0`

Проверить можно так:

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Добавьте пользователя в группу `dialout`:

```bash
sudo usermod -aG dialout $USER
```

После этого выйдите из системы и войдите заново.

## 3. Сборка пакета

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ROSiK_Lidar_UART/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

Если репозиторий лежит в другом месте — просто замените путь `~/ROSiK_Lidar_UART` на свой.

## 4. Запуск ноды лидара

Запуск только ноды:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ROSiK_Lidar_UART/ros2_ws
source install/setup.bash
ros2 run rosik_lidar rosik_lidar_node --ros-args -p port:=/dev/ttyUSB0
```

Если устройство определилось как `/dev/ttyACM0`, укажите его вместо `/dev/ttyUSB0`.

## 5. Запуск с RViz

Самый простой вариант — через launch-файл:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ROSiK_Lidar_UART/ros2_ws
source install/setup.bash
ros2 launch rosik_lidar lidar.launch.py port:=/dev/ttyUSB0 rviz:=true
```

## 6. Если хотите открыть RViz отдельно

Сначала запустите ноду (см. выше), затем в другом терминале:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ROSiK_Lidar_UART/ros2_ws
source install/setup.bash
rviz2 -d install/rosik_lidar/share/rosik_lidar/rviz/lidar.rviz
```

## 7. Что должно быть в RViz

В готовом конфиге уже настроено:

- `Fixed Frame = base_link`
- отображение `LaserScan`
- топик `/scan`
- вид сверху (`TopDownOrtho`)

Если настраивать вручную:

1. Откройте RViz2.
2. В `Global Options` установите `Fixed Frame = base_link`.
3. Нажмите `Add` → `LaserScan`.
4. Установите `Topic = /scan`.
5. При необходимости выставьте `Reliability Policy = Best Effort`.

## 8. Полезная проверка

```bash
ros2 topic hz /scan
ros2 topic echo /scan --once
ros2 run tf2_ros tf2_echo base_link laser
```

Если картинка повернута или зеркальна, настройте параметры:

- `mirror`
- `angle_offset_deg`

Например:

```bash
ros2 run rosik_lidar rosik_lidar_node --ros-args \
  -p port:=/dev/ttyUSB0 \
  -p mirror:=false \
  -p angle_offset_deg:=0.0
```
