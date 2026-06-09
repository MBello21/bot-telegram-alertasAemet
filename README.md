# 🌦️ Bot de Telegram — Alertas AEMET

## Arquitectura

```
LXC no privilegiado (Proxmox)
├── Docker
│   └── aemet-bot  ← bot interactivo, siempre activo
└── cron del LXC
    └── 07:00h → docker exec aemet-bot python enviar_resumen.py
```

El resumen matutino lo dispara el **cron nativo del LXC**, no un proceso dentro de Docker.
Esto evita problemas de capabilities con LXC no privilegiado.

---

## Requisitos

- LXC no privilegiado con **nesting=1** en Proxmox
- Docker y Docker Compose instalados en el LXC
- Token de bot Telegram ([@BotFather](https://t.me/BotFather))
- Clave API AEMET gratuita ([opendata.aemet.es](https://opendata.aemet.es/centrodedescargas/altaUsuario))

---

## Instalación

### 1. Configurar Proxmox para Docker en LXC no privilegiado

En el host Proxmox, editar `/etc/pve/lxc/<VMID>.conf` y añadir:

```
features: nesting=1
```

O desde la UI de Proxmox: LXC → Options → Features → ✅ Nesting.

### 2. Instalar Docker en el LXC

```bash
# Dentro del LXC
apt update && apt install -y curl
curl -fsSL https://get.docker.com | sh
```

### 3. Desplegar el bot

```bash
# Copiar los archivos al LXC y entrar al directorio
cp .env.example .env
nano .env          # Rellenar con tus credenciales

docker compose up -d --build
```

### 4. Configurar el cron en el LXC

```bash
crontab -e
```

Añadir esta línea (dispara a las 07:00 hora del LXC):

```
0 7 * * * docker exec aemet-bot python enviar_resumen.py >> /var/log/aemet_resumen.log 2>&1
```

Verificar que el LXC usa la zona horaria correcta:

```bash
timedatectl set-timezone Europe/Madrid
```

---

## Variables de entorno (.env)

| Variable | Descripción | Ejemplo |
|---|---|---|
| `TELEGRAM_TOKEN` | Token del bot (@BotFather) | `123456:AAxx...` |
| `CHAT_ID` | ID del chat donde enviar alertas | `123456789` |
| `AEMET_API_KEY` | Clave API AEMET OpenData (gratuita) | `eyJhbGci...` |
| `PROVINCIA_CODIGO` | Código INE de provincia (11 = Cádiz) | `11` |
| `MUNICIPIO_CODIGO` | Código INE de municipio (11012 = Cádiz) | `11012` |

**Cómo obtener el CHAT_ID:**
1. Envía cualquier mensaje a tu bot
2. Visita `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Busca el campo `"id"` dentro de `"chat"`

---

## Operación

```bash
# Estado del contenedor
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
```

---

## Comandos del bot

| Comando | Descripción |
|---|---|
| `/start` | Bienvenida y lista de comandos |
| `/alertas` | Evaluación completa ahora mismo |
| `/tiempo` | Tabla de predicción hoy (07h-23h) |
| `/info` | Configuración activa del bot |
