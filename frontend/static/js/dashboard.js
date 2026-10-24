let categoryChart, subjectChart;

async function loadDashboard() {
    try {
        const data = await fetchJSON("/api/dashboard");
        if (!data.has_data) {
            document.getElementById("empty-state").style.display = "block";
            document.getElementById("dashboard-content").style.display = "none";
            return;
        }
        document.getElementById("empty-state").style.display = "none";
        document.getElementById("dashboard-content").style.display = "block";

        document.getElementById("stat-total").textContent = data.total_students;
        document.getElementById("stat-average").textContent = data.class_average + "%";
        document.getElementById("stat-excellent").textContent = data.excellent;
        document.getElementById("stat-good").textContent = data.good;
        document.getElementById("stat-avgcat").textContent = data.average;
        document.getElementById("stat-risk").textContent = data.at_risk;

        renderCategoryChart(data.category_distribution);
        renderSubjectChart(data.subject_overview);

        const students = await fetchJSON("/api/students");
        renderStudentsTable(students.students);
    } catch (e) {
        console.error(e);
    }
}

function renderCategoryChart(distribution) {
    const ctx = document.getElementById("chart-category");
    const labels = distribution.map(d => d.category);
    const values = distribution.map(d => d.count);
    const colors = labels.map(l => CATEGORY_COLORS[l] || "#9ca3af");
    if (categoryChart) categoryChart.destroy();
    categoryChart = new Chart(ctx, {
        type: "doughnut",
        data: { labels, datasets: [{ data: values, backgroundColor: colors }] },
        options: { plugins: { legend: { position: "bottom" } } }
    });
}

function renderSubjectChart(subjectOverview) {
    const ctx = document.getElementById("chart-subjects");
    const labels = subjectOverview.map(s => s.subject_name);
    const values = subjectOverview.map(s => s.avg_marks);
    if (subjectChart) subjectChart.destroy();
    subjectChart = new Chart(ctx, {
        type: "bar",
        data: { labels, datasets: [{ label: "Average Marks", data: values, backgroundColor: "#4f46e5" }] },
        options: { scales: { y: { beginAtZero: true, max: 100 } }, plugins: { legend: { display: false } } }
    });
}

function renderStudentsTable(students) {
    const tbody = document.querySelector("#students-table tbody");
    tbody.innerHTML = "";
    students.forEach(s => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${s.student_id}</td>
            <td>${s.student_name}</td>
            <td>${s.branch}</td>
            <td>${s.semester}</td>
            <td>${s.overall_percentage != null ? s.overall_percentage + "%" : "-"}</td>
            <td><span class="${categoryBadgeClass(s.performance_category)}">${s.performance_category || "-"}</span></td>
            <td><a href="/student/${encodeURIComponent(s.student_id)}">View</a></td>
        `;
        tbody.appendChild(tr);
    });
}

loadDashboard();
