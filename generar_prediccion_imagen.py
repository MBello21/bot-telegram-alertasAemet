"""
Genera una imagen PNG con la prediccion de 4 dias.
Logo, cabecera, alertas activas si las hay, tabla por periodos 12h, leyenda.
"""

from PIL import Image, ImageDraw, ImageFont
import io
import os
from datetime import date, timedelta

# ── Colores ───────────────────────────────────────────────────────────────────
COLORES_CAT = {
    0: (255, 255, 255),
    1: (144, 238, 144),
    2: (220, 220, 220),
    3: (255, 255, 153),
    4: (255, 178, 102),
    5: (255, 102, 102),
}

COLOR_FONDO      = (250, 250, 250)
COLOR_CABECERA   = (25,  45,  75)
COLOR_TEXTO_CAB  = (255, 255, 255)
COLOR_HEAD_TAB   = (50,  80, 120)
COLOR_TEXTO_HT   = (255, 255, 255)
COLOR_BORDE      = (160, 160, 160)
COLOR_TEXTO      = (30,  30,  30)
COLOR_ND         = (215, 215, 215)
COLOR_ALERTA_BG  = (255, 245, 220)
COLOR_FECHA_BG   = (230, 238, 250)
COLOR_NIVEL = {
    "amarillo": (255, 230, 100),
    "naranja":  (255, 160,  60),
    "rojo":     (220,  60,  60),
    "verde":    (144, 238, 144),
}

ANCHO_IMG  = 720
ALTO_LOGO  = 110
ALTO_CAB   = 50
ALTO_FILA  = 34
PADDING    = 22

# Columnas: Fecha | Per. | TMax | TMin | Viento | P(%)
COL_W     = [110, 70, 80, 80, 100, 80]
COL_NAMES = ["Fecha", "Per.", "T Max", "T Min", "V km/h", "P %"]
TABLA_W   = sum(COL_W)

DIAS_ES = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
MESES_ES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


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


def _color_cat(cat):
    return COLORES_CAT.get(cat, (255, 255, 255))


def _fmt_fecha(fecha_str: str) -> str:
    try:
        d = date.fromisoformat(fecha_str[:10])
        return f"{DIAS_ES[d.weekday()]} {d.day:02d} {MESES_ES[d.month]}"
    except:
        return fecha_str[:10]


def generar_imagen_prediccion(
    dias_datos: list,
    alertas: list,
    logo_path: str | None = None,
) -> bytes:
    """
    dias_datos: lista de dicts con keys:
        fecha, periodos: [{periodo, temp_max, temp_min, viento, precip_prob,
                           cat_temp, cat_viento, cat_precip}]
    alertas: lista de dicts con keys: zona, nivelAviso, parametro, descripcion, inicio, fin
    """
    f_small  = _fuente(12)
    f_normal = _fuente(14)
    f_bold   = _fuente(14, bold=True)
    f_title  = _fuente(15, bold=True)
    f_alerta = _fuente(13)

    n_periodos = sum(len(d["periodos"]) for d in dias_datos)
    tabla_x    = (ANCHO_IMG - TABLA_W) // 2

    # Calcular alto de alertas
    alto_alertas = 0
    if alertas:
        alto_alertas = PADDING // 2 + len(alertas) * 70 + PADDING // 2

    leyenda_items = [
        (_color_cat(5), "CAT. V  — Alerta Roja"),
        (_color_cat(4), "CAT. IV — Alerta Naranja"),
        (_color_cat(3), "CAT. III — Alerta Amarilla"),
        (_color_cat(2), "CAT. II  — Precaucion Alta"),
        (_color_cat(1), "CAT. I   — Precaucion"),
    ]
    ALTO_LEYENDA = len(leyenda_items) * 24 + 16

    alto_img = (PADDING
                + ALTO_LOGO + PADDING
                + ALTO_CAB  + PADDING // 2
                + alto_alertas
                + ALTO_FILA                      # cabecera columnas
                + ALTO_FILA * n_periodos
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
        "COEX CA-03 — Prediccion Meteorologica 4 dias",
        font=f_title, fill=COLOR_TEXTO_CAB, anchor="mm"
    )
    y += ALTO_CAB + PADDING // 2

    # ── Alertas activas ───────────────────────────────────────────────────────
    if alertas:
        for a in alertas:
            nivel    = a.get("nivelAviso", "").lower()
            fenomeno = a.get("parametro", "")
            zona     = a.get("zona", "")
            desc     = a.get("descripcion", "")
            inicio   = a.get("inicio", "")
            fin      = a.get("fin", "")
            bg_niv   = COLOR_NIVEL.get(nivel, (255, 240, 150))

            draw.rounded_rectangle(
                [PADDING, y, ANCHO_IMG - PADDING, y + 62],
                radius=5, fill=COLOR_ALERTA_BG
            )
            draw.rounded_rectangle(
                [PADDING, y, PADDING + 8, y + 62],
                radius=3, fill=bg_niv
            )
            draw.text((PADDING + 16, y + 6),
                      f"⚠ Alerta AEMET — {zona}",
                      font=f_bold, fill=COLOR_TEXTO)
            draw.text((PADDING + 16, y + 24),
                      f"{fenomeno} — {nivel.capitalize()}   {inicio} — {fin}",
                      font=f_alerta, fill=COLOR_TEXTO)
            draw.text((PADDING + 16, y + 42),
                      desc[:80],
                      font=f_alerta, fill=(80, 80, 80))
            y += 70

        y += PADDING // 2

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
    for di, dia in enumerate(dias_datos):
        fecha_txt = _fmt_fecha(dia["fecha"])
        n_per     = len(dia["periodos"])

        for pi, per in enumerate(dia["periodos"]):
            periodo   = per.get("periodo", "")
            temp_max  = per.get("temp_max")
            temp_min  = per.get("temp_min")
            viento    = per.get("viento")
            precip    = per.get("precip_prob")
            cat_t     = per.get("cat_temp", 0)
            cat_v     = per.get("cat_viento", 0)
            cat_p     = per.get("cat_precip", 0)

            t_max_str = f"{temp_max}" if temp_max is not None else "ND"
            t_min_str = f"{temp_min}" if temp_min is not None else "ND"
            v_str     = f"{viento}"   if viento   is not None else "ND"
            p_str     = f"{precip}%"  if precip   is not None else "ND"

            col_tmax = _color_cat(cat_t) if temp_max is not None else COLOR_ND
            col_tmin = _color_cat(0)
            col_v    = _color_cat(cat_v) if viento   is not None else COLOR_ND
            col_p    = _color_cat(cat_p) if precip   is not None else COLOR_ND

            # Fila alterna para fecha
            col_fecha = COLOR_FECHA_BG if pi == 0 else (242, 242, 242)

            x = tabla_x

            # Celda fecha — solo en primera fila del dia
            draw.rectangle([x, y, x + COL_W[0], y + ALTO_FILA], fill=col_fecha)
            draw.rectangle([x, y, x + COL_W[0], y + ALTO_FILA], outline=COLOR_BORDE)
            if pi == 0:
                draw.text((x + COL_W[0] // 2, y + ALTO_FILA // 2), fecha_txt,
                          font=f_bold, fill=COLOR_TEXTO, anchor="mm")
            x += COL_W[0]

            # Periodo
            draw.rectangle([x, y, x + COL_W[1], y + ALTO_FILA], fill=(240, 240, 240))
            draw.rectangle([x, y, x + COL_W[1], y + ALTO_FILA], outline=COLOR_BORDE)
            draw.text((x + COL_W[1] // 2, y + ALTO_FILA // 2), periodo,
                      font=f_normal, fill=COLOR_TEXTO, anchor="mm")
            x += COL_W[1]

            # T Max
            draw.rectangle([x, y, x + COL_W[2], y + ALTO_FILA], fill=col_tmax)
            draw.rectangle([x, y, x + COL_W[2], y + ALTO_FILA], outline=COLOR_BORDE)
            draw.text((x + COL_W[2] // 2, y + ALTO_FILA // 2), t_max_str,
                      font=f_normal, fill=_texto_color(col_tmax), anchor="mm")
            x += COL_W[2]

            # T Min
            draw.rectangle([x, y, x + COL_W[3], y + ALTO_FILA], fill=col_tmin)
            draw.rectangle([x, y, x + COL_W[3], y + ALTO_FILA], outline=COLOR_BORDE)
            draw.text((x + COL_W[3] // 2, y + ALTO_FILA // 2), t_min_str,
                      font=f_normal, fill=_texto_color(col_tmin), anchor="mm")
            x += COL_W[3]

            # Viento
            draw.rectangle([x, y, x + COL_W[4], y + ALTO_FILA], fill=col_v)
            draw.rectangle([x, y, x + COL_W[4], y + ALTO_FILA], outline=COLOR_BORDE)
            draw.text((x + COL_W[4] // 2, y + ALTO_FILA // 2), v_str,
                      font=f_normal, fill=_texto_color(col_v), anchor="mm")
            x += COL_W[4]

            # Precip prob
            draw.rectangle([x, y, x + COL_W[5], y + ALTO_FILA], fill=col_p)
            draw.rectangle([x, y, x + COL_W[5], y + ALTO_FILA], outline=COLOR_BORDE)
            draw.text((x + COL_W[5] // 2, y + ALTO_FILA // 2), p_str,
                      font=f_normal, fill=_texto_color(col_p), anchor="mm")

            y += ALTO_FILA

    # ── Leyenda ───────────────────────────────────────────────────────────────
    y += PADDING
    sq    = 14
    max_w = max(draw.textlength(txt, font=f_small) for _, txt in leyenda_items)
    ley_w = sq + 8 + int(max_w)
    ley_x = (ANCHO_IMG - ley_w) // 2

    for bg, txt in leyenda_items:
        draw.rectangle([ley_x, y + 3, ley_x + sq, y + 3 + sq],
                       fill=bg, outline=COLOR_BORDE)
        draw.text((ley_x + sq + 8, y + 3), txt, font=f_small, fill=COLOR_TEXTO)
        y += 24

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


# ── Test ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from categorias import _cat_temperatura, _cat_viento

    def _cat_precip_prob(p):
        if p is None: return 0
        if p >= 80: return 3
        if p >= 50: return 2
        if p >= 30: return 1
        return 0

    dias_test = [
        {"fecha": "2026-06-09", "periodos": [
            {"periodo": "00-12", "temp_max": 23, "temp_min": 20, "viento": 10, "precip_prob": 0,
             "cat_temp": _cat_temperatura(23), "cat_viento": _cat_viento(10), "cat_precip": _cat_precip_prob(0)},
            {"periodo": "12-24", "temp_max": 25, "temp_min": 20, "viento": 15, "precip_prob": 0,
             "cat_temp": _cat_temperatura(25), "cat_viento": _cat_viento(15), "cat_precip": _cat_precip_prob(0)},
        ]},
        {"fecha": "2026-06-10", "periodos": [
            {"periodo": "00-12", "temp_max": 24, "temp_min": 20, "viento": 20, "precip_prob": 0,
             "cat_temp": _cat_temperatura(24), "cat_viento": _cat_viento(20), "cat_precip": _cat_precip_prob(0)},
            {"periodo": "12-24", "temp_max": 26, "temp_min": 20, "viento": 35, "precip_prob": 10,
             "cat_temp": _cat_temperatura(26), "cat_viento": _cat_viento(35), "cat_precip": _cat_precip_prob(10)},
        ]},
        {"fecha": "2026-06-11", "periodos": [
            {"periodo": "00-12", "temp_max": 27, "temp_min": 22, "viento": 35, "precip_prob": 0,
             "cat_temp": _cat_temperatura(27), "cat_viento": _cat_viento(35), "cat_precip": _cat_precip_prob(0)},
            {"periodo": "12-24", "temp_max": 29, "temp_min": 22, "viento": 50, "precip_prob": 0,
             "cat_temp": _cat_temperatura(29), "cat_viento": _cat_viento(50), "cat_precip": _cat_precip_prob(0)},
        ]},
        {"fecha": "2026-06-12", "periodos": [
            {"periodo": "00-12", "temp_max": 27, "temp_min": 22, "viento": 30, "precip_prob": 0,
             "cat_temp": _cat_temperatura(27), "cat_viento": _cat_viento(30), "cat_precip": _cat_precip_prob(0)},
            {"periodo": "12-24", "temp_max": 29, "temp_min": 22, "viento": 35, "precip_prob": 0,
             "cat_temp": _cat_temperatura(29), "cat_viento": _cat_viento(35), "cat_precip": _cat_precip_prob(0)},
        ]},
    ]

    alertas_test = [
        {
            "zona": "Litoral de Cadiz",
            "nivelAviso": "amarillo",
            "parametro": "Viento",
            "descripcion": "Viento del sur con rachas de 60 km/h.",
            "inicio": "14:00",
            "fin": "20:00",
        }
    ]

    img_bytes = generar_imagen_prediccion(
        dias_datos = dias_test,
        alertas    = alertas_test,
        logo_path  = "/mnt/user-data/uploads/1780573097513_image.png",
    )

    with open("/mnt/user-data/outputs/prediccion_test.png", "wb") as f:
        f.write(img_bytes)
    print("✅ prediccion_test.png generada")
