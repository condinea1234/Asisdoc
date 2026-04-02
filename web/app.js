const state = {
  token: localStorage.getItem("asisdoc_token") || "",
  teacher: JSON.parse(localStorage.getItem("asisdoc_teacher") || "null"),
  courses: [],
  students: [],
  evaluations: [],
  schedules: [],
};

const el = {
  authCard: document.getElementById("auth-card"),
  panelCard: document.getElementById("panel-card"),
  teacherLabel: document.getElementById("teacher-label"),
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

function showToast(message, isError = false) {
  el.toast.textContent = message;
  el.toast.classList.remove("hidden");
  el.toast.style.background = isError ? "#7f1d1d" : "#0f172a";
  setTimeout(() => el.toast.classList.add("hidden"), 4200);
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
    showToast("Cuenta creada. Ahora iniciá sesión.");
  } catch (error) {
    showToast(error.message, true);
  }
});

forms.login.addEventListener("submit", async (event) => {
  event.preventDefault();
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
    showToast(error.message, true);
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
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
  try {
    await downloadEvaluationDocx(Number(evaluationId));
    showToast("Documento Word descargado.");
  } catch (error) {
    showToast(error.message, true);
  }
});

setLoggedInUI();
if (state.token && state.teacher) {
  loadData();
}
