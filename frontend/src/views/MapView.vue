<template>
  <div class="page">
    <div class="header">
      <div>
        <h2>个性化电子地图</h2>
        <p class="subtitle">在地图上查看与你匹配的景点、酒店、美食、交通、活动与特产。</p>
      </div>
    </div>

    <div class="filters">
      <label>
        城市
        <input v-model="city" type="text" placeholder="如：呼和浩特、包头" />
      </label>
      <div class="cats">
        <label v-for="cat in categoryOptions" :key="cat.key" class="cat">
          <input type="checkbox" :value="cat.key" v-model="selectedCats" />
          {{ cat.label }}
        </label>
      </div>
      <button type="button" :disabled="loading" @click="load">
        {{ loading ? '加载中...' : '刷新地图' }}
      </button>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="layout">
      <section class="map-col">
        <AmapMapPanel
          :points="mapPoints"
          :height="460"
          empty-message="当前筛选下暂无可上图的点位（可能缺少坐标）。"
          test-id-prefix="personalized-map"
        />
        <p class="legend">
          共 {{ mapPoints.length }} 个可上图点位。未配置高德 Key 时，下方列表仍可浏览与查看详情。
        </p>
      </section>

      <aside class="list-col">
        <div v-for="cat in categoryOptions" :key="cat.key" class="cat-block">
          <template v-if="selectedCats.includes(cat.key) && (result[cat.key] || []).length">
            <div class="cat-title">{{ cat.label }}（{{ result[cat.key].length }}）</div>
            <ul class="point-list">
              <li
                v-for="p in result[cat.key]"
                :key="`${cat.key}-${p.id}`"
                class="point"
                :class="{ active: isActive(cat.key, p.id) }"
                @click="selectPoint(cat.key, p)"
              >
                <span class="p-name">{{ p.name }}</span>
                <span class="p-city">{{ p.city || '' }}</span>
              </li>
            </ul>
          </template>
        </div>

        <div v-if="selected" class="detail">
          <div class="detail-head">
            <strong>{{ selected.name }}</strong>
            <button type="button" class="ghost" @click="selected = null">关闭</button>
          </div>
          <div class="detail-type">{{ categoryLabel(selectedCat) }}</div>
          <div v-for="row in selectedRows" :key="row.k" class="d-row">
            <span class="dk">{{ row.k }}</span>
            <span class="dv">{{ row.v }}</span>
          </div>
          <p v-if="selected.description" class="d-desc">{{ selected.description }}</p>
          <ul v-if="selected.fit_reasons && selected.fit_reasons.length" class="reasons">
            <li v-for="(r, i) in selected.fit_reasons" :key="i">{{ r }}</li>
          </ul>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import AmapMapPanel from '../components/AmapMapPanel.vue';
import { fetchPersonalizedMap } from '../api/map';
import {
  getTransportationDetail,
  getActivityDetail,
  getSpecialtyDetail,
} from '../api/resources';
import { getCurrentUser } from '../utils/user';
import { toast } from '../utils/toast';

const categoryOptions = [
  { key: 'scenic_spot', label: '景点' },
  { key: 'hotel', label: '酒店' },
  { key: 'food_place', label: '美食' },
  { key: 'transportation', label: '交通' },
  { key: 'activity', label: '活动' },
  { key: 'specialty', label: '特产' },
];

const DETAIL_FETCHERS = {
  transportation: getTransportationDetail,
  activity: getActivityDetail,
  specialty: getSpecialtyDetail,
};

const city = ref('');
const selectedCats = ref(categoryOptions.map((c) => c.key));
const result = ref({});
const loading = ref(false);
const error = ref('');

const selected = ref(null);
const selectedCat = ref('');

const mapPoints = computed(() => {
  const points = [];
  let order = 0;
  for (const cat of categoryOptions) {
    if (!selectedCats.value.includes(cat.key)) continue;
    for (const p of result.value[cat.key] || []) {
      if (p.longitude == null || p.latitude == null) continue;
      order += 1;
      points.push({
        id: `${cat.key}-${p.id}`,
        order,
        title: p.name,
        longitude: p.longitude,
        latitude: p.latitude,
      });
    }
  }
  return points;
});

function categoryLabel(key) {
  return categoryOptions.find((c) => c.key === key)?.label || key;
}

function isActive(cat, id) {
  return selectedCat.value === cat && selected.value?.id === id;
}

const selectedRows = computed(() => {
  const item = selected.value;
  const cat = selectedCat.value;
  if (!item) return [];
  const rows = [];
  const push = (k, v) => {
    if (v !== null && v !== undefined && v !== '') rows.push({ k, v });
  };
  push('城市', item.city);
  push('地址', item.address);
  if (cat === 'transportation') {
    push('类型', item.transport_type);
    push('电话', item.phone);
    push('运营时间', item.operating_hours);
    push('预期消费', item.price_info);
  } else if (cat === 'activity') {
    push('类型', item.activity_type);
    push('电话', item.phone);
    push('举办时间', item.hold_time);
    push('票价', item.price_info);
    push('适配人群', item.tags);
  } else if (cat === 'specialty') {
    push('类别', item.category);
    push('电话', item.phone);
    push('营业时间', item.business_hours);
    push('价格区间', item.price_info);
  }
  push('评分', item.rating_avg);
  return rows;
});

async function selectPoint(cat, point) {
  selectedCat.value = cat;
  selected.value = point;
  const fetcher = DETAIL_FETCHERS[cat];
  if (fetcher) {
    try {
      const resp = await fetcher(point.id);
      selected.value = { ...point, ...resp.data };
    } catch (e) {
      // 详情拉取失败时保留地图返回的基础信息
    }
  }
}

async function load() {
  loading.value = true;
  error.value = '';
  selected.value = null;
  try {
    const user = getCurrentUser();
    const payload = {
      categories: selectedCats.value,
      limit_per_type: 30,
    };
    if (city.value) payload.city = city.value;
    if (user?.id) payload.user_id = user.id;

    const resp = await fetchPersonalizedMap(payload);
    result.value = resp.data?.items || {};
  } catch (e) {
    error.value = e.response?.data?.error || '加载地图失败';
    toast.error(error.value);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  load();
});
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header h2 {
  margin: 0;
}

.subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #6b7280;
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

input[type='text'] {
  margin-top: 4px;
  padding: 6px 8px;
  border-radius: 4px;
  border: 1px solid #d1d5db;
}

.cats {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.cat {
  flex-direction: row;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

button {
  padding: 8px 14px;
  border-radius: 6px;
  border: none;
  background: #2563eb;
  color: #ffffff;
  cursor: pointer;
}

button:disabled {
  opacity: 0.7;
}

.layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 16px;
}

.map-col {
  background: #ffffff;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.legend {
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
}

.list-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cat-block {
  background: #ffffff;
  border-radius: 8px;
  padding: 10px 12px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.cat-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 6px;
}

.point-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.point {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}

.point:hover {
  background: #f3f4f6;
}

.point.active {
  background: #eff6ff;
}

.p-city {
  color: #9ca3af;
}

.detail {
  background: #ffffff;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-type {
  font-size: 12px;
  color: #2563eb;
  margin: 2px 0 8px;
}

.ghost {
  background: transparent;
  color: #2563eb;
  padding: 2px 6px;
}

.d-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  padding: 2px 0;
}

.dk {
  color: #6b7280;
}

.dv {
  color: #111827;
  text-align: right;
}

.d-desc {
  margin-top: 6px;
  font-size: 13px;
  color: #374151;
}

.reasons {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 12px;
  color: #047857;
}

.error {
  color: #b91c1c;
  font-size: 13px;
}

@media (max-width: 960px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
