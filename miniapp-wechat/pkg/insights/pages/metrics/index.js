Page({
  data: {
    items: []
  },

  onShow() {
    const data = wx.getStorageSync('miniapp_analytics_events') || [];
    this.setData({ items: data.reverse() });
  }
});
