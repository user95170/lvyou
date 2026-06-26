<template>
  <div class="page">
    <h2>目的地浏览</h2>

    <div
      v-if="isColdStartMode"
      class="cold-start-tip"
      data-testid="browse-cold-start-tip"
    >
      <p class="cold-start-text">
        多浏览并给喜欢的内容打分，推荐会越来越贴合你的偏好。
      </p>
    </div>

    <div class="filters">
      <label>
        类型
        <select v-model="type" data-testid="browse-type" @change="fetchList">
          <option value="scenic">景点</option>
          <option value="hotel">酒店</option>
          <option value="food">美食</option>
          <option value="transportation">交通</option>
          <option value="activity">活动</option>
          <option value="specialty">特产</option>
        </select>
      </label>
      <label>
        城市
        <input
          v-model="city"
          data-testid="browse-city"
          type="text"
          placeholder="如：呼和浩特、包头"
        />
      </label>
      <button
        type="button"
        data-testid="browse-search"
        @click="fetchList"
        :disabled="loading"
      >
        {{ loading ? '搜索中...' : '搜索' }}
      </button>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <ul v-else class="card-list">
      <li v-for="item in items" :key="item.id" class="card" data-testid="browse-card">
        <h4>{{ item.name }}</h4>
        <p class="sub">
          <span>{{ item.city || '内蒙古' }}</span>
          <span class="dot">·</span>
          <span>{{ secondaryInfo(item) }}</span>
        </p>
        <p class="desc">
          {{ (item.description && item.description.slice(0, 60)) || item.tags || '暂无简介' }}
        </p>

        <p v-if="item.reasons && item.reasons.length" class="reasons">
          {{ item.reasons.join(' · ') }}
        </p>

        <div class="actions">
          <button
            v-if="canRate"
            type="button"
            data-testid="browse-rate-btn"
            @click="rateItem(item)"
          >
            我喜欢（打5分）
          </button>
          <button
            type="button"
            class="secondary"
            @click="toggleDetail(item)"
          >
            {{ detailFor === item.id ? '收起详情' : '查看详情' }}
          </button>
          <button
            v-if="type === 'scenic'"
            type="button"
            class="secondary"
            data-testid="browse-similar-btn"
            @click="loadSimilar(item)"
            :disabled="similarLoadingId === item.id"
          >
            {{ similarLoadingId === item.id ? '加载相似景点...' : '查看相似景点' }}
          </button>
        </div>

        <div v-if="detailFor === item.id" class="detail-block">
          <div v-for="row in detailRows(item)" :key="row.k" class="detail-row">
            <span class="dk">{{ row.k }}</span>
            <span class="dv">{{ row.v }}</span>
          </div>
          <p v-if="item.description" class="detail-desc">{{ item.description }}</p>
          <p v-if="audienceTip(item)" class="detail-tip">{{ audienceTip(item) }}</p>
        </div>

        <div
          v-if="type === 'scenic' && similarFor === item.id && similarItems.length"
          class="similar-block"
        >
          <p class="similar-title">相似景点推荐</p>
          <ul class="similar-list" data-testid="browse-similar-list">
            <li v-for="s in similarItems" :key="s.id" class="similar-item">
              {{ s.name }} · 评分 {{ s.rating_avg ?? '暂无' }}
            </li>
          </ul>
        </div>
      </li>
    </ul>

    <div v-if="!loading && !error && !items.length" class="empty">
      <p v-if="city">当前城市「{{ city }}」下暂无{{ typeLabel }}数据。</p>
      <p v-else>暂无{{ typeLabel }}数据，换个类型试试。</p>
      <button v-if="city" type="button" class="secondary" @click="clearCityAndSearch">
        清空城市并重新搜索
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { getCurrentUser } from '../utils/user';
import {
  getScenicSpots,
  getHotels,
  getFoods,
  getTransportations,
  getActivities,
  getSpecialties,
  createRating,
} from '../api/resources';
import { getSimilarScenicSpots } from '../api/recommend';
import { toast } from '../utils/toast';

const route = useRoute();
const isColdStartMode = route.query.mode === 'cold_start';

const type = ref('scenic');
const city = ref('');
const items = ref([]);
const loading = ref(false);
const error = ref('');

const detailFor = ref(null);
const similarFor = ref(null);
const similarItems = ref([]);
const similarLoadingId = ref(null);

const RATEABLE = {
  scenic: 'scenic_spot',
  hotel: 'hotel',
  food: 'food_place',
  transportation: 'transportation',
  activity: 'activity',
  specialty: 'specialty',
};
const canRate = computed(() => Boolean(RATEABLE[type.value]));

const TYPE_LABELS = {
  scenic: '景点',
  hotel: '酒店',
  food: '美食',
  transportation: '交通',
  activity: '活动',
  specialty: '特产',
};
const typeLabel = computed(() => TYPE_LABELS[type.value] || '');

function currentUserId() {
  const u = getCurrentUser();
  return u?.id ?? null;
}

function secondaryInfo(item) {
  if (type.value === 'scenic') return `评分 ${item.rating_avg ?? '暂无'}`;
  if (type.value === 'hotel') return `均价 ${item.avg_price ?? '暂无'}`;
  if (type.value === 'food') return item.cuisine_type || '特色美食';
  if (type.value === 'transportation') return item.transport_type || '交通节点';
  if (type.value === 'activity') return item.activity_type || '活动';
  if (type.value === 'specialty') return item.category || '特产';
  return '';
}

function detailRows(item) {
  const rows = [];
  const push = (k, v) => {
    if (v !== null && v !== undefined && v !== '') rows.push({ k, v });
  };
  push('地址', item.address);
  if (type.value === 'scenic') {
    push('开放时间', item.opening_hours);
    push('门票', item.ticket_price);
    push('评分', item.rating_avg);
  } else if (type.value === 'hotel') {
    push('星级', item.star_level);
    push('均价', item.avg_price);
    push('评分', item.rating_avg);
  } else if (type.value === 'food') {
    push('菜系', item.cuisine_type);
    push('人均', item.avg_price);
    push('评分', item.rating_avg);
  } else if (type.value === 'transportation') {
    push('类型', item.transport_type);
    push('电话', item.phone);
    push('运营时间', item.operating_hours);
    push('预期消费', item.price_info);
    push('评分', item.rating_avg);
  } else if (type.value === 'activity') {
    push('类型', item.activity_type);
    push('电话', item.phone);
    push('举办时间', item.hold_time);
    push('票价', item.price_info);
    push('评分', item.rating_avg);
  } else if (type.value === 'specialty') {
    push('类别', item.category);
    push('电话', item.phone);
    push('营业时间', item.business_hours);
    push('价格区间', item.price_info);
    push('评分', item.rating_avg);
  }
  return rows;
}

function audienceTip(item) {
  // 活动/特产的适配人群或地域提示，来自标签
  if (!item.tags) return '';
  if (type.value === 'activity') return `适配人群：${item.tags}`;
  if (type.value === 'specialty') return `标签：${item.tags}`;
  return '';
}

async function fetchList() {
  loading.value = true;
  error.value = '';
  detailFor.value = null;
  similarFor.value = null;
  similarItems.value = [];
  similarLoadingId.value = null;
  try {
    const params = { page: 1, page_size: 20 };
    if (city.value) params.city = city.value;
    const uid = currentUserId();
    if (uid) params.user_id = uid;

    const fetcher = {
      scenic: getScenicSpots,
      hotel: getHotels,
      food: getFoods,
      transportation: getTransportations,
      activity: getActivities,
      specialty: getSpecialties,
    }[type.value];

    const resp = await fetcher(params);
    items.value = resp.data.items || [];
  } catch (e) {
    error.value = e.response?.data?.error || '加载列表失败';
  } finally {
    loading.value = false;
  }
}

function toggleDetail(item) {
  detailFor.value = detailFor.value === item.id ? null : item.id;
}

function clearCityAndSearch() {
  city.value = '';
  fetchList();
}

async function rateItem(item) {
  const uid = currentUserId();
  if (!uid) {
    toast.warning('请先登录再进行评分');
    return;
  }
  const targetType = RATEABLE[type.value];
  if (!targetType) {
    toast.info('该类型暂不支持评分');
    return;
  }

  try {
    const payload = {
      user_id: uid,
      target_type: targetType,
      target_id: item.id,
      score: 5,
      comment: '我喜欢',
    };
    await createRating(payload);
    toast.success('感谢你的评分！推荐将逐渐向你的偏好靠拢。');
  } catch (e) {
    toast.error(e.response?.data?.error || '评分失败');
  }
}

async function loadSimilar(item) {
  if (!item || similarLoadingId.value) return;

  if (similarFor.value === item.id) {
    similarFor.value = null;
    similarItems.value = [];
    return;
  }

  similarLoadingId.value = item.id;
  similarItems.value = [];
  try {
    const resp = await getSimilarScenicSpots(item.id, { limit: 6 });
    const list = resp.data?.items || [];
    similarItems.value = list;
    similarFor.value = item.id;
    if (!list.length) {
      toast.info('暂无相似景点');
    }
  } catch (e) {
    similarItems.value = [];
    similarFor.value = item.id;
    toast.error(e.response?.data?.error || '加载相似景点失败');
  } finally {
    similarLoadingId.value = null;
  }
}

onMounted(() => {
  fetchList();
});
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cold-start-tip {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
}

.cold-start-text {
  font-size: 13px;
  color: #1d4ed8;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
  background: #ffffff;
  padding: 12px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

label {
  display: flex;
  flex-direction: column;
  font-size: 14px;
}

input,
select {
  margin-top: 4px;
  padding: 6px 8px;
  border-radius: 4px;
  border: 1px solid #d1d5db;
}

.card-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.card {
  background: #ffffff;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.sub {
  font-size: 13px;
  color: #4b5563;
}

.dot {
  margin: 0 6px;
  color: #9ca3af;
}

.desc {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
}

.reasons {
  margin-top: 4px;
  font-size: 12px;
  color: #047857;
}

button {
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 4px;
  border: none;
  background: #10b981;
  color: #ffffff;
  cursor: pointer;
}

.secondary {
  background: #e5e7eb;
  color: #374151;
}

.detail-block {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #e5e7eb;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.dk {
  color: #6b7280;
}

.dv {
  color: #111827;
  text-align: right;
}

.detail-desc {
  margin-top: 6px;
  font-size: 13px;
  color: #374151;
}

.detail-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #2563eb;
}

.similar-block {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed #e5e7eb;
}

.similar-title {
  font-size: 13px;
  color: #4b5563;
  margin-bottom: 4px;
}

.similar-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.similar-item {
  font-size: 13px;
  color: #6b7280;
}

.empty {
  font-size: 13px;
  color: #6b7280;
}

.error {
  color: #b91c1c;
  font-size: 13px;
}
</style>
