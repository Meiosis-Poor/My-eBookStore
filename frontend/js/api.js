const API_BASE_URL = "/api";

const STORAGE_KEYS = {
  TOKEN: "ebs_token",
  USER: "ebs_user",
};

function buildQuery(params = {}) {
  return new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  ).toString();
}

function getToken() {
  return localStorage.getItem(STORAGE_KEYS.TOKEN) || "";
}

function getCurrentUser() {
  const raw = localStorage.getItem(STORAGE_KEYS.USER);
  return raw ? JSON.parse(raw) : null;
}

function setSession(token, user) {
  localStorage.setItem(STORAGE_KEYS.TOKEN, token);
  localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user));
}

function clearSession() {
  localStorage.removeItem(STORAGE_KEYS.TOKEN);
  localStorage.removeItem(STORAGE_KEYS.USER);
}

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    ...(options.headers || {}),
  };
  const body =
    options.body && typeof options.body !== "string" ? JSON.stringify(options.body) : options.body;

  const res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, body });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok || (payload && payload.code !== undefined && payload.code !== 0)) {
    throw new Error((payload && payload.message) || `Request failed (HTTP ${res.status})`);
  }
  return payload && payload.data !== undefined ? payload.data : payload;
}

const AuthAPI = {
  registerUser(payload) {
    return request("/auth/register/user", { method: "POST", body: payload });
  },
  registerSeller(payload) {
    return request("/auth/register/seller", { method: "POST", body: payload });
  },
  login(payload) {
    return request("/auth/login", { method: "POST", body: payload });
  },
  async logout() {
    try {
      await request("/auth/logout", { method: "POST" });
    } finally {
      clearSession();
    }
  },
};

const BookAPI = {
  /** 获取图书分类列表 方法：GET 路径：/categories 响应：CategoryItem[] */
  async listCategories() {
    try {
      return await request("/categories");
    } catch (err) {
      console.warn("[BookAPI.listCategories] 使用模拟数据：", err.message);
      return mockDelay(MOCK_CATEGORIES);
    }
  },

  /**
   * 分类浏览 / 关键词搜索图书列表
   * 方法：GET 路径：/books
   * Query：{ keyword?, searchType?: "title"|"author"|"isbn"（默认 title，三种搜索方式互斥，不做混合匹配）,
   *          categoryId?, sort?: "default"|"sales"|"price_asc"|"price_desc", page?, pageSize? }
   * 响应：{ list: BookItem[], total: number }
   * 对应用例：4.2.2 Browse and Search Books
   */
  async list(params = {}) {
    try {
      const qs = new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== "")
      ).toString();
      return await request(`/books?${qs}`);
    } catch (err) {
      console.warn("[BookAPI.list] 使用模拟数据：", err.message);
      let list = [...MOCK_BOOKS];
      if (params.categoryId) {
        list = list.filter((b) => String(b.categoryId) === String(params.categoryId));
      }
      if (params.keyword) {
        const kw = params.keyword.trim().toLowerCase();
        const searchType = params.searchType || "title";
        list = list.filter((b) => {
          if (searchType === "author") return b.author.toLowerCase().includes(kw);
          if (searchType === "isbn") return b.isbn.toLowerCase().includes(kw);
          return b.bookName.toLowerCase().includes(kw);
        });
      }
      if (params.sort === "sales") list.sort((a, b) => b.salesCount - a.salesCount);
      if (params.sort === "price_asc") list.sort((a, b) => a.price - b.price);
      if (params.sort === "price_desc") list.sort((a, b) => b.price - a.price);
      return mockDelay({ list, total: list.length });
    }
  },

  /**
   * 首页推荐图书（调用推荐算法模块）
   * 方法：GET 路径：/books/recommended
   * Query：{ userId?: number, limit?: number }
   * 响应：BookItem[]
   */
  async recommended(params = {}) {
    try {
      const qs = new URLSearchParams(
        Object.entries({ limit: params.limit || 10, type: params.type }).filter(([, v]) => v !== undefined && v !== "")
      ).toString();
      return await request(`/books/recommended?${qs}`);
    } catch (err) {
      console.warn("[BookAPI.recommended] 使用模拟数据：", err.message);
      const list =
        params.type === "hot"
          ? [...MOCK_BOOKS].sort((a, b) => b.salesCount - a.salesCount)
          : MOCK_BOOKS;
      return mockDelay(list.slice(0, params.limit || 10));
    }
  },

  /**
   * 图书详情
   * 方法：GET 路径：/books/{bookItemId}
   * 响应：BookItem（含 description、embedding 相似推荐等扩展信息）
   */
  async detail(bookItemId) {
    try {
      return await request(`/books/${bookItemId}`);
    } catch (err) {
      console.warn("[BookAPI.detail] 使用模拟数据：", err.message);
      const book = MOCK_BOOKS.find((b) => String(b.bookItemId) === String(bookItemId)) || MOCK_BOOKS[0];
      return mockDelay(book);
    }
  },

  /**
   * 相似图书推荐（基于 embedding 相似度，用于详情页/搜索页兜底推荐）
   * 方法：GET 路径：/books/{bookItemId}/similar
   * 响应：BookItem[]
   */
  async similar(bookItemId) {
    try {
      return await request(`/books/${bookItemId}/similar`);
    } catch (err) {
      console.warn("[BookAPI.similar] 使用模拟数据：", err.message);
      return mockDelay(MOCK_BOOKS.filter((b) => String(b.bookItemId) !== String(bookItemId)).slice(0, 5));
    }
  },
};

/* ============================================================
 * 2.5 店铺模块  StoreAPI
 * 场景：图书详情页点击“进入书店” → 查看该书店主页及全部在架图书
 * ============================================================ */
const StoreAPI = {
  detail(storeId) {
    return request(`/stores/${storeId}`);
  },
  books(storeId, params = {}) {
    const qs = buildQuery(params);
    return request(`/stores/${storeId}/books${qs ? `?${qs}` : ""}`);
  },

  /**
   * 书店管理员维护本店基本信息（店铺名称 / 简介）
   * 方法：PUT 路径：/stores/{storeId}
   * 请求体：{ storeName?: string, description?: string }
   * 场景：后台“店铺信息设置”页保存
   */
  async updateProfile(storeId, payload) {
    try {
      return await request(`/stores/${storeId}`, { method: "PUT", body: payload });
    } catch (err) {
      console.warn("[StoreAPI.updateProfile] 使用模拟数据更新：", err.message);
      const profile = MOCK_STORE_PROFILES.find((s) => String(s.storeId) === String(storeId));
      if (profile) {
        Object.assign(profile, payload);
        persistMockStoreProfiles();
      }
      return mockDelay({ ok: true });
    }
  },
};

/* ============================================================
 * 2.6 搜索历史模块  SearchAPI
 * 场景：搜索框获得焦点 / 内容为空时下拉展示当前用户的历史搜索关键词
 * ============================================================ */
const SearchAPI = {
  /** 获取当前用户的搜索历史（按时间倒序） 方法：GET 路径：/search/history 响应：string[] */
  async history() {
    try {
      return await request("/search/history");
    } catch (err) {
      console.warn("[SearchAPI.history] 使用模拟数据：", err.message);
      return mockDelay([...MOCK_SEARCH_HISTORY]);
    }
  },

  /**
   * 记录一次搜索关键词（用户提交搜索后调用，静默失败即可，不影响搜索本身）
   * 方法：POST 路径：/search/history 请求体：{ keyword: string }
   */
  async record(keyword) {
    if (!keyword || !keyword.trim()) return;
    try {
      return await request("/search/history", { method: "POST", body: { keyword } });
    } catch (err) {
      MOCK_SEARCH_HISTORY = [keyword, ...MOCK_SEARCH_HISTORY.filter((k) => k !== keyword)].slice(0, 8);
      persistMockSearchHistory();
      return mockDelay({ ok: true });
    }
  },
};

/* ============================================================
 * 3. 购物车模块  CartAPI
 * ============================================================ */
const CartAPI = {
  list() {
    return request("/cart");
  },
  add(bookItemId, quantity = 1) {
    return request("/cart", { method: "POST", body: { bookItemId, quantity } });
  },
  updateQuantity(bookItemId, quantity) {
    return request(`/cart/${bookItemId}`, { method: "PUT", body: { quantity } });
  },
  remove(bookItemId) {
    return request(`/cart/${bookItemId}`, { method: "DELETE" });
  },
};

const AddressAPI = {
  list() {
    return request("/addresses");
  },
  create(payload) {
    return request("/addresses", { method: "POST", body: payload });
  },
  update(addressId, payload) {
    return request(`/addresses/${addressId}`, { method: "PUT", body: payload });
  },
  remove(addressId) {
    return request(`/addresses/${addressId}`, { method: "DELETE" });
  },
};

const OrderAPI = {
  create(payload) {
    return request("/orders", { method: "POST", body: payload });
  },
  pay(orderId, paymentMethod) {
    return request(`/orders/${orderId}/pay`, { method: "POST", body: { paymentMethod } });
  },
  list(params = {}) {
    const qs = buildQuery(params);
    return request(`/orders${qs ? `?${qs}` : ""}`);
  },
  detail(orderId) {
    return request(`/orders/${orderId}`);
  },
  cancel(orderId) {
    return request(`/orders/${orderId}/cancel`, { method: "POST" });
  },
  requestRefund(orderId, reason) {
    return request(`/orders/${orderId}/refund`, { method: "POST", body: { reason } });
  },
  submitReview(orderId, payload) {
    return request(`/orders/${orderId}/reviews`, { method: "POST", body: payload });
  },
};

const PromotionAPI = {
  listActivities() {
    return request("/promotions/activities");
  },
  checkin() {
    return request("/promotions/checkin", { method: "POST" });
  },
  joinActivity(activityId) {
    return request(`/promotions/activities/${activityId}/join`, { method: "POST" });
  },
  myCoupons(status = "unused") {
    return request(`/promotions/coupons/my?${buildQuery({ status })}`);
  },
  listRewards() {
    return request("/promotions/rewards");
  },
  redeemReward(rewardId) {
    return request(`/promotions/rewards/${rewardId}/redeem`, { method: "POST" });
  },
  claimWeeklyCoupon() {
    return request("/promotions/weekly-coupon/claim", { method: "POST" });
  },
};

const UserAPI = {
  me() {
    return request("/users/me");
  },
  updateProfile(payload) {
    return request("/users/me", { method: "PUT", body: payload });
  },
  points(params = {}) {
    const qs = buildQuery(params);
    return request(`/users/me/points${qs ? `?${qs}` : ""}`);
  },
};

const AdminAPI = {
  books: {
    /** 后台图书列表 方法：GET 路径：/admin/books Query：{ keyword?, status?, page?, pageSize? } */
    async list(params = {}) {
      try {
        return await request(`/admin/books?${new URLSearchParams(params)}`);
      } catch (err) {
        console.warn("[AdminAPI.books.list] 使用模拟数据：", err.message);
        let list = MOCK_BOOKS;
        if (params.keyword) {
          const kw = String(params.keyword).trim().toLowerCase();
          list = list.filter(
            (b) => b.bookName.toLowerCase().includes(kw) || b.author.toLowerCase().includes(kw) || b.isbn.includes(kw)
          );
        }
        return mockDelay({ list, total: list.length });
      }
    },
    /**
     * 新增图书 方法：POST 路径：/admin/books 请求体：BookInfo 表 + BookItem 表字段（名称/作者/出版社/ISBN/简介/分类/价格/库存等）
     * 备选事件流 E-1 ISBN 重复：后端应返回非 0 的 code，例如 { code: 4001, message: "ISBN已存在，请勿重复添加" }，
     * request() 会将其转换为 Error 抛出；调用方（admin/books.js）需 catch 后通过 err.message 弹窗提示。
     */
    async create(payload) {
      try {
        return await request("/admin/books", { method: "POST", body: payload });
      } catch (err) {
        if (payload.isbn && MOCK_BOOKS.some((b) => b.isbn === payload.isbn)) {
          throw new Error("ISBN已存在，请勿重复添加");
        }
        console.warn("[AdminAPI.books.create] 使用模拟数据新增：", err.message);
        const category = MOCK_CATEGORIES.find((c) => String(c.categoryId) === String(payload.categoryId));
        const newBook = {
          bookItemId: Date.now(),
          bookInfoId: Date.now(),
          bookName: payload.bookName,
          author: payload.author,
          publisher: payload.publisher || "",
          isbn: payload.isbn || "",
          categoryId: payload.categoryId,
          categoryName: category ? category.categoryName : "",
          description: payload.description || "",
          price: payload.price,
          originPrice: payload.price,
          stock: payload.stock,
          salesCount: 0,
          storeId: 0,
          storeName: getCurrentUser()?.storeName || "本店",
          cover: "📘",
          publishDate: new Date().toISOString().slice(0, 10),
        };
        MOCK_BOOKS.unshift(newBook);
        return mockDelay({ ok: true, bookItemId: newBook.bookItemId });
      }
    },
    /** 修改图书 方法：PUT 路径：/admin/books/{bookItemId} */
    async update(bookItemId, payload) {
      try {
        return await request(`/admin/books/${bookItemId}`, { method: "PUT", body: payload });
      } catch (err) {
        const book = MOCK_BOOKS.find((b) => String(b.bookItemId) === String(bookItemId));
        if (book) {
          Object.assign(book, payload);
          if (payload.categoryId) {
            const category = MOCK_CATEGORIES.find((c) => String(c.categoryId) === String(payload.categoryId));
            if (category) book.categoryName = category.categoryName;
          }
        }
        return mockDelay({ ok: true });
      }
    },
    /** 下架/删除图书 方法：DELETE 路径：/admin/books/{bookItemId} */
    async remove(bookItemId) {
      try {
        return await request(`/admin/books/${bookItemId}`, { method: "DELETE" });
      } catch (err) {
        const idx = MOCK_BOOKS.findIndex((b) => String(b.bookItemId) === String(bookItemId));
        if (idx !== -1) MOCK_BOOKS.splice(idx, 1);
        return mockDelay({ ok: true });
      }
    },
    /** 后台管理员强制下架违规图书 方法：POST 路径：/admin/books/{bookItemId}/force-takedown */
    async forceTakedown(bookItemId, reason) {
      try {
        return await request(`/admin/books/${bookItemId}/force-takedown`, { method: "POST", body: { reason } });
      } catch (err) {
        const idx = MOCK_BOOKS.findIndex((b) => String(b.bookItemId) === String(bookItemId));
        if (idx !== -1) MOCK_BOOKS.splice(idx, 1);
        return mockDelay({ ok: true });
      }
    },
  },

  /* ---- 7.2 订单管理 4.3.2 Order Management ---- */
  orders: {
    list(params = {}) {
      const qs = buildQuery(params);
      return request(`/admin/orders${qs ? `?${qs}` : ""}`);
    },
    updateStatus(orderId, status) {
      return request(`/admin/orders/${orderId}/status`, { method: "PUT", body: { status } });
    },
    handleRefund(orderId, approve) {
      return request(`/admin/orders/${orderId}/refund/${approve ? "approve" : "reject"}`, { method: "POST" });
    },
  },
  users: {
    list(params = {}) {
      const qs = buildQuery(params);
      return request(`/admin/users${qs ? `?${qs}` : ""}`);
    },
    addToStoreBlacklist(userId, reason) {
      return request(`/admin/users/${userId}/blacklist`, { method: "POST", body: { reason } });
    },
    setStatus(userId, status) {
      return request(`/admin/users/${userId}/status`, { method: "PUT", body: { status } });
    },
  },
  stores: {
    list(params = {}) {
      const qs = buildQuery(params);
      return request(`/admin/stores${qs ? `?${qs}` : ""}`);
    },
    setStatus(storeId, status) {
      return request(`/admin/stores/${storeId}/status`, { method: "PUT", body: { status } });
    },
  },
  promotions: {
    /** 活动列表（后台视角） 方法：GET 路径：/admin/promotions/activities */
    async listActivities() {
      try {
        return await request("/admin/promotions/activities");
      } catch (err) {
        console.warn("[AdminAPI.promotions.listActivities] 使用模拟数据：", err.message);
        return mockDelay(MOCK_ACTIVITIES);
      }
    },
    /** 后台管理员新增/修改活动类型与内容 方法：POST /admin/promotions/activities 或 PUT /admin/promotions/activities/{id} */
    async saveActivity(activity) {
      try {
        const method = activity.activityId ? "PUT" : "POST";
        const path = activity.activityId ? `/admin/promotions/activities/${activity.activityId}` : "/admin/promotions/activities";
        return await request(path, { method, body: activity });
      } catch (err) {
        return mockDelay({ ok: true });
      }
    },
    /**
     * 书店管理员设置是否参与活动及参与书目/店铺券额度
     * 方法：POST 路径：/admin/promotions/activities/{activityId}/store-participation
     * 请求体：{ participate: boolean, bookItemIds: number[]（从本店库存图书下拉框多选得到）, couponAmount, couponQuantity }
     */
    async setStoreParticipation(activityId, payload) {
      try {
        return await request(`/admin/promotions/activities/${activityId}/store-participation`, {
          method: "POST",
          body: payload,
        });
      } catch (err) {
        return mockDelay({ ok: true });
      }
    },
    /** 后台管理员设置平台代金券额度与发放数量 方法：POST 路径：/admin/promotions/coupons */
    async savePlatformCoupon(payload) {
      try {
        return await request("/admin/promotions/coupons", { method: "POST", body: payload });
      } catch (err) {
        return mockDelay({ ok: true });
      }
    },
    /** 调整积分兑换奖品种类与数量 方法：PUT 路径：/admin/promotions/rewards/{rewardId} */
    async saveReward(reward) {
      try {
        const method = reward.rewardId ? "PUT" : "POST";
        const path = reward.rewardId ? `/admin/promotions/rewards/${reward.rewardId}` : "/admin/promotions/rewards";
        return await request(path, { method, body: reward });
      } catch (err) {
        return mockDelay({ ok: true });
      }
    },
  },
  statistics: {
    overview(params = {}) {
      const qs = buildQuery(params);
      return request(`/admin/statistics/overview${qs ? `?${qs}` : ""}`);
    },
    riskStores() {
      return request("/admin/statistics/risk-stores");
    },
    exportUrl(params = {}) {
      return `${API_BASE_URL}/admin/statistics/export?${buildQuery(params)}`;
    },
  },
  recommendation: {
    settings() {
      return request("/admin/recommendation/settings");
    },
    update(payload) {
      return request("/admin/recommendation/settings", { method: "PUT", body: payload });
    },
  },
};
