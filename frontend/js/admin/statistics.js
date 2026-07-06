/**
 * admin/statistics.js — 后台数据统计与分析页逻辑
 * 依赖：../api.js、../mock-data.js、../common.js、common.js（本目录）
 * 对应用例：4.3.4 Data Analysis 数据统计与分析
 */
async function loadOverview(range) {
  const stats = await AdminAPI.statistics.overview({ range });

  document.getElementById("statTodaySales").textContent = formatPrice(stats.kpi.todaySales);
  document.getElementById("statTodayOrders").textContent = stats.kpi.todayOrders;
  document.getElementById("statTotalUsers").textContent = stats.kpi.totalUsers;

  const max = Math.max(...stats.salesTrend.map((d) => d.value));
  document.getElementById("trendChart").innerHTML = stats.salesTrend
    .map(
      (d) => `
    <div class="bar-col">
      <div class="bar" style="height:${(d.value / max) * 100}%" title="${formatPrice(d.value)}"></div>
      <div class="bar-label">${d.label}</div>
    </div>`
    )
    .join("");

  const maxSales = Math.max(...stats.hotBooks.map((b) => b.salesCount));
  document.getElementById("hotBookList").innerHTML = stats.hotBooks
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
    .join("");
}

async function loadRiskStores() {
  const risky = await AdminAPI.statistics.riskStores();
  const container = document.getElementById("riskStoreList");
  if (!container) return;
  container.innerHTML = risky
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
    .join("");
}

document.addEventListener("DOMContentLoaded", () => {
  const user = initAdminShell("statistics");
  if (!user) return;

  document.querySelectorAll(".admin-tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".admin-tabs button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      loadOverview(btn.dataset.range);
    });
  });

  loadOverview("7d");
  if (user.userType === "platform_admin") loadRiskStores();
});
