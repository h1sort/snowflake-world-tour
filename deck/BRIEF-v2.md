# Deck brief v2: the trust equation (supersedes the slide-by-slide part of BRIEF.md)

**Decided 13 Oct 03:36 CST by Carlos.** Live demo is CUT. No poll. The talk is rebuilt with the onion method: one core idea, one package.

- **Core idea:** an agent is only as trustworthy as its weakest link among context, evidence and control. If one is zero, trust is zero.
- **Package (the only one):** `Confianza = Contexto × Evidencia × Control`. Each factor has one question the audience can ask of any agent tomorrow:
  - Contexto → **¿Con qué definición respondió?**
  - Evidencia → **¿Qué evidencia lo respalda?**
  - Control → **¿Quién puede detenerlo?**
- **Santander framing:** "así pensamos estas decisiones". NEVER claim Santander does X in production. Allowed facts unchanged: "Sr. AI Engineer en Banco Santander", "casi 10 años lidiando con datos". Bank examples are labeled **Ilustrativo**.
- **Opening:** the tapping game (Elizabeth Newton, Stanford, 1990: tappers predicted listeners would name ~50% of songs; listeners named 3 of 120, 2.5%). Carlos taps *Las Mañanitas*.
- **Drop the English labels Ask / Judge / Act from slides** (they are "tune", not "taps"). Use Contexto / Evidencia / Control.
- All the hard rules of BRIEF.md still apply (Spanish, no em dashes, template look, ≥ 18 pt body, palette, Safe Harbor untouched, footers, file ownership, notes format `Propósito / Tiempo / Guion / Transición`). Live-demo `Demo:` / `Si falla:` lines are REMOVED everywhere.

## New order (14 slides, 12:45 planned, ~2:15 buffer for Q&A)

| # | File (`deck/src/ppt/slides/`) | Notes file | Owner | Time |
|---|---|---|---|---|
| 1 | slide1.xml (cover) | notesSlide1.xml | A (notes only) | 0:00–0:15 |
| 2 | slide2.xml (Safe Harbor) | notesSlide2.xml | nobody | 0:15–0:20 |
| 3 | slide13.xml | notesSlide13.xml | A | 0:20–1:20 |
| 4 | slide28.xml (copy of 13) | notesSlide28.xml | A | 1:20–2:05 |
| 5 | slide3.xml (¿Quién es este tipo?) | notesSlide3.xml | A (notes only) | 2:05–2:35 |
| 6 | slide25.xml (Mid Blue quote) | notesSlide25.xml | A | 2:35–3:35 |
| 7 | slide17.xml | notesSlide17.xml | B | 3:35–5:05 |
| 8 | slide14.xml | notesSlide14.xml | B | 5:05–6:35 |
| 9 | slide15.xml | notesSlide15.xml | B | 6:35–8:05 |
| 10 | slide11.xml (machine) | notesSlide11.xml | C | 8:05–9:20 |
| 11 | slide29.xml (copy of 21) | notesSlide29.xml | C | 9:20–10:20 |
| 12 | slide21.xml | notesSlide21.xml | C | 10:20–11:20 |
| 13 | slide27.xml (white quote) | notesSlide27.xml | C | 11:20–12:30 |
| 14 | slide9.xml (GRACIAS) | notesSlide9.xml | C (notes only) | 12:30–12:45 |

## Slide copy

**1 · Cover.** Unchanged. Notes: greet, no bio; transition "Antes de empezar, necesito su ayuda con algo."

**3 · Tapping (slide13).** Remove the poll entirely (QR image, URL text, the 3 numbered questions; delete their shapes and unused rels). Title: **¿Qué canción es?** Subtitle: **Escuchen con atención.** Body: one large line, left aligned: **Levanten la mano cuando la reconozcan.** plus a simple native-shape motif (e.g., a row of 8 Mid Blue dots of uneven spacing like taps on a table). No answer on the slide.
Notes: tap the melody of *Las Mañanitas* on the lectern, close to the mic, about 10 seconds, twice. Ask for hands. Ask one person. Reveal: "Era Las Mañanitas." Let the laugh happen. Transition: "Esto no es un juego: es uno de los experimentos más famosos de Stanford."

**4 · Reveal (slide28).** Same layout, replace body. Title: **La maldición del conocimiento**. Subtitle: **Elizabeth Newton · Stanford · 1990**. Two big stat callouts side by side (template big-number style, Snowflake Blue numbers ~96 pt, label ≥ 20 pt): **50 %** "lo que quienes tocaban creían que el público adivinaría" · **2.5 %** "lo que el público realmente adivinó (3 de 120 canciones)". Bottom Mid Blue band (like slides 8/9): **Para el banco, «cliente activo» es una canción obvia. Para un modelo, son golpes en la mesa.**
Notes: the tapper hears the whole song in their head; the listener hears noise. Banks are full of songs everyone inside "hears": cliente activo, cartera vencida, alerta. A model only gets the taps. Transition: "Antes de seguir: ¿quién les está contando esto?"

**5 · ¿Quién es este tipo?** Slide unchanged. Notes: Tiempo 2:05–2:35; transition: "Llevo años pensando en una pregunta: ¿cuándo podemos confiar en un agente? Lo resumo en una ecuación."

**6 · The equation (slide25, Mid Blue quote).** Quote text: **Confianza = Contexto × Evidencia × Control** (fit on max 2 lines; keep it big, ~66–72 pt; break after "=" if needed). Attribution line 1 (bold): **Si un factor es cero, la confianza es cero.** Line 2: **No es física: es una regla para decidir.**
Notes: it's a multiplication on purpose: the best model in the world with zero control gives zero trust. Three factors, one question each; that is the whole talk. "Así pensamos estas decisiones." Transition: "Empecemos por el contexto."

**7 · Contexto (slide17).** Title: **Contexto: ¿con qué definición respondió?** Subtitle: **¿Cuántos clientes activos tenemos?** Keep the Ilustrativo pill, left column (three definitions A/B/C) and right column (dueño · versión · fecha de corte · alcance + band "El warehouse reúne los datos. La capa semántica conserva su significado.") as they are.
Notes: back to the song: the same valid SQL gives three answers. The fix is not a smarter model, it's the definition with an owner and a version, given to the agent. Question to take home. Transition: "Segundo factor: la evidencia."

**8 · Evidencia (slide14).** Title: **Evidencia: ¿qué la respalda?** Subtitle: **Reglas que el código nunca deja romper**. Left zone header "Reglas (código)", four ✓ cards rewritten generic: **fuente y fecha de corte visibles** · **denominador explícito** · **muestra suficiente, o se dice** · **sin datos personales expuestos**. Right zone "Juicio (modelo)": keep the verdict card (`veredicto: pasa | revisar | rechazar`, `evidencia: […]`) and "Una salida válida no necesariamente es correcta." Bottom band unchanged ("Puede decidir qué evidencia revisar. No puede decidir que la evidencia obligatoria dejó de serlo.").
Notes: Ilustrativo fraud-alert framing: the agent may choose what extra evidence to look at; the mandatory evidence is not its call. Question to take home. Transition: "Tercer factor: el control."

**9 · Control (slide15).** Title: **Control: ¿quién puede detenerlo?** Subtitle: **El modelo propone, la aplicación ejecuta**. Keep the flow (Solicitud → Validación → Aprobación humana → Ejecución → Recibo, orange rejection branch) and the banner.
Notes: dual control is old banking wisdom: a vault needs two keys. Here: the application's key (identity, permissions, valid target) and, when the risk demands it, a human's. A request is not an action yet. Question to take home. Transition: "Juntemos los tres."

**10 · The machine (slide11).** Title: **Contexto × Evidencia × Control** Subtitle: **Si falta un factor, la solicitud sale sin efecto**. Keep the figure. Relabel the pills: "Contexto · definición v3", "Evidencia · 4 de 4", "Control · app + humano"; keep "Recibo" and "✕ rechazada · sin efecto". Keep the hidden `machine-fallback` group hidden.
Notes: walk the ticket left to right; then: "Quiten un solo pin de evidencia: no pasa. Eso es el ×0." Optional (only if the room has time and the laptop is on wifi): open h1sort.com/snowflake/maquina and press 3 to show a rejection live; never required. Transition: "¿Y dónde vive cada factor? Estamos en Snowflake."

**11 · Snowflake mapping (slide29, copy of 21: three columns with icons).** Title: **Dónde vive cada factor en Snowflake**. Ilustrativo pill NOT needed. Columns (reuse/adapt icons; Control may use a key or shield icon in Mid Blue):
- **Contexto** · "Semantic Views · Cortex Analyst" · "definiciones con dueño y versión; el agente consulta a través de ellas"
- **Evidencia** · "Datos gobernados · AI_COMPLETE con salida estructurada" · "consultas trazables y juicios que el código puede validar"
- **Control** · "RBAC · Cortex Agents" · "roles de solo lectura, herramientas permitidas; la aplicación decide qué se ejecuta"
All named features are GA (verified 12 Oct 2026). Notes: the platform gives you the place for each factor; deciding the definitions, the mandatory evidence and the keys is still your job. Transition: "Tres preguntas para llevarse."

**12 · Three questions (slide21).** Title: **Tres preguntas antes de confiar en un agente**. Keep the Ilustrativo pill. Columns (replace Falla/Control rows by Pregunta / Si es cero):
- **Contexto** · “¿Cuántos clientes activos tenemos?” · **Pregunta:** ¿con qué definición respondió? · **Si es cero:** respuesta equivocada
- **Evidencia** · Alerta de fraude · **Pregunta:** ¿qué evidencia lo respalda? · **Si es cero:** juicio sin evidencia
- **Control** · “Perdí mi tarjeta, bloquéala.” · **Pregunta:** ¿quién puede detenerlo? · **Si es cero:** acción equivocada
Notes: "Así pensamos estas decisiones" (never "así lo hace Santander"). Transition into the close.

**13 · Close (slide27, white quote).** Quote: **Confianza = Contexto × Evidencia × Control.** Second paragraph of the quote, smaller: **Si uno es cero, la confianza es cero.** Attribution unchanged (Carlos Haro | Sr. AI Engineer / Santander).
Notes: say the equation slowly; pause; "Mañana, ante cualquier agente, hagan las tres preguntas."

**14 · GRACIAS.** Slide unchanged (QR to h1sort.com/snowflake). Notes: Tiempo 12:30–12:45, Q&A with the buffer.
