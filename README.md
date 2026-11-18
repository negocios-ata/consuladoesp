# DATA ARUCA — sitio web

Landing page de **DATA ARUCA** con el bloque de trámites del Consulado que se actualiza solo
leyendo el texto de los canales de Telegram.

- Facebook: https://www.facebook.com/dataaruca/
- WhatsApp: +53 52164763 / +53 55857689
- Programado por DATA ARUCA

## Archivos

| Archivo | Qué es |
|---|---|
| `index.html` | Toda la página (CSS y JS incluidos). Lleva datos de respaldo dentro, así nunca se ve vacía |
| `logo.jpg` | Logotipo circular |
| `banner.png` | Portada de Facebook |
| `fechas.json` | Datos de los trámites (lo reescribe el bot) |
| `actualizar.py` | Entrada del bot |
| `canales_texto.py` | Lee los canales de Telegram y extrae fechas |
| `.github/workflows/actualizar.yml` | Ejecución diaria automática |

## Publicar en GitHub Pages

1. Repo **público** → subir todos los archivos, incluida la carpeta `.github/workflows/`.
2. **Settings → Pages → Deploy from a branch → main → / (root) → Save**.
3. **Actions → "Actualizar fechas (Telegram, texto)" → Run workflow** (primera prueba).
4. Queda en `https://TU-USUARIO.github.io/TU-REPO/`.

Si el paso de commit falla: **Settings → Actions → General → Workflow permissions →
Read and write permissions → Save**.

## El botón "Revisar fuentes"

Vuelve a pedir `fechas.json` al servidor saltándose la caché y repinta las tarjetas.
Si la fecha de actualización no cambió, dice **"Sin novedades"**. La lectura real de Telegram la hace
el bot una vez al día; el botón es para que el visitante no vea una copia vieja del navegador.

## Cómo cambiar el número de WhatsApp

En `index.html`, busca `wa.me/5352164763` y cámbialo. El texto del mensaje se arma solo e incluye la
frase *"Vengo desde su página web"* para que sepas que viene de aquí.

## Personalizar servicios y precios

Todo está en el HTML, en la sección `id="servicios"`. Cada tarjeta es un `<article class="srv">`.
