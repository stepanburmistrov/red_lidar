# Запуск под WSL2 на Windows 10 (с пробросом COM/USB) + RViz

Эта инструкция рассчитана на **Windows 10 + WSL2 + Ubuntu 24.04**.

Особенность Windows 10: для отображения RViz из WSL нужен **X-сервер** на Windows (например, VcXsrv), а для доступа к USB/UART-устройству — проброс USB через `usbipd-win`.

## 1. Что нужно заранее

На Windows:

- WSL2 с Ubuntu 24.04
- установлен `usbipd-win`
- установлен X-сервер, например **VcXsrv**
- подключён ESP32 с лидаром

Внутри WSL:

- ROS 2 Jazzy
- `python3-colcon-common-extensions`, `python3-serial`, `python3-rosdep`

## 2. Проброс USB-устройства в WSL

### 2.1. На Windows, в PowerShell **от имени администратора**

Посмотреть список USB-устройств:

```powershell
usbipd list
```

Найдите в списке ваш USB-UART адаптер / ESP32 и его `BUSID`, например `4-4`.

Один раз привяжите устройство:

```powershell
usbipd bind --busid 4-4
```

Подключите его к WSL:

```powershell
usbipd attach --wsl --busid 4-4
```

Если у вас несколько WSL-дистрибутивов, при необходимости укажите конкретный дистрибутив через параметры `usbipd`.

### 2.2. Внутри WSL

Проверьте, что устройство появилось:

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Обычно это будет `/dev/ttyUSB0` или `/dev/ttyACM0`.

Дайте пользователю доступ к порту:

```bash
sudo usermod -aG dialout $USER
```

После этого лучше закрыть сессию WSL и открыть снова.

## 3. Настройка графики для RViz (Windows 10)

### 3.1. На Windows

Установите и запустите **VcXsrv**.

Обычно достаточно режима:

- `Multiple windows`
- `Start no client`
- `Disable access control` (для простого локального запуска)

### 3.2. Внутри WSL

Настройте переменные окружения:

```bash
export DISPLAY=$(grep nameserver /etc/resolv.conf | awk '{print $2}'):0.0
export QT_X11_NO_MITSHM=1
export LIBGL_ALWAYS_INDIRECT=1
```

Если хотите, добавьте эти строки в `~/.bashrc`.

Проверить X-сервер можно любой GUI-программой, например `xeyes` или `xclock`, если они установлены.

## 4. Сборка пакета в WSL

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ROSiK_Lidar_UART/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

## 5. Запуск только ноды лидара

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ROSiK_Lidar_UART/ros2_ws
source install/setup.bash
ros2 run rosik_lidar rosik_lidar_node --ros-args -p port:=/dev/ttyUSB0
```

## 6. Запуск ноды вместе с RViz

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ROSiK_Lidar_UART/ros2_ws
source install/setup.bash
ros2 launch rosik_lidar lidar.launch.py port:=/dev/ttyUSB0 rviz:=true
```

## 7. Если хотите открыть RViz отдельно

В одном терминале запустите ноду, а в другом:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ROSiK_Lidar_UART/ros2_ws
source install/setup.bash
rviz2 -d install/rosik_lidar/share/rosik_lidar/rviz/lidar.rviz
```

## 8. Что проверить в RViz

- `Fixed Frame = base_link`
- display `LaserScan`
- topic `/scan`
- при необходимости `Reliability Policy = Best Effort`

## 9. Полезная диагностика

```bash
ros2 topic hz /scan
ros2 topic echo /scan --once
ros2 run tf2_ros tf2_echo base_link laser
```

## 10. Если RViz не запускается в WSL

Попробуйте:

```bash
export LIBGL_ALWAYS_SOFTWARE=1
rviz2
```

Это медленнее, но часто помогает на Windows 10 + WSL2.

## 11. Важные замечания

- Когда устройство подключено к WSL через `usbipd`, в Windows-программах оно в этот момент обычно недоступно.
- После переподключения ESP32 иногда нужно заново выполнить `usbipd attach --wsl --busid ...`.
- Если хотите не связываться с X-сервером, удобный вариант: запускать ROS 2 и RViz либо целиком в Ubuntu, либо целиком в Windows.
