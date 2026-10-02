# Запуск под Windows 10 + ROS 2 Jazzy

Эта инструкция подходит для нативного запуска ROS 2 Jazzy в Windows 10.

## 1. Что нужно заранее

- Windows 10
- установленный ROS 2 Jazzy for Windows
- желательно открывать всё из **ROS 2 Jazzy Command Prompt**
- подключённый ESP32 с прошивкой `rosik_lidar_uart.ino`
- известный номер COM-порта, например `COM6`

Проверить COM-порт можно в **Диспетчере устройств** → **Порты (COM & LPT)**.

## 2. Подготовка рабочего каталога

Распакуйте репозиторий, например в:

```text
C:\work\ROSiK_Lidar_UART
```

## 3. Установка Python-зависимостей для просмотрщика (необязательно, но полезно)

В `ROS 2 Jazzy Command Prompt`:

```bat
cd /d C:\work\ROSiK_Lidar_UART
py -m pip install -r requirements.txt
```

Проверка просмотрщика:

```bat
python tools\lidar_viewer.py COM6
```

## 4. Сборка ROS 2 пакета

Откройте **ROS 2 Jazzy Command Prompt** и выполните:

```bat
cd /d C:\work\ROSiK_Lidar_UART\ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --merge-install
call install\local_setup.bat
```

Если `rosdep` на Windows не настроен или ругается, можно собрать пакет и без этого шага, так как внешних зависимостей у пакета минимум.

## 5. Запуск только ноды лидара

```bat
cd /d C:\work\ROSiK_Lidar_UART\ros2_ws
call install\local_setup.bat
ros2 run rosik_lidar rosik_lidar_node --ros-args -p port:=COM6
```

## 6. Запуск ноды вместе с RViz

```bat
cd /d C:\work\ROSiK_Lidar_UART\ros2_ws
call install\local_setup.bat
ros2 launch rosik_lidar lidar.launch.py port:=COM6 rviz:=true
```

## 7. Если хотите открыть RViz отдельно

Сначала запустите ноду (см. выше), затем в новом окне **ROS 2 Jazzy Command Prompt**:

```bat
cd /d C:\work\ROSiK_Lidar_UART\ros2_ws
call install\local_setup.bat
rviz2 -d install\rosik_lidar\share\rosik_lidar\rviz\lidar.rviz
```

## 8. Что проверить в RViz

- `Fixed Frame = base_link`
- есть display типа `LaserScan`
- выбран топик `/scan`
- если точки не видны, для `LaserScan` установите `Reliability Policy = Best Effort`

## 9. Диагностика

```bat
ros2 topic hz /scan
ros2 topic echo /scan --once
ros2 run tf2_ros tf2_echo base_link laser
```

## 10. Частые проблемы

### RViz не показывает точки

Проверьте:

- правильный ли COM-порт указан;
- есть ли данные в `/scan` (`ros2 topic hz /scan`);
- выбран ли `Fixed Frame = base_link`;
- выставлен ли `Best Effort` в настройках `LaserScan`.

### Порт занят

Закройте Arduino Serial Monitor, Python viewer и другие программы, которые могут держать `COM6`.

### Лидар повернут не так

Попробуйте:

```bat
ros2 run rosik_lidar rosik_lidar_node --ros-args -p port:=COM6 -p mirror:=false -p angle_offset_deg:=0.0
```
