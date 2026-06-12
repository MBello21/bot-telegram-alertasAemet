# 🌦️ Bot de Telegram — Alertas AEMET

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Container-blue?style=for-the-badge&logo=docker&logoColor=white)
![Proxmox](https://img.shields.io/badge/Proxmox-LXC-orange?style=for-the-badge&logo=proxmox&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot--API-blue?style=for-the-badge&logo=telegram&logoColor=white)

Bot automatizado e interactivo para la monitorización, consulta y envío en tiempo real de alertas climatológicas oficiales emitidas por la **AEMET** (Agencia Estatal de Meteorología). Diseñado específicamente para entornos de infraestructura doméstica (*Home Lab*) o servidores de producción ligeros basados en contenedores.

---

## 🏗️ Arquitectura

El sistema delega la ejecución del resumen diario en el planificador del host físico (LXC) para garantizar la resiliencia del servicio sin comprometer la seguridad ni los privilegios del contenedor.

LXC no privilegiado (Proxmox)├── Docker│   └── aemet-bot  ← bot interactivo, siempre activo└── cron del LXC└── 07:00h → docker exec aemet-bot python enviar_resumen.py
> 💡 **Nota de Diseño:** El resumen matutino lo dispara el **cron nativo del LXC**, no un proceso continuo en segundo plano dentro de Docker. Esto mantiene el contenedor *single-process*, optimiza recursos y evita lidiar con problemas de *capabilities* o permisos en entornos virtuales LXC no privilegiados en Proxmox.

---

## 📋 Requisitos

- LXC no privilegiado con la característica **nesting=1** habilitada en Proxmox.
- Docker y Docker Compose instalados dentro del LXC.
- Token de acceso para el bot de Telegram (Generado vía [@BotFather](https://t.me/BotFather)).
- Clave API de AEMET OpenData gratuita (Solicítala en [opendata.aemet.es](https://opendata.aemet.es/centrodedescargas/altaUsuario)).

---

## 🚀 Instalación y Configuración

### 1. Configurar Proxmox para Docker en LXC no privilegiado

Para permitir la ejecución de contenedores Docker dentro de un LXC sin privilegios, es necesario activar el anidamiento (*nesting*).

**Opción A (Vía CLI en el Host Proxmox):**
Editar el archivo de configuración del contenedor `/etc/pve/lxc/<VMID>.conf` y añadir la siguiente línea:
```text
features: nesting=1
Opción B (Vía GUI de Proxmox):Navegar a: LXC ➔ Options ➔ Features ➔ Editar y marcar la casilla de Nesting.2. Instalar Docker en el LXCAccede a la consola de tu LXC y ejecuta el script oficial de instalación:Bash# Dentro del LXC
apt update && apt install -y curl
curl -fsSL [https://get.docker.com](https://get.docker.com) | sh
3. Desplegar el BotClona este repositorio en tu máquina, genera tu entorno de configuración y levanta el servicio:Bash# Copiar los archivos al LXC y entrar al directorio
cp .env.example .env
nano .env  # Rellena el archivo con tus credenciales privadas

# Levantar el contenedor construyendo la imagen
docker compose up -d --build
4. Configurar el Cron en el LXCPara que el resumen matutino se envíe puntualmente según la hora oficial, ajusta la zona horaria de tu LXC y añade la tarea programada:Bash# Abrir el editor del cron del sistema dentro del LXC
crontab -e
Añade la siguiente línea al final del archivo (disparará de forma desasistida a las 07:00h del LXC redireccionando los logs):Plaintext0 7 * * * docker exec aemet-bot python enviar_resumen.py >> /var/log/aemet_resumen.log 2>&1
Verificar que el LXC usa la zona horaria correcta:Bashtimedatectl set-timezone Europe/Madrid
⚙️ Variables de Entorno (.env)Asegúrate de configurar correctamente los siguientes parámetros en tu archivo de configuración:VariableDescripciónEjemplo / ValorTELEGRAM_TOKENToken secreto de autenticación del bot (@BotFather).123456:AAxx...CHAT_IDIdentificador único del chat o canal de destino.123456789AEMET_API_KEYClave de acceso al portal OpenData de la AEMET.eyJhbGci...PROVINCIA_CODIGOCódigo INE de la provincia a monitorizar (Cádiz = 11).11MUNICIPIO_CODIGOCódigo INE del municipio específico (Cádiz = 11012).11012Cómo obtener tu CHAT_ID:Envía cualquier mensaje o el comando /start a tu bot recién creado en Telegram.Visita la siguiente URL desde tu navegador: https://api.telegram.org/bot<TU_TELEGRAM_TOKEN>/getUpdatesBusca el campo "id" dentro del objeto "chat" en la respuesta JSON.🕹️ Comandos del BotPuedes interactuar directamente con el bot en Telegram utilizando los siguientes comandos integrados:ComandoDescripción/startMensaje de bienvenida, verificación de estado y comandos disponibles./alertasFuerza una evaluación meteorológica completa buscando avisos activos en este instante./tiempoDevuelve una tabla estructurada con la predicción del día en el rango de 07h a 23h./infoMuestra la configuración geográfica activa en el bot sin exponer credenciales.🛠️ Operación y MantenimientoComandos útiles para la gestión del ciclo de vida del contenedor, auditorías rápidas y depuración del servicio:Bash# Estado del contenedor
docker compose ps

# Logs del bot en tiempo real
docker compose logs -f

# Probar el envío matutino manualmente
docker exec aemet-bot python enviar_resumen.py

# Logs del cron
tail -f /var/log/aemet_resumen.log

# Reconstruir tras cambios en el código
docker compose up -d --build

# Parar
docker compose down
👤 AutorMiguel A. García BelloDevOps Specialist & Full Stack DeveloperGitHub: @MBello21
