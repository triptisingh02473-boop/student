async function loadReports() {
    try {
        const data = await fetchJSON("/api/reports");
        if (!data.has_data) {
            document.getElementById("reports-empty").style.display = "block";
            document.getElementById("reports-content").style.display = "none";
            return;
        }
        document.getElementById("reports-empty").style.display = "none";
        document.getElementById("reports-content").style.display = "block";

        const catLabels = data.category_distribution.map(d => d.category);
        const catValues = data.category_distribution.map(d => d.count);
        new Chart(document.getElementById("chart-category-dist"), {
            type: "pie",
            data: { labels: catLabels, datasets: [{ data: catValues, backgroundColor: catLabels.map(l => CATEGORY_COLORS[l] || "#9ca3af") }] },
        });

        const subjLabels = data.subject_overview.map(s => s.subject_name);
        const subjValues = data.subject_overview.map(s => s.avg_marks);
        new Chart(document.getElementById("chart-subject-avg"), {
            type: "bar",
            data: { labels: subjLabels, datasets: [{ label: "Average Marks", data: subjValues, backgroundColor: "#2563eb" }] },
            options: { scales: { y: { beginAtZero: true, max: 100 } }, plugins: { legend: { display: false } } }
        });

        const topBody = document.getElementById("top-students-body");
        topBody.innerHTML = "";
        data.top_students.forEach(s => {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td>${s.student_id}</td><td>${s.student_name}</td><td>${s.overall_percentage}%</td>`;
            topBody.appendChild(tr);
        });

        const attnBody = document.getElementById("attention-students-body");
        attnBody.innerHTML = "";
        data.students_needing_attention.forEach(s => {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td>${s.student_id}</td><td>${s.student_name}</td><td>${s.overall_percentage}%</td>
                <td style="color:${riskColor(s.risk_level)}; font-weight:700;">${s.risk_level || "-"}</td>`;
            attnBody.appendChild(tr);
        });

        new Chart(document.getElementById("chart-overview"), {
            type: "bar",
            data: {
                labels: ["Class Average"],
                datasets: [{ label: "Class Average %", data: [data.class_average], backgroundColor: "#16a34a" }]
            },
            options: { indexAxis: "y", scales: { x: { beginAtZero: true, max: 100 } } }
        });
    } catch (e) {
        console.error(e);
    }
}

loadReports();
