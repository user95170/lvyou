<template>
  <div class="page">
    <section class="block">
      <div class="section-header">
        <div>
          <h2>系统监控</h2>
          <p class="hint">查看资源规模、用户交互、推荐策略和路线服务运行指标。</p>
        </div>
        <button
          type="button"
          data-testid="monitor-refresh"
          @click="loadOverview"
          :disabled="loading"
        >
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <div v-if="error" class="error" data-testid="monitor-error">{{ error }}</div>

      <div v-if="overview" class="status-row">
        <div class="status-pill" data-testid="monitor-status">
          <span class="status-dot"></span>
          服务状态：{{ overview.health?.status || 'unknown' }}
        </div>
        <span class="hint">路线指标运行 {{ formatSeconds(overview.route?.uptime_sec) }}</span>
      </div>
    </section>

    <section v-if="overview" class="block">
      <h3>资源数据</h3>
      <div class="metric-grid">
        <div class="metric" data-testid="monitor-resource-scenic">
          <span>景点</span>
          <strong>{{ numberValue(overview.resources?.scenic_spots) }}</strong>
        </div>
        <div class="metric" data-testid="monitor-resource-hotels">
          <span>酒店</span>
          <strong>{{ numberValue(overview.resources?.hotels) }}</strong>
        </div>
        <div class="metric" data-testid="monitor-resource-foods">
          <span>美食</span>
          <strong>{{ numberValue(overview.resources?.foods) }}</strong>
        </div>
        <div class="metric" data-testid="monitor-resource-content">
          <span>标准化内容</span>
          <strong>{{ numberValue(overview.resources?.content_rows) }}</strong>
        </div>
      </div>
    </section>

    <section v-if="overview" class="block">
      <h3>用户与交互</h3>
      <div class="metric-grid">
        <div class="metric" data-testid="monitor-user-count">
          <span>用户</span>
          <strong>{{ numberValue(overview.users?.users) }}</strong>
        </div>
        <div class="metric">
          <span>画像</span>
          <strong>{{ numberValue(overview.users?.profiles) }}</strong>
        </div>
        <div class="metric" data-testid="monitor-rating-count">
          <span>评分</span>
          <strong>{{ numberValue(overview.users?.ratings) }}</strong>
        </div>
        <div class="metric" data-testid="monitor-behavior-count">
          <span>行为日志</span>
          <strong>{{ numberValue(overview.users?.behavior_logs) }}</strong>
        </div>
        <div class="metric">
          <span>行程</span>
          <strong>{{ numberValue(overview.users?.trips) }}</strong>
        </div>
      </div>
    </section>

    <section v-if="overview" class="block">
      <div class="section-header compact">
        <h3>推荐运行</h3>
        <span class="hint" data-testid="monitor-recommend-request-count">
          请求 {{ numberValue(overview.recommendation?.request_count) }} 次
        </span>
      </div>
      <div class="split-grid">
        <div>
          <h4>策略分布</h4>
          <ul class="plain-list">
            <li v-for="item in strategyItems" :key="item.name">
              <span>{{ item.name }}</span>
              <strong>{{ item.count }}</strong>
            </li>
            <li v-if="!strategyItems.length" class="empty">暂无策略计数</li>
          </ul>
        </div>
        <div>
          <h4>回退原因</h4>
          <ul class="plain-list">
            <li v-for="item in fallbackItems" :key="item.name">
              <span>{{ item.name }}</span>
              <strong>{{ item.count }}</strong>
            </li>
            <li v-if="!fallbackItems.length" class="empty">暂无回退记录</li>
          </ul>
        </div>
      </div>
    </section>

    <section v-if="overview" class="block">
      <h3>路线服务</h3>
      <div class="metric-grid">
        <div class="metric" data-testid="monitor-route-options-total">
          <span>路线方案</span>
          <strong>{{ numberValue(routeSummary?.route_options_total) }}</strong>
        </div>
        <div class="metric">
          <span>AMap 成功</span>
          <strong>{{ numberValue(routeSummary?.amap_success_total) }}</strong>
        </div>
        <div class="metric">
          <span>AMap 失败</span>
          <strong>{{ numberValue(routeSummary?.amap_fail_total) }}</strong>
        </div>
        <div class="metric">
          <span>成功率</span>
          <strong>{{ percentValue(routeSummary?.amap_success_rate) }}</strong>
        </div>
      </div>
      <p class="hint">
        回退：Distance API {{ numberValue(routeSummary?.fallback_amap_distance) }} 次，Haversine
        {{ numberValue(routeSummary?.fallback_haversine) }} 次。
      </p>
      <p class="hint">
        缓存：命中 {{ numberValue(routeSummary?.amap_cache_hit) }}，未命中
        {{ numberValue(routeSummary?.amap_cache_miss) }}，限流跳过
        {{ numberValue(routeSummary?.amap_rate_limited_skips) }}。
      </p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { getMonitorOverview } from '../api/monitor';

const overview = ref(null);
const loading = ref(false);
const error = ref('');

const routeSummary = computed(() => overview.value?.route?.summary || {});

const strategyItems = computed(() => toSortedItems(overview.value?.recommendation?.strategy_counts));
const fallbackItems = computed(() => toSortedItems(overview.value?.recommendation?.fallback_counts));

function toSortedItems(source) {
  return Object.entries(source || {})
    .map(([name, count]) => ({ name, count: Number(count) || 0 }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

function numberValue(value) {
  return Number.isFinite(Number(value)) ? Number(value).toLocaleString('zh-CN') : '0';
}

function percentValue(value) {
  if (!Number.isFinite(Number(value))) {
    return '-';
  }
  return `${Math.round(Number(value) * 100)}%`;
}

function formatSeconds(value) {
  if (!Number.isFinite(Number(value))) {
    return '-';
  }
  return `${Math.max(0, Number(value))} 秒`;
}

async function loadOverview() {
  loading.value = true;
  error.value = '';
  try {
    const resp = await getMonitorOverview();
    overview.value = resp.data || null;
  } catch (e) {
    error.value = e.response?.data?.error || '加载监控数据失败';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadOverview();
});
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.block {
  background: #ffffff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.section-header.compact {
  align-items: center;
}

.hint {
  margin: 4px 0 0;
  font-size: 13px;
  color: #6b7280;
}

button {
  padding: 8px 12px;
  border-radius: 4px;
  border: none;
  background: #2563eb;
  color: #ffffff;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.error {
  margin-top: 12px;
  color: #b91c1c;
  font-size: 13px;
}

.status-row {
  margin-top: 12px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  background: #ecfdf5;
  color: #047857;
  font-size: 13px;
  font-weight: 600;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #10b981;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.metric {
  min-height: 80px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 8px;
}

.metric span {
  font-size: 13px;
  color: #4b5563;
}

.metric strong {
  font-size: 26px;
  line-height: 1;
}

.split-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

h4 {
  margin: 0 0 8px;
}

.plain-list {
  list-style: none;
  padding: 0;
  margin: 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.plain-list li {
  min-height: 38px;
  padding: 8px 10px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #ffffff;
  font-size: 14px;
}

.plain-list li:last-child {
  border-bottom: none;
}

.plain-list .empty {
  color: #6b7280;
}

@media (max-width: 768px) {
  .section-header {
    flex-direction: column;
    align-items: stretch;
  }

  .metric strong {
    font-size: 22px;
  }
}
</style>
