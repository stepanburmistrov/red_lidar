# Windows 10 + WSL2 + ROS 2 Jazzy

WSL2 удобен для Linux-окружения ROS 2, но USB-устройство ESP32 нужно передать из Windows в WSL.

## 1. Подготовить WSL

Рекомендуется Ubuntu 24.04 в WSL2 и ROS 2 Jazzy.

## 2. Установить usbipd-win в Windows

После установки откройте PowerShell **от имени администратора**.

Посмотреть устройства:

```powershell
usbipd list
```

Найдите ESP32/USB-UART и его `BUSID`, например `4-4`.

Один раз разрешить экспорт:

```powershell
usbipd bind --busid 4-4
```

Подключить к WSL:

```powershell
usbipd attach --wsl --busid 4-4
```

После переподключения ESP32 команду `attach` иногда нужно выполнить снова.

## 3. Проверить устройство в WSL

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Добавить пользователя в `dialout`:

```bash
sudo usermod -aG dialout $USER
```

Перезапустите WSL-сессию.

## 4. Проверить лидар Python-тестом

```bash
cd ~/ROSiK_LiDAR
pip install -r requirements.txt
python3 tools/hardware_smoke.py /dev/ttyUSB0 --seconds 10
```

## 5. Собрать ROS 2 пакет

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ROSiK_LiDAR/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

## 6. Запустить ноду

```bash
ros2 run rosik_lidar rosik_lidar_node --ros-args -p port:=/dev/ttyUSB0
```

## 7. RViz под Windows 10

На Windows 10 WSL обычно требует отдельный X-сервер, например VcXsrv.

После запуска X-сервера в WSL можно задать:

```bash
export DISPLAY=$(grep nameserver /etc/resolv.conf | awk '{print $2}'):0.0
export QT_X11_NO_MITSHM=1
```

Если OpenGL работает нестабильно:

```bash
export LIBGL_ALWAYS_SOFTWARE=1
```

Запуск:

```bash
rviz2
```

или:

```bash
ros2 launch rosik_lidar lidar.launch.py port:=/dev/ttyUSB0 rviz:=true
```

## Важно

Когда USB-устройство передано в WSL через `usbipd`, Windows-приложения обычно не могут одновременно использовать тот же COM-порт.
