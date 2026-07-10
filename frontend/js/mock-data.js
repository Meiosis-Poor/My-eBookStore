/**
 * mock-data.js
 * ------------------------------------------------------------------
 * 【仅供前端独立开发/演示使用的模拟数据与模拟接口延迟】
 * 后端接口就绪后，本文件不再被 api.js 引用，可直接整体删除。
 * 数据结构字段命名参考《230711_9组_第二次需求报告》"数据库设计" 一章中的
 * book_infos / book_items / orders / coupons / point_rewards 等表设计，
 * 并在 JSON 中转换为小驼峰命名，便于前端使用。
 * ------------------------------------------------------------------
 */

/** 模拟网络延迟，让 loading 骨架屏等交互效果可被观察到 */
function mockDelay(data, ms = 300) {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms));
}

const MOCK_CATEGORIES = [
  { categoryId: 1, categoryName: "文学小说" },
  { categoryId: 2, categoryName: "经管励志" },
  { categoryId: 3, categoryName: "科技科普" },
  { categoryId: 4, categoryName: "计算机" },
  { categoryId: 5, categoryName: "少儿教育" },
  { categoryId: 6, categoryName: "历史人文" },
  { categoryId: 7, categoryName: "艺术设计" },
];

const MOCK_ICONS = ["📘", "📗", "📙", "📕", "📔", "📓"];

function buildMockBooks() {
  const titles = [
    "百年孤独", "活着", "三体", "人类简史", "小王子", "白夜行",
    "深入理解计算机系统", "算法导论", "клеан代码整洁之道", "设计模式之美",
    "苏东坡传", "明朝那些事儿", "梦的解析", "非暴力沟通", "刻意练习",
    "断舍离", "把时间当作朋友", "沉默的大多数", "平凡的世界", "围城",
  ];
  return titles.map((title, idx) => {
    const categoryId = MOCK_CATEGORIES[idx % MOCK_CATEGORIES.length].categoryId;
    return {
      bookItemId: 1000 + idx,
      bookInfoId: 2000 + idx,
      bookName: title,
      author: ["余华", "刘慈欣", "东野圭吾", "尤瓦尔·赫拉利", "钱钟书"][idx % 5],
      publisher: "人民文学出版社",
      isbn: `978-7-${100000 + idx}`,
      categoryId,
      categoryName: MOCK_CATEGORIES.find((c) => c.categoryId === categoryId).categoryName,
      description:
        "这是一段用于前端演示的图书简介占位文本，实际内容将由后端接口 GET /api/books/{id} 返回，包含完整的图书简介、目录与编辑推荐语等信息。",
      price: Number((19.9 + idx * 3.3).toFixed(2)),
      originPrice: Number((29.9 + idx * 3.3).toFixed(2)),
      stock: (idx * 7) % 40,
      salesCount: (idx * 53) % 900,
      storeId: 100 + (idx % 4),
      storeName: ["博文书店", "启明书城", "墨香书屋", "远方书局"][idx % 4],
      cover: MOCK_ICONS[idx % MOCK_ICONS.length],
      publishDate: "2022-05-01",
    };
  });
}

const MOCK_BOOKS = buildMockBooks();

/**
 * 店铺主页展示信息，storeId 与 MOCK_BOOKS 中 book.storeId 对应，供 StoreAPI 使用。
 * 通过 localStorage 持久化：书店管理员在“店铺信息设置”页保存后，即使跳转到其他
 * 页面（整页加载，mock-data.js 会重新执行）也能读到修改后的内容，行为更接近真实后端。
 */
const STORE_PROFILES_STORAGE_KEY = "ebs_mock_store_profiles";
const DEFAULT_STORE_PROFILES = [
  { storeId: 100, storeName: "博文书店", description: "深耕文学与人文社科领域十余年，甄选经典与畅销好书。", createdTime: "2025-09-01" },
  { storeId: 101, storeName: "启明书城", description: "专注科技与计算机类图书，紧跟技术前沿与经典教材。", createdTime: "2025-10-11" },
  { storeId: 102, storeName: "墨香书屋", description: "主打设计、艺术与生活方式类图书，精致小而美。", createdTime: "2025-11-02" },
  { storeId: 103, storeName: "远方书局", description: "覆盖少儿教育与历史人文，陪伴各年龄段读者成长。", createdTime: "2025-08-15" },
];

function loadMockStoreProfiles() {
  try {
    const raw = localStorage.getItem(STORE_PROFILES_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (err) {
    /* 忽略解析失败，回退到默认值 */
  }
  return DEFAULT_STORE_PROFILES.map((s) => ({ ...s }));
}

const MOCK_STORE_PROFILES = loadMockStoreProfiles();

/** 供 api.js 在店铺信息保存成功后调用，把最新数据写回 localStorage */
function persistMockStoreProfiles() {
  localStorage.setItem(STORE_PROFILES_STORAGE_KEY, JSON.stringify(MOCK_STORE_PROFILES));
}

/**
 * 用户收货地址簿，供 AddressAPI 及确认订单页“更换地址”功能使用。
 * 通过 localStorage 持久化：新增/编辑/删除地址后，即使跳转到其他页面
 * （整页加载，mock-data.js 会重新执行）也能读到最新数据。
 */
const ADDRESSES_STORAGE_KEY = "ebs_mock_addresses";
const DEFAULT_ADDRESSES = [
  { addressId: 1, recipientName: "周同学", phone: "13800008888", addressDetail: "江苏省南京市栖霞区仙林大道163号", isDefault: true },
  { addressId: 2, recipientName: "周同学（公司）", phone: "13900001234", addressDetail: "江苏省南京市建邺区庐山路88号", isDefault: false },
];

function loadMockAddresses() {
  try {
    const raw = localStorage.getItem(ADDRESSES_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (err) {
    /* 忽略解析失败，回退到默认值 */
  }
  return DEFAULT_ADDRESSES.map((a) => ({ ...a }));
}

const MOCK_ADDRESSES = loadMockAddresses();

/** 供 api.js 在地址新增/编辑/删除成功后调用，把最新数据写回 localStorage */
function persistMockAddresses() {
  localStorage.setItem(ADDRESSES_STORAGE_KEY, JSON.stringify(MOCK_ADDRESSES));
}

/**
 * 用户搜索历史，供搜索框下拉展示，真实场景下应由后端按用户维度返回。
 * 通过 localStorage 持久化，行为与地址簿 / 店铺信息一致。
 */
const SEARCH_HISTORY_STORAGE_KEY = "ebs_mock_search_history";

function loadMockSearchHistory() {
  try {
    const raw = localStorage.getItem(SEARCH_HISTORY_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (err) {
    /* 忽略解析失败，回退到空列表 */
  }
  return [];
}

let MOCK_SEARCH_HISTORY = loadMockSearchHistory();

function persistMockSearchHistory() {
  localStorage.setItem(SEARCH_HISTORY_STORAGE_KEY, JSON.stringify(MOCK_SEARCH_HISTORY));
}

const MOCK_COUPONS = [
  { couponId: 1, couponName: "新人无门槛券", couponType: "platform", amount: 5, minAmount: 0, validEnd: "2026-08-31" },
  { couponId: 2, couponName: "满99减15", couponType: "platform", amount: 15, minAmount: 99, validEnd: "2026-08-15" },
  { couponId: 3, couponName: "博文书店满50减10", couponType: "store", storeName: "博文书店", amount: 10, minAmount: 50, validEnd: "2026-07-20" },
];

const MOCK_REWARDS = [
  { rewardId: 1, rewardName: "5元无门槛代金券", rewardType: "coupon", requiredPoints: 200, requiredLevel: 1, stock: 999 },
  { rewardId: 2, rewardName: "帆布书袋", rewardType: "physical", requiredPoints: 500, requiredLevel: 1, stock: 30 },
  { rewardId: 3, rewardName: "10元无门槛代金券", rewardType: "coupon", requiredPoints: 800, requiredLevel: 2, stock: 999 },
  { rewardId: 4, rewardName: "限量书签套装", rewardType: "physical", requiredPoints: 1200, requiredLevel: 3, stock: 12 },
];

/** 图书详情页“用户评价”演示数据，供 BookAPI.detail() 在无后端时的模拟兜底使用 */
const MOCK_REVIEWS = [
  { bookItemId: 1000, userName: "reader_001", rating: 5, content: "经典之作，值得反复阅读。", createdTime: "2026-06-20 10:00:00" },
  { bookItemId: 1000, userName: "reader_002", rating: 4, content: "翻译流畅，包装也很好。", createdTime: "2026-06-25 15:30:00" },
  { bookItemId: 1002, userName: "reader_001", rating: 5, content: "科幻迷不容错过。", createdTime: "2026-07-01 09:12:00" },
];

/** 后台“店铺管理”共享的模拟数据源，供 AdminAPI.stores 读写复用，保证封禁/开放操作后再次查询时状态一致 */
const MOCK_STORES = [
  { storeId: 100, storeName: "博文书店", status: "active", createdTime: "2025-09-01", bookCount: 128, orderCount: 542 },
  { storeId: 101, storeName: "启明书城", status: "active", createdTime: "2025-10-11", bookCount: 96, orderCount: 310 },
  { storeId: 102, storeName: "墨香书屋", status: "banned", createdTime: "2025-11-02", bookCount: 40, orderCount: 58 },
];

/** 后台“用户管理”共享的模拟数据源，供 AdminAPI.users 读写复用，保证封禁/解封操作后再次查询时状态一致 */
const MOCK_ADMIN_USERS = [
  { userId: 1, userName: "reader_001", nickname: "爱读书的小周", status: "active", registeredAt: "2026-01-12" },
  { userId: 2, userName: "reader_002", nickname: "书虫小李", status: "active", registeredAt: "2026-02-03" },
  { userId: 3, userName: "reader_003", nickname: "匿名用户", status: "banned", registeredAt: "2026-03-19" },
];

const MOCK_ACTIVITIES = [
  { activityId: 1, activityName: "连续签到7天赢好礼", activityType: "checkin", description: "连续签到满7天可领取平台无门槛代金券。", startTime: "2026-07-01", endTime: "2026-07-31", status: "ongoing" },
  { activityId: 2, activityName: "暑期读书季·答题赢券", activityType: "quiz", description: "参与知识问答小游戏，答对即可获得部分商家专属代金券。", startTime: "2026-07-01", endTime: "2026-08-31", status: "ongoing" },
  { activityId: 3, activityName: "指定书目5折促销", activityType: "discount", description: "部分合作书店对指定书目提供5折优惠，先到先得。", startTime: "2026-06-20", endTime: "2026-07-10", status: "ongoing" },
];

/** 订单状态 -> 中文展示文案的统一映射，供 mock 写操作更新状态时同步刷新 statusLabel */
const ORDER_STATUS_LABELS = {
  pending_payment: "待支付",
  shipped: "待收货",
  completed: "已完成",
  refunding: "退款中",
  cancelled: "已取消",
  refunded: "已退款",
};

function buildMockOrders() {
  const statuses = [
    { orderStatus: "pending_payment", paymentStatus: "unpaid", label: "待支付" },
    { orderStatus: "completed", paymentStatus: "paid", label: "已完成" },
    { orderStatus: "shipped", paymentStatus: "paid", label: "待收货" },
    { orderStatus: "refunding", paymentStatus: "paid", label: "退款中" },
  ];
  return Array.from({ length: 8 }).map((_, idx) => {
    const st = statuses[idx % statuses.length];
    const items = MOCK_BOOKS.slice(idx, idx + 1 + (idx % 2)).map((b) => ({
      bookItemId: b.bookItemId,
      bookName: b.bookName,
      cover: b.cover,
      unitPrice: b.price,
      quantity: 1 + (idx % 2),
    }));
    const totalAmount = items.reduce((sum, it) => sum + it.unitPrice * it.quantity, 0);
    return {
      orderId: 5000 + idx,
      orderNo: `NO${20260700000 + idx}`,
      orderStatus: st.orderStatus,
      paymentStatus: st.paymentStatus,
      statusLabel: st.label,
      totalAmount: Number(totalAmount.toFixed(2)),
      discountAmount: 5,
      actualAmount: Number((totalAmount - 5).toFixed(2)),
      createdTime: `2026-07-0${(idx % 5) + 1} 14:${20 + idx}:00`,
      // 收货信息为下单时的快照，与地址簿解耦，故此处使用默认地址演示，与 checkout.js 中的行为保持一致
      receiverName: MOCK_ADDRESSES[0].recipientName,
      receiverPhone: MOCK_ADDRESSES[0].phone,
      receiverAddress: MOCK_ADDRESSES[0].addressDetail,
      items,
    };
  });
}

const MOCK_ORDERS = buildMockOrders();

const MOCK_CURRENT_USER = {
  userId: 1,
  userName: "reader_001",
  nickname: "爱读书的小周",
  userType: "customer",
  level: 3,
  totalPoints: 1380,
  availablePoints: 860,
  continuousCheckinDays: 4,
};

const MOCK_STATS = {
  salesTrend: [
    { label: "07-29", value: 3200 },
    { label: "07-30", value: 4100 },
    { label: "07-31", value: 3800 },
    { label: "08-01", value: 5200 },
    { label: "08-02", value: 4600 },
    { label: "08-03", value: 6100 },
    { label: "08-04", value: 5300 },
  ],
  hotBooks: MOCK_BOOKS.slice(0, 5).map((b) => ({ bookName: b.bookName, salesCount: b.salesCount })),
  kpi: {
    todaySales: 6180.5,
    todayOrders: 76,
    totalUsers: 12480,
    totalStores: 236,
  },
};
