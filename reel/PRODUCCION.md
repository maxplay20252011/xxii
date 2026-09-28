# ICON · Reel 9:16 — paquete de producción

Estado: **animatic terminado** (`reel/out/icon_reel_animatic.mp4`, 31,5 s, 1080×1920, 30 fps).
El bloque de la app y el cierre ya son definitivos: usan tus pantallas y tu logo tal cual, sin retoques.
Faltan **3 tomas reales** (escenas 1, 2 y 4), que hay que generar con IA, y montar la **voz en off**.

## Línea de tiempo

| Tiempo | Segmento | Contenido | Estado |
|---|---|---|---|
| 0,0–4,8 | Escena 1 · Problema | Toma real + texto en pantalla **“¿Otra vez no sabés qué ponerte?”** | Toma pendiente, texto listo |
| 4,8–7,0 | Escena 2 · ICON aparece | Toma real (saca el celular) → splash con el logo | Toma pendiente, splash listo |
| 7,0–10,2 | Armario digital | `app_armario`: las prendas entran una por una | ✅ |
| 10,2–11,2 | Paleta | `app_paleta` | ✅ |
| 11,2–13,2 | Outfit personalizado | Se arma pieza por pieza: top → abajo → calzado → accesorio | ✅ |
| 13,2–14,8 | Look completo | `app_look` | ✅ |
| 14,8–18,4 | Según la ocasión | Toggle Día → Noche: el look cambia (blazer/top/pantalón/cartera → campera/vestido/sandalias/aros) | ✅ |
| 18,4–21,6 | Prueba virtual | `app_prueba` con barrido de escaneo | ✅ |
| 21,6–24,6 | Dónde comprar | Ficha: precio, talles, envío, reseñas, botón “Dónde comprarlo” | ✅ (datos de ejemplo) |
| 24,6–28,0 | Escena 4 · Resultado | Selfie en el espejo con el look de ICON | Toma pendiente |
| 28,0–31,5 | Cierre | Logo ICON + “TU IMAGEN, TUS REGLAS.” (imagen original) | ✅ |

## Voz en off (es-AR, femenina, conversacional)

Voz probada: **Microsoft `es-AR-ElenaNeural`** (edge-tts), velocidad +6 %. Suena argentina y natural, sin tono de locutora.

| Entra en | Frase | Dura aprox. |
|---|---|---|
| 0,35 | ¿Otra vez no sabés qué ponerte? | 1,6 s |
| 2,20 | Tenés el placard lleno… y nada te convence. | 2,5 s |
| 4,90 | Tranqui. Abrí ICON. | 2,1 s |
| 7,40 | Subí tu ropa y armá tu armario digital. | 2,2 s |
| 10,40 | ICON combina tus prendas y te arma el look completo. | 2,6 s |
| 14,90 | ¿Salís de noche? El look se adapta a la ocasión. | 3,3 s |
| 18,70 | Probátelo virtualmente, sin salir de casa. | 2,6 s |
| 21,80 | Y si te falta algo, te dice dónde comprarlo. | 2,6 s |
| 25,60 | Por fin sé qué ponerme. | 1,1 s |
| 28,40 | ICON. Tu imagen, tus reglas. | 2,8 s |

Para generarla (en una máquina con acceso a `speech.platform.bing.com`):

```bash
pip install edge-tts
edge-tts --voice es-AR-ElenaNeural --rate=+6% --text "¿Otra vez no sabés qué ponerte?" --write-media l01.mp3
# … una línea por frase; después ubicar cada archivo con adelay según la tabla
```

En el animatic, las frases aparecen como subtítulos para poder revisar los tiempos. En el corte final conviene dejar solo el gancho y los chips de función. Así se cumple “evitar exceso de texto”.

## Tomas reales: prompts (Seedance 2.5 / Veo / Kling, 9:16, 1080p)

**Identidad fija (va en las 3 tomas y en la imagen de referencia):**
> Mujer argentina de 24 años, piel oliva clara con pecas suaves, pelo castaño oscuro ondulado en un rodete alto desprolijo con mechones sueltos enmarcando la cara, ojos marrones, cejas naturales, maquillaje suave, aros argolla dorados chicos. Cuarto luminoso y moderno: paredes blancas, ropa de cama lila suave, placard blanco. Luz natural de día, fotorrealista, grano de iPhone, sin texto.

Es el mismo tipo de chica que aparece en tus pantallas de la app, para que la prueba virtual y el resultado coincidan.

1. **Paso 0: imagen de referencia del personaje** (soul_2 / gpt_image_2, 3:4). Descripción de identidad + buzo tejido oversize crema y short gris. Todas las tomas se generan a partir de esta imagen, para que no cambie la cara.
2. **Escena 1 (4,8 s):** Frente al placard abierto, ropa apilada sobre la cama. Levanta un blazer beige y un vestido negro, los compara, los tira sobre la cama y resopla, abrumada pero natural. Cámara en mano, dos cortes rápidos (plano medio → detalle de ropa sobre la cama → plano medio). Mismo buzo crema. Sin texto en la imagen.
3. **Escena 2 (1,1 s de toma + splash):** Se sienta al borde de la cama, saca un iPhone blanco y toca la pantalla. Primer plano: la luz lila de la pantalla le ilumina la cara y aparece una media sonrisa. La pantalla no se ve de frente, así no hace falta inventar la UI.
4. **Escena 4 (3,4 s):** Selfie en el espejo del mismo cuarto con **el look de `app_look`**: blazer beige, musculosa crema, pantalón sastrero crema de pierna ancha, cartera crema y zapatos nude. Sonríe con seguridad, se acomoda el blazer y hace medio giro. Mismo iPhone blanco y mismo peinado.

Reglas: nada de rosa en decorado ni vestuario. Solo cambia la ropa entre la escena 1 y la 4, y ese cambio se justifica por la app. Sin texto incrustado en la generación.

## Montaje final

Reemplazar los 3 bloques “TOMA REAL” del animatic por los clips (mismos tiempos). Encima de la escena 1 va el texto del gancho, que ya existe en `seg_hook`: quitar el placeholder y dejar el texto. Después se mezcla la VO con la música (−14 LUFS y la música a −22 dB debajo de la voz). Para renderizar: `python3 reel/render.py` (requiere `pip install pillow numpy imageio-ffmpeg`).
