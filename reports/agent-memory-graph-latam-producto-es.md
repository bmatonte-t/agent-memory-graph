# Propuesta de Producto y Despliegue para LATAM Airlines

Fecha de Generación: 2026-06-

Autor: ADO — Analytics Data Office

Asunto: Plataforma Empresarial de Memoria para Agentes IA — Documento Interno


## 1. Resumen Ejecutivo

##### Agent Memory Graph (AMG) es una plataforma empresarial de coordinación de agentes IA, nativa en GCP,

##### que resuelve los fallos más críticos de los despliegues de IA en producción: pérdida de contexto,

##### alucinaciones y costo de inferencia descontrolado. Sus dos innovaciones principales — el pipeline de

##### razonamiento MindMap y el sistema de Cognitive Weighting — trabajan en conjunto para entregar IA

##### cualitativamente mejor: menor tasa de alucinación, recuperación más rápida y un consumo de tokens LLM

##### significativamente menor en comparación con arquitecturas RAG convencionales.

##### El pipeline MindMap (inspirado en el artículo ACL'24 de Wen, Wang y Sun) obliga a que cada respuesta del

##### agente sea construida exclusivamente a partir de evidencia recuperada del grafo. El sistema de Cognitive

##### Weighting (inspirado en la infraestructura de memoria demostrable de Engram) asigna puntuaciones de

##### confianza bayesianas a cada hecho en memoria, aplica decaimiento temporal al conocimiento obsoleto y

##### condiciona la síntesis a umbrales de frescura y confianza. El resultado práctico: los agentes recuperan

##### únicamente hechos recientes y de alta señal; los hechos no utilizados o contradictorios se desvanecen

##### automáticamente; y el contexto del token se mantiene acotado y relevante, evitando las ventanas de

##### contexto extensas y costosas propias del RAG ingenuo.

##### Para LATAM Airlines, AMG es la capa de coordinación que falta en la plataforma Cosmos: un tejido de

##### memoria persistente y compartido en el que todos los agentes — desde copilotos internos de ingeniería

##### hasta chatbots orientados a pasajeros — pueden confiar y razonar. AMG está listo para producción (v0.2,

##### 843 pruebas pasando, P99 < 5ms), se despliega dentro de la organización GCP existente de LATAM e

##### integra de manera natural con el Cosmos GenAI Gateway, DataHub y el catálogo Backstage.

###### Cifras clave: Latencia P99 < 5ms (10x por debajo del SLO). El Cognitive Weighting acota el contexto de

###### recuperación a solo los hechos de alta confianza, reduciendo directamente el gasto en tokens LLM por turno

###### del agente. Tasa de fundamentación: 100% de las respuestas respaldadas por evidencia o señal explícita de

###### insuficiencia (cero alucinaciones).

## 2. Descripción del Producto

##### Agent Memory Graph es un sistema de memoria determinista, con fundamentación prioritaria, para

##### coordinar múltiples agentes IA dentro de una sola empresa. Elimina las alucinaciones al obligar a que cada

##### respuesta del agente se derive de evidencia recuperada de una base de datos de grafos. Preserva el

##### contexto organizacional a través de sesiones, usuarios y agentes. Y provee trazas de auditoría inmutables

##### para cada paso de razonamiento, crítico para industrias reguladas y flujos de trabajo sensibles al

##### cumplimiento normativo.

### 2.1 Los Problemas que Resuelve

##### Los despliegues de IA empresarial fallan por razones consistentes y bien comprendidas. AMG aborda cada

##### una con una decisión arquitectónica específica, no con un parche temporal:


###### Problema Cómo lo Resuelve AMG Característica Clave

```
Pérdida de Contexto — los agentes
olvidan interacciones entre sesiones; los
usuarios deben re-explicar los mismos
problemas repetidamente
```
```
El nivel Context almacena el historial
completo de sesión; el nivel Semantic
persiste hechos organizacionales
indefinidamente; el recall es automático
en cada turno del agente
```
```
Modelo de Memoria Tripartita
```
```
Alucinación — los agentes inventan
hechos no fundamentados en datos
organizacionales; las salidas no pueden
ser confiables para decisiones
operativas o reguladas
```
```
Pipeline MindMap: la síntesis está
prohibida a menos que los hechos sean
recuperados y serializados primero. Sin
evidencia = señal explícita de
insuficiencia, nunca una suposición
```
```
Pipeline de Fundamentación MindMap
```
```
Alto Costo en Tokens — el RAG ingenuo
inunda el contexto del LLM con
fragmentos débilmente relevantes,
aumentando el gasto de inferencia a
escala
```
```
El Cognitive Weighting filtra el grafo de
recuperación a solo los hechos de alta
confianza, frescos y de alta señal antes
de la síntesis. Horizontes de traversal
acotados previenen la dispersión de
contexto
```
```
Cognitive Weighting (Bayesiano)
```
```
Baja Precisión de Recuperación — la
búsqueda por similitud vectorial retorna
fragmentos temáticamente similares
pero factualmente poco confiables
```
```
El traversal del grafo sobre el nivel
Semantic sigue relaciones tipadas entre
entidades, produciendo caminos
estructuralmente fundamentados, no
vecinos vectoriales aproximados
```
```
Recuperación por Grafo Spanner
```
```
Brecha de Auditabilidad — sin trazas de
razonamiento; imposible depurar
decisiones o demostrar cumplimiento
normativo
```
```
El nivel Audit registra cada acceso a
memoria, llamada a herramienta,
decisión de autorización y paso de
razonamiento de forma inmutable (solo
escritura, nunca eliminado)
```
```
Traza de Auditoría Inmutable
```
```
Fallos de Coordinación Multi-Agente —
múltiples agentes toman decisiones
contradictorias sin contexto compartido
```
```
Todos los agentes comparten el mismo
grafo Semantic dentro de la
organización. La detección de
contradicciones señala hechos en
conflicto antes de que lleguen a la
síntesis
```
```
Memoria Org. Compartida + Detección
de Contradicciones
```
### 2.2 Qué Ofrece AMG

- Modelo de Memoria Tripartita — Separación estricta de Context (historial de sesión específico del

##### usuario), Semantic (hechos organizacionales duraderos con puntuación bayesiana de confianza) y Audit

##### (registros inmutables de cumplimiento). Cada nivel tiene políticas independientes de retención,

##### mutabilidad y acceso.

- Pipeline de Razonamiento MindMap — Un pipeline determinista de cuatro etapas: Mine → Aggregate →

##### Serialize → Synthesize. Cada respuesta se construye exclusivamente a partir de evidencia recuperada

##### del grafo. Si la evidencia es insuficiente, el sistema lo señala explícitamente — sin alucinación.

- Sistema de Cognitive Weighting — Pesos log-odds bayesianos en cada nodo y arista, decaimiento

##### temporal para hechos obsoletos y condicionamiento de confianza y frescura en la síntesis. Solo los

##### hechos relevantes, recientes y de alta señal llegan a la ventana de contexto del LLM, reduciendo el

##### costo en tokens y mejorando la precisión.


- Coordinación Multi-Agente — Todos los agentes comparten el mismo grafo de memoria Semantic.

##### Operaciones coordinadas y no redundantes. La detección de contradicciones expone hechos en

##### conflicto antes de que influyan en una respuesta.

- Traza de Auditoría Inmutable — Cada acceso, llamada a herramienta y paso de razonamiento en el

##### nivel Audit (solo escritura) para completa trazabilidad de cumplimiento y forense de incidentes.

- Gobernanza ABAC — Controles de autorización de grano fino que delimitan qué agentes pueden

##### acceder a qué subgrafos, conjuntos de nodos y niveles. Denegación por defecto con códigos de razón

##### auditados.

- Pipeline de Extracción de Documentos — Ingesta PDFs y archivos PowerPoint, extrae entidades,

##### deduplica y puebla el grafo Semantic automáticamente, convirtiendo documentos institucionales en

##### memoria organizacional consultable.

## 3. Descripción de la Arquitectura

##### AMG es un servicio Python nativo en GCP construido sobre FastAPI, desplegado en Cloud Run, respaldado

##### por Google Cloud Spanner Graph para el almacén de memoria. Todos los componentes están

##### contenerizados y gestionados mediante infraestructura como código Terraform. El sistema se despliega

##### como un servicio dedicado de organización única dentro del proyecto GCP del cliente — ningún dato

##### abandona el entorno del cliente.

### 3.1 Niveles de Memoria

##### AMG divide todo el conocimiento en tres niveles estrictamente aislados con diferentes políticas de retención,

##### reglas de mutabilidad y controles de acceso. El diseño refleja la arquitectura de la memoria humana:

##### memoria de trabajo (Context), memoria a largo plazo (Semantic) y registro autobiográfico (Audit).

###### Nivel Alcance y

###### Propietario

###### Qué Almacena Actualizado Por Ciclo de Vida

```
CONTEXT Por usuario / por
sesión
```
```
Turnos de conversació
n específicos del
usuario, respuestas
del agente, estado de
sesión, razonamiento
intermedio. Limitado
estrictamente a una
sesión y un usuario —
sin intercambio entre
usuarios.
```
```
Cada mensaje enviado
o recibido, eventos de
inicio/fin de sesión,
llamadas a herramienta
s del agente durante
un turno.
```
```
24–48 horas (decaimie
nto bayesiano rápido
en sesiones inactivas)
```

###### Nivel Alcance y

###### Propietario

###### Qué Almacena Actualizado Por Ciclo de Vida

```
SEMANTIC A nivel de organización Hechos duraderos,
relaciones entre
entidades, insights
descubiertos,
conocimiento de
documentos ingestado
s. Compartido entre
todos los agentes de
la organización dentro
del alcance de la
política ABAC.
```
```
Adición de hechos por
agentes, pipeline de
extracción de
documentos, ingestión
desde DataHub,
inserciones manuales
de conocimiento vía
API.
```
```
Meses a años
(decaimiento lento;
refuerzo bayesiano en
accesos repetidos)
```
```
AUDIT Permanente /
cumplimiento
```
```
Cada acceso a
memoria, llamada a
herramienta,
concesión/denegación
de autorización, paso
de razonamiento y
traza de orquestación.
Indexado con códigos
de razón.
```
```
Solo escritura —
escrito por cada
operación en todos los
niveles. Nunca
modificado ni
eliminado.
```
```
Retención permanente
```
###### Nota de privacidad: El nivel Context es el lugar adecuado para cualquier dato identificable del usuario en

###### interacciones de agentes (IDs de pasajeros, IDs de empleados, contenido de sesión). Su decaimiento de

###### 24-48h y el alcance estricto por sesión significan que los datos personales no se persisten indefinidamente —

###### alineado con los principios de minimización de datos.

### 3.2 Pipeline de Razonamiento MindMap

##### El pipeline MindMap es el motor de razonamiento central de AMG. Está inspirado en el artículo de

##### investigación "MindMap: Knowledge Graph Prompting Sparks Graph of Thoughts in Large Language

##### Models" (Wen, Wang y Sun, ACL 2024 — github.com/wyl-willing/MindMap), que demostró que los LLMs

##### fundamentados en evidencia de grafos de conocimiento producen respuestas estructuralmente coherentes y

##### respaldadas por evidencia de manera mucho más confiable que la generación libre o el RAG ingenuo. AMG

##### adapta estas ideas en un pipeline determinista, seguro para empresas y listo para producción.

##### El pipeline impone una disciplina estricta de evidencia: ningún LLM genera respuestas directamente a partir

##### de la entrada del usuario. Cada respuesta pasa por cuatro etapas deterministas:

###### Etapa Qué Hace Salida

1. Mine Extrae intención estructurada y
    entidades nombradas de la solicitud del
    agente. Identifica anclas de consulta
    para el traversal del grafo.

```
Lista de entidades + clasificación de
intención
```

###### Etapa Qué Hace Salida

2. Aggregate Recorre el Spanner Graph desde las
    anclas identificadas. La profundidad
    acotada del traversal y los umbrales de
    cognitive weight filtran caminos
    obsoletos o de baja confianza. Solo se
    accede a los subgrafos permitidos por
    ABAC.

```
Conjunto de caminos de evidencia
(resultados de traversal tipado)
```
3. Serialize Convierte caminos y aristas del grafo en
    payloads de hechos canónicos y
    trazables. Cada hecho recibe un ID
    único para su citación en la respuesta
    final. La procedencia (nodo fuente, tipo
    de arista, puntuación de confianza) se
    preserva.

```
Payload de hechos serializados con IDs
de hechos
```
4. Synthesize Genera la respuesta del agente
    ÚNICAMENTE a partir del payload de
    hechos serializados usando el LLM
    configurado (Cosmos GenAI Gateway).
    Se verifican las compuertas de frescura
    y confianza antes de la síntesis. Si no
    existen hechos o la confianza está por
    debajo del umbral, retorna una señal
    explícita de insuficiencia — nunca
    supone.

```
Respuesta fundamentada o insuficiencia
explícita
```
###### Validación de fundamentación: tras la síntesis, AMG verifica que cada afirmación en la respuesta referencie

###### un ID de hecho presente en la evidencia serializada. Cualquier afirmación que referencie un ID de hecho

###### desconocido provoca que la respuesta falle de forma segura — una garantía sólida contra la alucinación.

### 3.3 Sistema de Cognitive Weighting

##### El sistema de Cognitive Weighting le da a AMG su capacidad de ofrecer recuperación de alta precisión a

##### bajo costo en tokens. Está inspirado en Engram — una infraestructura de memoria demostrable de código

##### abierto para agentes IA (github.com/Harshitk-cp/engram) que alcanza el 91.4% en LongMemEval, el

##### benchmark de ICLR 2025 para memoria conversacional a largo plazo. AMG adapta la intuición central de

##### Engram — que los recuerdos deben ganar confianza cuando son reforzados, perderla cuando son

##### contradichos y desvanecerse cuando no se usan — en un modelo de pesos log-odds bayesiano nativo al

##### modelo de datos de Spanner Graph.

##### Cada nodo y arista en el grafo de memoria lleva un LogOddsWeight:

###### Mecanismo Fórmula / Regla Efecto

```
Peso inicial LogOddsWeight = 0.5 (62% de confianza
base)
```
```
Los nuevos hechos entran con confianza
moderada — no se asume que son
completamente confiables.
```

###### Mecanismo Fórmula / Regla Efecto

```
Refuerzo bayesiano Weight += ln(1.25) ≈ +0.22 bits por
acceso exitoso
```
```
Los hechos recuperados frecuentemente
ganan confianza automáticamente. El
conocimiento de alta señal sube al tope
de los resultados de traversal.
```
```
Decaimiento temporal Weight(t) = Weight(0) × e^(−0.05 ×
horas_desde_acceso)
```
```
Los hechos no utilizados se desvanecen.
Un hecho con peso 2.73 tras uso intenso
decae a casi cero después de una
semana sin acceso — imitando el olvido.
```
```
Umbral de poda Weight < 0.30 → eliminación suave del
traversal activo
```
```
Los hechos obsoletos de baja confianza
dejan de contaminar los resultados de
recuperación sin una eliminación física
definitiva.
```
```
Detección de contradicciones En la ingestión, los hechos conflictivos
se señalan con un marcador de tensión
```
```
La síntesis es condicional: los hechos
contradictorios se presentan como
ambiguos, no como autoritativos.
```
```
Compuerta de frescura La síntesis verifica la frescura promedio
del conjunto de evidencia contra el
umbral de frescura configurado
```
```
Las respuestas señalan explícitamente
cuando la evidencia es obsoleta —
previniendo respuestas sobreconfiadas
basadas en conocimiento desactualizado.
```
##### El impacto directo en el negocio de este sistema: en lugar de enviar cientos de fragmentos RAG débilmente

##### relevantes al LLM, AMG envía únicamente los hechos de alta confianza, frescos y ponderados que pasaron

##### todos los filtros. Esto acota la ventana de contexto de síntesis, reduce el consumo de tokens LLM por turno

##### del agente y eleva la precisión de las respuestas — las dos palancas más importantes de costo y calidad

##### para la IA empresarial a escala.

### 3.4 Endpoints Principales de la API

###### Endpoint Método Propósito

```
/health GET Sonda de disponibilidad y preparación
para verificaciones de salud en Cloud
Run
```
```
/api/v1/agent/respond POST Turno completo del agente con múltiples
herramientas: orquesta recuperación de
memoria, búsqueda en grafo, síntesis de
evidencia y registro de trazas en una
sola solicitud
```
```
/api/v1/mindmap/execute POST Ejecución directa del pipeline MindMap
— Mine → Aggregate → Serialize →
Synthesize
```
```
/api/v1/mcp/invoke POST Invocación de herramientas MCP:
memory_search, memory_add_fact,
memory_recall_context,
memory_log_trace. Compatible con
Claude Code, Codeen y el registro MCP
del Cosmos GenAI Hub.
```

###### Endpoint Método Propósito

```
/internal/decay-weights POST Decaimiento programado de pesos
cognitivos — reduce pesos de
nodos/aristas inactivos
```
```
/internal/prune-weights POST Elimina evidencia de baja confianza con
eliminación suave del nivel Semantic
```
### 3.5 Stack Tecnológico

###### Componente Tecnología Notas

```
Runtime Python 3.14 / FastAPI Verificación estricta de tipos
(basedpyright, 0 errores, 0 advertencias)
```
```
Almacén de Memoria Google Cloud Spanner Graph Consultas ISO GQL, almacenamiento de
aristas intercalado para traversal rápido
```
```
Despliegue Cloud Run (contenerizado) IaC con Terraform, estrategia de 3
entornos (dev/intg/prod)
```
```
Observabilidad GCP Logging + Tracing + Metrics Logs JSON estructurados, trazas
OpenTelemetry, Cloud Monitoring
```
```
Autenticación y Gobernanza ABAC Interno o Delegación Externa Conectable: Okta, Auth0, Plataforma de
Derechos o política interna
```
```
Backend LLM Cosmos GenAI Gateway Llama claude-sonnet-4-6,
claude-opus-4-8, gemini-2.5-pro, gpt-
según configuración
```
```
CI/CD GitLab CI / Cloud Build Pre-commit hooks, linting ruff,
basedpyright, pytest — requeridos antes
del merge
```
```
Pruebas pytest — 843 pruebas, 100% pasando Unitarias + Integración + Aislamiento
cross-tenant + Escenarios de caos
```
```
Ingestión de Docs Pipeline de extracción PDF/PPTX Deduplicación difusa de entidades,
puntuación de confianza, desplegado en
Cloud Run
```
### 3.6 Modelo de Despliegue

##### AMG se despliega como un servicio dedicado de organización única dentro de la organización GCP del

##### cliente. Todos los agentes de la organización comparten memoria dentro del mismo contexto de

##### company_id. No hay multi-tenencia — los datos nunca se filtran entre organizaciones. El despliegue sigue

##### una estrategia de tres entornos gestionados mediante workspaces de Terraform:

- Desarrollo — Pruebas de integración de agentes, conexión MCP, validación de esquema, incorporación

##### del primer squad.

- Integración (INTG) — Ingeniería de caos, pruebas de carga (objetivo: 7.500+ req/seg), validación de

##### aislamiento cross-tenant, revisión de documentación de cumplimiento.


- Producción — Despliegue canario (5% del tráfico) → monitoreo 24h → tráfico completo. Tiempo de

##### rollback: < 5 minutos a la versión anterior.

###### Modo de Gobernanza Descripción Cuándo Usar

```
ABAC Interno (por defecto) Políticas de autorización almacenadas
en Spanner. Gestionado por LATAM. Sin
dependencias externas.
```
```
Recomendado para el despliegue inicial
y la mayoría de casos de uso
```
```
Delegación Externa Las decisiones de autorización se
delegan a un servicio de política externo
mediante POST /authorize. Respuesta:
permitir/denegar con código de razón.
```
```
Cuando LATAM desea sincronizar los
permisos de AMG con una plataforma de
identidad existente (ej. un servicio
centralizado de derechos)
```
## 4. Valor Estratégico para LATAM Airlines

##### LATAM Airlines ya ha invertido significativamente en una plataforma moderna de IA y datos: el Cosmos

##### GenAI Gateway (accediendo a Claude, GPT-5, Gemini y modelos Llama), DataHub para gobernanza de

##### datos empresariales a través de dominios (CUSTOMER, MAINTENANCE, REFERENCE DATA, DATA

##### INSIGHTS), Backstage para el catálogo de servicios y el Cosmos Feedback Engine para la mejora de la

##### calidad de los chatbots. Agent Memory Graph es la capa de coordinación persistente que hace que estas

##### inversiones se potencien: cada agente mejora la memoria compartida; cada squad se beneficia de lo que

##### otros han aprendido.

### 4.1 El Ecosistema GenAI de LATAM Hoy

##### A través del Cosmos GenAI Gateway, LATAM opera una flota diversa de modelos servida desde Vertex AI y

##### OpenAI: Claude Opus 4.8, Claude Sonnet 4.6, GPT-5, Gemini 3.1 Pro, Llama 4 Scout y más — con

##### seguimiento de costo por usuario y controles de presupuesto. LATAM también ejecuta el Cosmos Feedback

##### Engine, un sistema de mejora de calidad de chatbots de cuatro módulos (pipeline Dataflow, UI de revisión

##### experta, gestor Cloud Run, liquidador diario) que ya enriquece las respuestas de chatbots con conocimiento

##### validado por humanos. La plataforma demuestra una madurez de IA considerable.

##### Sin embargo, estos modelos son sin estado: cada llamada comienza desde cero, sin contexto compartido

##### entre agentes, squads o sesiones. AMG aborda directamente esta brecha — es la capa de memoria

##### persistente y compartida que transforma llamadas aisladas a modelos en flujos de trabajo de agentes

##### coordinados, contextualizados y auditables.

### 4.2 Chatbots para Personal de LATAM y Clientes

##### Una de las aplicaciones de mayor impacto de AMG en LATAM es como columna vertebral de memoria para

##### chatbots y asistentes IA que interactúan con dos audiencias distintas: el personal interno de LATAM y los

##### pasajeros externos. Ambos segmentos tienen iniciativas de IA activas y problemas de memoria no resueltos.

### 4.2.1 Chatbots para Personal Interno

##### Los equipos ADO de LATAM, tripulaciones de operaciones, ingenieros de mantenimiento y agentes de

##### contact center interactúan cada vez más con copilotos IA para búsqueda de conocimiento, guía de procesos


##### y apoyo a la toma de decisiones. Sin memoria persistente, estos agentes se reinician en cada sesión —

##### obligando a los empleados a re-proveer contexto, re-explicar problemas en curso y redescubrir soluciones

##### que otros agentes ya encontraron.

- Mantenimiento (MAPIS) — Los técnicos que consultan la base de conocimiento MAPIS (ya catalogada

##### en BigQuery: emx-data-prod-e6c5.raw_emx_mapis_rag.mapis_knowledge_jan_26) se benefician de un

##### copiloto IA que recuerda diagnósticos previos, sabe qué soluciones se aplicaron a fallos similares y cita

##### sus fuentes para trazabilidad de seguridad crítica.

- Copilotos de Operaciones — Los agentes de gestión de disrupciones comparten un grafo Semantic

##### común para que el hallazgo de un agente sobre la causa de un retraso informe inmediatamente a todos

##### los demás agentes coordinadores — sin consultas redundantes ni decisiones contradictorias.

- Asistentes de Gobernanza de Datos — Los ingenieros ADO que interactúan con DataHub para revisión

##### de propiedad de datasets, linaje y gestión de solicitudes de acceso obtienen un asistente con memoria

##### que retiene el contexto del proyecto a través de semanas de trabajo sin necesidad de re-prompts.

- Copilotos de Ingeniería ADO — Los ingenieros incorporándose a nuevos datasets o pipelines obtienen

##### un copiloto que recuerda qué han explorado, qué decisiones se tomaron y qué patrones existen —

##### reduciendo significativamente el tiempo de incorporación.

### 4.2.2 Chatbots Orientados a Pasajeros

##### El dominio de experiencia del cliente de LATAM es uno de los más ricos en datos de la organización:

##### encuestas NPS (digital, contact center y a bordo), tablas de voz del cliente e historiales de interacción ya

##### están catalogados en DataHub bajo el dominio CUSTOMER (cus-data-prod.customer_experience.*). Estos

##### datasets representan miles de interacciones diarias de pasajeros — una fuente valiosa para fundamentar la

##### IA orientada a pasajeros.

##### AMG habilita una clase cualitativamente diferente de chatbot para pasajeros:

- Continuidad de sesión — Un pasajero que inicia una consulta de reserva, se desconecta y regresa

##### horas después encuentra al agente aún con conocimiento de su itinerario, preferencias y pasos previos

##### — no una pizarra en blanco que requiere re-explicación.

- Consistencia entre canales — Un pasajero que llamó al contact center ayer y ahora chatea en la app

##### encuentra el mismo contexto. El nivel Semantic compartido (con alcance por entidad de pasajero)

##### conecta canales sin requerir una consulta al CRM en cada turno.

- Respuestas fundamentadas y confiables — Las reglas tarifarias, políticas de equipaje y estados de

##### vuelo se recuperan de evidencia fundamentada en el grafo — sin alucinaciones a partir de datos de

##### entrenamiento que pueden estar desactualizados meses.

- Traza de auditoría lista para cumplimiento — Cada interacción de pasajero se registra en el nivel Audit.

##### Para quejas reguladas, solicitudes de acceso de sujetos de datos o investigaciones de calidad, LATAM

##### dispone de una traza de razonamiento completa e inmutable para cada decisión del chatbot.

- Integración de señal NPS — Las tablas NPS y de voz del cliente de DataHub pueden alimentar el nivel

##### Semantic: los agentes que saben que un pasajero tuvo una mala experiencia reciente pueden adaptar

##### su tono y umbral de escalación — una capa de personalización fundamentada en datos de

##### comportamiento real.


###### Sinergia con el Cosmos Feedback Engine: el nivel Semantic de AMG es el almacén ideal a largo plazo para

###### los pares P/R validados que el Feedback Engine produce diariamente. En lugar de solo actualizar una base de

###### datos vectorial en Cloud SQL, las respuestas validadas pueden ingestarse en el grafo Semantic de AMG —

###### haciéndolas disponibles para todos los agentes a nivel organizacional, no solo para el chatbot para el que se

###### construyó el Feedback Engine.

### 4.3 Casos de Uso de Alto Impacto en los Dominios de LATAM

###### Dominio Caso de Uso Capacidad AMG Utilizada Impacto en el Negocio

```
Experiencia del Cliente Chatbot multi-sesión para
pasajeros con contexto
persistente a través de app,
web y canales de contact
center
```
```
Nivel Context (por pasajero),
hechos Semantic entre
canales, ingestión de datos
NPS
```
```
Menor tiempo de atención,
mayor resolución en el primer
contacto, UX consistente
entre canales
```
```
Gestión de Ingresos Agentes que consultan reglas
tarifarias, datos de mercado y
política de precios sin
reingestar conocimiento en
cada llamada
```
```
Nivel Semantic,
fundamentación MindMap,
priorización por cognitive
weight
```
```
Ciclos de análisis más
rápidos, cero reglas tarifarias
alucinadas en decisiones
automatizadas
```
```
Mantenimiento (MRO) Copiloto IA para técnicos que
acceden al conocimiento
MAPIS con trazabilidad de
seguridad crítica para cada
recomendación
```
```
Pipeline de extracción de
documentos (PDFs MAPIS),
nivel Audit, validación de
fundamentación
```
```
Recomendaciones IA listas
para cumplimiento con traza
de auditoría completa
```
```
Gobernanza de Datos Asistente integrado con
DataHub con contexto
persistente sobre propiedad
de datasets, linaje, historial
de acceso y estado de
gobernanza
```
```
Nivel Semantic (entidades
DataHub), gobernanza
ABAC, nivel Audit
```
```
Gestión de gobernanza
automatizada con plena
auditabilidad
```
```
Operaciones Coordinación multi-agente
para gestión de disrupciones
— ningún agente actúa sobre
información obsoleta o
contradictoria
```
```
Grafo Semantic compartido,
detección de contradicciones,
contexto entre agentes
```
```
Decisiones operativas
consistentes y no
redundantes a escala
```
```
Copilotos Internos (ADO) Asistentes IA para ingenieros
y data scientists que
recuerdan el contexto del
proyecto, decisiones
arquitectónicas y análisis
previos a través de semanas
```
```
Niveles Context + Semantic,
integración MCP con Claude
Code / Codeen
```
```
Incorporación más rápida,
eliminación de la sobrecarga
de re-explicación de contexto
```
### 4.4 Alineación con la Infraestructura Existente de LATAM

- Nativo en GCP — Se despliega en la organización GCP de LATAM con los patrones de Cloud Run +

##### Spanner + IAM ya establecidos en la plataforma Cosmos.


- Integración con Cosmos GenAI Gateway — La etapa Synthesize de AMG llama al GenAI Gateway

##### como backend LLM. El acceso existente de LATAM a Claude/GPT/Gemini, el seguimiento de costos y

##### los límites de tasa aplican.

- Soporte del Protocolo MCP — AMG expone una interfaz de herramientas compatible con MCP,

##### compatible con Claude Code, Codeen y el registro MCP del Cosmos GenAI Hub. Regístrelo como

##### Servidor MCP interno y todos los equipos de LATAM pueden descubrirlo y usarlo desde el catálogo

##### Hub.

- Integración con DataHub — El pipeline de extracción de AMG puede ingestar activos catalogados en

##### DataHub, enriqueciendo el nivel Semantic con metadatos de propiedad, linaje y calidad de datasets.

- Catálogo Backstage — AMG incluye un catalog-info.yaml que lo hace inmediatamente registrable como

##### componente Backstage en el catálogo de servicios Cosmos.

- Cosmos Feedback Engine — Los pares P/R validados del Feedback Engine pueden fluir hacia el nivel

##### Semantic de AMG, haciendo el conocimiento validado por expertos disponible para todos los agentes.

### 4.5 El Efecto Multiplicador Organizacional

##### El valor compuesto de AMG crece a medida que más agentes y squads lo adoptan. Hoy cada iniciativa de IA

##### en LATAM opera de forma aislada — un chatbot de mantenimiento no sabe nada de lo que un agente de

##### ingresos descubrió la semana pasada. AMG crea un grafo de conocimiento organizacional compartido

##### donde los hallazgos de cada agente enriquecen el corpus para todos los agentes futuros. El cognitive

##### weighting asegura que los hechos más frecuentemente útiles asciendan automáticamente al tope, mientras

##### que el conocimiento no utilizado o contradicho decae — de modo que la memoria compartida se

##### auto-mantiene sin curación manual.

###### Alineación con cumplimiento normativo: LATAM opera en entornos regulados — seguridad aérea, reportes

###### financieros, protección de datos de pasajeros. El nivel AUDIT inmutable de AMG y los controles ABAC

###### proveen la trazabilidad y gobernanza de acceso requeridas para el uso de IA en decisiones de seguridad

###### crítica y sensibles al cumplimiento. Ningún stack simple de RAG o chat sin estado provee esto.

## 5. Plan de Desarrollo y Despliegue para LATAM

##### AMG v0.2 está listo para producción. El plan de despliegue para LATAM se centra en integración, adopción

##### y escalado — no en construir desde cero. El siguiente plan se estructura en cuatro fases a lo largo de

##### aproximadamente 16 semanas.

### 5.1 Equipo Requerido

###### Rol Cantidad Responsabilidad Fuente Sugerida

```
Ingeniero de Plataforma
(GCP)
```
```
1 FTE Terraform, Cloud Run,
Spanner, IAM, CI/CD,
monitoreo
```
```
Cosmos Platform Engineering
```

###### Rol Cantidad Responsabilidad Fuente Sugerida

```
Ingeniero Backend (Python) 1–2 FTE Integración de API, conexión
con GenAI Gateway,
conector Feedback Engine,
adaptadores del pipeline de
extracción
```
```
Squad GenAI (GENAI) o
capítulo ADO
```
```
Ingeniero de Datos / IA 1 FTE Diseño de esquema de
entidades, estrategia de
población del grafo Semantic,
conectores DataHub y MAPIS
```
```
Capítulo Data & AI (cualquier
squad)
```
```
Seguridad / Gobernanza 0.5 FTE Diseño de políticas ABAC,
auditoría IAM, documentación
de cumplimiento,
confirmación de residencia de
datos
```
```
Seguridad de la Información /
Habilitadores de Gobernanza
ADO
```
```
Product Manager / Líder 0.5 FTE Coordinación del squad
piloto, seguimiento de KPIs,
alineación con stakeholders,
requisitos del chatbot de
clientes
```
```
Líder de Capítulo (squad
GENAI o jefe de capítulo
ADO)
```
```
QA / Integración 0.5 FTE Pruebas end-to-end,
ingeniería de caos, validación
de aislamiento cross-tenant
```
```
Dentro de cualquiera de los
squads anteriores
```
##### Total: aproximadamente 4.5–5.5 FTE a lo largo de 16 semanas. Un piloto reducido (1 caso de uso, 1 squad)

##### puede comenzar con 3 FTE en la Fase 1.

### 5.2 Presupuesto Estimado

###### Categoría Ítem Est. Mensual (USD) Notas

```
Infraestructura Cloud Run (2 instancias,
autoescalado)
```
```
$150–400/mes Escala con el volumen de
solicitudes
```
```
Infraestructura Cloud Spanner (1 nodo, ~10k
RU/día)
```
```
$365/mes Escala horizontalmente; 1
nodo maneja cientos de
req/seg
```
```
Infraestructura Cloud Build / pipeline CI $50–100/mes Según la frecuencia de builds
```
```
Infraestructura GCP Logging + Monitoring +
Tracing
```
```
$50–200/mes Depende del volumen de logs
y la retención
```
```
Inferencia LLM Cosmos GenAI Gateway
(etapa Synthesis)
```
```
Presupuesto existente Claude Sonnet 4.6:
~$0.003/1k tokens de entrada
vía gateway
```
```
Ingeniería Equipo de plataforma (4.
FTE × 16 semanas)
```
```
Único ~$120–180k Aprovecha ingenieros
internos; sin licencias de
vendor
```

###### Categoría Ítem Est. Mensual (USD) Notas

```
TOTAL INFRAESTRUCTURA
(mensual, estado estable
post go-live)
```
```
~$615–1.100/mes
```
###### Nota de costos: A escala piloto (< 1k req/día), una instancia fraccionada de Spanner reduce la infraestructura

###### a ~$100–200/mes. El Cognitive Weighting acota el contexto LLM por solicitud, manteniendo el costo de

###### inferencia predecible a escala.

### 5.3 Fases y Cronograma

### Fase 1 — Fundación y Piloto (Semanas 1–4)

##### Objetivo: Desplegar AMG en el entorno dev de GCP de LATAM y validar el pipeline central de memoria con

##### un caso de uso real (recomendado: chatbot de mantenimiento MAPIS o asistente de gobernanza DataHub).

###### Semana Actividad Responsable Entregable

```
1 Configuración GCP: Spanner,
Cloud Run, IAM, workspaces
Terraform, alertas de
monitoreo
```
```
Ingeniero de Plataforma Entorno dev en funcionamient
o
```
```
1–2 Conexión del Cosmos GenAI
Gateway a la etapa
Synthesize de AMG; prueba
de humo de respuesta
fundamentada end-to-end
```
```
Ingeniero Backend Pipeline completo retornando
respuesta fundamentada
```
```
2 Registro catalog-info.yaml en
Backstage; registro MCP en
GenAI Hub
```
```
Ingeniero de Plataforma AMG visible en Cosmos
Backstage + descubrible
desde Claude Code / Codeen
```
```
2–3 Incorporación del primer
squad piloto — squad GenAI
con un caso de uso; 50+
interacciones de agentes en
dev
```
```
Product Lead + Backend Piloto validado en dev
```
```
4 Revisión Fase 1: calidad de
fundamentación, latencia
P99, costo en tokens vs.
línea base
```
```
Todos Decisión Go/No-Go para
Fase 2
```
### Fase 2 — Integración y Enriquecimiento de Datos (Semanas 5–9)

##### Objetivo: Enriquecer el grafo Semantic con datos organizacionales de LATAM, integrar DataHub y el

##### Feedback Engine, y expandir a 2–3 squads piloto incluyendo un chatbot orientado a pasajeros.


###### Semana Actividad Responsable Entregable

```
5–6 Conector DataHub: ingestar
metadatos de datasets,
propiedad y linaje en el nivel
Semantic
```
```
Ingeniero de Datos/IA Entidades DataHub
consultables desde AMG
```
```
6–7 Pipeline de extracción de
documentos para MAPIS y
bases de conocimiento
internas de LATAM
```
```
Backend + Ingeniero de Datos Primer corpus de
conocimiento ingestado y
ponderado
```
```
7 Conector Cosmos Feedback
Engine: pares P/R validados
fluyen al nivel Semantic
```
```
Ingeniero Backend Conocimiento del Feedback
Engine disponible para todos
los agentes
```
```
7–8 Diseño de políticas ABAC
alineado con el modelo
IAM/identidad de LATAM
```
```
Seguridad / Gobernanza Documento de política de
autorización aprobado
```
```
8–9 Expansión a 2–3 squads:
piloto de chatbot de
experiencia del cliente + un
squad interno
```
```
Product Lead Piloto multi-squad en vivo con
caso de uso orientado a
pasajeros
```
```
9 Revisión Fase 2: cobertura
de datos, cumplimiento de
autorizaciones, coordinación
entre squads
```
```
Todos Aprobación para Fase 3
```
### Fase 3 — Hardening y Producción (Semanas 10–14)

##### Objetivo: Desplegar en INTG y PROD, completar la documentación de cumplimiento y certificar para casos

##### de uso de seguridad crítica y regulados.

###### Semana Actividad Responsable Entregable

```
10–11 Despliegue INTG: ingeniería
de caos, pruebas de carga
(7.500+ req/seg), validación
de aislamiento cross-tenant,
prueba de integración de
datos NPS
```
```
Plataforma + QA Entorno INTG validado
```
```
11–12 Documentación de
cumplimiento: revisión de
traza de auditoría, auditoría
de políticas ABAC,
confirmación de residencia de
datos de pasajeros,
verificación de alineación
GDPR/PDPA
```
```
Seguridad / Gobernanza Documento de aprobación de
cumplimiento
```
```
12–13 Despliegue canario en PROD
(5% del tráfico) → monitoreo
24h → tráfico completo
```
```
Ingeniero de Plataforma Entorno PROD en
funcionamiento
```

###### Semana Actividad Responsable Entregable

```
13–14 Runbook, procedimientos de
escalación, configuración
on-call, dashboard de SLO
en Cloud Monitoring
```
```
Plataforma + Producto Runbook operativo publicado
```
```
14 Revisión Fase 3:
disponibilidad, completitud de
auditoría, calidad del chatbot
de pasajeros
```
```
Todos Aprobación para producción
```
### Fase 4 — Escala y Expansión (Semanas 15–16+)

- Incorporar todos los squads interesados del Capítulo Data & AI con documentación de autoservicio y

##### grafos de conocimiento de dominio pre-cargados (mantenimiento, ingresos, experiencia del cliente).

- Expandir el chatbot de pasajeros a canales adicionales (app, web, contact center) usando el nivel

##### Context + Semantic compartido para continuidad entre canales.

- Evaluar la publicación de AMG como componente reutilizable de la plataforma Cosmos, disponible para

##### todos los squads de productos de LATAM a través del catálogo Backstage.

- Definir el roadmap v0.3: recuperación basada en embeddings, búsqueda vectorial sobre el nivel

##### Semantic, plantillas de flujos de trabajo agénticos y señales de personalización impulsadas por NPS.

### 5.4 Registro de Riesgos

###### Riesgo Probabilidad Impacto Mitigación

```
Demoras en cuota de Cloud
Spanner
```
```
Baja Medio Solicitar aumento de cuota al
inicio de la Fase 1; el
emulador de Spanner está
disponible para desarrollo
local de inmediato
```
```
Requisitos de privacidad de
datos de pasajeros
(GDPR/PDPA)
```
```
Media Alto El nivel Context tiene
decaimiento de 24-48h; sin
PII persistente en el nivel
Semantic por política; los
controles ABAC gestionan el
acceso; revisión legal en
Fase 3
```
```
Complejidad creciente de
políticas ABAC
```
```
Media Bajo Comenzar con denegación
por defecto para todos los
agentes y luego otorgar
acceso de forma incremental
— no al revés. Mantener las
políticas declarativas.
```

###### Riesgo Probabilidad Impacto Mitigación

```
Calidad de datos del grafo
Semantic (basura entra,
basura sale)
```
```
Media Alto Usar puntuaciones de calidad
de DataHub para condicionar
la ingestión; el pipeline de
extracción incluye
deduplicación difusa y
puntuación de confianza
```
```
Sobrecosto LLM a escala del
chatbot de pasajeros
```
```
Baja Medio El cognitive weighting acota
el contexto por solicitud; el
Cosmos Gateway provee
seguimiento de presupuesto
por usuario y límites estrictos
```
```
Disponibilidad del equipo
(equipo reducido)
```
```
Alta Medio La Fase 1 puede ejecutarse
con 3 FTE; AMG ya está
construido — no se necesita
I+D central. Acotar el alcance
del piloto antes de escalar el
equipo
```
## 6. Métricas de Éxito

###### Métrica Objetivo Medición

```
Tasa de Fundamentación 100% de respuestas respaldadas por
evidencia o insuficiencia explícita
```
```
Nivel Audit: flag de fundamentación por
respuesta
```
```
Tasa de Alucinación 0% (ninguna afirmación no respaldada
pasa la compuerta de validación de
fundamentación)
```
```
Verificación automática de
fundamentación en etapa de síntesis +
revisión de auditoría selectiva
```
```
Reducción de Costo en Tokens >30% de reducción vs. RAG de línea
base por turno del agente
```
```
Logs de tokens por turno del Cosmos
Gateway antes vs. después de adopción
de AMG
```
```
Latencia P99 < 50ms end-to-end (línea base medida
actual: < 5ms)
```
```
Métricas de percentil de Cloud Monitoring
```
```
Disponibilidad 99.9% de uptime Verificaciones de salud Cloud Run +
alerta de uptime en Cloud Monitoring
```
```
Cobertura de Auditoría 100% de decisiones de autorización
registradas con código de razón
```
```
Consulta al nivel Audit: eventos
concedidos/denegados por día
```
```
Adopción de Agentes 5+ squads de LATAM usando AMG al
final de la Fase 4
```
```
Conteo de invocaciones MCP por squad
vía logs del GenAI Gateway
```
```
Calidad del Chatbot de Pasajeros Mejora de NPS ≥ 5 puntos vs. línea base
de chatbot sin estado
```
```
Tablas NPS de DataHub
(cus-data-prod.customer_experience_ana
lysis.nps_*)
```
```
Costo por Solicitud < $0.01 por turno del agente
(infraestructura + LLM)
```
```
Logs de costos del Gateway + métricas
de uso de Spanner combinados
```

## 7. Recomendación y Próximos Pasos

##### Agent Memory Graph está listo para producción hoy. El enfoque recomendado para LATAM es comenzar

##### con un piloto enfocado de 4 semanas liderado por el squad GenAI en un único caso de uso de alto valor y

##### bien delimitado — ya sea el asistente de conocimiento de mantenimiento MAPIS o el copiloto de

##### gobernanza DataHub. Ambos tienen fuentes de datos claras ya catalogadas, métricas de calidad claras y

##### limitadas implicaciones de privacidad de datos de pasajeros, haciéndolos ideales para una primera

##### validación antes de expandirse a chatbots orientados a clientes externos.

- Semana 1: El ingeniero de plataforma despliega el entorno dev en GCP; el GenAI Gateway se conecta

##### con AMG.

- Semana 2: El squad GenAI ejecuta las primeras interacciones de agentes a través del pipeline

##### MindMap; se valida la fundamentación y la completitud de la traza de auditoría.

- Semana 3: El stakeholder de seguridad/gobernanza revisa la configuración ABAC y los logs de

##### auditoría.

- Semana 4: Decisión Go/No-Go. Si supera los umbrales → proceder al plan completo de 16 semanas. Si

##### no → identificar la causa raíz e iterar antes de expandir.

##### El caso de uso del chatbot orientado a pasajeros — la aplicación de mayor escala e impacto — debe entrar

##### al plan en la Fase 2, una vez que el piloto interno haya validado el pipeline central y el modelo de

##### gobernanza. Esta secuencia gestiona el riesgo preservando el cronograma para la entrega de valor

##### orientado al cliente.

###### Punto de contacto sugerido: squad GenAI (Squad Lead: claudio.urbina@latam.com), en coordinación con el

###### Capítulo Data & AI Ops (Chapter Head: grp_llmops_team@latam.com). Para alineación de gobernanza:

###### Habilitadores de Gobernanza ADO (juanjose.gutierrezt@latam.com). Para requisitos del chatbot de pasajeros:

###### Capítulo Data & AI Passenger (ATO-ATW).
