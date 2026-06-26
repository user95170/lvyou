<template>
  <div class="page">
    <h2>个性化推荐</h2>
    <p class="hint">
      结合你的偏好与多源数据，为你推荐内蒙古的景点、酒店与美食。
    </p>

    <div
      v-if="scenicMeta && scenicMeta.cold_start && currentUserId()"
      class="cold-start-banner"
      data-testid="home-cold-start-banner"
    >
      <p class="cold-start-text">
        你的评分和偏好还比较少，推荐可能不够精准。先去浏览打分或完善偏好吧。
      </p>
      <div class="cold-start-actions">
        <router-link
          :to="{ path: '/browse', query: { mode: 'cold_start' } }"
          class="link-button"
          data-testid="home-cold-start-browse-link"
        >
          去浏览打分
        </router-link>
        <router-link to="/profile" class="link-button secondary">完善偏好</router-link>
      </div>
    </div>

    <section class="block">
      <header class="block-header">
        <h3>推荐景点</h3>
        <div class="block-header-right">
          <button type="button" @click="fetchScenic" :disabled="loadingScenic">
            {{ loadingScenic ? '加载中...' : '刷新' }}
          </button>
        </div>
      </header>
      <p v-if="scenicMeta" class="strategy-meta">
        当前策略：{{ scenicMeta.strategy || scenicStrategy || 'multi_source' }}
      </p>
      <details v-if="currentUserId()" class="advanced-strategy">
        <summary>高级策略</summary>
        <div class="strategy-select">
          <label>
            策略
            <select v-model="scenicStrategy" :disabled="loadingScenic">
              <option value="">自动</option>
              <option value="popular">热门</option>
              <option value="profile">画像</option>
              <option value="cf">CF</option>
              <option value="mf">MF</option>
              <option value="hybrid">混合</option>
            </select>
          </label>
          <p class="advanced-tip">评分较少时 CF/MF/混合 会自动回退到热门或画像。</p>
        </div>
        <div class="metrics-block">
          <button type="button" @click="fetchMetrics" :disabled="loadingMetrics">
            {{ loadingMetrics ? '加载统计中...' : '查看推荐统计' }}
          </button>
          <p v-if="metricsError" class="error">{{ metricsError }}</p>
          <div v-if="metrics">
            <p class="metrics-summary">推荐请求数：{{ metrics.request_count ?? 0 }}</p>
            <div class="metrics-section">
              <strong>策略分布</strong>
              <ul>
                <li v-for="(count, name) in metrics.strategy_counts || {}" :key="name">
                  {{ name }}：{{ count }}
                </li>
              </ul>
            </div>
            <div class="metrics-section">
              <strong>回退统计</strong>
              <ul>
                <li v-for="(count, name) in metrics.fallback_counts || {}" :key="name">
                  {{ name }}：{{ count }}
                </li>
              </ul>
            </div>
          </div>
        </div>
      </details>
      <div v-if="scenicError" class="error">{{ scenicError }}</div>
      <ul v-else class="card-list" data-testid="home-scenic-list">
        <li
          v-for="item in scenicItems"
          :key="item.id"
          class="card"
          data-testid="home-scenic-card"
          @click="handleScenicClick(item, $event)"
        >
          <h4>{{ item.name }}</h4>
          <p class="sub">{{ item.city }} · 评分 {{ item.rating_avg ?? '暂无' }}</p>
          <p v-if="item.reasons && item.reasons.length" class="reason">
            推荐理由：{{ item.reasons.slice(0, 3).join('·') }}
          </p>
          <p class="desc">{{ item.description?.slice(0, 60) || '暂无更多介绍' }}</p>
          <div class="card-actions">
            <button
              type="button"
              class="btn-add-trip"
              data-testid="home-add-trip-btn"
              @click="handleAddToTrip(item)"
            >
              加入行程
            </button>
          </div>
        </li>
      </ul>
    </section>

    <section class="block">
      <header class="block-header">
        <h3>推荐酒店</h3>
        <button type="button" @click="fetchHotels" :disabled="loadingHotels">
          {{ loadingHotels ? '加载中...' : '刷新' }}
        </button>
      </header>
      <div v-if="hotelError" class="error">{{ hotelError }}</div>
      <ul v-else class="card-list">
        <li v-for="item in hotelItems" :key="item.id" class="card">
          <h4>{{ item.name }}</h4>
          <p class="sub">
            {{ item.city }} · 均价 {{ item.avg_price ?? '暂无' }} · 评分 {{ item.rating_avg ?? '暂无' }}
          </p>
          <p class="desc">{{ item.tags || '暂无更多介绍' }}</p>
        </li>
      </ul>
    </section>

    <section class="block">
      <header class="block-header">
        <h3>推荐美食</h3>
        <button type="button" @click="fetchFoods" :disabled="loadingFoods">
          {{ loadingFoods ? '加载中...' : '刷新' }}
        </button>
      </header>
      <div v-if="foodError" class="error">{{ foodError }}</div>
      <ul v-else class="card-list">
        <li v-for="item in foodItems" :key="item.id" class="card">
          <h4>{{ item.name }}</h4>
          <p class="sub">
            {{ item.city }} · {{ item.cuisine_type || '特色美食' }} · 人均 {{ item.avg_price ?? '暂无' }}
          </p>
          <p class="desc">{{ item.tags || '暂无更多介绍' }}</p>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { getCurrentUser } from '../utils/user';
import {
  getScenicRecommendations,
  getHotelRecommendations,
  getFoodRecommendations,
  getRecommendMetrics,
} from '../api/recommend';
import { logBehavior } from '../api/behavior';
import { addPendingSpot } from '../utils/trip';
import { useRouter } from 'vue-router';
import { toast } from '../utils/toast';

const scenicItems = ref([]);
const scenicStrategy = ref('');
const scenicMeta = ref(null);
const hotelItems = ref([]);
const foodItems = ref([]);

const metrics = ref(null);
const loadingMetrics = ref(false);
const metricsError = ref('');

const router = useRouter();

const loadingScenic = ref(false);
const loadingHotels = ref(false);
const loadingFoods = ref(false);

const scenicError = ref('');
const hotelError = ref('');
const foodError = ref('');

function currentUserId() {
  const u = getCurrentUser();
  return u?.id ?? null;
}

async function handleScenicClick(item, event) {
  if (event.target.closest('.card-actions')) {
    return;
  }

  const uid = currentUserId();
  try {
    await logBehavior({
      user_id: uid,
      target_type: 'scenic_spot',
      target_id: item.id,
      behavior_type: 'click',
      device: 'web',
    });
  } catch (e) {
    console.error('行为埋点失败', e);
  }
}

function handleAddToTrip(item) {
  const success = addPendingSpot(item);
  if (success) {
    toast.success(`已把"${item.name}"加入待规划列表`);
  } else {
    toast.warning(`"${item.name}"已在待规划列表中`);
  }
}

function goToTrip() {
  router.push('/route');
}

async function fetchScenic() {
  loadingScenic.value = true;
  scenicError.value = '';
  try {
    const params = { limit: 6 };
    const uid = currentUserId();
    if (uid) params.user_id = uid;
    if (scenicStrategy.value) params.strategy = scenicStrategy.value;
    const resp = await getScenicRecommendations(params);
    scenicItems.value = resp.data.items || [];
    scenicMeta.value = resp.data.meta || null;
  } catch (e) {
    const errorMsg = e.response?.data?.error || '加载推荐景点失败';
    scenicError.value = errorMsg;
    toast.error(errorMsg);
  } finally {
    loadingScenic.value = false;
  }
}

async function fetchHotels() {
  loadingHotels.value = true;
  hotelError.value = '';
  try {
    const params = { limit: 6 };
    const uid = currentUserId();
    if (uid) params.user_id = uid;
    const resp = await getHotelRecommendations(params);
    hotelItems.value = resp.data.items || [];
  } catch (e) {
    hotelError.value = e.response?.data?.error || '加载酒店推荐失败';
  } finally {
    loadingHotels.value = false;
  }
}

async function fetchFoods() {
  loadingFoods.value = true;
  foodError.value = '';
  try {
    const params = { limit: 6 };
    const uid = currentUserId();
    if (uid) params.user_id = uid;
    const resp = await getFoodRecommendations(params);
    foodItems.value = resp.data.items || [];
  } catch (e) {
    foodError.value = e.response?.data?.error || '加载美食推荐失败';
  } finally {
    loadingFoods.value = false;
  }
}

async function fetchMetrics() {
  loadingMetrics.value = true;
  metricsError.value = '';
  try {
    const resp = await getRecommendMetrics();
    metrics.value = resp.data || null;
  } catch (e) {
    metricsError.value = e.response?.data?.error || '加载推荐统计失败';
  } finally {
    loadingMetrics.value = false;
  }
}

onMounted(() => {
  if (currentUserId()) {
    scenicStrategy.value = 'hybrid';
  }
  fetchScenic();
  fetchHotels();
  fetchFoods();
});
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.hint {
  font-size: 13px;
  color: #6b7280;
}

.cold-start-banner {
  margin-top: 8px;
  margin-bottom: 8px;
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
}

.cold-start-text {
  font-size: 13px;
  color: #1d4ed8;
}

.cold-start-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.link-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  font-size: 13px;
  border-radius: 4px;
  border: 1px solid #2563eb;
  color: #ffffff;
  background: #2563eb;
  text-decoration: none;
}

.link-button.secondary {
  border-color: #d1d5db;
  background: #ffffff;
  color: #374151;
}

.block {
  background: #ffffff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.block-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.strategy-select {
  font-size: 12px;
  color: #4b5563;
}

.strategy-select select {
  margin-left: 4px;
}

.card-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.card {
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  cursor: pointer;
  transition: all 0.2s;
}

.card:hover {
  border-color: #2563eb;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.1);
}

.card-actions {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 8px;
}

.btn-add-trip {
  padding: 4px 12px;
  font-size: 12px;
  border-radius: 4px;
  border: 1px solid #2563eb;
  background: #ffffff;
  color: #2563eb;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-add-trip:hover {
  background: #2563eb;
  color: #ffffff;
}

.sub {
  font-size: 13px;
  color: #4b5563;
}

.desc {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
}

.strategy-meta {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.advanced-strategy {
  margin-bottom: 8px;
  font-size: 12px;
  color: #4b5563;
}

.advanced-strategy summary {
  cursor: pointer;
}

.advanced-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}

.reason {
  margin-top: 4px;
  font-size: 12px;
  color: #059669;
}

.error {
  color: #b91c1c;
  font-size: 13px;
}
</style>
