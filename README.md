# 🌍 Mundial 2026 Live

**Dashboard en tiempo real del Mundial FIFA 2026 — Canadá · México · Estados Unidos**

[![Live](https://img.shields.io/badge/Live-luquitapalu.github.io-ef2b3d?style=flat-square&logo=github)](https://luquitapalu.github.io/mundial-2026-live)
[![HTML](https://img.shields.io/badge/HTML-CSS-JS-0c1b3a?style=flat-square&logo=html5)](https://luquitapalu.github.io/mundial-2026-live)
[![API](https://img.shields.io/badge/API-football--data.org-f5c451?style=flat-square)](https://www.football-data.org/)

---

## ¿Qué es esto?

Sitio web estático que muestra resultados, clasificaciones, goleadores y estadísticas del Mundial 2026 actualizados automáticamente con cada partido. Sin frameworks, sin dependencias pesadas: HTML, CSS y JavaScript puro.

Los datos se actualizan cada 30 minutos desde la API de [football-data.org](https://www.football-data.org/) a través de un script en Python que corre en background y escribe los archivos JSON que consume el frontend.

---

## 🚀 Features

### ⚽ Partidos
- Todos los 104 partidos del torneo ordenados cronológicamente por día y horario local.
- Indicador **En vivo** con minutaje en tiempo real para los partidos en curso.
- Los días ya jugados se **colapsan automáticamente** (acordeón) para mantener el foco en lo que viene.

### 🏆 Play-Off
- Bracket visual de la fase eliminatoria: 16avos, Octavos, Cuartos, Semifinales y Final.
- Se va completando con los clasificados a medida que avanza el torneo.

### 📊 Clasificaciones
- Tabla de posiciones de los 12 grupos con destacado de los clasificados (dorado) y los mejores terceros (azul).
- **Tabla de mejores terceros** con los 12 terceros de todos los grupos, ordenados por los criterios reales de desempate del torneo, con los 8 clasificados resaltados.

### 🥅 Goleadores
- Top 20 artilleros del torneo con goles y asistencias.

### 📈 Estadísticas
- **KPIs globales del torneo**: partidos jugados, goles totales, promedio de goles y porcentaje de empates.
- Estadísticas históricas + datos del torneo por selección (mundiales disputados, títulos, mejor resultado, rendimiento actual).

### 📲 Compartir por WhatsApp
- Botón flotante que genera un resumen automático del día (resultados + equipos) listo para compartir en cualquier grupo.

---

## 🛠️ Stack técnico

| Capa | Tecnología |
|---|---|
| Frontend | HTML5 · CSS3 · JavaScript (vanilla) |
| Datos | [football-data.org API](https://www.football-data.org/) |
| Actualización | Python (script con cron job) |
| Deploy | GitHub Pages |
| Fuentes | Google Fonts (Anton, Bebas Neue, Barlow) |

---

## 📁 Estructura del proyecto

```
mundial-2026-live/
├── index.html              # Frontend completo (HTML + CSS + JS)
├── actualizar_2026.py      # Script Python que consulta la API y actualiza los JSON
├── servidor.py             # Servidor local para desarrollo
├── data/
│   ├── live.json           # Partidos, clasificaciones y goleadores en tiempo real
│   ├── standings.json      # Tabla de posiciones desde la API
│   └── historico.json      # Datos históricos de cada selección
├── assets/
│   └── og-mundial-2026.jpg # Imagen para Open Graph / redes sociales
└── requirements.txt
```

---

## ⚙️ Cómo correrlo localmente

1. Cloná el repositorio:
```bash
git clone https://github.com/luquitapalu/mundial-2026-live.git
cd mundial-2026-live
```

2. Instalá las dependencias de Python:
```bash
pip install -r requirements.txt
```

3. Configurá tu API key de football-data.org en `actualizar_2026.py`:
```python
API_KEY = "tu_api_key_aqui"
```

4. Corré el script para poblar los datos:
```bash
python actualizar_2026.py
```

5. Abrí `index.html` en el browser o levantá el servidor local:
```bash
python servidor.py
```

---

## 🔄 Actualización automática de datos

El script `actualizar_2026.py` consulta la API de football-data.org y genera/actualiza los archivos JSON en la carpeta `data/`. En producción corre cada 30 minutos mediante un cron job. Durante partidos en vivo la frecuencia puede aumentarse editando el intervalo en el script.

---

## 🌐 Demo

**[luquitapalu.github.io/mundial-2026-live](https://luquitapalu.github.io/mundial-2026-live)**

---

## 👤 Autor

Hecho por **Lucas** · [@elprofedata](https://twitter.com/elprofedata)

Profe de Educación Física y preparador físico apasionado por los datos y el desarrollo web.

---

*Datos provistos por [football-data.org](https://www.football-data.org/) · Mundial FIFA 2026*
