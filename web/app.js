const state = {
  token: localStorage.getItem("asisdoc_token") || "",
  teacher: JSON.parse(localStorage.getItem("asisdoc_teacher") || "null"),
  courses: [],
  students: [],
  evaluations: [],
  schedules: [],
  demoMode: false,
};

const el = {
  authCard: document.getElementById("auth-card"),
  panelCard: document.getElementById("panel-card"),
  teacherLabel: document.getElementById("teacher-label"),
  authMessage: document.getElementById("auth-status"),
  toast: document.getElementById("toast"),
  coursesList: document.getElementById("courses-list"),
  studentsList: document.getElementById("students-list"),
  evaluationsList: document.getElementById("evaluations-list"),
  schedulesList: document.getElementById("schedules-list"),
  resultsBox: document.getElementById("results-box"),
};

const forms = {
  register: document.getElementById("register-form"),
  login: document.getElementById("login-form"),
  course: document.getElementById("course-form"),
  student: document.getElementById("student-form"),
  evaluation: document.getElementById("evaluation-form"),
  schedule: document.getElementById("schedule-form"),
  textSubmission: document.getElementById("submission-text-form"),
  photoSubmission: document.getElementById("submission-photo-form"),
};

const selects = {
  studentCourse: document.getElementById("student-course"),
  evalCourse: document.getElementById("eval-course"),
  scheduleEvaluation: document.getElementById("schedule-evaluation"),
  submissionEvaluation: document.getElementById("submission-evaluation"),
  submissionStudent: document.getElementById("submission-student"),
  photoEvaluation: document.getElementById("photo-evaluation"),
  photoStudent: document.getElementById("photo-student"),
};

function persistSession() {
  if (state.token) {
    localStorage.setItem("asisdoc_token", state.token);
  } else {
    localStorage.removeItem("asisdoc_token");
  }

  if (state.teacher) {
    localStorage.setItem("asisdoc_teacher", JSON.stringify(state.teacher));
  } else {
    localStorage.removeItem("asisdoc_teacher");
  }
}

const DEMO_DATA = {
  teacher: { full_name: "Docente Demo", email: "demo@asisdoc.local" },
  courses: [
    { id: 101, name: "3°A Ciencias", description: "Ciencias Naturales" },
    { id: 102, name: "4°B Lengua", description: "Lengua y Literatura" },
  ],
  students: [
    { id: 201, full_name: "Ana Pérez", course_id: 101 },
    { id: 202, full_name: "Juan Gómez", course_id: 101 },
    { id: 203, full_name: "Lucía Díaz", course_id: 102 },
  ],
  evaluations: [
    {
      id: 301,
      title: "Evaluación de Células",
      evaluation_type: "multiple_choice",
      difficulty: "medium",
    },
    {
      id: 302,
      title: "Comprensión lectora",
      evaluation_type: "open_answer",
      difficulty: "hard",
    },
  ],
  schedules: [
    {
      id: 401,
      evaluation_id: 301,
      scheduled_for: "2026-06-20T09:00:00",
      notes: "Bloque de mañana",
    },
    {
      id: 402,
      evaluation_id: 302,
      scheduled_for: "2026-06-25T11:00:00",
      notes: "Aula 4B",
    },
  ],
};

function showToast(message, isError = false) {
  el.toast.textContent = message;
  el.toast.classList.remove("hidden");
  el.toast.style.background = isError ? "#7f1d1d" : "#0f172a";
  setTimeout(() => el.toast.classList.add("hidden"), 4200);
}

function setAuthMessage(message, isError = false) {
  if (!el.authMessage) return;
  if (!message) {
    el.authMessage.className = "auth-status hidden";
    el.authMessage.textContent = "";
    return;
  }
  el.authMessage.className = `auth-status ${isError ? "error" : "ok"}`;
  el.authMessage.textContent = message;
}

function authHeaders(extra = {}) {
  const headers = { ...extra };
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }
  return headers;
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, options);
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }
  if (!response.ok) {
    throw new Error(data?.detail || "Ocurrió un error en la solicitud.");
  }
  return data;
}

function setLoggedInUI() {
  const loggedIn = Boolean(state.token && state.teacher);
  el.authCard.classList.toggle("hidden", loggedIn);
  el.panelCard.classList.toggle("hidden", !loggedIn);
  el.teacherLabel.textContent = loggedIn
    ? `${state.teacher.full_name} (${state.teacher.email})`
    : "";
  if (loggedIn) {
    setAuthMessage("");
  }
}

function clearAllState() {
  state.token = "";
  state.teacher = null;
  state.courses = [];
  state.students = [];
  state.evaluations = [];
  state.schedules = [];
  persistSession();
  setLoggedInUI();
}

function fillSelect(select, items, getText, emptyLabel) {
  const prev = select.value;
  select.innerHTML = `<option value="">${emptyLabel}</option>`;
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = String(item.id);
    option.textContent = getText(item);
    select.appendChild(option);
  });
  if ([...select.options].some((opt) => opt.value === prev)) {
    select.value = prev;
  }
}

function renderLists() {
  el.coursesList.innerHTML = state.courses.length
    ? state.courses
        .map(
          (course) =>
            `<li><strong>${course.name}</strong> ${
              course.description ? `- ${course.description}` : ""
            }</li>`
        )
        .join("")
    : "<li>No hay cursos cargados.</li>";

  el.studentsList.innerHTML = state.students.length
    ? state.students
        .map(
          (student) =>
            `<li><strong>${student.full_name}</strong> (curso ${student.course_id})</li>`
        )
        .join("")
    : "<li>No hay alumnos cargados.</li>";

  el.evaluationsList.innerHTML = state.evaluations.length
    ? state.evaluations
        .map(
          (evaluation) =>
            `<li>
              <strong>${evaluation.title}</strong> (${evaluation.evaluation_type}, ${evaluation.difficulty})
              <button class="link-btn" data-download-evaluation="${evaluation.id}" type="button">
                Descargar Word
              </button>
            </li>`
        )
        .join("")
    : "<li>No hay evaluaciones cargadas.</li>";

  el.schedulesList.innerHTML = state.schedules.length
    ? state.schedules
        .map(
          (schedule) =>
            `<li>Evaluación ${schedule.evaluation_id} - ${new Date(
              schedule.scheduled_for
            ).toLocaleString("es-AR")} ${schedule.notes ? `(${schedule.notes})` : ""}</li>`
        )
        .join("")
    : "<li>No hay exámenes agendados.</li>";
}

function renderSelects() {
  fillSelect(
    selects.studentCourse,
    state.courses,
    (course) => `${course.id} - ${course.name}`,
    "Seleccioná un curso"
  );
  fillSelect(
    selects.evalCourse,
    state.courses,
    (course) => `${course.id} - ${course.name}`,
    "Seleccioná un curso"
  );
  fillSelect(
    selects.scheduleEvaluation,
    state.evaluations,
    (evaluation) => `${evaluation.id} - ${evaluation.title}`,
    "Seleccioná una evaluación"
  );
  fillSelect(
    selects.submissionEvaluation,
    state.evaluations,
    (evaluation) => `${evaluation.id} - ${evaluation.title}`,
    "Seleccioná una evaluación"
  );
  fillSelect(
    selects.photoEvaluation,
    state.evaluations,
    (evaluation) => `${evaluation.id} - ${evaluation.title}`,
    "Seleccioná una evaluación"
  );
  fillSelect(
    selects.submissionStudent,
    state.students,
    (student) => `${student.id} - ${student.full_name}`,
    "Seleccioná un alumno"
  );
  fillSelect(
    selects.photoStudent,
    state.students,
    (student) => `${student.id} - ${student.full_name}`,
    "Seleccioná un alumno"
  );
}

async function loadData() {
  if (state.demoMode) {
    state.courses = DEMO_DATA.courses;
    state.students = DEMO_DATA.students;
    state.evaluations = DEMO_DATA.evaluations;
    state.schedules = DEMO_DATA.schedules;
    renderSelects();
    renderLists();
    return;
  }
  if (!state.token) return;
  try {
    const [courses, students, evaluations, schedules] = await Promise.all([
      apiJson("/courses", { headers: authHeaders() }),
      apiJson("/students", { headers: authHeaders() }),
      apiJson("/evaluations", { headers: authHeaders() }),
      apiJson("/schedules", { headers: authHeaders() }),
    ]);
    state.courses = courses;
    state.students = students;
    state.evaluations = evaluations;
    state.schedules = schedules;
    renderSelects();
    renderLists();
  } catch (error) {
    if (String(error.message).toLowerCase().includes("token")) {
      clearAllState();
      showToast("La sesión expiró. Ingresá nuevamente.", true);
    } else {
      showToast(error.message, true);
    }
  }
}

function enableDemoMode() {
  state.demoMode = true;
  state.token = "demo-token";
  state.teacher = DEMO_DATA.teacher;
  persistSession();
  setLoggedInUI();
  loadData();
  el.resultsBox.textContent = JSON.stringify(
    {
      modo: "demo",
      mensaje:
        "Estás viendo una vista previa visual. Los datos son de ejemplo y no se guardan en base real.",
      sugerencia:
        "Para pruebas reales, ingresá a la pantalla principal y usá registro/login normal.",
    },
    null,
    2
  );
  showToast("Modo demo activo: visualización rápida en móvil.");
}

async function downloadEvaluationDocx(evaluationId) {
  const teacherName = encodeURIComponent(state.teacher?.full_name || "Docente");
  const response = await fetch(
    `/evaluations/${evaluationId}/export-docx?school_header=Asisdoc&teacher_name=${teacherName}`,
    { headers: authHeaders() }
  );
  if (!response.ok) {
    let detail = "No se pudo descargar el documento.";
    try {
      const json = await response.json();
      detail = json?.detail || detail;
    } catch (error) {
      // ignore
    }
    throw new Error(detail);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `evaluacion_${evaluationId}.docx`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

forms.register.addEventListener("submit", async (event) => {
  event.preventDefault();
  setAuthMessage("");
  if (state.demoMode) {
    const msg = "En modo demo no se puede registrar. Abrí / para modo real.";
    setAuthMessage(msg, true);
    showToast(msg, true);
    return;
  }
  try {
    await apiJson("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: document.getElementById("reg-name").value.trim(),
        email: document.getElementById("reg-email").value.trim(),
        password: document.getElementById("reg-password").value,
      }),
    });
    forms.register.reset();
    const msg = "Cuenta creada. Ahora iniciá sesión.";
    setAuthMessage(msg, false);
    showToast(msg);
  } catch (error) {
    setAuthMessage(error.message, true);
    showToast(error.message, true);
  }
});

forms.login.addEventListener("submit", async (event) => {
  event.preventDefault();
  setAuthMessage("");
  if (state.demoMode) {
    const msg = "En modo demo no se inicia sesión real. Abrí / para modo real.";
    setAuthMessage(msg, true);
    showToast(msg, true);
    return;
  }
  try {
    const data = await apiJson("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: document.getElementById("login-email").value.trim(),
        password: document.getElementById("login-password").value,
      }),
    });
    state.token = data.access_token;
    state.teacher = data.teacher;
    persistSession();
    setLoggedInUI();
    await loadData();
    showToast("Sesión iniciada correctamente.");
  } catch (error) {
    setAuthMessage(error.message, true);
    showToast(error.message, true);
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  if (state.demoMode) {
    window.location.href = "/";
    return;
  }
  try {
    await apiJson("/auth/logout", { method: "POST", headers: authHeaders() });
  } catch (error) {
    // no-op
  } finally {
    clearAllState();
    showToast("Sesión cerrada.");
  }
});

forms.course.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.demoMode) {
    showToast("Modo demo: acción simulada (no persiste).");
    return;
  }
  try {
    await apiJson("/courses", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        name: document.getElementById("course-name").value.trim(),
        description: document.getElementById("course-description").value.trim() || null,
      }),
    });
    forms.course.reset();
    await loadData();
    showToast("Curso creado.");
  } catch (error) {
    showToast(error.message, true);
  }
});

forms.student.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.demoMode) {
    showToast("Modo demo: acción simulada (no persiste).");
    return;
  }
  try {
    await apiJson("/students", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        full_name: document.getElementById("student-name").value.trim(),
        course_id: Number(document.getElementById("student-course").value),
      }),
    });
    forms.student.reset();
    await loadData();
    showToast("Alumno registrado.");
  } catch (error) {
    showToast(error.message, true);
  }
});

forms.evaluation.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.demoMode) {
    showToast("Modo demo: acción simulada (no persiste).");
    return;
  }
  try {
    await apiJson("/evaluations", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        title: document.getElementById("eval-title").value.trim(),
        course_id: Number(document.getElementById("eval-course").value),
        evaluation_type: document.getElementById("eval-type").value,
        difficulty: document.getElementById("eval-difficulty").value,
        question_count: Number(document.getElementById("eval-count").value),
        material_text: document.getElementById("eval-material").value.trim() || null,
        use_internal_knowledge: document.getElementById("eval-use-knowledge").checked,
      }),
    });
    forms.evaluation.reset();
    await loadData();
    showToast("Evaluación generada.");
  } catch (error) {
    showToast(error.message, true);
  }
});

forms.schedule.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.demoMode) {
    showToast("Modo demo: acción simulada (no persiste).");
    return;
  }
  try {
    const datetimeValue = document.getElementById("schedule-date").value;
    await apiJson("/schedules", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        evaluation_id: Number(document.getElementById("schedule-evaluation").value),
        scheduled_for: new Date(datetimeValue).toISOString(),
        notes: document.getElementById("schedule-notes").value.trim() || null,
      }),
    });
    forms.schedule.reset();
    await loadData();
    showToast("Examen agendado.");
  } catch (error) {
    showToast(error.message, true);
  }
});

forms.textSubmission.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.demoMode) {
    const maxScore = Number(document.getElementById("submission-max-score").value || 10);
    el.resultsBox.textContent = JSON.stringify(
      {
        entrega_id: 9991,
        texto_detectado: document.getElementById("submission-raw-text").value.trim(),
        puntaje: Math.round(maxScore * 0.8 * 100) / 100,
        puntaje_maximo: maxScore,
        devolucion:
          "Modo demo: corrección simulada. Se detecta buen manejo conceptual general.",
      },
      null,
      2
    );
    showToast("Modo demo: corrección simulada.");
    return;
  }
  try {
    const submission = await apiJson("/submissions", {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        evaluation_id: Number(document.getElementById("submission-evaluation").value),
        student_id: Number(document.getElementById("submission-student").value),
        raw_text: document.getElementById("submission-raw-text").value.trim(),
      }),
    });

    const correction = await apiJson(`/submissions/${submission.id}/correct`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        criteria: document.getElementById("submission-criteria").value.trim(),
        max_score: Number(document.getElementById("submission-max-score").value),
        use_llm: document.getElementById("submission-use-llm").checked,
      }),
    });

    el.resultsBox.textContent = JSON.stringify(
      {
        entrega_id: submission.id,
        texto_detectado: submission.raw_text || "",
        puntaje: correction.score,
        puntaje_maximo: correction.max_score,
        devolucion: correction.feedback,
      },
      null,
      2
    );
    forms.textSubmission.reset();
    showToast("Entrega corregida correctamente.");
  } catch (error) {
    showToast(error.message, true);
  }
});

forms.photoSubmission.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.demoMode) {
    const maxScore = Number(document.getElementById("photo-max-score").value || 10);
    el.resultsBox.textContent = JSON.stringify(
      {
        entrega_id: 9992,
        texto_ocr: "Texto OCR simulado desde imagen en modo demo.",
        puntaje: Math.round(maxScore * 0.7 * 100) / 100,
        puntaje_maximo: maxScore,
        devolucion:
          "Modo demo: resultado de OCR/corrección simulado para vista previa visual.",
      },
      null,
      2
    );
    showToast("Modo demo: carga y corrección simuladas.");
    return;
  }
  try {
    const file = document.getElementById("photo-file").files[0];
    if (!file) {
      throw new Error("Seleccioná una imagen para corregir.");
    }
    const formData = new FormData();
    formData.append("evaluation_id", document.getElementById("photo-evaluation").value);
    formData.append("student_id", document.getElementById("photo-student").value);
    formData.append("image_file", file);

    const submission = await apiJson("/submissions/photo", {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });

    const correction = await apiJson(`/submissions/${submission.id}/correct`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        criteria: document.getElementById("photo-criteria").value.trim(),
        max_score: Number(document.getElementById("photo-max-score").value),
        use_llm: false,
      }),
    });

    el.resultsBox.textContent = JSON.stringify(
      {
        entrega_id: submission.id,
        texto_ocr: submission.raw_text || "",
        puntaje: correction.score,
        puntaje_maximo: correction.max_score,
        devolucion: correction.feedback,
      },
      null,
      2
    );
    forms.photoSubmission.reset();
    showToast("Foto procesada y corregida.");
  } catch (error) {
    showToast(error.message, true);
  }
});

el.evaluationsList.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const evaluationId = target.dataset.downloadEvaluation;
  if (!evaluationId) return;
  if (state.demoMode) {
    showToast("Modo demo: descarga simulada.");
    return;
  }
  try {
    await downloadEvaluationDocx(Number(evaluationId));
    showToast("Documento Word descargado.");
  } catch (error) {
    showToast(error.message, true);
  }
});

setLoggedInUI();
if (window.location.pathname === "/demo") {
  enableDemoMode();
} else if (state.token && state.teacher) {
  loadData();
}
