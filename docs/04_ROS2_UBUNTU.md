# Ubuntu 24.04 + ROS 2 Jazzy

## 1. Установить ROS 2 Jazzy

Предполагается Ubuntu 24.04 и установленный `ros-jazzy-desktop`.

Дополнительные пакеты:

```bash
sudo apt update
sudo apt install -y python3-colcon-common-extensions python3-rosdep python3-serial
```

Если `rosdep` ещё не инициализирован:

```bash
sudo rosdep init
rosdep update
```

## 2. Проверить порт ESP32

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Обычно ESP32 будет `/dev/ttyUSB0` или `/dev/ttyACM0`.

Добавить пользователя в `dialout`:

```bash
sudo usermod -aG dialout $USER
```

После изменения группы выйдите из сеанса и войдите снова.

## 3. Сначала проверить Python

```bash
cd ~/ROSiK_LiDAR
pip install -r requirements.txt
python3 tools/hardware_smoke.py /dev/ttyUSB0 --seconds 10
```

## 4. Собрать ROS workspace

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ROSiK_LiDAR/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

## 5. Запустить ноду

```bash
ros2 run rosik_lidar rosik_lidar_node --ros-args -p port:=/dev/ttyUSB0
```

## 6. Проверить `/scan`

```bash
ros2 topic hz /scan
ros2 topic echo /scan --once --qos-reliability best_effort --qos-durability volatile
ros2 topic echo /scan --once --field intensities --qos-reliability best_effort --qos-durability volatile
```

## 7. RViz

```bash
ros2 launch rosik_lidar lidar.launch.py port:=/dev/ttyUSB0 rviz:=true
```

или:

```bash
rviz2 -d "$(ros2 pkg prefix rosik_lidar)/share/rosik_lidar/rviz/lidar.rviz"
```

Настройки — в `docs/06_RVIZ.md`.
