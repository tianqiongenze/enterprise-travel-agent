Page({
  data: {
    items: []
  },

  onShow() {
    const data = wx.getStorageSync('miniapp_analytics_events') || [];
    // WXML cannot call global functions like JSON.stringify; precompute the
    // display text per row before setData.
    const items = [...data]
      .reverse()
      .map((item) => ({
        ...item,
        payloadText: JSON.stringify(item.payload || {}),
      }));
    this.setData({ items });
  },
});
