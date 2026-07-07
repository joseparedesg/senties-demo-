# Orkesta Fianzas — Demo Senties Chauvet

Demo funcional del producto Orkesta Fianzas para presentar a Diego Senties.
Datos sintéticos realistas del sector fianzas mexicano.

## Contenido

- **500 fianzas activas** distribuidas entre 6 afianzadoras (Chubb 60%, Aserta 20%, Tokio 10%, resto minoritario)
- **200 propuestas** de los últimos 90 días con estatus realistas
- **40 fiados** con RFCs y sectores del mercado
- **15 beneficiarios reales del sector público federal** (Pemex, IMSS, ISSSTE, Tesorería, etc.)
- **4 dashboards ejecutivos:** Salud del agente, Pipeline, Cartera por ejecutivo, Cobranza
- **Chat conversacional con Claude Sonnet 4.6** (o fallback local si no hay API key)
- **3 usuarios con roles diferenciados:** admin, operativo, ejecutivo

## Estructura del proyecto

```
senties-demo/
├── app/
│   ├── main.py              # FastAPI + rutas
│   ├── services/
│   │   ├── db.py            # Helper SQLite
│   │   ├── queries.py       # Queries de los 4 dashboards
│   │   └── chat.py          # Claude Sonnet + function calling
│   ├── templates/           # Jinja2 (login, hub, 4 dashboards, chat)
│   └── static/css/          # Estilos Orkesta
├── scripts/
│   └── generate_synthetic_data.py   # Genera SQLite con datos
├── data/                    # SQLite generado aquí
├── requirements.txt
├── Procfile                 # Railway
├── railway.json             # Railway config
├── runtime.txt              # Python 3.11.9
└── README.md
```

## Correr en localhost (5 minutos)

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Generar datos sintéticos
python scripts/generate_synthetic_data.py

# 3. (Opcional) Setear API key de Anthropic para chat real
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Correr servidor
uvicorn app.main:app --reload --port 8000
```

Abrir http://localhost:8000

**Usuarios demo (password para todos: `senties2026`):**
- `diego` — admin (Diego Senties)
- `marlene` — operativo (Marlene Barrera)
- `alfonso` — ejecutivo (Alfonso Vázquez, cartera AVAZQUEZ5274)

## Deploy a Railway

### Paso 1 — Crear repositorio en GitHub

```bash
cd senties-demo
git init
git add .
git commit -m "Initial commit: Orkesta Fianzas demo"
git remote add origin https://github.com/tuusuario/orkesta-fianzas-demo.git
git push -u origin main
```

### Paso 2 — Crear proyecto en Railway

1. Ir a https://railway.app/new
2. **"Deploy from GitHub repo"** → seleccionar `orkesta-fianzas-demo`
3. Railway detecta Python automáticamente (por `runtime.txt` y `requirements.txt`)
4. Deploy inicial arranca solo con el comando de `Procfile`

### Paso 3 — Configurar variables de entorno

En Railway → Project → Variables, agregar:

```
ANTHROPIC_API_KEY = sk-ant-... (tu API key de Anthropic)
SESSION_SECRET = <un string random largo>
```

### Paso 4 — Configurar dominio público

Railway → Settings → Networking → **Generate Domain**
Te da una URL tipo `orkesta-fianzas-demo.up.railway.app`

**Sugerencia:** cambiar el nombre del servicio en Railway a "senties-demo" para que la URL quede más elegante.

### Paso 5 — Verificar

Abrir la URL en el browser. Debe redirigir a `/login`. Ingresar como `diego` / `senties2026`.

## Preguntas prototípicas para la demo con Diego

Estas están probadas y garantizadas de dar respuestas impresionantes:

1. **"¿Cuál es mi exposición con Pemex?"** — responde $722M MXN desglosado por subsidiaria
2. **"¿Qué propuestas están atoradas?"** — lista propuestas con >5 días en trámite
3. **"Top 10 fiados por monto"** — ranking con línea disponible
4. **"Distribución por afianzadora"** — muestra los 6 sistemas
5. **"¿Cuántas fianzas necesito cancelar?"** — número de cancelables + monto liberable
6. **"¿Qué fianzas vencen el próximo mes?"** — lista ordenada por fecha
7. **"Consulta el fiado Motores e Ingeniería"** — información completa + fianzas activas
8. **"¿Cuál es la salud del negocio?"** — KPIs globales

## Detalles del chat conversacional

El chat usa **Claude Sonnet 4.6 con function calling**. Tiene 8 tools registradas:

- `consultar_kpis_globales`
- `exposicion_por_beneficiario`
- `propuestas_atoradas`
- `fianzas_por_vencer`
- `top_fiados`
- `consultar_fiado`
- `resumen_cancelables`
- `distribucion_por_afianzadora`

Claude decide qué tool usar según la pregunta, ejecuta consultas al SQLite, y responde en lenguaje natural con datos reales.

**Fallback sin API key:** si `ANTHROPIC_API_KEY` no está seteada, el chat usa un keyword matcher local que responde las mismas preguntas prototípicas pero sin capacidad de conversación libre. Para la demo real con Diego, usar la API key para experiencia completa.

## Cómo enmarcar el demo con Diego

Sugerencia de script (misma lógica que Orkesta Retail Demo):

> *"Diego, lo que vas a ver son los 4 dashboards de Orkesta Fianzas con datos sintéticos que simulan la operación de un broker parecido a Senties. Los beneficiarios (Pemex, IMSS, Tesorería) son los reales del mercado, los volúmenes son proporcionales a los tuyos (~10K fianzas activas). Cuando conectemos con Chubb real, donde aquí dice 'Motores e Ingeniería Mexmot' vas a ver a tus fiados reales, donde dice '$2 billones en Producción' vas a ver tu exposición real. El motor es el mismo."*

## Roadmap post-demo

Si Diego firma, este demo se convierte en el arranque de Fase 1 de producción:

1. **Semana 1:** migrar SQLite → PostgreSQL en Railway
2. **Semana 1-2:** reemplazar datos sintéticos con ETL nocturno de Chubb (código ya existente en `orkesta_chubb/`)
3. **Semana 2-3:** integración del generador Excel branded ya construido
4. **Semana 3:** demo formal con datos reales
5. **Semanas 4-15:** Acerta, Tokio, parsers de correo

Las 20-28 horas que costó este demo **cuentan dentro del presupuesto de Fase 1** — no es trabajo perdido.
