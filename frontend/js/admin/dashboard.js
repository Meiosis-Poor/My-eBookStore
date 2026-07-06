/**
 * admin/dashboard.js — 后台数据总览页逻辑
 * 依赖：../api.js、../mock-data.js、../common.js、common.js（本目录）
 * 对应用例：4.3.4 Data Analysis 数据统计与分析（概览部分）
 */
document.addEventListener("DOMContentLoaded", async () => {
  const user = initAdminShell("dashboard");
  if (!user) return;

  const stats = await AdminAPI.statistics.overview({ range: "7d" });

  document.getElementById("kpiTodaySales").textContent = formatPrice(stats.kpi.todaySales);
  document.getElementById("kpiTodayOrders").textContent = stats.kpi.todayOrders;
  document.getElementById("kpiTotalUsers").textContent = stats.kpi.totalUsers;
  document.getElementById("kpiTotalStores").textContent = stats.kpi.totalStores;

  // 简易销售趋势柱状图（原生实现，无外部依赖）
  const max = Math.max(...stats.salesTrend.map((d) => d.value));
  document.getElementById("salesBarChart").innerHTML = stats.salesTrend
    .map(
      (d) => `
    <div class="bar-col">
      <div class="bar" style="height:${(d.value / max) * 100}%" title="${formatPrice(d.value)}"></div>
      <div class="bar-label">${d.label}</div>
    </div>`
    )
    .join("");

  // 热门图书排行
  const maxSales = Math.max(...stats.hotBooks.map((b) => b.salesCount));
  document.getElementById("hotBookRank").innerHTML = stats.hotBooks
    .map(
      (b, idx) => `
    <div class="rank-item">
      <div class="rank-no">${idx + 1}</div>
      <div class="rank-name">${b.bookName}</div>
      <div class="rank-value">${b.salesCount} 件</div>
    </div>`
    )
    .join("");

  // 最新订单预览
  const orderRes = await AdminAPI.orders.list({ page: 1, pageSize: 5 });
  document.getElementById("recentOrderTableBody").innerHTML = orderRes.list
    .slice(0, 5)
    .map(
      (o) => `
    <tr>
      <td>${o.orderNo}</td>
      <td>${formatDate(o.createdTime)}</td>
      <td>${formatPrice(o.actualAmount)}</td>
      <td><span class="badge badge-info">${o.statusLabel}</span></td>
    </tr>`
    )
    .join("");
});
