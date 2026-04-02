const estado = {
  token: localStorage.getItem("asisdoc_token") || "",
  docente: JSON.parse(localStorage.getItem("asisdoc_docente") || "null"),
  cursos: [],
  alumnos: [],
  evaluaciones: [],
  entregas: [],
};

const ui = {
  authSeccion: document.getElementById("auth-seccion"),
  appSeccion: document.getElementById("app-seccion"),
  authMensaje: document.getElementById("auth-mensaje"),
  docenteNombre: document.getElementById("docente-nombre"),
  docenteCorreo: document.getElementById("docente-correo"),
  appMensaje: document.getElementById("app-mensaje"),
  listaCursos: document.getElementById("lista-cursos"),
  listaAlumnos: document.getElementById("lista-alumnos"),
  listaEvaluaciones: document.getElementById("lista-evaluaciones"),
  listaEntregas: document.getElementById("lista-entregas"),
  listaNotas: document.getElementById("lista-notas"),
};

const formularios = {
  login: document.getElementById("form-login"),
  registro: document.getElementById("form-registro"),
  curso: document.getElementById("form-curso"),
  alumno: document.getElementById("form-alumno"),
  evaluacion: document.getElementById("form-evaluacion"),
  agenda: document.getElementById("form-agenda"),
  entregaTexto: document.getElementById("form-entrega-texto"),
  entregaFoto: document.getElementById("form-entrega-foto"),
  correccion: document.getElementById("form-correccion"),
  notas: document.getElementById("form-notas"),
};

function limpiarMensajeAuth() {
  ui.authMensaje.textContent = "";
}

function mostrarMensajeAuth(msg, esError = false) {
  ui.authMensaje.textContent = msg;
  ui.authMensaje.className = esError ? "mensaje error" : "mensaje ok";
}

function mostrarMensajeApp(msg, esError = false) {
  ui.appMensaje.textContent = msg;
  ui.appMensaje.className = esError ? "mensaje error" : "mensaje ok";
}

function guardarSesion() {
  if (estado.token) {
    localStorage.setItem("asisdoc_token", estado.token);
  } else {
    localStorage.removeItem("asisdoc_token");
  }

  if (estado.docente) {
    localStorage.setItem("asisdoc_docente", JSON.stringify(estado.docente));
  } else {
    localStorage.removeItem("asisdoc_docente");
  }
}

function construirHeaders(extra = {}) {
  const headers = { ...extra };
  if (estado.token) {
    headers.Authorization = `Bearer ${estado.token}`;
  }
  return headers;
}

async function requestJSON(url, options = {}) {
  const response = await fetch(url, options);
  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }
  if (!response.ok) {
    const detail = data?.detail || "Error inesperado";
    throw new Error(detail);
  }
  return data;
}

function renderizarVista() {
  const logueado = Boolean(estado.token && estado.docente);
  ui.authSeccion.classList.toggle("oculto", logueado);
  ui.appSeccion.classList.toggle("oculto", !logueado);
  if (logueado) {
    ui.docenteNombre.textContent = estado.docente.full_name;
    ui.docenteCorreo.textContent = estado.docente.email;
  }
}

function poblarSelects() {
  const selectsCurso = [
    "alumno-curso-id",
    "evaluacion-curso-id",
    "filtro-curso-evaluaciones",
  ]
    .map((id) => document.getElementById(id))
    .filter(Boolean);

  for (const select of selectsCurso) {
    const valorActual = select.value;
    select.innerHTML = `<option value="">Seleccionar curso</option>`;
    for (const curso of estado.cursos) {
      const option = document.createElement("option");
      option.value = String(curso.id);
      option.textContent = `${curso.id} - ${curso.name}`;
      select.appendChild(option);
    }
    if ([...select.options].some((o) => o.value === valorActual)) {
      select.value = valorActual;
    }
  }

  const selectsAlumno = ["entrega-alumno-id", "entrega-foto-alumno-id", "notas-alumno-id"]
    .map((id) => document.getElementById(id))
    .filter(Boolean);
  for (const select of selectsAlumno) {
    const valorActual = select.value;
    select.innerHTML = `<option value="">Seleccionar alumno</option>`;
    for (const alumno of estado.alumnos) {
      const option = document.createElement("option");
      option.value = String(alumno.id);
      option.textContent = `${alumno.id} - ${alumno.full_name}`;
      select.appendChild(option);
    }
    if ([...select.options].some((o) => o.value === valorActual)) {
      select.value = valorActual;
    }
  }

  const selectsEvaluacion = [
    "agenda-evaluacion-id",
    "entrega-evaluacion-id",
    "entrega-foto-evaluacion-id",
  ]
    .map((id) => document.getElementById(id))
    .filter(Boolean);
  for (const select of selectsEvaluacion) {
    const valorActual = select.value;
    select.innerHTML = `<option value="">Seleccionar evaluación</option>`;
    for (const evaluacion of estado.evaluaciones) {
      const option = document.createElement("option");
      option.value = String(evaluacion.id);
      option.textContent = `${evaluacion.id} - ${evaluacion.title}`;
      select.appendChild(option);
    }
    if ([...select.options].some((o) => o.value === valorActual)) {
      select.value = valorActual;
    }
  }

  const selectEntrega = document.getElementById("correccion-entrega-id");
  if (selectEntrega) {
    const valorActual = selectEntrega.value;
    selectEntrega.innerHTML = `<option value="">Seleccionar entrega</option>`;
    for (const entrega of estado.entregas) {
      const option = document.createElement("option");
      option.value = String(entrega.id);
      option.textContent = `${entrega.id} - Alumno ${entrega.student_id} / Eval ${entrega.evaluation_id}`;
      selectEntrega.appendChild(option);
    }
    if ([...selectEntrega.options].some((o) => o.value === valorActual)) {
      selectEntrega.value = valorActual;
    }
  }
}

function renderizarListas() {
  ui.listaCursos.innerHTML = estado.cursos.length
    ? estado.cursos
        .map(
          (c) =>
            `<li><strong>${c.name}</strong> <span class="muted">(${c.description || "sin descripción"})</span></li>`
        )
        .join("")
    : "<li>No hay cursos cargados.</li>";

  ui.listaAlumnos.innerHTML = estado.alumnos.length
    ? estado.alumnos
        .map(
          (a) =>
            `<li><strong>${a.full_name}</strong> <span class="muted">(curso ${a.course_id})</span></li>`
        )
        .join("")
    : "<li>No hay alumnos cargados.</li>";

  ui.listaEvaluaciones.innerHTML = estado.evaluaciones.length
    ? estado.evaluaciones
        .map(
          (e) =>
            `<li>
              <strong>${e.title}</strong>
              <span class="muted">(tipo: ${e.evaluation_type}, dificultad: ${e.difficulty})</span>
              <a class="boton secundario boton-link" href="/evaluations/${e.id}/export-docx?school_header=Escuela%20Demo&teacher_name=${encodeURIComponent(
                estado.docente?.full_name || "Docente"
              )}" target="_blank" rel="noreferrer">Descargar Word</a>
            </li>`
        )
        .join("")
    : "<li>No hay evaluaciones cargadas.</li>";

  ui.listaEntregas.innerHTML = estado.entregas.length
    ? estado.entregas
        .map(
          (s) =>
            `<li>
              <strong>Entrega ${s.id}</strong>
              <span class="muted">(alumno ${s.student_id}, evaluación ${s.evaluation_id})</span>
              <div class="muted">${(s.raw_text || "").slice(0, 140) || "sin texto extraído"}</div>
            </li>`
        )
        .join("")
    : "<li>No hay entregas cargadas.</li>";
}

async function cargarCursos() {
  estado.cursos = await requestJSON("/courses", {
    headers: construirHeaders(),
  });
}

async function cargarAlumnos() {
  estado.alumnos = await requestJSON("/students", {
    headers: construirHeaders(),
  });
}

async function cargarEvaluaciones() {
  estado.evaluaciones = await requestJSON("/evaluations", {
    headers: construirHeaders(),
  });
}

async function recargarTodo() {
  if (!estado.token) return;
  try {
    await Promise.all([cargarCursos(), cargarAlumnos(), cargarEvaluaciones()]);
    poblarSelects();
    renderizarListas();
  } catch (error) {
    if (String(error.message).includes("Token")) {
      cerrarSesionLocal();
      mostrarMensajeAuth("La sesión expiró. Iniciá sesión nuevamente.", true);
    } else {
      mostrarMensajeApp(error.message, true);
    }
  }
}

function cerrarSesionLocal() {
  estado.token = "";
  estado.docente = null;
  estado.cursos = [];
  estado.alumnos = [];
  estado.evaluaciones = [];
  estado.entregas = [];
  estado.notas = [];
  guardarSesion();
  renderizarVista();
}

formularios.registro.addEventListener("submit", async (event) => {
  event.preventDefault();
  limpiarMensajeAuth();
  const payload = {
    full_name: document.getElementById("registro-nombre").value.trim(),
    email: document.getElementById("registro-email").value.trim(),
    password: document.getElementById("registro-password").value,
  };
  try {
    await requestJSON("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    mostrarMensajeAuth("Registro exitoso. Ahora podés iniciar sesión.");
    formularios.registro.reset();
  } catch (error) {
    mostrarMensajeAuth(error.message, true);
  }
});

formularios.login.addEventListener("submit", async (event) => {
  event.preventDefault();
  limpiarMensajeAuth();
  const payload = {
    email: document.getElementById("login-email").value.trim(),
    password: document.getElementById("login-password").value,
  };
  try {
    const data = await requestJSON("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    estado.token = data.access_token;
    estado.docente = data.teacher;
    guardarSesion();
    renderizarVista();
    mostrarMensajeApp("Sesión iniciada correctamente.");
    await recargarTodo();
  } catch (error) {
    mostrarMensajeAuth(error.message, true);
  }
});

document.getElementById("btn-logout").addEventListener("click", async () => {
  try {
    await requestJSON("/auth/logout", {
      method: "POST",
      headers: construirHeaders(),
    });
  } catch (error) {
    // Ignorado: igualmente se cierra sesión local.
  } finally {
    cerrarSesionLocal();
    mostrarMensajeAuth("Sesión cerrada.");
  }
});

formularios.curso.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    name: document.getElementById("curso-nombre").value.trim(),
    description: document.getElementById("curso-descripcion").value.trim() || null,
  };
  try {
    await requestJSON("/courses", {
      method: "POST",
      headers: construirHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    mostrarMensajeApp("Curso creado.");
    formularios.curso.reset();
    await recargarTodo();
  } catch (error) {
    mostrarMensajeApp(error.message, true);
  }
});

formularios.alumno.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    full_name: document.getElementById("alumno-nombre").value.trim(),
    course_id: Number(document.getElementById("alumno-curso-id").value),
  };
  try {
    await requestJSON("/students", {
      method: "POST",
      headers: construirHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    mostrarMensajeApp("Alumno registrado.");
    formularios.alumno.reset();
    await recargarTodo();
  } catch (error) {
    mostrarMensajeApp(error.message, true);
  }
});

formularios.evaluacion.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    title: document.getElementById("evaluacion-titulo").value.trim(),
    course_id: Number(document.getElementById("evaluacion-curso-id").value),
    evaluation_type: document.getElementById("evaluacion-tipo").value,
    difficulty: document.getElementById("evaluacion-dificultad").value,
    question_count: Number(document.getElementById("evaluacion-cantidad").value),
    material_text: document.getElementById("evaluacion-material").value.trim() || null,
    use_internal_knowledge: document.getElementById("evaluacion-usar-ia").checked,
  };
  try {
    await requestJSON("/evaluations", {
      method: "POST",
      headers: construirHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    mostrarMensajeApp("Evaluación creada.");
    formularios.evaluacion.reset();
    await recargarTodo();
  } catch (error) {
    mostrarMensajeApp(error.message, true);
  }
});

formularios.agenda.addEventListener("submit", async (event) => {
  event.preventDefault();
  const fecha = document.getElementById("agenda-fecha").value;
  const hora = document.getElementById("agenda-hora").value || "08:00";
  const payload = {
    evaluation_id: Number(document.getElementById("agenda-evaluacion-id").value),
    scheduled_for: `${fecha}T${hora}:00`,
    notes: document.getElementById("agenda-notas").value.trim() || null,
  };
  try {
    await requestJSON("/schedules", {
      method: "POST",
      headers: construirHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    mostrarMensajeApp("Examen programado en agenda.");
    formularios.agenda.reset();
  } catch (error) {
    mostrarMensajeApp(error.message, true);
  }
});

formularios.entregaTexto.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    evaluation_id: Number(document.getElementById("entrega-evaluacion-id").value),
    student_id: Number(document.getElementById("entrega-alumno-id").value),
    raw_text: document.getElementById("entrega-texto").value.trim() || "",
    image_reference: null,
  };
  try {
    const entrega = await requestJSON("/submissions", {
      method: "POST",
      headers: construirHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    estado.entregas.unshift(entrega);
    poblarSelects();
    renderizarListas();
    mostrarMensajeApp(`Entrega de texto creada (ID ${entrega.id}).`);
    formularios.entregaTexto.reset();
  } catch (error) {
    mostrarMensajeApp(error.message, true);
  }
});

formularios.entregaFoto.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData();
  formData.append(
    "evaluation_id",
    document.getElementById("entrega-foto-evaluacion-id").value
  );
  formData.append("student_id", document.getElementById("entrega-foto-alumno-id").value);
  const archivo = document.getElementById("entrega-foto-archivo").files[0];
  if (!archivo) {
    mostrarMensajeApp("Seleccioná una imagen del examen.", true);
    return;
  }
  formData.append("image_file", archivo);

  try {
    const entrega = await requestJSON("/submissions/photo", {
      method: "POST",
      headers: construirHeaders(),
      body: formData,
    });
    estado.entregas.unshift(entrega);
    poblarSelects();
    renderizarListas();
    mostrarMensajeApp(
      `Entrega por foto creada (ID ${entrega.id}). Texto OCR: ${(entrega.raw_text || "vacío").slice(
        0,
        90
      )}`
    );
    formularios.entregaFoto.reset();
  } catch (error) {
    mostrarMensajeApp(error.message, true);
  }
});

formularios.correccion.addEventListener("submit", async (event) => {
  event.preventDefault();
  const entregaId = Number(document.getElementById("correccion-entrega-id").value);
  const payload = {
    criteria: document.getElementById("correccion-criterios").value.trim(),
    max_score: Number(document.getElementById("correccion-puntaje-max").value),
    use_llm: document.getElementById("correccion-usar-llm").checked,
  };
  try {
    const data = await requestJSON(`/submissions/${entregaId}/correct`, {
      method: "POST",
      headers: construirHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    });
    mostrarMensajeApp(`Corrección lista. Puntaje: ${data.score}/${data.max_score}`);
    formularios.correccion.reset();
  } catch (error) {
    mostrarMensajeApp(error.message, true);
  }
});

formularios.notas.addEventListener("submit", async (event) => {
  event.preventDefault();
  const studentId = Number(document.getElementById("notas-alumno-id").value);
  try {
    const [notas, progreso] = await Promise.all([
      requestJSON(`/students/${studentId}/grades`, {
        headers: construirHeaders(),
      }),
      requestJSON(`/students/${studentId}/progress`, {
        headers: construirHeaders(),
      }),
    ]);
    ui.listaNotas.innerHTML = `
      <li><strong>Evaluaciones corregidas:</strong> ${progreso.evaluations_count}</li>
      <li><strong>Promedio numérico:</strong> ${progreso.average_score}</li>
      <li><strong>Promedio porcentual:</strong> ${progreso.average_percentage}%</li>
      <li><strong>Último puntaje:</strong> ${progreso.last_score}</li>
      <li><strong>Detalle:</strong></li>
      ${notas
        .map(
          (n) =>
            `<li class="muted">Eval ${n.evaluation_id}: ${n.score}/${n.max_score} - ${
              n.feedback || "sin devolución"
            }</li>`
        )
        .join("")}
    `;
    mostrarMensajeApp("Notas y progreso cargados.");
  } catch (error) {
    mostrarMensajeApp(error.message, true);
  }
});

document.getElementById("btn-recargar").addEventListener("click", async () => {
  await recargarTodo();
  mostrarMensajeApp("Datos actualizados.");
});

document.getElementById("btn-limpiar-mensaje").addEventListener("click", () => {
  ui.appMensaje.textContent = "";
  ui.appMensaje.className = "mensaje";
});

if (estado.token && estado.docente) {
  renderizarVista();
  recargarTodo();
} else {
  renderizarVista();
}
