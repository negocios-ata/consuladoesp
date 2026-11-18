#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lee los canales públicos de Telegram y extrae los reportes del MES EN CURSO.

Recorre todas las páginas necesarias hasta llegar al día 1 del mes actual,
clasifica cada reporte por trámite y se queda con el ÚLTIMO de cada uno.

Canales:
  @AsesorVirtualC  → reportes con fecha (credenciales, legalizaciones, pasaportes…)
  @LMDCuba         → Boletín Informativo (días de demora)

Solo texto: sin imágenes ni OCR.

Uso:
    python3 canales_texto.py           # escribe fechas.json
    python3 canales_texto.py --json    # lo imprime
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, "fechas.json")

CANALES = ["AsesorVirtualC", "LMDCuba"]
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36",
}
MAX_PAGINAS = 14            # tope de seguridad

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11,
         "diciembre": 12}

EMOJI_DIG = {
    "0️⃣": "0", "1️⃣": "1", "2️⃣": "2", "3️⃣": "3", "4️⃣": "4",
    "5️⃣": "5", "6️⃣": "6", "7️⃣": "7", "8️⃣": "8", "9️⃣": "9",
    "0⃣": "0", "1⃣": "1", "2⃣": "2", "3⃣": "3", "4⃣": "4",
    "5⃣": "5", "6⃣": "6", "7⃣": "7", "8⃣": "8", "9⃣": "9",
}

# Clasificación por orden de prioridad: la primera que encaje gana.
REGLAS = [
    (r"credenciales?\s+de\s+servicio|solicitud\s+de\s+credenciales|credenciales\s+lmd",
     "Credenciales LMD"),
    (r"legalizaci[oó]n\s+consular|credenciales\s+de\s+legalizaci|legalizaci[oó]n",
     "Credenciales de Legalización"),
    (r"primer\s+pasaporte|pasaporte\s+espa", "Primer Pasaporte"),
    (r"transcripci[oó]n", "Transcripción de Matrimonio"),
    (r"certificado\s+de\s+matrimonio", "Certificado de Matrimonio"),
    (r"visado\s+de\s+turismo", "Credenciales de Visado de Turismo"),
    (r"visado\s+de\s+residencia|residencia", "Credenciales de Visado de Residencia"),
    (r"visado\s+schengen", "Credenciales de Visado Schengen"),
    (r"inscripci[oó]n\s+directa", "Inscripción Directa"),
    (r"inscripci[oó]n\s+de\s+matrimonio", "Inscripción de Matrimonio"),
    (r"literal", "Literales"),
    (r"inscripci[oó]n", "Inscripciones"),
]

# Mensajes que NO son reportes (publicidad de servicios)
BASURA = [
    "turnos habilitados", "contacto para gestion", "obtengalo actual",
    "homologación de títulos", "homologacion de titulos", "te informamos",
    "info-credenciales", "info-resueltos", "flayer", "flyer", "al cierre semanal",
    "nuestro equipo se complace", "portal privado", "¿sabías que",
]

RE_OTRO_CONS = re.compile(
    r"miami|san francisco|houston|nueva york|new york|boston|washington|chicago|"
    r"los angeles|monterrey|buenos aires|caracas|uruguay|chile|paraguay|venezuela|"
    r"puerto rico|quito|lima|bogota|panama|madrid", re.I)

RE_FECHA_TXT = re.compile(
    r"(\d{1,2})\s*(?:de\s+)?(" + "|".join(MESES) + r")\s*(?:de\s+|del\s+)?(20\d{2})", re.I)
RE_FECHA_NUM = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b")


def get(url, intentos=4):
    """GET con reintentos: Telegram corta la conexión si se pide muy rápido."""
    ultimo = None
    for n in range(intentos):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) \
                .read().decode("utf-8", "replace")
        except Exception as e:
            ultimo = e
            time.sleep(2 + n * 3)      # 2s, 5s, 8s…
    raise ultimo


def limpia(s):
    for k, v in EMOJI_DIG.items():
        s = s.replace(k, v)
    s = s.replace("\u200d", "").replace("\ufe0f", "")
    for a, b in (("&quot;", '"'), ("&amp;", "&"), ("&#33;", "!"), ("&nbsp;", " ")):
        s = s.replace(a, b)
    return re.sub(r"[ \t]+", " ", s)


def mensajes(html, canal):
    """[(fecha_iso, texto)] de los mensajes con texto de una página."""
    salida = []
    for b in re.split(r'class="tgme_widget_message\b', html)[1:]:
        if canal not in b:
            continue
        m = re.search(r'<time[^>]*datetime="([^"]+)"', b)
        fecha = m.group(1)[:10] if m else None
        t = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
        if not t:
            continue
        txt = re.sub(r"<br\s*/?>", "\n", t.group(1))
        txt = re.sub(r"<[^>]+>", "", txt)
        txt = re.sub(r"\n\s*\n+", "\n", limpia(txt)).strip()
        if txt:
            salida.append((fecha, txt))
    return salida


def lee_canal(canal, desde, verbose=True, hasta_atras=120):
    """Recorre páginas hasta 120 días atrás. Marca qué es del mes en curso."""
    desde_min = (desde - datetime.timedelta(days=hasta_atras)).isoformat()
    base = "https://t.me/s/%s" % canal
    html = get(base)
    vistas, dentro = set(), []
    paginas = 0

    while html and paginas < MAX_PAGINAS:
        paginas += 1
        pagina = mensajes(html, canal)
        if not pagina:
            break
        for fecha, texto in pagina:
            if texto in vistas:
                continue
            vistas.add(texto)
            if fecha and fecha >= desde_min:
                dentro.append((fecha, texto, fecha >= desde.isoformat()))
        # ¿ya llegamos a mensajes anteriores al mes? entonces paramos
        fechas = [f for f, _t in pagina if f]
        if fechas and min(fechas) < desde_min:
            break
        ids = [int(x) for x in re.findall(r'data-post="%s/(\d+)"' % re.escape(canal), html)]
        if not ids:
            break
        time.sleep(1.2)                # pausa entre páginas
        html = get("%s?before=%d" % (base, min(ids)))

    if verbose:
        del_mes = sum(1 for _f, _t, m in dentro if m)
        print("   @%s: %d del mes + %d de respaldo (%d vistos, %d páginas)"
              % (canal, del_mes, len(dentro) - del_mes, len(vistas), paginas), flush=True)
    return dentro, len(vistas), paginas



RE_PAR = re.compile(
    r"(APROBADOS|INSCRITOS|LITERALES)\s*:\s*(\d{1,2})\s*DE\s*([A-ZÁÉÍÓÚÑ]+)"
    r"(?:\s*DE\s*(20\d{2}))?", re.I)


def parsea_novedades(texto, fecha_post):
    """Post tipo 'WEB DE CONSULTA DE EXPEDIENTES' con Aprobados/Inscritos/Anexo 7.

    Ejemplo:
        LEY DE MEMORIA DEMOCRÁTICA – HABANA: APROBADOS: 9 DE ABRIL  INSCRITOS: 03 DE FEBRERO
        ANEXO 7  APROBADOS: 17 DE ENERO DE 2025
    """
    low = texto.lower()
    if "consulta de expedientes" not in low and "novedades" not in low:
        return []
    if not RE_PAR.search(texto):
        return []

    anio_post = int((fecha_post or "2025")[:4])
    anios = [int(a) for a in re.findall(r"de\s*(20\d{2})", texto, re.I)]
    pos_anexo = low.find("anexo 7")

    salida = []
    for m in RE_PAR.finditer(texto):
        campo, dia, mes, anio = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        clave_mes = mes.lower()
        if clave_mes not in MESES or not (1 <= dia <= 31):
            continue
        a = int(anio) if anio else (anios[0] if anios else anio_post)
        es_anexo = pos_anexo != -1 and m.start() > pos_anexo
        prefijo = "Anexo 7" if es_anexo else "LMD"
        etiqueta = "%s · %s" % (prefijo, campo.capitalize())
        salida.append({
            "tipo": "fecha",
            "etiqueta": etiqueta,
            "fecha": "%04d-%02d-%02d" % (a, MESES[clave_mes], dia),
            "mensaje": fecha_post,
            "fuente": None,          # se rellena fuera
            "texto": " ".join(texto.split())[:150],
        })
    # quita duplicados por etiqueta dentro del mismo post
    vistos, limpio = set(), []
    for x in salida:
        if x["etiqueta"] in vistos:
            continue
        vistos.add(x["etiqueta"])
        limpio.append(x)
    return limpio


def fechas_en(texto):
    res = []
    for m in RE_FECHA_TXT.finditer(texto):
        d, me, a = int(m.group(1)), MESES[m.group(2).lower()], int(m.group(3))
        if 1 <= d <= 31:
            res.append(("%04d-%02d-%02d" % (a, me, d), m.start()))
    for m in RE_FECHA_NUM.finditer(texto):
        d, me, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= d <= 31 and 1 <= me <= 12:
            res.append(("%04d-%02d-%02d" % (a, me, d), m.start()))
    res.sort(key=lambda x: x[1])
    return res



RE_MES_ANIO = re.compile(r"\b(" + "|".join(MESES) + r")\s+DE\s+(20\d{2})", re.I)


def fechas_mes_en(texto):
    """Fechas donde el día no está escrito (emoji personalizado): devuelve (iso_mes, pos).

    AVC publica a veces "🔢🔢DE OCTUBRE DE 2026": el día es un emoji, el mes y el año
    sí son texto. Se devuelve el mes con precisión "mes".
    """
    salida = []
    for m in RE_MES_ANIO.finditer(texto):
        antes = texto[max(0, m.start() - 14):m.start()]
        # si justo antes hay un número de 1-2 dígitos, el día SÍ está escrito: lo maneja fechas_en()
        if re.search(r"\b\d{1,2}\s*(?:de\s*)?$", antes, re.I):
            continue
        salida.append(("%04d-%02d" % (int(m.group(2)), MESES[m.group(1).lower()]), m.start()))
    return salida


def clasifica(texto, hasta):
    previo = texto[:hasta].lower()[-240:]
    for patron, etiqueta in REGLAS:
        if re.search(patron, previo):
            return etiqueta
    return None


def es_basura(texto):
    t = texto.lower()
    return any(b in t for b in BASURA)


def recolecta(desde, verbose=True):
    datos = []
    for canal in CANALES:
        msgs, _vistos, _pag = lee_canal(canal, desde, verbose)
        for fecha_post, texto, en_mes in msgs:
            if es_basura(texto):
                continue
            if RE_OTRO_CONS.search(texto) and "habana" not in texto.lower():
                continue

            # 1) post de "consulta de expedientes" (Aprobados / Inscritos / Anexo 7)
            novedades = parsea_novedades(texto, fecha_post)
            if novedades:
                for x in novedades:
                    x["fuente"] = "https://t.me/%s" % canal
                    x["en_mes"] = en_mes
                    x["precision"] = "dia"
                datos.extend(novedades)
                continue

            # 2) fechas con día escrito
            ya = set()
            for iso, pos in fechas_en(texto):
                et = clasifica(texto, pos)
                if not et:
                    continue
                ya.add(et)
                datos.append({
                    "tipo": "fecha", "etiqueta": et, "fecha": iso, "precision": "dia",
                    "mensaje": fecha_post, "fuente": "https://t.me/%s" % canal,
                    "texto": " ".join(texto.split())[:150], "en_mes": en_mes,
                })

            # 3) fechas con el día en emoji: solo mes y año
            for iso_mes, pos in fechas_mes_en(texto):
                et = clasifica(texto, pos)
                if not et or et in ya:
                    continue
                ya.add(et)
                datos.append({
                    "tipo": "fecha", "etiqueta": et, "fecha": iso_mes + "-01", "precision": "mes",
                    "mensaje": fecha_post, "fuente": "https://t.me/%s" % canal,
                    "texto": " ".join(texto.split())[:150], "en_mes": en_mes,
                })
    return datos


def consolida(datos):
    """El reporte más reciente de cada trámite; prioriza el mes en curso y el día exacto."""
    def mejor(a, b):
        """¿a es mejor que b?"""
        if a.get("en_mes") != b.get("en_mes"):
            return bool(a.get("en_mes"))
        ma, mb = a["fecha"][:7], b["fecha"][:7]
        # el día exacto gana sobre "solo el mes" si no es más atrasado
        if a.get("precision") == "dia" and b.get("precision") == "mes" and ma >= mb:
            return True
        if b.get("precision") == "dia" and a.get("precision") == "mes" and mb >= ma:
            return False
        return (a.get("mensaje") or "") >= (b.get("mensaje") or "")

    por_et = {}
    for d in datos:
        prev = por_et.get(d["etiqueta"])
        if prev is None or mejor(d, prev):
            por_et[d["etiqueta"]] = d

    salida = []
    for et, d in por_et.items():
        limpio = {k: v for k, v in d.items() if k != "en_mes"}
        limpio["antiguo"] = not d.get("en_mes", False)
        salida.append(limpio)
    return sorted(salida, key=lambda x: x["etiqueta"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--mes", help="AAAA-MM (por defecto, el mes en curso)")
    args = ap.parse_args()

    if args.mes:
        a, m = map(int, args.mes.split("-"))
        desde = datetime.date(a, m, 1)
    else:
        hoy = datetime.date.today()
        desde = datetime.date(hoy.year, hoy.month, 1)

    print("Revisando el mes desde %s" % desde.isoformat(), flush=True)
    datos = consolida(recolecta(desde))
    if not datos:
        print("ERROR: no se extrajo ningún dato del mes. No se toca fechas.json.", file=sys.stderr)
        return 2

    actualizado = max((d.get("mensaje") or "") for d in datos) or None
    salida = {
        "actualizado": actualizado,
        "mes": desde.strftime("%Y-%m"),
        "canales": ["https://t.me/%s" % c for c in CANALES],
        "datos": datos,
    }

    if args.json:
        print(json.dumps(salida, ensure_ascii=False, indent=2))
        return 0

    anterior = None
    if os.path.exists(SALIDA):
        try:
            anterior = json.load(open(SALIDA, encoding="utf-8"))
        except Exception:
            pass
    if anterior == salida:
        print("SIN CAMBIOS: no hay reportes nuevos este mes.")
        return 0

    json.dump(salida, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("OK · actualizado=%s · %d reportes" % (actualizado, len(datos)))
    for d in datos:
        print("   %-34s %s   (post %s)" % (d["etiqueta"], d["fecha"], d["mensaje"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
