async function loadStudent() {
    try {
        const data = await fetchJSON(`/api/students/${encodeURIComponent(STUDENT_ID)}`);
        const s = data.student;
        document.getElementById("detail-content").style.display = "block";
        document.getElementById("d-id").textContent = s.student_id;
        document.getElementById("d-name").textContent = s.student_name;
        document.getElementById("d-branch").textContent = s.branch;
        document.getElementById("d-semester").textContent = s.semester;
        document.getElementById("d-overall").textContent = s.overall_percentage + "%";
        document.getElementById("d-category").innerHTML = `<span class="${categoryBadgeClass(s.performance_category)}">${s.performance_category}</span>`;

        const labels = s.marks.map(m => m.subject_name);
        const values = s.marks.map(m => m.marks);
        new Chart(document.getElementById("chart-student-marks"), {
            type: "bar",
            data: { labels, datasets: [{ label: "Marks", data: values, backgroundColor: "#4f46e5" }] },
            options: { scales: { y: { beginAtZero: true, max: 100 } }, plugins: { legend: { display: false } } }
        });

        const riskEl = document.getElementById("d-risk-level");
        riskEl.textContent = s.risk_level;
        riskEl.style.background = "#f3f4f6";
        riskEl.style.color = riskColor(s.risk_level);
        document.getElementById("d-risk-reasoning").textContent = s.risk_reasoning;
    } catch (e) {
        document.getElementById("detail-error").style.display = "block";
        document.getElementById("detail-error").textContent = e.message || "Student not found.";
    }
}

loadStudent();
