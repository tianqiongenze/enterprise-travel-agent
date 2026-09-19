// API 网关地址：生产包必须通过 build 配置或 storage 覆盖，禁止携带 localhost 上线。
const DEFAULT_BASE_URL = 'https://api.travel.example.com';
const REQUEST_TIMEOUT = 20000;
const RETRY_COUNT = 2;

function getBaseUrl() {
  try {
    const overridden = wx.getStorageSync('travel_api_base_url');
    if (typeof overridden === 'string' && overridden.trim()) {
      return overridden.trim().replace(/\/+$/, '');
    }
  } catch (storageError) {
    // storage 不可用时退回默认值
  }
  return DEFAULT_BASE_URL;
}

module.exports = {
  get DEFAULT_BASE_URL() {
    return DEFAULT_BASE_URL;
  },
  REQUEST_TIMEOUT,
  RETRY_COUNT,
  getBaseUrl,
};
