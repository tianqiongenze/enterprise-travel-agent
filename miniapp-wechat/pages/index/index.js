const { postRecommend } = require('../../utils/api');
const { track } = require('../../utils/analytics');

function newConversationId() {
  return `conv-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

Page({
  data: {
    loading: false,
    error: '',
    response: '',
    cards: {
      traceId: '',
      aiRationale: '',
      hotels: [],
      transports: [],
      itinerary: []
    },
    form: {
      tenantId: 'tenant-demo',
      userId: 'user-mini',
      policyId: 'policy-default',
      conversationId: newConversationId(),
      idempotencyKey: `idem-${Date.now()}`,
      city: '北京',
      days: '3',
      budget: '3000',
      travelers: '2',
      preferences: 'family,budget',
      maxAgentSteps: '10',
      maxToolCalls: '10',
      allowedTools: 'search_hotels,search_transports,search_attractions'
    }
  },

  onInput(event) {
    const key = event.currentTarget.dataset.key;
    const value = event.detail.value;
    this.setData({
      [`form.${key}`]: value
    });
  },

  async onSubmit() {
    const { form } = this.data;
    const payload = {
      tenantId: form.tenantId,
      userId: form.userId,
      policyId: form.policyId,
      conversationId: form.conversationId,
      idempotencyKey: form.idempotencyKey,
      city: form.city,
      days: Number(form.days),
      budget: Number(form.budget),
      travelers: Number(form.travelers),
      preferences: form.preferences.split(',').map((item) => item.trim()).filter(Boolean),
      maxAgentSteps: Number(form.maxAgentSteps),
      maxToolCalls: Number(form.maxToolCalls),
      allowedTools: form.allowedTools.split(',').map((item) => item.trim()).filter(Boolean)
    };

    if (!payload.tenantId || !payload.userId || !payload.policyId || !payload.conversationId || !payload.idempotencyKey || !payload.city) {
      this.setData({ error: '必填字段不能为空' });
      return;
    }
    if (!Number.isFinite(payload.days) || payload.days < 1) {
      this.setData({ error: 'days 必须大于等于 1' });
      return;
    }
    if (!Number.isFinite(payload.budget) || payload.budget < 1) {
      this.setData({ error: 'budget 必须大于等于 1' });
      return;
    }
    if (!Number.isFinite(payload.travelers) || payload.travelers < 1) {
      this.setData({ error: 'travelers 必须大于等于 1' });
      return;
    }
    if (!Number.isFinite(payload.maxAgentSteps) || payload.maxAgentSteps < 1) {
      this.setData({ error: 'maxAgentSteps 必须大于等于 1' });
      return;
    }
    if (!Number.isFinite(payload.maxToolCalls) || payload.maxToolCalls < 1) {
      this.setData({ error: 'maxToolCalls 必须大于等于 1' });
      return;
    }

    if (payload.allowedTools.length === 0) {
      this.setData({ error: 'allowedTools cannot be empty' });
      return;
    }

    this.setData({ loading: true, error: '', response: '' });
    track('recommend_submit', {
      city: payload.city,
      travelers: payload.travelers,
      days: payload.days,
    });
    try {
      const data = await postRecommend(payload);
      track('recommend_success', {
        traceId: data.traceId || '',
        hotels: Array.isArray(data.hotelOptions) ? data.hotelOptions.length : 0,
        transports: Array.isArray(data.transportOptions) ? data.transportOptions.length : 0,
      });
      this.setData({
        response: JSON.stringify(data, null, 2),
        cards: {
          traceId: data.traceId || '',
          aiRationale: data.aiRationale || '',
          hotels: Array.isArray(data.hotelOptions) ? data.hotelOptions : [],
          transports: Array.isArray(data.transportOptions) ? data.transportOptions : [],
          itinerary: Array.isArray(data.itinerary) ? data.itinerary : []
        }
      });
    } catch (error) {
      track('recommend_error', {
        message: String(error && error.message ? error.message : error),
      });
      this.setData({ error: String(error && error.message ? error.message : error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  goMetrics() {
    wx.navigateTo({
      url: '/pkg/insights/pages/metrics/index'
    });
  }
});
