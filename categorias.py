"""
Logica de categorizacion interna segun la tabla de umbrales.

CAT.  Color   Sens.Termica(C)  Tª AEMET(C)  Viento(km/h)  Precip.(mm/h)
  0   🟦      ST < 20          < 22          0 < v < 25    I < 5
  I   🟩      20 <= ST < 27    27            25 <= v < 45  5 <= I < 10
  II  ⬜      27 <= ST <= 31   29            45 <= v < 50  10 <= I < 15
  III 🟨      31 < ST <= 39    36            50 <= v < 70  15 <= I < 30
  IV  🟧      39 < ST <= 54    39            70 <= v < 90  30 <= I < 60
  V   🟥      ST > 54          42            v >= 90       I >= 60
"""

from dataclasses import dataclass

CATEGORIA_MINIMA_ALERTA = 2  # CAT. II

NOMBRES = ["CAT. 0", "CAT. I", "CAT. II", "CAT. III", "CAT. IV", "CAT. V"]
COLORES = ["🟦", "🟩", "⬜", "🟨", "🟧", "🟥"]


@dataclass
class ResultadoCategoria:
    categoria:        int
    nombre:           str
    color:            str
    variable_critica: str
    detalle:          str

    @property
    def debe_alertar(self) -> bool:
        return self.categoria >= CATEGORIA_MINIMA_ALERTA


def _cat_sens_termica(st: float | None) -> int:
    if st is None: return 0
    if st > 54:    return 5
    if st > 39:    return 4
    if st > 31:    return 3
    if st >= 27:   return 2
    if st >= 20:   return 1
    return 0


def _cat_temperatura(t: float | None) -> int:
    if t is None: return 0
    if t >= 42:   return 5
    if t >= 39:   return 4
    if t >= 36:   return 3
    if t >= 29:   return 2
    if t >= 27:   return 1
    return 0


def _cat_viento(v: float | None) -> int:
    if v is None: return 0
    if v >= 90:   return 5
    if v >= 70:   return 4
    if v >= 50:   return 3
    if v >= 45:   return 2
    if v >= 25:   return 1
    return 0


def _cat_precipitacion(p: float | None) -> int:
    if p is None: return 0
    if p >= 60:   return 5
    if p >= 30:   return 4
    if p >= 15:   return 3
    if p >= 10:   return 2
    if p >= 5:    return 1
    return 0


def calcular_categoria(
    sens_termica_max:  float | None,
    temperatura_max:   float | None,
    viento_max:        float | None,
    precip_max_hora:   float | None,
) -> ResultadoCategoria:
    candidatos = {
        f"Sensacion termica ({sens_termica_max}C)": _cat_sens_termica(sens_termica_max),
        f"Temperatura ({temperatura_max}C)":         _cat_temperatura(temperatura_max),
        f"Viento ({viento_max} km/h)":               _cat_viento(viento_max),
        f"Precipitacion ({precip_max_hora} mm/h)":   _cat_precipitacion(precip_max_hora),
    }
    variable_critica = max(candidatos, key=candidatos.get)
    cat = candidatos[variable_critica]

    partes = []
    if sens_termica_max is not None:
        partes.append(f"ST {sens_termica_max}C")
    if temperatura_max is not None:
        partes.append(f"T {temperatura_max}C")
    if viento_max is not None:
        partes.append(f"V {viento_max} km/h")
    if precip_max_hora is not None:
        partes.append(f"P {precip_max_hora} mm/h")

    return ResultadoCategoria(
        categoria        = cat,
        nombre           = NOMBRES[cat],
        color            = COLORES[cat],
        variable_critica = variable_critica,
        detalle          = " · ".join(partes),
    )
