# Bodega visual: planta 2D y vista 3D

*Maestros → Bodegas → Plano 2D / 3D.* **Se edita en planta y se consulta en 3D**: arrastrar objetos en perspectiva es impreciso;
la planta con grilla es rápida y exacta, y la vista 3D sirve para navegar y mostrar.

## Modelo

- **`ubicaciones`**: estructura lógica en árbol (bodega → … → posición). Cada una tiene un código jerárquico, por ejemplo `FIT-R02-N03-P04`.
  La jerarquía es opcional y libre: una bodega puede tener solo ubicaciones planas.
- **`elementos_plano`**: geometría (tipo, posición `x`,`y` en metros desde la esquina, largo, fondo, alto, rotación 0° / 90°, color).
  Un rack o un área apunta a su ubicación lógica.

**Cada posición física corresponde a una ubicación lógica.** Un rack de *N* niveles × *M* posiciones genera
`RACK → NIVEL (N01…) → POSICIÓN (P01…)`; solo las posiciones almacenan stock.

## Editor en planta (2D)

| Función | Cómo |
|---|---|
| Agregar | Barra superior: Rack, Zona, Área de piso, Pasillo, Obstáculo |
| Mover | Arrastrar; ajuste magnético cada 0,25 m; no sale de la bodega |
| Editar dimensiones | Panel lateral: posición, largo, fondo, alto, rotación, niveles y posiciones, color |
| Rotar, duplicar, eliminar | Barra superior |
| Deshacer y rehacer | Barra superior (un arrastre completo es un solo paso) |
| Dimensiones de la bodega | Panel lateral sin selección |
| **Publicar plano** | Guarda todo en una operación |

Al publicar:

- Los racks nuevos generan sus ubicaciones; las zonas y áreas de piso, una ubicación almacenable.
- Mover o redimensionar un elemento **conserva** sus ubicaciones.
- Un elemento **con stock no puede eliminarse**. Sin stock, sus ubicaciones se desactivan (no se borran: pueden tener historia).
- Los niveles y posiciones de un rack publicado quedan fijos; para otra configuración se duplica o se crea otro.

Las ubicaciones también pueden crearse sin plano en *Ubicaciones* (alta individual o *Generar rack*).

## Vista 3D

Navegación con arrastre (girar), rueda (acercar) y clic derecho (desplazar). Cada posición se dibuja como una caja cuya altura refleja la ocupación;
las áreas de piso muestran un bulto por existencia.

**Colorear por:**

| Modo | Escala |
|---|---|
| Ocupación | Vacía · baja · media · alta (según la capacidad de la ubicación) |
| Antigüedad | 0–30 · 31–60 · 61–90 · más de 90 días desde el ingreso |
| Vencimiento | Sin vencimiento · más de 90 días · 31–90 · ≤ 30 · vencido |
| Valorización | Bajo · medio · alto (requiere permiso de costos) |

**Clic en una posición, rack o área** → panel con productos, lotes, cantidad, fecha de ingreso, vencimiento, valor del inventario
y capacidad disponible, con enlace a cada existencia. La planta 2D ofrece la misma consulta y los mismos modos de color.

## Guardar productos desde el plano

1. Haga clic en una posición (vista 3D) o en un rack de la planta: aparece **Posiciones de R04**, una vista frontal con una casilla por nivel y posición.
2. Clic en la casilla → panel de la ubicación → **Guardar producto aquí**.
3. Elija la existencia (búsqueda por código, producto o lote; se sugieren las que están en la bodega sin ubicación) y la cantidad.
4. **Guardar**: queda registrado como traslado. Si la cantidad es parcial nace una existencia nueva con su propio QR; si viene de otra bodega es un traslado entre bodegas.

Requiere el permiso `traslados:crear`. Los racks, niveles y pasillos no almacenan: hay que elegir una posición o un área de piso.
Si la cantidad supera la capacidad libre se advierte, pero no se impide. La posición cambia de color al instante.
Lo mismo está disponible en *Ubicaciones*, al hacer clic en una fila.

## Capacidad máxima de una ubicación

En el panel de cualquier posición o área: **Definir / Cambiar capacidad máxima** (permiso `bodegas:administrar`).

| Capacidad | Qué limita | Ejemplo |
|---|---|---|
| **Máximo de envases** (`capacidad_bultos`) | Número de tambores, bidones o pallets, sin importar su contenido | Área de tambores: 12 |
| Máximo en cantidad (`capacidad`) | Suma de lo almacenado en su unidad principal | Posición de rack: 400 L |

- Cada existencia cuenta los envases que agrupa (un ingreso consolidado de 3 tambores cuenta 3; una existencia por envase cuenta 1).
  Un tambor a medio consumir sigue ocupando su lugar.
- El panel muestra `5 / 12` y cuántos caben; la ocupación (color) se calcula con los envases si hay máximo de envases, y si no con la cantidad.
- Al guardar un producto que no cabe **se advierte, pero no se bloquea**.
- En la vista 3D las áreas de piso dibujan un bulto por envase almacenado.

En el Demo, el área *TAMBORES* admite 12.

El buscador general lleva a una ubicación (`FIT-R01-N02`) y abre su contenido en el plano.

## Tecnología y límites

- Planta: SVG. Vista 3D: Three.js con React Three Fiber, cargada solo al abrir esta pantalla.
- Las etiquetas son HTML superpuesto (no se descargan fuentes externas: funciona sin Internet).
- Cada posición es una malla propia. Fluido con cientos de posiciones (el Demo tiene ~110).
  **Para bodegas de varios miles de posiciones conviene migrar a mallas instanciadas**; no está hecho.
- En teléfonos la vista 3D funciona en modo consulta; el editor está pensado para pantalla grande.
- No hay muros interiores, puertas ni niveles de edificio; la rotación es de 0° o 90°.

## Demo

*Bodega Fitosanitarios* (24 × 14 × 6 m): cinco racks, zona de cuarentena, área de tambores, recepción, pasillo y un pilar.
*Bodega Mantención* (16 × 10 × 5 m): dos racks, área de lubricantes y zona de herramientas.
