# RViz2: отображение ROSiK LiDAR

## Готовый конфиг

В репозитории уже есть:

```text
ros2_ws/src/rosik_lidar/rviz/lidar.rviz
```

Запуск через launch:

```bash
ros2 launch rosik_lidar lidar.launch.py port:=/dev/ttyUSB0 rviz:=true
```

Windows:

```powershell
ros2 launch rosik_lidar lidar.launch.py port:=COM6 rviz:=true
```

## Настройка вручную

1. Запустите `rviz2`.
2. В `Global Options` задайте `Fixed Frame`.
3. Добавьте Display → `LaserScan`.
4. Выберите `/scan`.

### QoS

Для `/scan`:

```text
Reliability Policy: Best Effort
Durability Policy: Volatile
History Policy: Keep Last
Depth: 5 или 10
```

Если QoS не совпадает, RViz пишет предупреждение `incompatible QoS`, а точки не отображаются.

## Окраска по intensity

Для LaserScan:

```text
Color Transformer: Intensity
Channel Name: intensity
Use rainbow: true
Autocompute Intensity Bounds: true
```

Если автодиапазон выглядит неудачно, отключите `Autocompute Intensity Bounds` и задайте диапазон вручную, например 0…255.

## Проверить intensity до запуска RViz

```bash
ros2 topic echo /scan --once --field intensities --qos-reliability best_effort --qos-durability volatile
```

Должен быть массив с числами. Если массив пустой, RViz не сможет раскрасить точки по интенсивности.

## Fixed Frame

Нода публикует `frame_id = laser`. При включённом `publish_static_tf` также публикуется статическое преобразование `base_link -> laser`.

Поэтому можно использовать:

```text
Fixed Frame = base_link
```

или для простой проверки:

```text
Fixed Frame = laser
```

## Внешний вид

Удобные параметры:

```text
Style: Flat Squares или Points
Size: 0.02–0.04 m
Decay Time: 0
```

Для плоской карты удобно переключить вид на `TopDownOrtho`.
