/**
 * home.js — 首页逻辑
 * 依赖：api.js、mock-data.js、common.js
 * 对应接口：BookAPI.listCategories()、BookAPI.recommended()（4.2.2 图书浏览与搜索流程）
 */
document.addEventListener("DOMContentLoaded", async () => {
  const categoryNav = document.getElementById("categoryNav");
  const bookGrid = document.getElementById("recommendedGrid");

  try {
    const categories = await BookAPI.listCategories();
    categoryNav.innerHTML =
      `<a href="search.html" class="active">全部</a>` +
      categories
        .map((c) => `<a href="search.html?categoryId=${c.categoryId}">${c.categoryName}</a>`)
        .join("");
  } catch (err) {
    console.error("加载分类失败", err);
  }

  try {
    const books = await BookAPI.recommended({ limit: 12 });
    bookGrid.innerHTML = books.map(renderBookCard).join("");
    bindAddToCartButtons(bookGrid);
  } catch (err) {
    bookGrid.innerHTML = `<div class="empty-state">推荐图书加载失败，请稍后重试。</div>`;
    console.error("加载推荐图书失败", err);
  }
});
