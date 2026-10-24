async function loadPredictions() {
    try {
        const data = await fetchJSON("/api/prediction");
        const tbody = document.getElementById("prediction-table-body");
        if (!data.predictions || data.predictions.length === 0) {
            document.getElementById("prediction-empty").style.display = "block";
            document.getElementById("prediction-content").style.display = "none";
            return;
        }
        document.getElementById("prediction-empty").style.display = "none";
        document.getElementById("prediction-content").style.display = "block";
        tbody.innerHTML = "";
        data.predictions.forEach(p => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><a href="/student/${encodeURIComponent(p.student_id)}">${p.student_id}</a></td>
                <td>${p.student_name}</td>
                <td>${p.overall_percentage}%</td>
                <td><span class="${categoryBadgeClass(p.performance_category)}">${p.performance_category}</span></td>
                <td><span style="color:${riskColor(p.risk_level)}; font-weight:700;">${p.risk_level}</span></td>
                <td class="muted">${p.reasoning}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error(e);
    }
}

loadPredictions();
