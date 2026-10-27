const startBtn = document.getElementById("start-btn");
const stopBtn = document.getElementById("stop-btn");
const pill = document.getElementById("status-pill");
const video = document.getElementById("video");
const placeholder = document.getElementById("placeholder");
const errorBox = document.getElementById("error");
const savedNote = document.getElementById("saved-note");
const todayText = document.getElementById("today").textContent;

const classSelect = document.getElementById("class-select");
const classModeSelect = document.getElementById("class-mode");
const subjectWrap = document.getElementById("subject-wrap");
const subjectInput = document.getElementById("subject");
const classInfo = document.getElementById("class-info");
const addClassBtn = document.getElementById("add-class-btn");
const addClassForm = document.getElementById("add-class-form");
const saveClassBtn = document.getElementById("save-class-btn");
const manageLink = document.getElementById("manage-link");

const suggestCard = document.getElementById("suggest-card");
const suggestBtn = document.getElementById("suggest-btn");
const suggestList = document.getElementById("suggest-list");
const suggestSource = document.getElementById("suggest-source");

let classes = [];
let isRunning = false;
let lastSessionId = null;
let previewRows = [];

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
}

function selectedClass() {
    return classes.find(c => String(c.id) === classSelect.value) || null;
}

function setBanner(c) {
    document.getElementById("banner-class").textContent = c ? c.grade : "–";
    document.getElementById("banner-section").textContent = c && c.section ? c.section : "–";
    document.getElementById("banner-strength").textContent = c ? c.strength + " students" : "–";
    document.getElementById("banner-type").textContent =
        c ? (c.mode === "daily" ? "Once a day" : "Every lecture") : "–";
}

function updateClassUI() {
    const c = selectedClass();
    subjectWrap.hidden = !(c && c.mode === "lecture");
    classModeSelect.disabled = !c || isRunning;
    setBanner(c);

    if (!c) {
        classInfo.textContent = "No class yet. Click + Add class.";
        manageLink.hidden = true;
        previewRows = [];
        renderRoster([]);
        return;
    }

    manageLink.hidden = false;
    manageLink.href = "/classes/" + c.id;
    classModeSelect.value = c.mode;

    let status;
    if (c.mode === "daily") {
        status = c.today
            ? "attendance already taken today at " + c.today.time +
              " (" + c.today.present + " present, " + c.today.absent + " absent)"
            : "attendance not taken yet today";
    } else {
        status = c.today
            ? "last attendance today at " + c.today.time
            : "no attendance taken yet today";
    }
    const strength = c.strength === 0
        ? "no students yet (click Manage students to add them)"
        : c.strength + " students";
    classInfo.textContent = strength + " | " + status;
    loadPreview(c.id);
}

async function loadPreview(classId) {
    try {
        const res = await fetch("/api/classes/" + classId + "/students");
        const rows = await res.json();
        if (!selectedClass() || selectedClass().id !== classId) return;
        previewRows = rows.map(r => ({ roll_no: r.roll_no, name: r.name, status: "–", first_seen: null }));
        if (!isRunning) renderRoster(previewRows);
    } catch (e) {
        /* ignore */
    }
}

function renderRoster(rows) {
    const body = document.getElementById("roster-body");
    body.innerHTML = "";
    if (rows.length === 0) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 4;
        td.className = "muted";
        td.textContent = selectedClass()
            ? "No students in this class yet. Click Manage students."
            : "Select a class to see its students.";
        tr.appendChild(td);
        body.appendChild(tr);
        return;
    }
    rows.forEach(r => {
        const tr = document.createElement("tr");
        const cells = [r.roll_no, r.name, r.status, r.first_seen || "–"];
        cells.forEach((text, i) => {
            const td = document.createElement("td");
            td.textContent = text;
            if (i === 2) {
                if (text === "Present") td.className = "st-present";
                else if (text === "Absent") td.className = "st-absent";
                else td.className = "muted";
            }
            tr.appendChild(td);
        });
        body.appendChild(tr);
    });
}

async function loadClasses(selectId) {
    const res = await fetch("/api/classes");
    classes = await res.json();
    classSelect.innerHTML = "";
    if (classes.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "No classes yet";
        classSelect.appendChild(opt);
    } else {
        classes.forEach(c => {
            const opt = document.createElement("option");
            opt.value = String(c.id);
            opt.textContent = c.name;
            classSelect.appendChild(opt);
        });
        if (selectId) classSelect.value = String(selectId);
    }
    updateClassUI();
}

async function loadHistory() {
    try {
        const res = await fetch("/api/history");
        const rows = await res.json();
        const body = document.getElementById("history-body");
        if (rows.length === 0) {
            body.innerHTML = '<tr><td colspan="7" class="muted">No sessions yet.</td></tr>';
            return;
        }
        body.innerHTML = rows.map(r => `<tr>
            <td>${r.session_date}</td>
            <td>${escapeHtml(r.class_name)}</td>
            <td>${r.subject ? escapeHtml(r.subject) : "–"}</td>
            <td>${r.started_at.slice(11, 16)} – ${r.ended_at ? r.ended_at.slice(11, 16) : ""}</td>
            <td>${r.present_count}</td>
            <td>${r.absent_count}</td>
            <td><a href="/records/${r.id}">Details</a></td>
        </tr>`).join("");
    } catch (e) {
        /* ignore */
    }
}

async function saveClass() {
    errorBox.hidden = true;
    const payload = {
        grade: document.getElementById("new-grade").value,
        section: document.getElementById("new-section").value,
        mode: document.getElementById("new-class-mode").value,
    };
    const res = await fetch("/api/classes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
        showError(data.error || "Could not save the class.");
        return;
    }
    addClassForm.hidden = true;
    document.getElementById("new-grade").value = "";
    document.getElementById("new-section").value = "";
    await loadClasses(data.id);
}

async function changeMode() {
    const c = selectedClass();
    if (!c) return;
    errorBox.hidden = true;
    const res = await fetch("/api/classes/" + c.id + "/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: classModeSelect.value }),
    });
    if (!res.ok) {
        const data = await res.json();
        showError(data.error || "Could not change the attendance type.");
    }
    await loadClasses(c.id);
}

function setRunning(running) {
    if (running === isRunning) return;
    isRunning = running;
    startBtn.disabled = running;
    stopBtn.disabled = !running;
    classSelect.disabled = running;
    classModeSelect.disabled = running || !selectedClass();
    subjectInput.disabled = running;
    addClassBtn.disabled = running;
    pill.textContent = running ? "Running" : "Stopped";
    pill.className = "pill " + (running ? "live" : "idle");
    if (running) {
        video.src = "/video_feed?t=" + Date.now();
        video.hidden = false;
        placeholder.hidden = true;
    } else {
        video.removeAttribute("src");
        video.hidden = true;
        placeholder.hidden = false;
    }
}

async function startSession() {
    errorBox.hidden = true;
    savedNote.hidden = true;
    startBtn.disabled = true;

    const res = await fetch("/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            class_id: classSelect.value,
            subject: subjectInput.value,
        }),
    });

    if (!res.ok) {
        const data = await res.json();
        showError(data.error || "Could not start the session.");
        startBtn.disabled = false;
        return;
    }
    setRunning(true);
}

async function stopSession() {
    stopBtn.disabled = true;
    await fetch("/api/stop", { method: "POST" });
    setRunning(false);
    await refresh();
}

function renderChart(timeline) {
    const chart = document.getElementById("chart");
    const rows = timeline.slice(-12);
    if (rows.length === 0) {
        chart.innerHTML = '<div class="muted">Bars appear every 5 seconds.</div>';
        return;
    }
    chart.innerHTML = rows.map(r => {
        const e = r.engagement === null ? 0 : r.engagement;
        const cls = e >= 70 ? "high" : e >= 40 ? "mid" : "low";
        return `<div class="bar-wrap" title="${r.time} | engagement ${e} | speaking ${r.speaking_pct}%">
            <div class="bar ${cls}" style="height:${Math.round(e * 1.2)}px"></div>
            <div class="bar-label">${r.time.slice(3)}</div>
        </div>`;
    }).join("");
}

function renderLog(log) {
    const list = document.getElementById("attendance-log");
    list.innerHTML = "";
    if (log.length === 0) {
        const li = document.createElement("li");
        li.className = "muted";
        li.textContent = "No events yet.";
        list.appendChild(li);
        return;
    }
    log.slice(-10).reverse().forEach(e => {
        const li = document.createElement("li");
        const name = document.createElement("span");
        name.textContent = e.label;
        const text = document.createTextNode(" marked present ");
        const time = document.createElement("time");
        time.textContent = e.time;
        li.appendChild(name);
        li.appendChild(text);
        li.appendChild(time);
        list.appendChild(li);
    });
}

function renderPersons(persons) {
    const body = document.getElementById("persons-body");
    body.innerHTML = "";
    if (persons.length === 0) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 4;
        td.className = "muted";
        td.textContent = "No one detected";
        tr.appendChild(td);
        body.appendChild(tr);
        return;
    }
    persons.forEach(p => {
        let attendance;
        if (p.state === "known") attendance = p.present ? "Present" : "Verifying";
        else if (p.state === "unknown") attendance = "Not in class list";
        else attendance = "Identifying...";

        const cells = [p.label, attendance, p.status + (p.inactive ? " (inactive)" : ""), p.score];
        const tr = document.createElement("tr");
        cells.forEach(text => {
            const td = document.createElement("td");
            td.textContent = text;
            tr.appendChild(td);
        });
        body.appendChild(tr);
    });
}

function render(s) {
    document.getElementById("stat-people").textContent = s.people;
    document.getElementById("stat-present").textContent = s.present;
    document.getElementById("stat-absent").textContent = s.total ? s.absent : "–";
    document.getElementById("stat-total").textContent = s.total ? s.total : "–";
    document.getElementById("stat-engagement").textContent =
        s.engagement === null ? "–" : Math.round(s.engagement) + " / 100";
    document.getElementById("stat-audio").textContent =
        !s.audio_ok ? "No mic" : (s.speaking ? "Speaking" : "Quiet");

    if (s.error) {
        showError(s.error);
    }

    const saved = !s.running && s.saved_session_id;
    suggestCard.hidden = !saved;
    if (saved) {
        if (s.saved_session_id !== lastSessionId) {
            lastSessionId = s.saved_session_id;
            suggestList.innerHTML = "";
            suggestSource.textContent = "";
            loadClasses(classSelect.value);
            loadHistory();
        }
        const opt = classSelect.selectedOptions[0];
        savedNote.textContent = "Attendance saved for " + (opt ? opt.textContent : "the class") +
            " on " + todayText + ". See it in Recent attendance history below.";
        savedNote.hidden = false;
    } else {
        savedNote.hidden = true;
    }

    renderPersons(s.persons);
    renderRoster(s.roster && s.roster.length ? s.roster : previewRows);
    renderChart(s.timeline);
    renderLog(s.attendance);
}

async function refresh() {
    try {
        const res = await fetch("/api/stats");
        const s = await res.json();
        render(s);
        setRunning(s.running);
    } catch (e) {
        /* server not reachable, ignore */
    }
}

suggestBtn.addEventListener("click", async () => {
    if (!lastSessionId) return;
    suggestBtn.disabled = true;
    suggestSource.textContent = "Generating suggestions...";
    suggestList.innerHTML = "";
    try {
        const res = await fetch("/api/suggestions/" + lastSessionId);
        const data = await res.json();
        if (!res.ok) {
            suggestSource.textContent = data.error || "Could not get suggestions.";
        } else {
            data.items.forEach(text => {
                const li = document.createElement("li");
                li.textContent = text;
                suggestList.appendChild(li);
            });
            suggestSource.textContent = data.source === "gemini"
                ? "Generated by Gemini (" + data.model + ") from a numbers-only summary."
                : "Generated by built-in rules (no internet used). " + (data.note || "");
        }
    } catch (e) {
        suggestSource.textContent = "Could not reach the server.";
    }
    suggestBtn.disabled = false;
});

classSelect.addEventListener("change", updateClassUI);
classModeSelect.addEventListener("change", changeMode);
addClassBtn.addEventListener("click", () => { addClassForm.hidden = !addClassForm.hidden; });
saveClassBtn.addEventListener("click", saveClass);
startBtn.addEventListener("click", startSession);
stopBtn.addEventListener("click", stopSession);

loadClasses(null);
loadHistory();
setInterval(refresh, 1000);
refresh();
