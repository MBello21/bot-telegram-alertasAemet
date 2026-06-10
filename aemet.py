"""
Cliente para AEMET OpenData.

Fuentes:
  - API horaria: /api/prediccion/especifica/municipio/horaria/{codmun}
  - API CAP:     /api/avisos_cap/ultimoelaborado/area/{CAP_AREA} (TAR con XMLs CAP)
"""

import asyncio
import io
import json
import logging
import os
import tarfile
from datetime import date
from dataclasses import dataclass
from xml.etree import ElementTree as ET

import httpx
from categorias import (
    calcular_categoria, ResultadoCategoria, COLORES, NOMBRES,
    CATEGORIA_MINIMA_ALERTA, _cat_temperatura, _cat_viento, _cat_precipitacion
)

logger = logging.getLogger(__name__)

BASE_URL         = "https://opendata.aemet.es/opendata/api"
CAP_AREA         = os.environ.get("CAP_AREA", "61")
CAP_ZONA_PREFIJO = os.environ.get("CAP_ZONA_PREFIJO", "")

PROVINCIAS = {
    "01": "Alava",         "02": "Albacete",      "03": "Alicante",
    "04": "Almeria",       "05": "Avila",          "06": "Badajoz",
    "07": "Baleares",      "08": "Barcelona",      "09": "Burgos",
    "10": "Caceres",       "11": "Cadiz",          "12": "Castellon",
    "13": "Ciudad Real",   "14": "Cordoba",        "15": "A Coruna",
    "16": "Cuenca",        "17": "Girona",         "18": "Granada",
    "19": "Guadalajara",   "20": "Gipuzkoa",       "21": "Huelva",
    "22": "Huesca",        "23": "Jaen",           "24": "Leon",
    "25": "Lleida",        "26": "La Rioja",       "27": "Lugo",
    "28": "Madrid",        "29": "Malaga",         "30": "Murcia",
    "31": "Navarra",       "32": "Ourense",        "33": "Asturias",
    "34": "Palencia",      "35": "Las Palmas",     "36": "Pontevedra",
    "37": "Salamanca",     "38": "Santa Cruz de Tenerife", "39": "Cantabria",
    "40": "Segovia",       "41": "Sevilla",        "42": "Soria",
    "43": "Tarragona",     "44": "Teruel",         "45": "Toledo",
    "46": "Valencia",      "47": "Valladolid",     "48": "Bizkaia",
    "49": "Zamora",        "50": "Zaragoza",       "51": "Ceuta",
    "52": "Melilla",
}

NIVEL_EMOJI = {"amarillo": "🟡", "naranja": "🟠", "rojo": "🔴", "verde": "🟢"}
FENOMENO_EMOJI = {
    "lluvia": "🌧", "nieve": "❄", "viento": "💨", "tormenta": "⛈",
    "niebla": "🌫", "oleaje": "🌊", "temperatura": "🌡",
    "costero": "⚓", "deshielo": "💧", "incendio": "🔥",
}

HORAS_TABLA = list(range(7, 24))

DESCRIPCIONES = [
    "Sin riesgo",
    "Precaucion (Riesgo muy bajo)",
    "Precaucion Alta (Riesgo bajo)",
    "Alerta Amarilla (Riesgo medio)",
    "Alerta Naranja (Riesgo alto)",
    "Alerta Roja (Riesgo muy alto)",
]

LEYENDA = (
    "\n"
    "🟥 CAT.V  — Alerta Roja (Riesgo muy alto)\n"
    "🟧 CAT.IV — Alerta Naranja (Riesgo alto)\n"
    "🟨 CAT.III — Alerta Amarilla (Riesgo medio)\n"
    "⬜ CAT.II  — Precaucion Alta (Riesgo bajo)\n"
    "🟩 CAT.I   — Precaucion (Riesgo muy bajo)\n"
    "🟦 CAT.0   — Sin riesgo"
)

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"


def _float(v) -> float | None:
    try:
        return float(v) if v not in (None, "", "Ip") else None
    except (ValueError, TypeError):
        return None


def _cap(tag: str) -> str:
    return f"{{{CAP_NS}}}{tag}"


@dataclass
class DatoHora:
    hora:   int
    temp:   float | None
    viento: float | None
    precip: float | None


class AemetClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"api_key": api_key}

    async def _get_json(self, url: str) -> dict | list | None:
        async with httpx.AsyncClient(timeout=20) as c:
            try:
                r = await c.get(url, headers=self.headers)
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError as e:
                logger.error(f"HTTP error: {e}")
                return None

    async def _get_datos(self, datos_url: str) -> list | None:
        async with httpx.AsyncClient(timeout=20) as c:
            try:
                r = await c.get(datos_url, headers=self.headers)
                r.raise_for_status()
                content = r.content.decode("latin-1")
                return json.loads(content)
            except httpx.HTTPError as e:
                logger.error(f"HTTP error (datos): {e}")
                return None

    async def _get_bytes(self, url: str) -> bytes | None:
        async with httpx.AsyncClient(timeout=30) as c:
            try:
                r = await c.get(url, headers=self.headers)
                r.raise_for_status()
                return r.content
            except httpx.HTTPError as e:
                logger.error(f"HTTP error (bytes): {e}")
                return None

    async def _obtener_dias_horarios(self, codmun: str) -> list | None:
        url = f"{BASE_URL}/prediccion/especifica/municipio/horaria/{codmun}"
        meta = await self._get_json(url)
        if not meta or not isinstance(meta, dict):
            return None
        datos_url = meta.get("datos")
        if not datos_url:
            return None
        datos = await self._get_datos(datos_url)
        if not datos or not isinstance(datos, list):
            return None
        try:
            return datos[0]["prediccion"]["dia"]
        except (KeyError, IndexError, TypeError):
            return None

    def _parsear_dia_hoy(self, dias: list) -> tuple[str, list[DatoHora]]:
        hoy = date.today().isoformat()
        filas: list[DatoHora] = []

        for dia in dias:
            if dia.get("fecha", "")[:10] != hoy:
                continue

            temp_por_hora = {int(e["periodo"]): _float(e.get("value"))
                             for e in dia.get("temperatura", [])
                             if e.get("periodo", "").isdigit()}

            viento_por_hora = {int(e["periodo"]): _float(e["velocidad"][0])
                               for e in dia.get("vientoAndRachaMax", [])
                               if e.get("periodo", "").isdigit()
                               and "velocidad" in e}

            precip_por_hora = {int(e["periodo"]): _float(e.get("value"))
                               for e in dia.get("precipitacion", [])
                               if e.get("periodo", "").isdigit()}

            for h in HORAS_TABLA:
                filas.append(DatoHora(
                    hora   = h,
                    temp   = temp_por_hora.get(h),
                    viento = viento_por_hora.get(h),
                    precip = precip_por_hora.get(h),
                ))

        return "", filas

    def _maximos_de_filas(self, filas: list[DatoHora]) -> dict:
        temps   = [f.temp   for f in filas if f.temp   is not None]
        vientos = [f.viento for f in filas if f.viento is not None]
        precips = [f.precip for f in filas if f.precip is not None]
        return {
            "temp_max":   max(temps,   default=None),
            "st_max":     None,
            "viento_max": max(vientos, default=None),
            "precip_max": max(precips, default=None),
        }

    def _alertas_internas(self, filas: list[DatoHora], nombre_prov: str) -> list[dict]:
        alertas = []

        horas_temp = [(f.hora, f.temp) for f in filas
                      if f.temp is not None and _cat_temperatura(f.temp) >= CATEGORIA_MINIMA_ALERTA]
        if horas_temp:
            val_max = max(v for _, v in horas_temp)
            cat = calcular_categoria(None, val_max, None, None)
            alertas.append({
                "zona":        nombre_prov,
                "nivelAviso":  DESCRIPCIONES[cat.categoria],
                "parametro":   "Temperatura maxima",
                "descripcion": f"Temperatura maxima: {val_max:.0f}C",
                "inicio":      f"{horas_temp[0][0]:02d}:00",
                "fin":         f"{horas_temp[-1][0]:02d}:59",
                "cat":         cat,
                "interna":     True,
            })

        horas_viento = [(f.hora, f.viento) for f in filas
                        if f.viento is not None and _cat_viento(f.viento) >= CATEGORIA_MINIMA_ALERTA]
        if horas_viento:
            val_max = max(v for _, v in horas_viento)
            cat = calcular_categoria(None, None, val_max, None)
            alertas.append({
                "zona":        nombre_prov,
                "nivelAviso":  DESCRIPCIONES[cat.categoria],
                "parametro":   "Viento maximo sostenido",
                "descripcion": f"Viento maximo: {val_max:.0f} km/h",
                "inicio":      f"{horas_viento[0][0]:02d}:00",
                "fin":         f"{horas_viento[-1][0]:02d}:59",
                "cat":         cat,
                "interna":     True,
            })

        horas_precip = [(f.hora, f.precip) for f in filas
                        if f.precip is not None and _cat_precipitacion(f.precip) >= CATEGORIA_MINIMA_ALERTA]
        if horas_precip:
            val_max = max(v for _, v in horas_precip)
            cat = calcular_categoria(None, None, None, val_max)
            alertas.append({
                "zona":        nombre_prov,
                "nivelAviso":  DESCRIPCIONES[cat.categoria],
                "parametro":   "Precipitacion",
                "descripcion": f"Precipitacion maxima: {val_max:.1f} mm/h",
                "inicio":      f"{horas_precip[0][0]:02d}:00",
                "fin":         f"{horas_precip[-1][0]:02d}:59",
                "cat":         cat,
                "interna":     True,
            })

        return alertas

    def _parsear_tar_cap(self, contenido: bytes, provincia_codigo: str) -> list[dict]:
        hoy = date.today().isoformat()
        alertas = []
        try:
            tar = tarfile.open(fileobj=io.BytesIO(contenido))
        except tarfile.TarError as e:
            logger.error(f"Error abriendo TAR: {e}")
            return []

        for member in tar.getmembers():
            if not member.name.endswith(".xml"):
                continue
            f = tar.extractfile(member)
            if not f:
                continue
            try:
                root = ET.fromstring(f.read())
            except ET.ParseError as e:
                logger.error(f"Error parseando XML {member.name}: {e}")
                continue

            for info in root.findall(_cap("info")):
                lang = info.findtext(_cap("language")) or ""
                if not lang.startswith("es"):
                    continue

                zona = ""
                for geocode in info.findall(f".//{_cap('geocode')}"):
                    vname = geocode.findtext(_cap("valueName")) or ""
                    if "zona" in vname.lower():
                        zona = geocode.findtext(_cap("value")) or ""
                        break

                # Usar CAP_ZONA_PREFIJO si esta definido, si no usar provincia_codigo
                prefijo = CAP_ZONA_PREFIJO if CAP_ZONA_PREFIJO else provincia_codigo
                if len(zona) < 4 or zona[2:4] != prefijo:
                    continue

                onset = info.findtext(_cap("onset")) or ""
                if not onset.startswith(hoy):
                    continue

                nivel = ""
                parametro = ""
                for param in info.findall(_cap("parameter")):
                    vname = param.findtext(_cap("valueName")) or ""
                    value = param.findtext(_cap("value")) or ""
                    if "nivel" in vname.lower():
                        nivel = value.lower()
                    if "parametro" in vname.lower():
                        partes = value.split(";")
                        parametro = partes[1] if len(partes) > 1 else value

                # Si parametro vacio intentar obtenerlo de eventCode
                if not parametro:
                    for ec in info.findall(_cap("eventCode")):
                        vname = ec.findtext(_cap("valueName")) or ""
                        if "fenomeno" in vname.lower():
                            value = ec.findtext(_cap("value")) or ""
                            partes = value.split(";")
                            parametro = partes[1] if len(partes) > 1 else value
                            break

                # Si aun vacio usar event
                if not parametro:
                    parametro = info.findtext(_cap("event"), default="")

                alertas.append({
                    "zona":       info.findtext(_cap("areaDesc"), default=zona),
                    "nivelAviso": nivel,
                    "parametro":  parametro,
                    "inicio":     onset[11:16],
                    "fin":        (info.findtext(_cap("expires")) or "")[11:16],
                    "interna":    False,
                })

        return alertas

    async def obtener_alertas_cap(self, provincia_codigo: str) -> tuple[bool, list]:
        url = f"{BASE_URL}/avisos_cap/ultimoelaborado/area/{CAP_AREA}"
        meta = await self._get_json(url)
        if not meta or not isinstance(meta, dict):
            return False, []
        if meta.get("estado") == 404:
            return False, []
        datos_url = meta.get("datos")
        if not datos_url:
            return False, []
        contenido = await self._get_bytes(datos_url)
        if not contenido:
            return False, []
        alertas = self._parsear_tar_cap(contenido, provincia_codigo)
        if not alertas:
            return False, []
        return True, alertas

    def _fmt_alertas(self, alertas: list, maximos: dict) -> str:
        """Solo texto de alertas, sin tabla ni leyenda."""
        lineas = []
        for a in alertas:
            interna  = a.get("interna", False)
            nivel    = str(a.get("nivelAviso", "")).strip()
            fenomeno = str(a.get("parametro", "")).strip()
            zona     = a.get("zona", "")
            inicio   = a.get("inicio", "")
            fin      = a.get("fin", "")

            if interna:
                cat  = a.get("cat")
                en   = cat.color if cat else "⚠️"
                tipo = "Alerta Interna"
                desc = a.get("descripcion", "")
            else:
                en   = NIVEL_EMOJI.get(nivel.lower(), "⚠️")
                tipo = "Alerta AEMET"
                fenomeno_lower = fenomeno.lower()
                if "temperatura" in fenomeno_lower and maximos.get("temp_max") is not None:
                    desc = f"Temperatura maxima: {maximos['temp_max']:.0f}C"
                elif "viento" in fenomeno_lower and maximos.get("viento_max") is not None:
                    desc = f"Viento maximo: {maximos['viento_max']:.0f} km/h"
                elif ("lluvia" in fenomeno_lower or "precipit" in fenomeno_lower) and maximos.get("precip_max") is not None:
                    desc = f"Precipitacion maxima: {maximos['precip_max']:.1f} mm/h"
                else:
                    desc = a.get("descripcion", "")

            lineas.append(
                f"{en} *{tipo} — {zona}*\n"
                f"   {fenomeno} — {nivel.capitalize()}\n"
                f"   {desc}\n"
                f"   🕐 {inicio} — {fin}"
            )

        return "\n\n".join(lineas)

    def _tabla_prediccion(
        self, filas: list[DatoHora], nombre_prov: str,
        hay_cap: bool = False, hay_interna: bool = False,
        horas_cap: set = None
    ) -> str:
        if horas_cap is None:
            horas_cap = set()

        cab_tabla = "|  Hr  | Of. |  TºC   |  P mm/h   |  V Km/h  |"
        sep       = "-" * 46
        lineas    = [cab_tabla, sep]

        for f in filas:
            cat_t = _cat_temperatura(f.temp)
            cat_v = _cat_viento(f.viento)
            cat_p = _cat_precipitacion(f.precip)

            ic_t = COLORES[cat_t] if cat_t > 0 else "  "
            ic_v = COLORES[cat_v] if cat_v > 0 else "  "
            ic_p = COLORES[cat_p] if cat_p > 0 else "  "

            t = f"{ic_t}{f.temp:.0f}"   if f.temp   is not None else "ND"
            v = f"{ic_v}{f.viento:.0f}" if f.viento is not None else "ND"
            p = f"{f.precip:.1f}"       if f.precip is not None else "ND"

            of = NIVEL_EMOJI.get("amarillo", "🟡") if f.hora in horas_cap else "   "

            lineas.append(f"| {f.hora:02d}   | {of} | {t:>6} | {p:>9} | {v:>8} |")

        if hay_cap:
            estado_cap = "⚠️ Hay alertas oficiales AEMET activas"
        else:
            estado_cap = "✅ No hay alertas oficiales AEMET activas"

        cab  = f"Avisos por fenomenos meteorologicos adversos\n{estado_cap}\n"
        tabla = "```\n" + "\n".join(lineas) + "\n```"

        leyenda = (
            "Col. Of. = Alerta oficial AEMET activa en esa hora\n"
            "🟥 Alerta Roja  (prioridad maxima)\n"
            "🟧 Alerta Naranja\n"
            "🟨 Alerta Amarilla\n"
            "⬜ CAT. II: Riesgo bajo\n"
            "🟩 CAT. I: Riesgo muy bajo"
        )

        return cab + tabla + "\n\n" + leyenda

    async def obtener_tabla_y_maximos(
        self, codmun: str, nombre_prov: str = "Cadiz",
        hay_cap: bool = False, hay_interna: bool = False,
        horas_cap: set = None
    ) -> tuple[str, dict, list[DatoHora]]:
        dias = await self._obtener_dias_horarios(codmun)
        if not dias:
            return "No se pudo obtener la prediccion horaria.", {}, []
        _, filas = self._parsear_dia_hoy(dias)
        maximos  = self._maximos_de_filas(filas)
        tabla    = self._tabla_prediccion(filas, nombre_prov, hay_cap, hay_interna, horas_cap or set())
        return tabla, maximos, filas

    async def obtener_datos_municipio(self, codmun: str) -> dict:
        _, maximos, _ = await self.obtener_tabla_y_maximos(codmun)
        return maximos

    async def obtener_solo_alertas(self, codmun: str, provincia_codigo: str) -> tuple[bool, str]:
        """Para /alertas — devuelve solo texto de alertas, sin tabla ni leyenda."""
        nombre_prov = PROVINCIAS.get(provincia_codigo, provincia_codigo)

        (_, maximos, filas), (hay_cap, alertas_cap) = await asyncio.gather(
            self.obtener_tabla_y_maximos(codmun, nombre_prov),
            self.obtener_alertas_cap(provincia_codigo),
        )

        cat: ResultadoCategoria | None = None
        if maximos:
            cat = calcular_categoria(
                sens_termica_max = maximos.get("st_max"),
                temperatura_max  = maximos.get("temp_max"),
                viento_max       = maximos.get("viento_max"),
                precip_max_hora  = maximos.get("precip_max"),
            )

        if hay_cap:
            alertas = alertas_cap
        elif cat is not None and cat.debe_alertar:
            alertas = self._alertas_internas(filas, nombre_prov)
        else:
            color  = cat.color  if cat else "🟦"
            nombre = cat.nombre if cat else "CAT. 0"
            return False, f"✅ *Sin alertas activas — {nombre_prov}*\n{color} {nombre} — Sin riesgo"

        return True, self._fmt_alertas(alertas, maximos)

    async def evaluar_y_formatear(self, codmun: str, provincia_codigo: str) -> tuple[bool, str, bytes]:
        """Para el cron — devuelve flag + texto alertas + imagen PNG."""
        nombre_prov = PROVINCIAS.get(provincia_codigo, provincia_codigo)

        (_, maximos, filas), (hay_cap, alertas_cap) = await asyncio.gather(
            self.obtener_tabla_y_maximos(codmun, nombre_prov),
            self.obtener_alertas_cap(provincia_codigo),
        )

        cat: ResultadoCategoria | None = None
        if maximos:
            cat = calcular_categoria(
                sens_termica_max = maximos.get("st_max"),
                temperatura_max  = maximos.get("temp_max"),
                viento_max       = maximos.get("viento_max"),
                precip_max_hora  = maximos.get("precip_max"),
            )

        if hay_cap:
            alertas     = alertas_cap
            hay_interna = False
        elif cat is not None and cat.debe_alertar:
            alertas     = self._alertas_internas(filas, nombre_prov)
            hay_interna = True
        else:
            alertas     = []
            hay_interna = False

        if not alertas:
            return False, "", b""

        # Calcular horas con alerta CAP activa
        horas_cap = set()
        if hay_cap:
            for a in alertas_cap:
                inicio_str = a.get("inicio", "")
                fin_str    = a.get("fin", "")
                if inicio_str and fin_str:
                    try:
                        h_ini = int(inicio_str[:2])
                        h_fin = int(fin_str[:2])
                        for h in range(h_ini, h_fin + 1):
                            horas_cap.add(h)
                    except ValueError:
                        pass

        texto_alertas = self._fmt_alertas(alertas, maximos)
        imagen = self._generar_imagen(filas, hay_cap, horas_cap)
        return True, texto_alertas, imagen

    async def obtener_imagen_tiempo(self, codmun: str, nombre_prov: str = "Cadiz") -> bytes:
        """Para /tiempo — devuelve solo la imagen de la tabla."""
        _, maximos, filas = await self.obtener_tabla_y_maximos(codmun, nombre_prov)
        if not filas:
            return b""

        hay_cap, alertas_cap = await self.obtener_alertas_cap(
            next((k for k, v in PROVINCIAS.items() if v == nombre_prov), "11")
        )

        horas_cap = set()
        if hay_cap:
            for a in alertas_cap:
                try:
                    h_ini = int(a.get("inicio", "")[:2])
                    h_fin = int(a.get("fin", "")[:2])
                    for h in range(h_ini, h_fin + 1):
                        horas_cap.add(h)
                except (ValueError, TypeError):
                    pass

        return self._generar_imagen(filas, hay_cap, horas_cap)

    def _generar_imagen(self, filas: list[DatoHora], hay_cap: bool, horas_cap: set) -> bytes:
        """Construye las filas_datos y llama al generador de imagen."""
        try:
            from generar_tabla_imagen import generar_imagen_tabla

            filas_datos = [{
                "hora":       f.hora,
                "temp":       f.temp,
                "precip":     f.precip,
                "viento":     f.viento,
                "temp_cat":   _cat_temperatura(f.temp),
                "precip_cat": _cat_precipitacion(f.precip),
                "viento_cat": _cat_viento(f.viento),
            } for f in filas]

            logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
            return generar_imagen_tabla(
                filas_datos = filas_datos,
                hay_cap     = hay_cap,
                horas_cap   = horas_cap,
                logo_path   = logo_path if os.path.exists(logo_path) else None,
            )
        except Exception as e:
            logger.error(f"Error generando imagen: {e}")
            return b""

    async def obtener_prediccion_4dias(self, codmun: str, provincia_codigo: str) -> tuple[list, list]:
        """
        Devuelve (dias_datos, alertas) para la imagen de prediccion 4 dias.
        dias_datos: lista de dicts con fecha y periodos 00-12 / 12-24.
        alertas: lista de alertas CAP activas o futuras proximos dias.
        """
        from categorias import _cat_temperatura, _cat_viento

        def _cat_precip_prob(p):
            if p is None: return 0
            if p >= 80: return 3
            if p >= 50: return 2
            if p >= 30: return 1
            return 0

        # Prediccion diaria
        url  = f"{BASE_URL}/prediccion/especifica/municipio/diaria/{codmun}"
        meta = await self._get_json(url)
        if not meta or not isinstance(meta, dict):
            return [], []
        datos_url = meta.get("datos")
        if not datos_url:
            return [], []
        datos = await self._get_datos(datos_url)
        if not datos or not isinstance(datos, list):
            return [], []

        try:
            dias_api = datos[0]["prediccion"]["dia"][:4]
        except (KeyError, IndexError):
            return [], []

        dias_datos = []
        for dia in dias_api:
            fecha = (dia.get("fecha") or "")[:10]
            temp_max = dia.get("temperatura", {}).get("maxima")
            temp_min = dia.get("temperatura", {}).get("minima")

            vientos = {v["periodo"]: v.get("velocidad") for v in dia.get("viento", [])
                       if v.get("periodo") in ["00-12", "12-24"]}
            precips = {p["periodo"]: p.get("value") for p in dia.get("probPrecipitacion", [])
                       if p.get("periodo") in ["00-12", "12-24"]}

            periodos = []
            for periodo in ["00-12", "12-24"]:
                v   = vientos.get(periodo)
                p   = precips.get(periodo)
                periodos.append({
                    "periodo":     periodo,
                    "temp_max":    temp_max,
                    "temp_min":    temp_min,
                    "viento":      v,
                    "precip_prob": p,
                    "cat_temp":    _cat_temperatura(temp_max),
                    "cat_viento":  _cat_viento(v),
                    "cat_precip":  _cat_precip_prob(p),
                })

            dias_datos.append({"fecha": fecha, "periodos": periodos})

        # Alertas CAP — incluir activas y proximas (expires >= hoy)
        alertas_img = []
        try:
            from datetime import date as _date
            hoy = _date.today().isoformat()
            contenido_cap = None
            url_cap = f"{BASE_URL}/avisos_cap/ultimoelaborado/area/{CAP_AREA}"
            meta_cap = await self._get_json(url_cap)
            if meta_cap and meta_cap.get("estado") != 404 and meta_cap.get("datos"):
                contenido_cap = await self._get_bytes(meta_cap["datos"])

            if contenido_cap:
                import tarfile as _tar
                from xml.etree import ElementTree as _ET
                zona_objetivo = os.environ.get("CAP_ZONA_ESPECIFICA", "")
                if zona_objetivo:
                    if zona != zona_objetivo:
                        continue
                else:
                    prefijo = CAP_ZONA_PREFIJO if CAP_ZONA_PREFIJO else provincia_codigo
                    if len(zona) < 4 or zona[2:4] != prefijo:
                        continue
                tar = _tar.open(fileobj=io.BytesIO(contenido_cap))
                vistos = set()
                for member in tar.getmembers():
                    if not member.name.endswith(".xml"):
                        continue
                    f = tar.extractfile(member)
                    if not f:
                        continue
                    root = _ET.fromstring(f.read())
                    for info in root.findall(_cap("info")):
                        lang = info.findtext(_cap("language")) or ""
                        if not lang.startswith("es"):
                            continue
                        zona = ""
                        for geocode in info.findall(f".//{_cap('geocode')}"):
                            vname = geocode.findtext(_cap("valueName")) or ""
                            if "zona" in vname.lower():
                                zona = geocode.findtext(_cap("value")) or ""
                                break
                        if len(zona) < 4 or zona[2:4] != prefijo:
                            continue
                        expires = info.findtext(_cap("expires")) or ""
                        if not expires or expires[:10] < hoy:
                            continue
                        nivel = ""
                        parametro = ""
                        for param in info.findall(_cap("parameter")):
                            vname = param.findtext(_cap("valueName")) or ""
                            value = param.findtext(_cap("value")) or ""
                            if "nivel" in vname.lower():
                                nivel = value.lower()
                            if "parametro" in vname.lower():
                                partes = value.split(";")
                                parametro = partes[1] if len(partes) > 1 else value
                        if not parametro:
                            for ec in info.findall(_cap("eventCode")):
                                vname = ec.findtext(_cap("valueName")) or ""
                                if "fenomeno" in vname.lower():
                                    value = ec.findtext(_cap("value")) or ""
                                    partes = value.split(";")
                                    parametro = partes[1] if len(partes) > 1 else value
                                    break
                        if not parametro:
                            parametro = info.findtext(_cap("event"), default="")

                        onset   = info.findtext(_cap("onset"), default="")
                        clave   = f"{zona}-{onset}-{nivel}"
                        if clave in vistos:
                            continue
                        vistos.add(clave)

                        alertas_img.append({
                            "zona":        info.findtext(_cap("areaDesc"), default=zona),
                            "nivelAviso":  nivel,
                            "parametro":   parametro,
                            "descripcion": info.findtext(_cap("description"), default=""),
                            "inicio":      onset[11:16],
                            "fin":         expires[11:16],
                        })
        except Exception as e:
            logger.error(f"Error obteniendo alertas para prediccion: {e}")

        return dias_datos, alertas_img

    async def obtener_imagen_prediccion(self, codmun: str, provincia_codigo: str) -> bytes:
        """Para /prediccion — genera imagen con tabla 4 dias + alertas."""
        try:
            from generar_prediccion_imagen import generar_imagen_prediccion

            dias_datos, alertas = await self.obtener_prediccion_4dias(codmun, provincia_codigo)
            if not dias_datos:
                return b""

            logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
            return generar_imagen_prediccion(
                dias_datos = dias_datos,
                alertas    = alertas,
                logo_path  = logo_path if os.path.exists(logo_path) else None,
            )
        except Exception as e:
            logger.error(f"Error generando imagen prediccion: {e}")
            return b""
