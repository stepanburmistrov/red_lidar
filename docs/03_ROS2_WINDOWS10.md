# ROS 2 Jazzy под Windows 10

## Установка ROS 2

Для установки под Windows 10 можно использовать подробный урок:

https://stepik.org/lesson/2012052/step/1?unit=2040279

Бесплатный курс целиком:

https://stepik.org/course/221157/syllabus

Ниже приведён запуск ROSiK LiDAR для конфигурации, где ROS 2 установлен в `C:\pixi_ws\ros2-windows` и используется `pixi shell`.

## 1. Открыть окружение ROS 2

```powershell
cd C:\pixi_ws
pixi shell
. "C:\pixi_ws\ros2-windows\local_setup.ps1"
```

Проверка:

```powershell
ros2 --help
```

## 2. Перейти в workspace проекта

Например:

```powershell
cd C:\work\ROSiK_LiDAR\ros2_ws
```

## 3. Собрать пакет

Первая или чистая сборка:

```powershell
Remove-Item -Recurse -Force build, install, log -ErrorAction SilentlyContinue
colcon build --merge-install
```

## 4. Подключить собранный workspace

В PowerShell используйте **PowerShell-скрипт**, а не `.bat`:

```powershell
. .\install\local_setup.ps1
```

Точка, пробел и затем путь — это dot-sourcing PowerShell. Переменные окружения применяются к текущей консоли.

Неправильно для PowerShell:

```text
.\install\local_setup.bat
```

`.bat` выполняется через `cmd.exe`, и его изменения окружения не обязаны сохраниться в текущей PowerShell-сессии.

## 5. Проверить пакет

```powershell
ros2 pkg prefix rosik_lidar
```

Путь должен указывать на `install` именно текущего workspace.

Также:

```powershell
ros2 pkg executables rosik_lidar
```

Ожидается `rosik_lidar_node`.

## 6. Запустить ноду

Пусть ESP32 определилась как `COM6`:

```powershell
ros2 run rosik_lidar rosik_lidar_node --ros-args -p port:=COM6
```

Не запускайте одновременно `hardware_smoke.py` или `lidar_viewer.py`: они тоже используют COM6.

## 7. Проверить `/scan`

Во втором PowerShell повторно активируйте ROS 2 и workspace:

```powershell
cd C:\pixi_ws
pixi shell
. "C:\pixi_ws\ros2-windows\local_setup.ps1"
cd C:\work\ROSiK_LiDAR\ros2_ws
. .\install\local_setup.ps1
```

Затем:

```powershell
ros2 topic hz /scan
```

Проверка одного сообщения:

```powershell
ros2 topic echo /scan --once --qos-reliability best_effort --qos-durability volatile
```

Только intensity:

```powershell
ros2 topic echo /scan --once --field intensities --qos-reliability best_effort --qos-durability volatile
```

Нормально, если вывод содержит `array('f', [...])` с числами. Пустой `array('f')` означает, что intensity не прикреплена к LaserScan.

## 8. Запустить RViz2

```powershell
rviz2
```

Либо через launch:

```powershell
ros2 launch rosik_lidar lidar.launch.py port:=COM6 rviz:=true
```

Настройки RViz подробно: `docs/06_RVIZ.md`.

## 9. Запустить готовый конфиг RViz вручную

```powershell
$p = ros2 pkg prefix rosik_lidar
rviz2 -d "$p\share\rosik_lidar\rviz\lidar.rviz"
```

## 10. Следующий запуск

Если пакет уже собран, обычно достаточно:

```powershell
cd C:\pixi_ws
pixi shell
. "C:\pixi_ws\ros2-windows\local_setup.ps1"
cd C:\work\ROSiK_LiDAR\ros2_ws
. .\install\local_setup.ps1
ros2 run rosik_lidar rosik_lidar_node --ros-args -p port:=COM6
```
