<p align="center">
  <img src="https://github.com/user-attachments/assets/d4f48f71-d76e-4ffe-9fb1-0b075d79bf05" alt="logo de forza-painter FH6" width="720">
</p>

<h1 align="center">forza-painter FH6</h1>

<p align="center">
  <strong>Generador e importador de imágenes a Grupos de Vinilo para Forza Horizon 6.</strong>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">中文</a> ·
  <a href="README.ko-KR.md">한국어</a> ·
  <a href="README.es-MX.md">Español</a>
</p>

<p align="center">
  <code>v1.9.1</code> · <code>Windows</code> · <code>Forza Horizon 6</code> · <code>GPU/OpenCL</code> · <code>EXE de un solo archivo</code>
</p>

<p align="center">
  <a href="https://github.com/bvzrays/forza-painter-fh6/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=bvzrays/forza-painter-fh6" alt="Contributors" />
  </a>
</p>

Convierte imágenes PNG/JPG/BMP en capas de Grupo de Vinilo para Forza Horizon 6. La aplicación integra la generación, la vista previa y la importación en una sola ventana de escritorio; los usuarios normales no necesitan Python, `.venv`, archivos batch ni direcciones de memoria manuales.

> **Descarga el EXE:** obtén `forza-painter-fh6-v1.9.1.exe` desde [Releases](https://github.com/bvzrays/forza-painter-fh6/releases) y ejecútalo directamente.

> **Preset Market:** explora imágenes compartidas, presets y paquetes JSON en https://painter6.com o usa el nuevo banner del mercado dentro de la aplicación.

> **Si el resultado se ve borroso:** aumenta primero `Random samples`. Los valores por encima de **200000** suelen mejorar mucho la calidad; entre más alto sea el valor, más claro será el resultado, pero también tardará mucho más en generarse.

> **La importación puede tardar:** desde la versión v1.4.1, la app prueba varios localizadores de plantillas de FH6 y puede tardar hasta 5 minutos en encontrar de forma segura la tabla de capas. Mantén FH6 en el Editor de Grupo de Vinilo, no cambies de menú y exporta un registro detallado si sigue fallando.

| Qué hace | Detalles |
| --- | --- |
| Generar JSON | Convierte imágenes a geometry JSON con el generador GPU/OpenCL incluido. |
| Vista previa de salida | Muestra vistas previas de la imagen original y de la geometría generada dentro de la app. |
| Importar a FH6 | Importa JSON al Editor de Grupo de Vinilo de FH6 que esté abierto actualmente. |
| Flujo seguro para FH6 | Localiza automáticamente y verifica la tabla de capas editable antes de escribir. |
| Preset Market | Abre https://painter6.com desde la app para explorar imágenes compartidas, presets y paquetes JSON. |
| Verificación de actualizaciones | Busca nuevas versiones al iniciar y muestra notas del changelog cuando están disponibles. |

## Inicio rápido

1. Descarga `forza-painter-fh6-v1.9.1.exe` desde [Releases](https://github.com/bvzrays/forza-painter-fh6/releases).
2. Coloca el EXE en una carpeta normal con permisos de escritura, por ejemplo `Desktop\forza-painter-fh6`.
3. Haz doble clic en el EXE. Para importar a FH6, ejecútalo como administrador si Windows bloquea el acceso al proceso.
4. En FH6, abre `Create Vinyl Group` / `Vinyl Group Editor`, carga una plantilla de esferas y luego usa `Ungroup`.
5. En la aplicación, genera el JSON, abre la página `Import`, escribe el número exacto de capas de la plantilla y después importa.

No descargues el ZIP automático de `Source code` de GitHub a menos que vayas a desarrollar el proyecto. Los usuarios normales solo necesitan el archivo `.exe`.

## Vista previa

<table>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/app-import-preview.png" alt="Página de importación de la app"><br>
      <strong>Página de importación de la app</strong>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-template-ready.png" alt="Plantilla lista en FH6"><br>
      <strong>Plantilla lista en FH6</strong>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-import-result.png" alt="Resultado importado en FH6"><br>
      <strong>Resultado importado</strong>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-car-applied.png" alt="Resultado aplicado al auto en FH6"><br>
      <strong>Aplicado al auto</strong>
    </td>
  </tr>
</table>

## Generar JSON

1. Abre la página `Generate JSON`.
2. Haz clic en `Add images` y elige imágenes PNG/JPG/BMP.
3. Selecciona un preset de calidad.
4. Opcional: activa `Use custom settings` para cambiar las capas de salida, la resolución, las muestras aleatorias y las muestras mutadas.
5. Haz clic en el botón fijo inferior `Start generating`.
6. Espera a que se actualicen la vista previa y los registros.

Los archivos generados se guardan junto a la imagen original, por ejemplo `image.500.json`, `image.1000.json` e `image.3000.json`.

Una sola imagen puede generar varios archivos JSON de punto de control. Se recomienda usar el JSON con más capas que coincida con tu plantilla; por ejemplo, usa `image.3000.json` o el `image.json` final con una plantilla de 3000 capas. Importar un JSON de 500 capas en una plantilla de 3000 capas hará que el resultado se vea borroso.

| Preset | Capas de salida | Muestras aleatorias | Caso de uso |
| --- | ---: | ---: | --- |
| extremely fast | 500 | 30000 | Revisiones rápidas de composición |
| fast | 1000 | 60000 | Borradores rápidos utilizables |
| balanced | 1800 | 120000 | Opción recomendada por defecto |
| slow | 2500 | 220000 | Calidad final; empieza a usar el rango de calidad de 200k+ |
| super slow | 3000 | 350000 | Mejor claridad, muy lento |

## Importar JSON

1. Inicia FH6 y mantén abierto `Vinyl Group Editor`.
2. Carga o crea una plantilla hecha con muchas capas simples de esfera.
3. Usa `Ungroup` en la plantilla y recuerda el número exacto de capas que aparece dentro del juego.
4. En la app, abre `Import`, haz clic en `Refresh` y selecciona `forzahorizon6.exe`.
5. Escribe el número exacto de capas de la plantilla.
6. Agrega el archivo `.json` generado o haz clic en `Use generated JSON`.
7. Deja vacíos los campos avanzados de direcciones y haz clic en `Import JSON`.

FH necesita 4 capas extra de límite para guardar correctamente la portada y aplicar los límites. Ejemplo: un JSON de 1000 capas debe usar al menos una plantilla de 1004 capas; una plantilla de 3000 capas puede importar aproximadamente 2996 formas dibujables.

## Pintura por Regiones Experimental (Region Paint)

Region Paint es un flujo de trabajo de pintura iterativa que genera un pase de capas base en toda la imagen, luego te permite seleccionar regiones (usando herramientas de Rectángulo o Elipse) y refinar solo esas áreas con capas adicionales.

- Agrega una sola imagen, elige un Perfil de Calidad (que establece el presupuesto Total desde `stopAt`) y ajusta las capas del Primer pase y de Región.
- Haz clic en `Start First Pass` para generar las capas base. Aparecerá una vista previa en el lienzo derecho.
- Usa la herramienta Rectángulo o Elipse en el lienzo izquierdo para dibujar una región de selección. La superposición roja muestra tu selección.
- Haz clic en `Paint Selected Region` para agregar más capas solo dentro de esa región. Repite para cada área.
- Después de todos los pases, usa `Open Result Folder` o `Save Result JSON` para obtener el `base.json` final.
- Importa el JSON resultante usando la pestaña `Import` — el mismo flujo que la generación estándar.
- El presupuesto restante se muestra junto a `Remaining`. Cada pase de región consume capas de este presupuesto.

## Reglas importantes

- La plantilla de FH6 debe estar desagrupada antes de importar.
- El número de capas en la app debe coincidir exactamente con el del juego.
- No cambies de menú dentro del juego mientras se está importando.
- Después de reiniciar FH6, recargar la plantilla o cambiar el número de capas, importa de nuevo con el nuevo conteo correcto.
- Si el JSON tiene menos capas que la plantilla, las capas no utilizadas de la plantilla se ocultan.
- Si el JSON tiene más capas que la plantilla, las formas sobrantes se recortan.
- Los fondos transparentes de archivos PNG no se importan como fondos visibles.

## Archivos de ejecución

El EXE de un solo archivo extrae temporalmente sus archivos internos y guarda los datos normales de ejecución fuera del EXE. La app muestra las rutas exactas en el registro de inicio y en la página `Tools`.

Carpetas externas esperadas junto al EXE:

- `runtime/`: registros, datos de sesión generados y archivos temporales de la app.
- `webui-data/`: caché local del navegador/interfaz.

Estas carpetas pueden eliminarse cuando la app esté cerrada si quieres restablecer los datos locales de ejecución.

## Solución de problemas

- **El EXE no importa en FH6:** cierra la app y ejecuta el EXE como administrador.
- **Error de GPU/OpenCL:** actualiza los controladores gráficos de NVIDIA/AMD/Intel. El generador incluido usa OpenCL.
- **No se puede localizar la plantilla:** confirma que estás en Vinyl Group Editor, que la plantilla está desagrupada, que el conteo de capas es exacto y que no cambiaste de menú durante el escaneo.
- **El resultado importado se ve borroso:** usa un JSON con más capas o aumenta `Output layers` / `Random samples`.
- **Necesitas ayuda para depurar:** usa `Export detailed log` en la app y adjunta el registro en un issue.

## Recursos

- Video de guía de importación: https://www.bilibili.com/video/BV1hG5Z6nENZ
- Preset Market: https://painter6.com
- Código fuente/referencia del generador GPU incluido: https://github.com/zjl88858/forza-painter-geometrize-gpu
- Changelog completo: [CHANGELOG.md](CHANGELOG.md)

## Changelog

Aquí solo se conservan las entradas de versiones publicadas. Consulta [CHANGELOG.md](CHANGELOG.md) para ver el changelog que muestra el aviso de actualización de la app.
### v1.9.1 / 2026-06-17

- **Puntos de control en Region Paint** — Cada pase (Primer Pase y cada Pintar Región Seleccionada) ahora guarda un JSON de punto de control independiente, vista previa y mapa de calor. Cambie libremente entre cualquier punto de control pasado desde el Historial de Pases sin perder datos.
  - Volver a ejecutar el mismo pase después de restaurar crea un nuevo intento sin sobrescribir el anterior.
  - Seleccione cualquier punto de control y haga clic en "Restaurar Punto de Control" para cambiar instantáneamente el estado activo, la vista previa y el mapa de calor.
  - Las acciones del Paso 4, el Historial de Pases y los botones de resultado ahora están en un área desplazable separada debajo de los Pasos 1–3 para mejor usabilidad en pantallas pequeñas.

### v1.9.0 / 2026-06-14

- **Text Vinyl** — Nueva pestaña Text para generar JSON de código de tipo FH6 a partir de texto Unicode. Soporta latín, japonés, coreano y chino (simplificado/tradicional) con interfaz localizada.
  - Escriba o pegue texto y genere capas de vinilo; explore y cargue archivos de fuentes o descubra fuentes CJK instaladas (ordenadas alfabéticamente).
  - Conversor de color DxBang integrado para selección precisa de color con valores hexadecimales.
  - Conectado al flujo de importación existente con guía descartable sobre plantillas circulares.
  - Trazador de pixel art para convertir imágenes en geometría de código de tipo escalada.
  - Sistema de muestras de color compartido entre pestañas para reutilizar colores.

### v1.8.5 / 2026-06-13

- **Control de presupuesto en Region Paint**: Al hacer clic en `Start First Pass` cuando las capas del primer pase exceden el Presupuesto Total, o al hacer clic en `Paint Selected Region` cuando las capas usadas + capas de región exceden el Presupuesto Total, ahora se muestra una advertencia clara en el registro y se detiene en lugar de exceder el presupuesto silenciosamente.
- **Soporte de arrastre multidireccional**: Las herramientas de selección Rectángulo y Elipse en Region Paint ahora funcionan al arrastrar en cualquier dirección (ej. de abajo-derecha a arriba-izquierda). Anteriormente, los arrastres que no fueran de arriba-izquierda a abajo-derecha fallaban con un error de generación de máscara.
- **Mejoras en el borrado de máscaras**: El botón `Clear All` (renombrado de "Clear Mask") elimina todas las máscaras de selección. Un nuevo botón `Clear Selected` elimina solo la máscara actualmente seleccionada, registrando una sugerencia si no hay nada seleccionado.
- **Accesibilidad en pantallas pequeñas**: Se agregaron botones duplicados `Open Result Folder` y `Save Result JSON` dentro del área desplazable del Paso 3 con la indicación "(for small screens)", para que los usuarios de portátiles puedan acceder a las acciones de resultado cuando los botones inferiores están fuera de pantalla.

### v1.8.4 / 2026-06-07

- Las formas de selección en Pintura Regional ahora permiten **arrastrar para mover**, **redimensionar desde las esquinas** y **rotar** (control deslizante, rueda del ratón, entrada de texto o manija en el lienzo).
- Se agregó un preset recomendado que ofrece buena calidad con relativamente poca potencia de cómputo.

### v1.8.3 / 2026-06-06

- Se agregó una pestaña de **Mapa de calor** al lienzo de Pintura Regional, que muestra la densidad de formas en la imagen generada con una barra de escala de color. El mapa se genera automáticamente después de cada pase y se almacena en caché para cambiar de pestaña al instante.
- Se mejoró significativamente la velocidad de generación de la vista previa en Pintura Regional.

### v1.8.2 / 2026-06-06

- Se eliminó el control de Suavizado (Feather) de las herramientas de selección del Paso 3 en Pintura Regional. Las máscaras de selección ahora siempre tienen borde duro (0 suavizado), lo que corrige los problemas que el suavizado causaba en la función Pintar Región Seleccionada.

### v1.8.1 / 2026-06-05

- Se agregó Pintura Regional (Region Paint) — un nuevo flujo de trabajo de pintura iterativa. Genere un pase de capas base en toda la imagen, luego seleccione regiones (usando herramientas de Rectángulo o Elipse) y refine solo esas áreas con capas adicionales. Incluye gestión de presupuesto de capas, historial de pases, lienzo de vista previa en vivo y exportación de JSON del resultado.
- Se corrigió el área de registro en la parte inferior de la ventana que quedaba parcialmente oculta detrás de las pestañas del Notebook.
### v1.7.0 / 2026-06-01

- Se actualizó la versión de la app a `v1.7.0`; los paquetes de lanzamiento ahora usan `forza-painter-fh6-v1.7.0.exe`.
- Se agregó un banner destacado de Preset Market en las páginas Generate, Import, Tools y Tutorial.
- El nuevo botón del mercado abre https://painter6.com para que los usuarios puedan explorar imágenes compartidas, presets y paquetes JSON directamente desde la app.

### v1.6.8 / 2026-05-28

- Se actualizó la versión de la app a `v1.6.8`; los paquetes de lanzamiento ahora usan `forza-painter-fh6-v1.6.8.exe`.
- Se conservaron el ancho y alto flotantes de las elipses de los últimos cambios de `main` en GitHub, mejorando la precisión de importación dentro del juego.
- Se agregó una nota en el panel de vista previa indicando que v1.6.8 prioriza una mejor salida dentro del juego, aunque las vistas previas siguen siendo aproximadas.
- Se mejoró el renderizado de vista previa JSON con supersampling para reducir la degradación de vista previa en elipses de tamaño flotante.

### v1.6.7 / 2026-05-27

- Se actualizó la versión de la app a `v1.6.7`; los paquetes de lanzamiento ahora usan `forza-painter-fh6-v1.6.7.exe`.
- Se actualizó el generador GPU incluido a upstream `canary-26052702`.
- Se reemplazaron los números mágicos de escala de importación de FH6 por constantes con nombre para los tamaños base de círculo y rectángulo.
- Se mejoró la estimación de tiempo restante de generación para la salida almacenada en búfer del generador y los cambios de velocidad de generación.

### v1.6.6 / 2026-05-26

- Se actualizó la versión de la app a `v1.6.6`; los paquetes de lanzamiento ahora usan `forza-painter-fh6-v1.6.6.exe`.
- Se agregaron traducciones de interfaz en chino tradicional y se mejoró el diseño del selector de idioma.
- Se corrigió el preprocesamiento `luma_band` para imágenes RGB, se hicieron más seguras las escrituras de imágenes preprocesadas y se agregaron pruebas para el manejo de datos de geometría/color.
- Se empaquetaron OpenCV y NumPy dentro del EXE de un solo archivo para que el preprocesamiento `luma_band` funcione en builds de lanzamiento.
- La importación ahora requiere el conteo de capas de la plantilla de FH6 antes de iniciar.
- Se refactorizaron los módulos principales con excepciones tipadas y utilidades compartidas.

### v1.6.5 / 2026-05-25

- Se actualizó la versión de la app a `v1.6.5`; los paquetes de lanzamiento ahora usan `forza-painter-fh6-v1.6.5.exe`.
- Se actualizó el generador GPU incluido a upstream `v1.2-Canary-20260525`.
- Los presets incluidos ahora establecen `forceOpaqueShapes = false` por defecto.
- Se redujo la sobrecarga de la app principal durante la generación usando un entorno de generador saneado, un sondeo de archivos más lento y escrituras de vista previa menos frecuentes en el preset más pesado.
- Se corrigió el seguimiento de salida generada cuando el preprocesamiento crea una imagen de entrada separada.

### v1.6.1 / 2026-05-24

- Se actualizó la versión de la app a `v1.6.1`; los paquetes de lanzamiento ahora usan `forza-painter-fh6-v1.6.1.exe`.
- Se desactivó el preprocesamiento `luma_band` por defecto en los presets incluidos.
- La importación ya no reutiliza datos obsoletos de sesión de FH6 desde `webui-data`; vuelve a localizar la plantilla actual antes de escribir.
- Las vistas previas JSON ahora usan una ruta de renderizado estable para evitar diferencias de distorsión de elipses entre entornos EXE empaquetados.

### v1.6.0 / 2026-05-24

- Se actualizó la versión de la app a `v1.6.0`; los paquetes de lanzamiento ahora usan `forza-painter-fh6-v1.6.0.exe`.
- Se actualizó el generador GPU incluido a upstream `canary-26052401`.
- Se agregó soporte para el preset upstream `errorGridSize`.
- Se integró el ajuste del algoritmo upstream para evitar sobresalientes en áreas transparentes.
- Se mejoró significativamente la calidad de generación para la elipse grande en la parte inferior de imágenes transparentes.

### v1.5.4 / 2026-05-23

- Se corrigió el escalado de vista previa para imágenes fuente de alta resolución, PNGs de vista previa del generador y vistas previas JSON, de modo que la imagen completa encaje en el panel actual sin estirarse.
- Se corrigió el renderizado de elipses rotadas tipo 16 en vistas previas JSON para que las vistas previas de la página Import ya no aplanen ni roten incorrectamente los trazos de elipse.

### v1.5.3 / 2026-05-22

- Se agregó importación de presets personalizados compatible con EXE, eliminación de listas de imágenes/JSON, reutilización de checkpoints, nombres de salida más seguros y fallback de vista previa con Pillow.

### v1.5.2 / 2026-05-22

- Se agregó un EXE real de un solo archivo, por lo que los usuarios normales ya no necesitan Python, `.venv` ni archivos auxiliares.
- El EXE con GUI puede relanzarse a sí mismo en modo auxiliar oculto para importación y sondeo de memoria de FH6.
- La página Tools y el registro de inicio ahora muestran las ubicaciones externas de runtime/caché.

### v1.5.1 / 2026-05-22

- Se corrigió la instalación de dependencias al inicio cuando existe un `.venv` del proyecto pero su Python no tiene `pip`.
- Se mejoraron los diagnósticos del script de inicio para extracciones incompletas del paquete fuente.

### v1.5.0 / 2026-05-22

- Se actualizó el generador GPU/OpenCL incluido a upstream `canary-26052102`.
- Se agregó el algoritmo upstream de evaluación por grupos de trabajo del PR #4 para una evaluación más rápida de candidatos en GPU.
- Se agregaron verificación de actualizaciones al inicio, `CHANGELOG.md` raíz y la interfaz de escritorio oscura.

### v1.4.1 / 2026-05-21

- La autolocalización de plantillas de FH6 ahora prueba estrategias de escaneo de v1.3 y v1.4 antes de rendirse.
- Se agregó un localizador alternativo basado en RTTI vtable y se aumentó el tiempo máximo de espera para autolocalización.

### v1.4.0 / 2026-05-21

- Se agregó exportación de registro detallado limitada a 50000 caracteres.
- Se mejoró la autolocalización de plantillas FH6 para regiones grandes de memoria con permisos de escritura.

### v1.3.0 / 2026-05-21

- Se actualizó el generador GPU/OpenCL incluido a upstream `canary-26052101`.
- Se agregó la corrección upstream de selección de dispositivo GPU y el registro del dispositivo seleccionado.

### v1.2.0 / 2026-05-20

- Se actualizó el generador GPU/OpenCL incluido a upstream `canary-26052001`.
- Se agregó `forceOpaqueShapes = true` a las configuraciones de generación incluidas y personalizadas.

### v1.1.1 / 2026-05-20

- Se agregó gestión centralizada de versión para la ventana de la app, la CLI y los nombres de paquetes de lanzamiento.
- Se reorganizó la estructura del repositorio y el empaquetado de lanzamientos.
