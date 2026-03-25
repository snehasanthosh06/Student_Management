(() => {
    const words = [
        "Secure Admin",
        "Fast CRUD",
        "Search & Sort",
        "Validated Marks",
        "Attendance Tracking"
    ];

    const rotatingEl = document.getElementById("rotatingText");
    if (rotatingEl) {
        let idx = 0;
        rotatingEl.textContent = words[idx];
        setInterval(() => {
            idx = (idx + 1) % words.length;
            rotatingEl.textContent = words[idx];
        }, 2200);
    }

    const scrollBtn = document.getElementById("scrollToFeatures");
    if (scrollBtn) {
        scrollBtn.addEventListener("click", () => {
            const el = document.getElementById("features");
            if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
        });
    }

    const accRoot = document.getElementById("accordion");
    if (accRoot) {
        const buttons = accRoot.querySelectorAll(".acc-btn");
        buttons.forEach((btn) => {
            btn.addEventListener("click", () => {
                const item = btn.closest(".acc-item");
                if (!item) return;
                item.classList.toggle("open");
            });
        });
    }

    // Demo KPI (client-only placeholder). Real count requires a secured API endpoint.
    const kpi = document.getElementById("kpiStudents");
    if (kpi) {
        kpi.textContent = "—";
    }
})();

