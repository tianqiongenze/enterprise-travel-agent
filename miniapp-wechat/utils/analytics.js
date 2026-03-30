function track(eventName, payload) {
  const event = {
    eventName,
    payload,
    timestamp: new Date().toISOString(),
  };
  try {
    const key = 'miniapp_analytics_events';
    const existing = wx.getStorageSync(key) || [];
    const next = [...existing, event].slice(-200);
    wx.setStorageSync(key, next);
  } catch (error) {
    console.warn('analytics track failed', error);
  }
}

module.exports = {
  track,
};
