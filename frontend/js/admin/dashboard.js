/**
 * admin/dashboard.js — 后台数据总览页逻辑
 * 依赖：../api.js、../common.js、common.js（本目录）
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

  const trendBox = document.getElementById("salesBarChart");
  const max = Math.max(...stats.salesTrend.map((d) => Number(d.value) || 0), 0);
  trendBox.innerHTML = stats.salesTrend.length
    ? stats.salesTrend
        .map(
          (d) => `
    <div class="bar-col">
      <div class="bar" style="height:${max ? ((Number(d.value) || 0) / max) * 100 : 0}%" title="${formatPrice(d.value)}"></div>
      <div class="bar-label">${d.label}</div>
    </div>`
        )
        .join("")
    : '<div class="empty-state">暂无销售趋势数据</div>';

  document.getElementById("hotBookRank").innerHTML = stats.hotBooks.length
    ? stats.hotBooks
        .map(
          (b, idx) => `
    <div class="rank-item">
      <div class="rank-no">${idx + 1}</div>
      <div class="rank-name">${b.bookName}</div>
      <div class="rank-value">${b.salesCount} 件</div>
    </div>`
        )
        .join("")
    : '<div class="empty-state">暂无热销图书数据</div>';

  const orderRes = await AdminAPI.orders.list({ page: 1, pageSize: 5 });
  document.getElementById("recentOrderTableBody").innerHTML = orderRes.list.length
    ? orderRes.list
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
        .join("")
    : '<tr><td colspan="4" class="text-center text-muted" style="padding:32px">暂无订单数据</td></tr>';
});
