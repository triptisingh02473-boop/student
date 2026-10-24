async function loadSubjects() {
    try {
        const data = await fetchJSON("/api/subjects");
        const container = document.getElementById("subjects-content");
        if (!data.subjects || data.subjects.length === 0) {
            document.getElementById("subjects-empty").style.display = "block";
            container.innerHTML = "";
            return;
        }
        document.getElementById("subjects-empty").style.display = "none";
        container.innerHTML = "";

        data.subjects.forEach((subj, i) => {
            const card = document.createElement("div");
            card.className = "card";
            card.innerHTML = `
                <h3>${subj.subject}</h3>
                <div class="stat-grid" style="grid-template-columns: repeat(4, 1fr);">
                    <div class="stat-card"><div class="stat-label">Average</div><div class="stat-value">${subj.average}</div></div>
                    <div class="stat-card"><div class="stat-label">Highest</div><div class="stat-value">${subj.highest}</div></div>
                    <div class="stat-card"><div class="stat-label">Lowest</div><div class="stat-value">${subj.lowest}</div></div>
                    <div class="stat-card"><div class="stat-label">Students</div><div class="stat-value">${subj.num_students}</div></div>
                </div>
                <canvas id="subject-chart-${i}" height="80"></canvas>
                <div style="display:flex; gap:24px; margin-top:16px;">
                    <div style="flex:1;">
                        <strong>Performing well (&ge;80)</strong>
                        <ul>${(subj.strong_students || []).map(s => `<li>${s.student_name} (${s.student_id})</li>`).join("") || "<li class='muted'>None</li>"}</ul>
                    </div>
                    <div style="flex:1;">
                        <strong>Performing poorly (&lt;40)</strong>
                        <ul>${(subj.weak_students || []).map(s => `<li>${s.student_name} (${s.student_id})</li>`).join("") || "<li class='muted'>None</li>"}</ul>
                    </div>
                </div>
            `;
            container.appendChild(card);

            const marks = (subj.all_students || []).map(s => s.marks);
            const names = (subj.all_students || []).map(s => s.student_name);
            if (marks.length) {
                new Chart(document.getElementById(`subject-chart-${i}`), {
                    type: "bar",
                    data: { labels: names, datasets: [{ label: subj.subject, data: marks, backgroundColor: "#4f46e5" }] },
                    options: { scales: { y: { beginAtZero: true, max: 100 } }, plugins: { legend: { display: false } } }
                });
            }
        });
    } catch (e) {
        console.error(e);
    }
}

loadSubjects();
