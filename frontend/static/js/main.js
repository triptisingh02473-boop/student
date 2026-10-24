function categoryBadgeClass(category) {
    switch (category) {
        case "Excellent": return "badge badge-excellent";
        case "Good": return "badge badge-good";
        case "Average": return "badge badge-average";
        case "At Risk": return "badge badge-at-risk";
        default: return "badge";
    }
}

function riskColor(level) {
    switch (level) {
        case "Low Risk": return "#16a34a";
        case "Moderate Risk": return "#d97706";
        case "High Risk": return "#dc2626";
        default: return "#6b7280";
    }
}

async function fetchJSON(url, options) {
    const res = await fetch(url, options);
    const data = await res.json();
    if (!res.ok || data.success === false) {
        const err = new Error(data.error || "Request failed");
        err.data = data;
        throw err;
    }
    return data;
}

const CATEGORY_COLORS = {
    "Excellent": "#16a34a",
    "Good": "#2563eb",
    "Average": "#d97706",
    "At Risk": "#dc2626",
};
