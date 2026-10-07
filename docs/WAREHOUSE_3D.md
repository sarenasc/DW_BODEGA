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
