"""
Genera una imagen PNG con la tabla meteorologica.
Logo centrado arriba, cabecera, tabla centrada, leyenda en columna centrada.
"""

from PIL import Image, ImageDraw, ImageFont
import io
import os

# ── Colores por categoria ─────────────────────────────────────────────────────
COLORES_CAT = {
    0: (255, 255, 255),
    1: (144, 238, 144),
    2: (220, 220, 220),
    3: (255, 255, 153),
    4: (255, 178, 102),
    5: (255, 102, 102),
}

COLOR_FONDO     = (250, 250, 250)
COLOR_CABECERA  = (25,  45,  75)
COLOR_TEXTO_CAB = (255, 255, 255)
COLOR_HEAD_TAB  = (50,  80, 120)
COLOR_TEXTO_HT  = (255, 255, 255)
COLOR_BORDE     = (160, 160, 160)
COLOR_TEXTO     = (30,  30,  30)
COLOR_ND        = (215, 215, 215)
COLOR_CAP_OF    = (255, 210,  80)

ANCHO_IMG   = 700
ALTO_LOGO   = 120
ALTO_CAB    = 50
ALTO_FILA   = 34
PADDING     = 24

# Columnas: Hr | Of. | TºC | P mm/h | V km/h
COL_W     = [52, 44, 90, 100, 100]
COL_NAMES = ["Hr", "Of.", "TºC", "P mm/h", "V km/h"]
TABLA_W   = sum(COL_W)


def _fuente(size, bold=False):
    try:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else \
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()


def _texto_color(bg):
    r, g, b = bg
    return (20, 20, 20) if (0.299*r + 0.587*g + 0.114*b) > 140 else (255, 255, 255)


def generar_imagen_tabla(
    filas_datos: list,
    hay_cap: bool,
    horas_cap: set,
    logo_path: str | None = None,
) -> bytes:

    n_filas  = len(filas_datos)
    tabla_x  = (ANCHO_IMG - TABLA_W) // 2

    leyenda_items = [
        (COLORES_CAT[5], "CAT. V  — Alerta Roja (Riesgo muy alto)"),
        (COLORES_CAT[4], "CAT. IV — Alerta Naranja (Riesgo alto)"),
        (COLORES_CAT[3], "CAT. III — Alerta Amarilla (Riesgo medio)"),
        (COLORES_CAT[2], "CAT. II  — Precaucion Alta (Riesgo bajo)"),
        (COLORES_CAT[1], "CAT. I   — Precaucion (Riesgo muy bajo)"),
        (COLOR_CAP_OF,   "★  Alerta oficial AEMET activa en esa hora"),
    ]

    f_small  = _fuente(12)
    f_normal = _fuente(14)
    f_bold   = _fuente(14, bold=True)
    f_title  = _fuente(15, bold=True)

    ALTO_LEYENDA = len(leyenda_items) * 26 + 16
    alto_img = (PADDING
                + ALTO_LOGO + PADDING
                + ALTO_CAB  + PADDING // 2
                + ALTO_FILA                    # cabecera columnas
                + ALTO_FILA * n_filas
                + PADDING
                + ALTO_LEYENDA
                + PADDING)

    img  = Image.new("RGB", (ANCHO_IMG, alto_img), COLOR_FONDO)
    draw = ImageDraw.Draw(img)

    y = PADDING

    # ── Logo ──────────────────────────────────────────────────────────────────
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        lh   = ALTO_LOGO
        lw   = int(logo.width * lh / logo.height)
        logo = logo.resize((lw, lh), Image.LANCZOS)
        lx   = (ANCHO_IMG - lw) // 2
        img.paste(logo, (lx, y), logo)
    y += ALTO_LOGO + PADDING

    # ── Cabecera ──────────────────────────────────────────────────────────────
    draw.rounded_rectangle(
        [PADDING, y, ANCHO_IMG - PADDING, y + ALTO_CAB],
        radius=6, fill=COLOR_CABECERA
    )
    draw.text(
        (ANCHO_IMG // 2, y + ALTO_CAB // 2),
        "COEX CA-03 — Avisos por Fenomenos meteorologicos adversos",
        font=f_title, fill=COLOR_TEXTO_CAB, anchor="mm"
    )
    y += ALTO_CAB + PADDING // 2

    # ── Cabecera columnas ─────────────────────────────────────────────────────
    x = tabla_x
    for cw, cname in zip(COL_W, COL_NAMES):
        draw.rectangle([x, y, x + cw, y + ALTO_FILA], fill=COLOR_HEAD_TAB)
        draw.rectangle([x, y, x + cw, y + ALTO_FILA], outline=COLOR_BORDE)
        draw.text((x + cw // 2, y + ALTO_FILA // 2), cname,
                  font=f_bold, fill=COLOR_TEXTO_HT, anchor="mm")
        x += cw
    y += ALTO_FILA

    # ── Filas de datos ────────────────────────────────────────────────────────
    for fd in filas_datos:
        hora    = fd["hora"]
        temp    = fd.get("temp")
        precip  = fd.get("precip")
        viento  = fd.get("viento")
        cat_t   = fd.get("temp_cat",   0)
        cat_p   = fd.get("precip_cat", 0)
        cat_v   = fd.get("viento_cat", 0)
        es_cap  = hora in horas_cap

        t_str = f"{temp:.0f}"   if temp   is not None else "ND"
        p_str = f"{precip:.1f}" if precip is not None else "ND"
        v_str = f"{viento:.0f}" if viento is not None else "ND"

        col_t  = COLORES_CAT[cat_t] if temp   is not None else COLOR_ND
        col_p  = COLORES_CAT[cat_p] if precip is not None else COLOR_ND
        col_v  = COLORES_CAT[cat_v] if viento is not None else COLOR_ND
        col_of = COLOR_CAP_OF if es_cap else (248, 248, 248)
        of_txt = "★" if es_cap else ""

        celdas = [
            (f"{hora:02d}", (242, 242, 242), f_bold),
            (of_txt,        col_of,          f_bold),
            (t_str,         col_t,           f_normal),
            (p_str,         col_p,           f_normal),
            (v_str,         col_v,           f_normal),
        ]

        x = tabla_x
        for (txt, bg, fuente), cw in zip(celdas, COL_W):
            draw.rectangle([x, y, x + cw, y + ALTO_FILA], fill=bg)
            draw.rectangle([x, y, x + cw, y + ALTO_FILA], outline=COLOR_BORDE)
            if txt:
                draw.text((x + cw // 2, y + ALTO_FILA // 2), txt,
                          font=fuente, fill=_texto_color(bg), anchor="mm")
            x += cw
        y += ALTO_FILA

    # ── Leyenda en columna centrada ───────────────────────────────────────────
    y += PADDING
    sq = 16
    max_txt_w = max(
        draw.textlength(txt, font=f_small) for _, txt in leyenda_items
    )
    ley_w  = sq + 8 + int(max_txt_w)
    ley_x  = (ANCHO_IMG - ley_w) // 2

    for bg, txt in leyenda_items:
        draw.rectangle([ley_x, y + 3, ley_x + sq, y + 3 + sq],
                       fill=bg, outline=COLOR_BORDE)
        draw.text((ley_x + sq + 8, y + 3), txt,
                  font=f_small, fill=COLOR_TEXTO)
        y += 26

    # ── Exportar ──────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


# ── Test ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from categorias import _cat_temperatura, _cat_viento, _cat_precipitacion

    datos_prueba = [
        (7,  18, 0.0, 12), (8,  19, 0.0, 14), (9,  22, 0.0, 18),
        (10, 25, 0.0, 20), (11, 28, 0.0, 22), (12, 31, 0.0, 25),
        (13, 33, 0.0, 28), (14, 35, 0.0, 30), (15, 37, 0.0, 32),
        (16, 38, 0.0, 35), (17, 39, 0.0, 38), (18, 38, 0.0, 35),
        (19, 36, 0.0, 30), (20, 34, 0.0, 28), (21, 32, 0.0, 25),
        (22, 30, 0.0, 22), (23, 27, 0.0, 18),
    ]

    filas = [{
        "hora":       h,
        "temp":       t,
        "precip":     p,
        "viento":     v,
        "temp_cat":   _cat_temperatura(t),
        "precip_cat": _cat_precipitacion(p),
        "viento_cat": _cat_viento(v),
    } for h, t, p, v in datos_prueba]

    img_bytes = generar_imagen_tabla(
        filas_datos = filas,
        hay_cap     = True,
        horas_cap   = {14, 15, 16, 17, 18, 19},
        logo_path   = "/mnt/user-data/uploads/1780573097513_image.png",
    )

    with open("/mnt/user-data/outputs/tabla_test.png", "wb") as f:
        f.write(img_bytes)
    print("✅ tabla_test.png generada")
