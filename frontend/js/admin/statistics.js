/**
 * admin/statistics.js — 后台数据统计与分析页逻辑
 * 依赖：../api.js、../common.js、common.js（本目录）
 * 对应用例：4.3.4 Data Analysis 数据统计与分析
 */
async function loadOverview(range) {
  const stats = await AdminAPI.statistics.overview({ range });

  document.getElementById("statTodaySales").textContent = formatPrice(stats.kpi.todaySales);
  document.getElementById("statTodayOrders").textContent = stats.kpi.todayOrders;
  document.getElementById("statTotalUsers").textContent = stats.kpi.totalUsers;

  const max = Math.max(...stats.salesTrend.map((d) => d.value), 1);
  document.getElementById("trendChart").innerHTML = stats.salesTrend
    .map(
      (d) => `
    <div class="bar-col">
      <div class="bar" style="height:${(d.value / max) * 100}%" title="${formatPrice(d.value)}"></div>
      <div class="bar-label">${d.label}</div>
    </div>`
    )
    .join("");

  const maxSales = Math.max(...stats.hotBooks.map((b) => b.salesCount), 1);
  document.getElementById("hotBookList").innerHTML = stats.hotBooks.length
    ? stats.hotBooks
        .map(
          (b, idx) => `
    <div class="rank-item">
      <div class="rank-no">${idx + 1}</div>
      <div style="flex:1">
        <div class="rank-name">${b.bookName}</div>
        <div class="progress-track"><div class="progress-fill" style="width:${(b.salesCount / maxSales) * 100}%"></div></div>
      </div>
      <div class="rank-value">${b.salesCount}</div>
    </div>`
        )
        .join("")
    : '<div class="empty-state">暂无热门图书数据</div>';
}

async function loadRiskStores() {
  const risky = await AdminAPI.statistics.riskStores();
  const container = document.getElementById("riskStoreList");
  if (!container) return;
  container.innerHTML = risky.length
    ? risky
        .map(
          (r) => `
    <div class="flex justify-between items-center" style="padding:10px 0;border-bottom:1px solid var(--color-border)">
      <div>
        <div style="font-weight:600">${r.storeName}</div>
        <div class="text-muted" style="font-size:12px">${r.reason}</div>
      </div>
      <span class="badge badge-danger">风险值 ${r.riskScore}</span>
    </div>`
        )
        .join("")
    : '<div class="empty-state">暂无异常风险数据</div>';
}

async function exportStatistics(range) {
  const res = await fetch(AdminAPI.statistics.exportUrl({ range }), {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error(`导出失败（HTTP ${res.status}）`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `ebookstore-statistics-${range}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function loadRecommendationSettings() {
  const form = document.getElementById("recommendationForm");
  if (!form) return;
  const settings = await AdminAPI.recommendation.settings();
  form.guessWeight.value = settings.guessWeight === undefined || settings.guessWeight === null ? 1 : settings.guessWeight;
  form.hotWeight.value = settings.hotWeight === undefined || settings.hotWeight === null ? 1 : settings.hotWeight;
  form.searchEmbeddingEnabled.checked = settings.searchEmbeddingEnabled !== false;
  form.detailSameStoreEnabled.checked = settings.detailSameStoreEnabled !== false;
}

document.addEventListener("DOMContentLoaded", () => {
  const user = initAdminShell("statistics");
  if (!user) return;
  let currentRange = "7d";

  document.querySelectorAll(".admin-tabs button").forEach((btn) => {
    if (!btn.dataset.range) return;
    btn.addEventListener("click", () => {
      document.querySelectorAll(".admin-tabs button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentRange = btn.dataset.range;
      loadOverview(currentRange);
    });
  });

  const exportBtn = document.getElementById("exportStatsBtn");
  if (exportBtn) exportBtn.addEventListener("click", async () => {
    try {
      await exportStatistics(currentRange);
    } catch (err) {
      showToast(err.message || "报表导出失败", "danger");
    }
  });

  const recommendationForm = document.getElementById("recommendationForm");
  if (recommendationForm) recommendationForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    await AdminAPI.recommendation.update({
      guessWeight: Number(form.guessWeight.value) || 1,
      hotWeight: Number(form.hotWeight.value) || 1,
      searchEmbeddingEnabled: form.searchEmbeddingEnabled.checked,
      detailSameStoreEnabled: form.detailSameStoreEnabled.checked,
    });
    showToast("推荐策略已保存", "success");
  });

  loadOverview("7d");
  if (user.userType === "platform_admin") {
    loadRiskStores();
    loadRecommendationSettings();
  }
});
