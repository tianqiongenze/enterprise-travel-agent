const { getBaseUrl, REQUEST_TIMEOUT, RETRY_COUNT } = require('./config');

function createTraceId() {
  return `mini-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function mapHttpError(statusCode, data) {
  if (statusCode === 400) {
    return new Error(`请求参数错误: ${JSON.stringify(data)}`);
  }
  if (statusCode === 401 || statusCode === 403) {
    return new Error('鉴权失败或策略拒绝');
  }
  if (statusCode === 429) {
    return new Error('请求频率过高，请稍后重试');
  }
  if (statusCode >= 500) {
    return new Error(`服务端异常(${statusCode})，请稍后重试`);
  }
  return new Error(`请求失败(${statusCode}): ${JSON.stringify(data)}`);
}

function doRequest(data, retryLeft) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${BASE_URL}/api/v1/travel/recommend`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json',
        'X-Trace-Id': createTraceId(),
      },
      data,
      timeout: REQUEST_TIMEOUT,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        if ((res.statusCode === 502 || res.statusCode === 503 || res.statusCode === 504) && retryLeft > 0) {
          doRequest(data, retryLeft - 1).then(resolve).catch(reject);
          return;
        }
        reject(mapHttpError(res.statusCode, res.data));
      },
      fail: (error) => {
        if (retryLeft > 0) {
          doRequest(data, retryLeft - 1).then(resolve).catch(reject);
          return;
        }
        reject(new Error(`网络不可用或网关不可达: ${JSON.stringify(error)}`));
      },
    });
  });
}

function postRecommend(data) {
  return doRequest(data, RETRY_COUNT);
}


function buildHeaders() {
  const headers = { 'content-type': 'application/json' };
  try {
    const token = wx.getStorageSync('travel_auth_token');
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  } catch (storageError) {
    // no token available; gateway will reject with 401
  }
  return headers;
}

function saveToken(token) {
  try {
    wx.setStorageSync('travel_auth_token', token || '');
  } catch (storageError) {
    // ignore storage failures
  }
}

module.exports = {
  saveToken,
  buildHeaders,
  postRecommend,
};
