const classId = document.body.dataset.classId;
const rollInput = document.getElementById("roll-no");
const nameInput = document.getElementById("student-name");
const fileInput = document.getElementById("photo-files");
const camBtn = document.getElementById("cam-btn");
const captureBtn = document.getElementById("capture-btn");
const cam = document.getElementById("cam");
const shotText = document.getElementById("shot-text");
const saveBtn = document.getElementById("save-student-btn");
const msg = document.getElementById("msg");
const body = document.getElementById("students-body");
const strengthEl = document.getElementById("strength");

let stream = null;
let shots = [];

function setMessage(text, kind) {
    msg.textContent = text;
    msg.className = kind === "error" ? "error" : (kind === "ok" ? "saved" : "muted");
    msg.hidden = !text;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function loadStudents() {
    const res = await fetch("/api/classes/" + classId + "/students");
    const rows = await res.json();
    strengthEl.textContent = rows.length;
    body.innerHTML = "";

    if (rows.length === 0) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 3;
        td.className = "muted";
        td.textContent = "No students yet. Add the first one above.";
        tr.appendChild(td);
        body.appendChild(tr);
        return;
    }

    rows.forEach(r => {
        const tr = document.createElement("tr");

        const roll = document.createElement("td");
        roll.textContent = r.roll_no;
        const name = document.createElement("td");
        name.textContent = r.name;

        const action = document.createElement("td");
        const del = document.createElement("button");
        del.className = "btn danger small";
        del.type = "button";
        del.textContent = "Delete";
        del.addEventListener("click", async () => {
            if (!confirm("Delete " + r.name + " (roll " + r.roll_no + ") from this class?")) return;
            await fetch("/api/students/" + r.id + "/delete", { method: "POST" });
            await loadStudents();
        });
        action.appendChild(del);

        tr.appendChild(roll);
        tr.appendChild(name);
        tr.appendChild(action);
        body.appendChild(tr);
    });
}

function stopCamera() {
    if (stream) {
        stream.getTracks().forEach(t => t.stop());
    }
    stream = null;
    cam.srcObject = null;
    cam.hidden = true;
    captureBtn.hidden = true;
    camBtn.textContent = "Use camera instead";
}

async function toggleCamera() {
    if (stream) {
        stopCamera();
        return;
    }
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480 },
            audio: false,
        });
    } catch (e) {
        stream = null;
        setMessage("Could not open the camera. Stop any running session on the dashboard, close other apps using the camera, and allow camera access in the browser.", "error");
        return;
    }
    setMessage("", "");
    cam.srcObject = stream;
    cam.hidden = false;
    captureBtn.hidden = false;
    camBtn.textContent = "Turn camera off";
}

async function captureShots() {
    if (!stream || !cam.videoWidth) {
        setMessage("The camera is not ready yet. Wait a second and try again.", "error");
        return;
    }
    captureBtn.disabled = true;
    shots = [];
    const canvas = document.createElement("canvas");
    for (let i = 0; i < 5; i++) {
        canvas.width = cam.videoWidth;
        canvas.height = cam.videoHeight;
        canvas.getContext("2d").drawImage(cam, 0, 0);
        const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.92));
        shots.push(blob);
        shotText.textContent = "Captured " + shots.length + " of 5. Turn your head slightly between photos.";
        await sleep(700);
    }
    shotText.textContent = "5 camera photos ready.";
    captureBtn.disabled = false;
}

async function saveStudent() {
    setMessage("", "");
    const form = new FormData();
    form.append("roll_no", rollInput.value);
    form.append("name", nameInput.value);
    Array.from(fileInput.files).forEach(f => form.append("photos", f));
    shots.forEach((blob, i) => form.append("photos", blob, "shot" + i + ".jpg"));

    saveBtn.disabled = true;
    setMessage("Saving. Reading the faces can take a few seconds...", "info");
    try {
        const res = await fetch("/api/classes/" + classId + "/students", {
            method: "POST",
            body: form,
        });
        const data = await res.json();
        if (!res.ok) {
            setMessage(data.error || "Could not save the student.", "error");
        } else {
            setMessage("Saved " + nameInput.value + " using " + data.used + " photo(s)." +
                (data.warning ? " " + data.warning : ""), "ok");
            rollInput.value = "";
            nameInput.value = "";
            fileInput.value = "";
            shots = [];
            shotText.textContent = "";
            await loadStudents();
        }
    } catch (e) {
        setMessage("Could not reach the server.", "error");
    }
    saveBtn.disabled = false;
}

camBtn.addEventListener("click", toggleCamera);
captureBtn.addEventListener("click", captureShots);
saveBtn.addEventListener("click", saveStudent);
window.addEventListener("beforeunload", stopCamera);

loadStudents();