# Deck brief: Snowflake World Tour CDMX 2026

**Talk:** *El futuro de los servicios financieros: agentes con contexto de la industria y conectividad*
**Speaker:** Carlos Haro, Sr. AI Engineer, Santander
**When:** Tue 13 Oct 2026, 11:00 CST, Breakout Room 2, Level 2, Diego 2. **15 minutes, hard stop.**
**Audience:** mixed business + engineering, Mexico City. **All slide copy and speaker notes in Spanish.**

## The one message
> *El futuro de la banca no son agentes más listos: son agentes con contexto y con límites.*

Secondary goal: the audience leaves convinced Santander does AI *seriously*. That signal comes from rigor (definitions, invariants, refusals), never from claims or numbers about the bank.

## Hard rules (every agent)
1. **Spanish copy.** No em dashes (use commas, colons, periods or `·`). En dashes only for numeric ranges.
2. **Santander facts allowed, exhaustive list:** "Sr. AI Engineer en Banco Santander", "casi 10 años lidiando con datos". Nothing else about Santander: no metrics, no systems, no clients, no logos besides what the template already carries. Every banking example carries the tag **Ilustrativo**.
3. **Snowflake legal:** slide 2 (Safe Harbor) is untouched. The "© 2026 Snowflake Inc." footer comes from the layouts, never delete it. Any Snowflake feature named on a slide that is not GA gets "(vista previa pública)" or "(vista previa privada)".
4. **Stay in the template's visual language:** its fonts (Arial bold titles, Arial/Lato body), its sizes, the blue title tab, palette only: Snowflake Blue `29B5E8`, Mid Blue `11567F`, Midnight `000000`, Star Blue `71D3DC`, Valencia Orange `FF9F36` (refusal / consequence only), Purple Moon `7D44CF` (model proposals only), Iceberg `003545`, Winter `24323D`, Windy City `8A999E` (muted). White content backgrounds. No accent lines under titles, no decorative stripes, no gradients.
5. **Few words.** Titles ≤ 9 words. Body text is for the back row: nothing under 18 pt on a 20 in × 11.25 in slide. If it doesn't fit, cut words.
6. **Diagrams with native shapes** (rounded rectangles, connectors, icons from the template). No screenshots of code. A rejected path is drawn in Valencia Orange with "✕ rechazada · sin efecto".
7. **Speaker notes** (Spanish) on every slide you own, in this shape:
   `Propósito: … / Tiempo: m:ss–m:ss (m:ss) / Guion: … (what to say, short lines) / Transición: "…"`. Live-demo slides also get `Demo: …` with the exact steps and `Si falla: …` (play the labeled recording; never fake results).

## File ownership (the package is shared; touch only your files)
The slide files keep their template names. **Deck position → file:**

| # | File (`deck/src/ppt/slides/`) | Notes file (`ppt/notesSlides/`) | Owner |
|---|---|---|---|
| 1 | slide1.xml | notesSlide1.xml | A |
| 2 | slide2.xml | notesSlide2.xml | nobody (Safe Harbor) |
| 3 | slide13.xml | notesSlide13.xml | A |
| 4 | slide3.xml | notesSlide3.xml | A |
| 5 | slide6.xml | notesSlide6.xml | B |
| 6 | slide25.xml | notesSlide25.xml | B |
| 7 | slide11.xml | notesSlide11.xml | B |
| 8 | slide17.xml | notesSlide17.xml | C |
| 9 | slide14.xml | notesSlide14.xml | C |
| 10 | slide15.xml | notesSlide15.xml | C |
| 11 | slide21.xml | notesSlide21.xml | D |
| 12 | slide27.xml | notesSlide27.xml | D |
| 13 | slide9.xml | notesSlide9.xml | D |

- You may edit **only** your slide XML, its `_rels/slideN.xml.rels`, its notes slide, and add new media named `ppt/media/swt-<owner>-<name>.png|jpg`.
- **Never** edit `presentation.xml`, `[Content_Types].xml` (png/jpg are already registered; don't add svg), layouts, masters or the theme.
- Parse/write XML with `defusedxml.minidom` or careful string edits; never round-trip through `xml.etree`.
- Preview: `deck/tools/pack.sh /tmp/swt-<owner>` (packs, validates, renders PNGs). Look at your slides at full size before you finish.
- Don't commit. Report what you changed.

## Live data used across the deck
- **Poll QR (slide 3):** `https://h1sort.com/swt` (a redirect we will point at the poll group). Show the URL in text under the QR as `h1sort.com/swt`.
- **Slides QR (slide 13):** `https://h1sort.com/snowflake`, shown as `h1sort.com/snowflake`.
- QR generation: `python3 -m pip install --break-system-packages qrcode[pil]`, black on white, quiet zone 2, PNG ≥ 1000 px.
- **The three poll questions:**
  1. ¿Cuál describe mejor tu rol? · Negocio / Ingeniería / Datos y analítica / Liderazgo / Otro
  2. En los últimos 7 días, ¿usaste IA para trabajar con datos? · Sí / No
  3. ¿Le darías a un agente permiso de actuar en producción? · Sí / Sí, con aprobación humana / No
- **The live Ask question:** "Por rol, ¿qué porcentaje le daría a un agente permiso de actuar en producción? Solo cuenta a quien respondió rol y P3."
- **Definitions the Semantic View must encode:** "permiso" = P3 is "Sí" or "Sí, con aprobación humana"; denominator = browsers that answered both P1 and P3; a missing answer is never a "No".
- **Judge verdict values:** `pasa | revisar | rechazar`. Only `pasa` unlocks Act. (Not "aprobar": that collides with "definición aprobada" and "aprobación humana".)
- **Names used consistently:** "loader incremental", "Control de la aplicación" (architecture) / "la aplicación" (Act slide).

## Slide by slide (timings total 13:20, 1:40 buffer)

### 1 · Cover (slide1.xml): A · 0:00–0:15
Keep the "SNOWFLAKE WORLD TOUR" lockup and skyline art. Replace "FROM BLUEPRINT TO BUSINESS IMPACT" with **EL FUTURO DE LOS SERVICIOS FINANCIEROS** (same style, caps). Subtitle: **Agentes con contexto de la industria y conectividad**. Add a line: **Carlos Haro · Sr. AI Engineer, Santander**.
Notes: one-line greeting, no bio (bio is slide 4). Transition: "Saquen el teléfono."

### 2 · Safe Harbor (slide2.xml): untouched · 0:15–0:20
### 3 · "Saquen el teléfono" (slide13.xml, dotted wave): A · 0:20–1:35
Title: **Los datos empiezan aquí**. Subtitle: **3 preguntas · 1 minuto**. Big QR to the right, `h1sort.com/swt` under it. Left: the three questions as a short numbered list (question text only, no options).
Notes: the room creates the dataset; no prepared data. Talk over the voting (who's in the room, why live data). Before the talk: open the poll group (all questions OPEN) and test the QR on a phone. Count rows, not people (a browser is not a person). Transition: "Mientras votan, ¿quién les está contando esto?"

### 4 · ¿Quién es este tipo? (slide3.xml, "About Our Company"): A · 1:35–2:05
Replace the template stock photo with `assets/carlos-portrait.png` (B&W portrait, crop to a square centered on the face, keep the template's circle frame). Header bar text: **¿Quién es este tipo?** Company name: **Santander**. Industry: **Servicios financieros**. Person: **Carlos Haro**, title **Sr. AI Engineer**, company **Santander**. Metric 1: **~10** · "años lidiando con datos". Metric 2: **@h1sort** · "h1sort.com". Description area: **Hot takes:** pandas es una pésima librería para el análisis de datos · los perros son mejores que los gatos · Santos Laguna es el mejor equipo de futbol de la historia.
Notes: one sentence of bio, deliver one hot take as the laugh, move on.

### 5 · Conectividad: arquitectura (slide6.xml): B · 2:05–3:20
Remove the red INSTRUCTIONS box. Title: **Conectividad: sus votos ya están en Snowflake**. Rebuild the template's architecture grid as the demo's *real* flow, keeping its column headers style (FUENTES · INGESTA · SIGNIFICADO · AGENTES · ENTREGA):
- **Fuentes:** App de encuestas (h1sort.com · Cloudflare D1), votos en vivo.
- **Ingesta:** Loader en micro-lotes, cada ~3 s → tablas RAW. (Do NOT say Snowpipe Streaming; we are not using it.)
- **Significado:** Semantic View: definiciones aprobadas (rol, respuesta válida, denominador).
- **Agentes:** Cortex Agent con Cortex Analyst (Ask) · AI_COMPLETE con salida tipada (Judge).
- **Entrega:** Harness de la aplicación: validación, aprobación humana, recibo → cierra la encuesta y publica resultados en h1sort.com.
Keep the bottom "GOVERN & MONITOR" band but translate and limit to what we use: **RBAC granular (rol de solo lectura) · Guardrails en la aplicación · Evaluación · Auditoría**. Grey out nothing; just fewer items. Verify GA status of Semantic Views, Cortex Agents, Cortex Analyst and AI_COMPLETE on docs.snowflake.com (WebSearch/WebFetch) and tag anything non-GA.
Notes: 20 seconds max on plumbing; then switch to Snowsight and show the row count ticking. Business framing: "La app es la sucursal. Snowflake es la memoria gobernada del banco. Los agentes trabajan sobre la memoria, nunca sobre la sucursal."

### 6 · Thesis quote (slide25.xml, Mid Blue quote): B · 3:20–3:50
Quote: **La respuesta abunda. El criterio sigue siendo escaso.** Attribution: **Carlos Haro | Sr. AI Engineer** / **Santander**.
Notes: producing analysis got cheap (callback to the agent that will answer in a minute); agreeing on what it means still takes judgment. Transition: "Así se ve el criterio cuando lo convertimos en infraestructura."

### 7 · La máquina: Ask · Judge · Act (slide11.xml, multi-use): B · 3:50–4:35
Title: **El mismo modelo. Distintas consecuencias.** Subtitle: **Consultar · Juzgar · Ejecutar**.
Body: a horizontal flow of three stations, left to right, on one rail: **Ask** (contexto: definición aprobada) → **Judge** (invariantes: evidencia obligatoria) → **Act** (frontera: el modelo propone, la aplicación ejecuta) → **Recibo**. Under each station its failure mode in small muted text: "respuesta equivocada" / "juicio sin evidencia" / "acción equivocada". Build this with native shapes as the **fallback**; an isometric figure (agent E) may later replace the body area, so keep the body inside the region x 1.0–19.0 in, y 2.6–10.2 in and name the group `machine-fallback`.
Notes: "No son niveles de madurez: son arquetipos de autoridad que un mismo sistema puede combinar." Transition into the live demo.

### 8 · Ask: contexto de la industria (slide17.xml, two columns): C · 4:35–7:35 (includes LIVE)
Title: **Ask: ¿cuántos clientes activos tenemos?** Tag **Ilustrativo**. Left column, "Una consulta válida, tres respuestas": three small cards, Definición A: saldo mayor a 0 al corte · Definición B: al menos una transacción en 90 días · Definición C: sesión en la app en 30 días. Right column, "Una definición aprobada": dueño · versión · fecha de corte · alcance, ending in the line **El warehouse reúne los datos. La capa semántica conserva su significado.**
Notes: then LIVE: ask the agent the poll question (exact wording above). Point at denominators: someone who skipped P3 is not a "No". Show the SQL it ran, the cutoff, numerators and denominators. If the sample is tiny, say so; don't invent findings. `Si falla:` recording.

### 9 · Judge: invariantes (slide14.xml, dotted wave 2): C · 7:35–9:20 (includes LIVE)
Title: **Judge: agencia local, invariantes globales**. Two zones. Left "Invariantes (código)": ✓ denominador = respuestas válidas · ✓ n ≥ 5 por grupo o "muestra insuficiente" · ✓ sin identificadores · ✓ corte visible. Right "Juicio (modelo)": a typed verdict card `veredicto: aprobar | revisar | rechazar` + `evidencia: […]`, with the line **Una salida válida no necesariamente es correcta.** Bottom statement: **Puede decidir qué evidencia revisar. No puede decidir que la evidencia obligatoria dejó de serlo.**
Notes: LIVE: the judge runs on the Ask answer; read the verdict. Only an "aprobar" unlocks Act.

### 10 · Act: la frontera (slide15.xml, dotted arrows): C · 9:20–11:35 (includes LIVE)
Title: **Act: el modelo propone, la aplicación ejecuta**. Flow left to right: **Solicitud** (propuesta del modelo, Purple Moon) → **Validación** (identidad · permisos · objetivo válido) → **Aprobación humana** → **Ejecución** → **Recibo**. From Validación, a Valencia Orange branch down to **✕ rechazada · sin efecto**. Small line: **Que el modelo pida una acción no significa que ya ocurrió.**
Notes: LIVE: (1) ask the agent to "borrar los votos incompletos": rejected, there is no delete tool, nothing happened; (2) the agent proposes closing the poll; validation passes; Carlos approves on stage; results appear on everyone's phone. That moment is the climax: pause.

### 11 · En un banco (slide21.xml, three columns with icons): D · 11:35–12:35
Title: **En un banco, lo que está en juego cambia**. Subtitle: **Ilustrativo**. Three columns, reuse the template icons (or close equivalents):
- **Ask · "¿Cuántos clientes activos tenemos?"** Falla: respuesta equivocada. Control: definición aprobada con dueño y versión.
- **Judge · Alerta de fraude.** Falla: juicio sin evidencia. Control: evidencia obligatoria y revisión humana antes de recomendar.
- **Act · "Perdí mi tarjeta, bloquéala."** Falla: acción equivocada. Control: identidad, autorización, efecto exacto, recibo.
Notes: same three patterns, real stakes. This is how we think about it, not a description of any Santander system.

### 12 · Closing quote (slide27.xml, white quote): D · 12:35–13:05
Quote: **El futuro de la banca no son agentes más listos: son agentes con contexto y con límites.** Attribution: **Carlos Haro | Sr. AI Engineer** / **Santander**.
Notes: say it slowly, then stop talking for a beat.

### 13 · Gracias (slide9.xml, THANK YOU): D · 13:05–13:20
Replace "THANK YOU" with **GRACIAS**. Add a white rounded card with the slides QR (`h1sort.com/snowflake`) and **@h1sort** under it, placed so it doesn't overlap the skyline art.
Notes: invite questions if time allows; point to the QR.
