<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>行程详情</h2>
        <p class="hint">支持单日和多日行程编辑，可保存空草稿、补充自定义条目，并进行跨天移动与资源选点。</p>
      </div>
      <router-link to="/trips" class="link-button secondary">返回列表</router-link>
    </div>

    <div v-if="!currentUser" class="empty-state">
      <p>请先登录后查看行程详情。</p>
      <router-link to="/login" class="link-button">前往登录</router-link>
    </div>

    <div v-else-if="loading" class="hint" data-testid="trip-loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <form
      v-else
      class="detail-form"
      data-testid="trip-detail-form"
      @submit.prevent="handleSave"
    >
      <section class="block" data-testid="trip-map-section">
        <div class="section-header">
          <div>
            <h3>行程地图</h3>
            <p class="hint">按 Day 查看当前可上图条目，地图会随着本地编辑即时更新。</p>
          </div>
          <span class="map-summary">
            Day {{ selectedMapDayIndex + 1 }} 可上图 {{ selectedMapPoints.length }}/{{ selectedMapDayItemCount }}
          </span>
        </div>

        <div class="map-day-tabs">
          <button
            v-for="(day, dayIndex) in form.trip_days"
            :key="day.localKey"
            type="button"
            class="map-day-tab"
            :class="{ active: dayIndex === selectedMapDayIndex }"
            data-testid="trip-map-day-btn"
            @click="selectedMapDayIndex = dayIndex"
          >
            Day {{ dayIndex + 1 }}
          </button>
        </div>

        <p class="hint">
          当前查看 {{ selectedMapDayLabel }}，可上图 {{ selectedMapPoints.length }} 条，未上图条目仍会保留在编辑器中。
        </p>

        <AmapMapPanel
          :points="selectedMapPoints"
          test-id-prefix="trip-map"
          empty-message="当前 Day 暂无可上图条目"
          config-error-message="未配置高德地图 Key，暂时无法显示行程地图。"
        />
      </section>

      <section class="block">
        <div class="field-grid">
          <label>
            标题
            <input
              v-model="form.title"
              data-testid="trip-title-input"
              type="text"
              required
            />
          </label>

          <label>
            出发城市
            <input
              v-model="form.origin_city"
              data-testid="trip-origin-city-input"
              type="text"
              required
            />
          </label>

          <label>
            出发日期
            <input
              v-model="form.start_date"
              data-testid="trip-start-date-input"
              type="date"
            />
          </label>

          <label>
            预算等级
            <select v-model="form.budget_level" data-testid="trip-budget-level-select">
              <option :value="null">未设置</option>
              <option :value="1">低</option>
              <option :value="2">中</option>
              <option :value="3">高</option>
            </select>
          </label>

          <label>
            出游风格
            <select v-model="form.travel_style" data-testid="trip-travel-style-select">
              <option value="">未设置</option>
              <option value="relax">轻松</option>
              <option value="adventure">探索</option>
              <option value="family">亲子</option>
              <option value="culture">人文</option>
              <option value="photography">摄影</option>
            </select>
          </label>
        </div>

        <div class="trip-summary">
          <span>天数：{{ form.trip_days.length }}</span>
          <span>条目总数：{{ totalItemCount }}</span>
          <span>结束日期：{{ previewEndDate }}</span>
        </div>
      </section>

      <section class="block">
        <div class="section-header">
          <div>
            <h3>每日安排</h3>
            <p class="hint">支持同日排序、跨天移动、资源重选；仍允许空 Day 和整单空草稿。</p>
          </div>
          <button
            type="button"
            data-testid="trip-add-day-btn"
            @click="addDay"
          >
            新增一天
          </button>
        </div>

        <div ref="dayListRef" class="day-list">
          <section
            v-for="(day, dayIndex) in form.trip_days"
            :key="day.localKey"
            class="day-card"
            data-testid="trip-day-card"
          >
            <div class="day-header">
              <div>
                <h4>Day {{ dayIndex + 1 }}</h4>
                <p class="hint">{{ formatDayDate(day, dayIndex) }}</p>
              </div>

              <div class="day-actions">
                <button
                  type="button"
                  class="button-secondary"
                  data-testid="trip-add-resource-btn"
                  @click="openResourcePicker('add', dayIndex)"
                >
                  从资源库添加
                </button>
                <button
                  type="button"
                  data-testid="trip-add-item-btn"
                  @click="addItem(dayIndex)"
                >
                  新增条目
                </button>
                <button
                  type="button"
                  class="danger ghost-danger"
                  data-testid="trip-remove-day-btn"
                  :disabled="form.trip_days.length === 1"
                  @click="removeDay(dayIndex)"
                >
                  删除 Day
                </button>
              </div>
            </div>

            <label class="block-field">
              当日备注
              <textarea
                v-model="day.note"
                data-testid="trip-day-note-input"
                rows="3"
              ></textarea>
            </label>

            <section
              class="route-recommendation"
              data-testid="trip-route-recommendation"
            >
              <div class="route-recommendation-header">
                <div>
                  <h5>路线建议</h5>
                  <p class="hint">
                    当前 Day 可路由 {{ dayRouteRecommendations[dayIndex]?.routeableCount || 0 }}/{{ day.items.length }}
                    个条目，建议结果会在点击“应用推荐顺序”后写入当前编辑顺序。
                  </p>
                </div>
                <button
                  v-if="dayRouteRecommendations[dayIndex]?.canApply"
                  type="button"
                  class="button-secondary"
                  data-testid="trip-apply-recommendation-btn"
                  @click="applyDayRecommendation(dayIndex)"
                >
                  应用推荐顺序
                </button>
              </div>

              <div
                v-if="!dayRouteRecommendations[dayIndex]?.canApply"
                class="empty-items route-recommendation-empty"
                data-testid="trip-route-recommendation-empty"
              >
                {{ dayRouteRecommendations[dayIndex]?.reason || '当前 Day 暂无路线建议' }}
              </div>

              <div v-else class="route-recommendation-body">
                <ol
                  class="route-recommendation-list"
                  data-testid="trip-route-recommendation-list"
                >
                  <li
                    v-for="(recommendedItem, recommendationIndex) in dayRouteRecommendations[dayIndex].recommendedItems"
                    :key="`${recommendedItem.localKey}-recommendation`"
                    class="route-recommendation-item"
                    data-testid="trip-route-recommendation-item"
                  >
                    <span class="route-recommendation-order">{{ recommendationIndex + 1 }}</span>
                    <span class="route-recommendation-title">
                      {{ recommendedItem.title_snapshot || '未命名条目' }}
                    </span>
                    <span
                      class="route-recommendation-badge"
                      :class="{ muted: recommendedItem.longitude == null || recommendedItem.latitude == null }"
                    >
                      {{ recommendedItem.longitude != null && recommendedItem.latitude != null ? '可路由' : '末尾保留' }}
                    </span>
                  </li>
                </ol>
                <p
                  v-if="dayRouteRecommendations[dayIndex].skippedCount > 0"
                  class="hint"
                >
                  应用后，{{ dayRouteRecommendations[dayIndex].skippedCount }} 个无坐标条目会按原相对顺序排到当前 Day 末尾。
                </p>
              </div>
            </section>

            <section
              class="route-recommendation route-recommendation-real"
              data-testid="trip-real-route-panel"
            >
              <div class="route-recommendation-header">
                <div>
                  <h5>真实路线重算</h5>
                  <p class="hint">
                    当前 Day 可路由 {{ getDayMappableCount(day) }}/{{ day.items.length }}
                    个条目，点击后会串行评估真实道路优先方案。
                  </p>
                </div>

                <div class="route-recommendation-actions">
                  <button
                    type="button"
                    data-testid="trip-real-route-recalc-btn"
                    :disabled="getRealRouteState(day.localKey).loading"
                    @click="recalculateRealRoute(dayIndex)"
                  >
                    {{ getRealRouteState(day.localKey).loading ? '重算中...' : '开始重算' }}
                  </button>
                  <button
                    v-if="getRealRouteState(day.localKey).bestOrderKeys.length > 0"
                    type="button"
                    class="button-secondary"
                    data-testid="trip-real-route-apply-btn"
                    :disabled="
                      getRealRouteState(day.localKey).loading ||
                      getRealRouteState(day.localKey).stale
                    "
                    @click="applyRealRoute(dayIndex)"
                  >
                    应用到当前 Day
                  </button>
                </div>
              </div>

              <p
                v-if="getRealRouteState(day.localKey).loading"
                class="hint"
              >
                正在串行评估候选顺序，请稍候...
              </p>
              <p
                v-else-if="getRealRouteState(day.localKey).error"
                class="error"
              >
                {{ getRealRouteState(day.localKey).error }}
              </p>
              <div
                v-else-if="getRealRouteEmptyReason(day)"
                class="empty-items route-recommendation-empty"
                data-testid="trip-real-route-empty"
              >
                {{ getRealRouteEmptyReason(day) }}
              </div>
              <div v-else class="route-recommendation-body">
                <p
                  v-if="getRealRouteState(day.localKey).stale"
                  class="hint real-route-stale"
                >
                  当前结果已过期，请重新点击“开始重算”获取最新方案。
                </p>

                <div class="real-route-metrics">
                  <span
                    class="real-route-metric"
                    data-testid="trip-real-route-metric"
                  >
                    耗时 {{ getRealRouteState(day.localKey).bestOption?.duration_min ?? '-' }} 分钟
                  </span>
                  <span
                    class="real-route-metric"
                    data-testid="trip-real-route-metric"
                  >
                    距离 {{ getRealRouteState(day.localKey).bestOption?.distance_km ?? '-' }} km
                  </span>
                </div>

                <ol
                  class="route-recommendation-list"
                  data-testid="trip-real-route-list"
                >
                  <li
                    v-for="(realRouteItem, realRouteIndex) in getRealRouteSummaryItems(day)"
                    :key="`${realRouteItem.localKey}-real-route`"
                    class="route-recommendation-item"
                  >
                    <span class="route-recommendation-order">{{ realRouteIndex + 1 }}</span>
                    <span class="route-recommendation-title">
                      {{ realRouteItem.title_snapshot || '未命名条目' }}
                    </span>
                    <span class="route-recommendation-badge">
                      可路由
                    </span>
                  </li>
                </ol>

                <p
                  v-if="getRealRouteState(day.localKey).skippedCount > 0"
                  class="hint"
                >
                  应用后，{{ getRealRouteState(day.localKey).skippedCount }}
                  个 custom/无坐标条目会按原相对顺序追加到当前 Day 末尾。
                </p>
              </div>
            </section>

            <div
              v-if="resourcePicker.isOpen && resourcePicker.dayIndex === dayIndex"
              class="resource-panel"
              data-testid="trip-resource-panel"
            >
              <div class="resource-panel-header">
                <div>
                  <h5>{{ resourcePickerTitle }}</h5>
                  <p class="hint">{{ resourcePickerHint }}</p>
                </div>
                <button
                  type="button"
                  class="link-like"
                  data-testid="trip-resource-close-btn"
                  @click="closeResourcePicker"
                >
                  收起
                </button>
              </div>

              <div class="field-grid compact-grid">
                <label>
                  资源类型
                  <select
                    v-model="resourcePicker.resourceType"
                    data-testid="trip-resource-type-select"
                    @change="handleResourceTypeChange"
                  >
                    <option
                      v-for="option in resourceTypeOptions"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </label>

                <label>
                  搜索城市
                  <input
                    v-model="resourcePicker.city"
                    data-testid="trip-resource-city-input"
                    type="text"
                    placeholder="默认使用当前行程城市"
                    @keydown.enter.prevent="searchResourceOptions"
                  />
                </label>

                <label>
                  关键词
                  <input
                    v-model="resourcePicker.keyword"
                    data-testid="trip-resource-keyword-input"
                    type="text"
                    placeholder="输入名称或标签"
                    @keydown.enter.prevent="searchResourceOptions"
                  />
                </label>
              </div>

              <div class="resource-panel-actions">
                <button
                  type="button"
                  data-testid="trip-resource-search-btn"
                  :disabled="resourcePicker.loading"
                  @click="searchResourceOptions"
                >
                  {{ resourcePicker.loading ? '搜索中...' : '搜索资源' }}
                </button>
                <span class="hint">选中后会写入快照字段，资源结果默认取前 10 条。</span>
              </div>

              <p v-if="resourcePicker.error" class="error">{{ resourcePicker.error }}</p>
              <p v-else-if="resourcePicker.loading" class="hint">正在加载资源...</p>
              <div v-else-if="resourcePicker.results.length === 0" class="empty-items">
                当前没有匹配资源，可以换个关键词，或直接保留 custom 条目。
              </div>
              <ul v-else class="resource-result-list">
                <li
                  v-for="resource in resourcePicker.results"
                  :key="`${resourcePicker.resourceType}-${resource.id}`"
                  class="resource-result"
                  data-testid="trip-resource-result"
                >
                  <div class="resource-result-main">
                    <div class="item-title">{{ resource.name }}</div>
                    <div class="item-meta">
                      <span>类型：{{ getResourceTypeLabel(resourcePicker.resourceType) }}</span>
                      <span>城市：{{ resource.city || '未设置' }}</span>
                      <span>地址：{{ resource.address || '暂无地址' }}</span>
                      <span>{{ formatResourceSummary(resourcePicker.resourceType, resource) }}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    data-testid="trip-resource-select-btn"
                    @click="applyResourceSelection(resource)"
                  >
                    选择
                  </button>
                </li>
              </ul>
            </div>

            <div v-if="day.items.length === 0" class="empty-items">
              这一天还没有条目，可以先新增一个自定义安排，或从资源库选点。
            </div>

            <ul
              class="item-list"
              :class="{ 'is-empty': day.items.length === 0 }"
              :data-empty="day.items.length === 0 ? 'true' : 'false'"
              :data-day-key="day.localKey"
              :data-day-index="dayIndex"
              data-testid="trip-item-list"
            >
              <li
                v-for="(item, itemIndex) in day.items"
                :key="item.localKey"
                class="item-card"
                :data-item-key="item.localKey"
                data-testid="trip-item-card"
              >
                <div class="item-header">
                  <div class="item-summary">
                    <div class="item-title">
                      {{ itemIndex + 1 }}. {{ item.title_snapshot || '未命名条目' }}
                    </div>
                    <div class="item-meta">
                      <span>类型：{{ item.item_type || 'custom' }}</span>
                      <span>城市：{{ item.city_snapshot || form.origin_city || '未设置' }}</span>
                      <span>地址：{{ item.address_snapshot || '暂无地址' }}</span>
                    </div>
                    <div
                      class="drag-handle"
                      data-testid="trip-drag-handle"
                      title="拖拽排序"
                    >
                      ::
                    </div>
                  </div>

                  <div class="item-actions">
                    <button
                      type="button"
                      :disabled="itemIndex === 0"
                      @click="moveItem(dayIndex, itemIndex, -1)"
                    >
                      上移
                    </button>
                    <button
                      type="button"
                      :disabled="itemIndex === day.items.length - 1"
                      @click="moveItem(dayIndex, itemIndex, 1)"
                    >
                      下移
                    </button>
                    <button
                      type="button"
                      class="button-secondary"
                      data-testid="trip-move-prev-day-btn"
                      :disabled="dayIndex === 0"
                      @click="moveItemToAdjacentDay(dayIndex, itemIndex, -1)"
                    >
                      移到上一天
                    </button>
                    <button
                      type="button"
                      class="button-secondary"
                      data-testid="trip-move-next-day-btn"
                      :disabled="dayIndex === form.trip_days.length - 1"
                      @click="moveItemToAdjacentDay(dayIndex, itemIndex, 1)"
                    >
                      移到下一天
                    </button>
                    <button
                      type="button"
                      class="button-secondary"
                      data-testid="trip-repick-resource-btn"
                      @click="openResourcePicker('replace', dayIndex, itemIndex)"
                    >
                      资源重选
                    </button>
                    <button
                      type="button"
                      class="danger ghost-danger"
                      data-testid="trip-remove-item-btn"
                      @click="removeItem(dayIndex, itemIndex)"
                    >
                      删除
                    </button>
                  </div>
                </div>

                <div class="field-grid">
                  <label>
                    类型
                    <input
                      v-model="item.item_type"
                      data-testid="trip-item-type-input"
                      @input="handleItemTypeInput(item)"
                      type="text"
                      placeholder="例如：custom / scenic_spot"
                    />
                  </label>

                  <label>
                    标题快照
                    <input
                      v-model="item.title_snapshot"
                      data-testid="trip-item-title-input"
                      type="text"
                      placeholder="请输入条目标题"
                      required
                    />
                  </label>

                  <label>
                    城市快照
                    <input
                      v-model="item.city_snapshot"
                      data-testid="trip-item-city-input"
                      type="text"
                      placeholder="可留空"
                    />
                  </label>

                  <label>
                    地址快照
                    <input
                      v-model="item.address_snapshot"
                      data-testid="trip-item-address-input"
                      type="text"
                      placeholder="可留空"
                    />
                  </label>

                  <label>
                    开始时间
                    <input
                      v-model="item.start_time"
                      data-testid="trip-item-start-time-input"
                      type="time"
                    />
                  </label>

                  <label>
                    结束时间
                    <input
                      v-model="item.end_time"
                      data-testid="trip-item-end-time-input"
                      type="time"
                    />
                  </label>

                  <label>
                    交通方式
                    <input
                      v-model="item.transport_mode"
                      data-testid="trip-item-transport-mode-input"
                      type="text"
                      placeholder="walk / drive / transit"
                    />
                  </label>
                </div>

                <label class="block-field">
                  条目备注
                  <input
                    v-model="item.note"
                    data-testid="trip-item-note-input"
                    type="text"
                    placeholder="补充说明"
                  />
                </label>
              </li>
            </ul>
          </section>
        </div>
      </section>

      <div class="page-actions">
        <button type="submit" data-testid="trip-save-btn" :disabled="saving">
          {{ saving ? '保存中...' : '保存修改' }}
        </button>
        <button
          type="button"
          class="danger"
          data-testid="trip-delete-btn"
          @click="handleDelete"
        >
          删除行程
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import Sortable from 'sortablejs';
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AmapMapPanel from '../components/AmapMapPanel.vue';
import { routeOptions } from '../api/route';
import { searchTripResources } from '../api/resources';
import { deleteTrip, getTrip, updateTrip } from '../api/trips';
import { buildDayRouteRecommendation } from '../utils/tripRouteRecommendation.mjs';
import {
  MAX_REAL_ROUTE_POINTS,
  applyTripRealRouteOrder,
  createTripRealRouteSignature,
  evaluateTripRealRoute,
} from '../utils/tripRealRouteRecommendation.mjs';
import { toast } from '../utils/toast';
import { getCurrentUser } from '../utils/user';

const MAX_TRIP_DAYS = 10;
const RESOURCE_TYPE_OPTIONS = [
  { value: 'scenic_spot', label: '景点' },
  { value: 'food_place', label: '美食' },
  { value: 'hotel', label: '酒店' },
];
const RESOURCE_TYPE_LABELS = RESOURCE_TYPE_OPTIONS.reduce((map, option) => {
  map[option.value] = option.label;
  return map;
}, {});
const SUPPORTED_RESOURCE_TYPES = RESOURCE_TYPE_OPTIONS.map((option) => option.value);

const route = useRoute();
const router = useRouter();
const currentUser = getCurrentUser();

const loading = ref(false);
const saving = ref(false);
const error = ref('');
const tripId = Number(route.params.id);
const dayListRef = ref(null);

let daySeed = 0;
let itemSeed = 0;
const sortableInstances = new Map();

const form = reactive({
  title: '',
  origin_city: '',
  start_date: '',
  budget_level: null,
  travel_style: '',
  trip_days: [],
});

const resourcePicker = reactive({
  isOpen: false,
  mode: 'add',
  dayIndex: -1,
  itemIndex: -1,
  resourceType: 'scenic_spot',
  city: '',
  keyword: '',
  loading: false,
  error: '',
  results: [],
  requestToken: 0,
});

const resourceTypeOptions = RESOURCE_TYPE_OPTIONS;
const selectedMapDayIndex = ref(0);
const realRouteStates = reactive({});

function normalizeCoordinate(value) {
  if (value === '' || value == null) {
    return null;
  }
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : null;
}

function isSupportedResourceType(value) {
  return SUPPORTED_RESOURCE_TYPES.includes(String(value || '').trim());
}

function getDayMappableCount(day) {
  return (day?.items || []).filter((item) => {
    const longitude = normalizeCoordinate(item?.longitude);
    const latitude = normalizeCoordinate(item?.latitude);
    return longitude != null && latitude != null;
  }).length;
}

const totalItemCount = computed(() =>
  form.trip_days.reduce((sum, day) => sum + day.items.length, 0)
);

const previewEndDate = computed(() => {
  if (!form.start_date || form.trip_days.length === 0) {
    return '未设置';
  }
  return formatDateByOffset(form.start_date, form.trip_days.length - 1) || '未设置';
});

const selectedMapDay = computed(() => form.trip_days[selectedMapDayIndex.value] || null);

const selectedMapPoints = computed(() =>
  (selectedMapDay.value?.items || [])
    .map((item, index) => {
      const longitude = normalizeCoordinate(item?.longitude);
      const latitude = normalizeCoordinate(item?.latitude);
      if (longitude == null || latitude == null) {
        return null;
      }
      return {
        id: item?.localKey || `trip-map-item-${index + 1}`,
        order: index + 1,
        title: item?.title_snapshot || `Day ${selectedMapDayIndex.value + 1} Item ${index + 1}`,
        longitude,
        latitude,
      };
    })
    .filter(Boolean)
);

const selectedMapDayItemCount = computed(() => selectedMapDay.value?.items?.length || 0);

const selectedMapDayLabel = computed(() => `Day ${selectedMapDayIndex.value + 1}`);

const dayRouteRecommendations = computed(() =>
  form.trip_days.map((day) => buildDayRouteRecommendation(day.items || []))
);

function createRealRouteState() {
  return {
    loading: false,
    stale: false,
    error: '',
    emptyReason: '',
    routeableCount: 0,
    skippedCount: 0,
    bestOrderKeys: [],
    bestItems: [],
    bestOption: null,
    lastEvaluatedSignature: '',
    requestToken: 0,
  };
}

function getRealRouteState(dayKey) {
  if (!dayKey) {
    return createRealRouteState();
  }
  if (!realRouteStates[dayKey]) {
    realRouteStates[dayKey] = createRealRouteState();
  }
  return realRouteStates[dayKey];
}

function syncRealRouteStates(days, resetAll = false) {
  const nextDayKeys = new Set((days || []).map((day) => day.localKey));
  Object.keys(realRouteStates).forEach((dayKey) => {
    if (!nextDayKeys.has(dayKey)) {
      delete realRouteStates[dayKey];
      return;
    }
    if (resetAll) {
      Object.assign(realRouteStates[dayKey], createRealRouteState());
    }
  });

  (days || []).forEach((day) => {
    const state = getRealRouteState(day.localKey);
    if (resetAll) {
      Object.assign(state, createRealRouteState());
    }
  });
}

function invalidateRealRouteByDayKeys(dayKeys = []) {
  [...new Set(dayKeys.filter(Boolean))].forEach((dayKey) => {
    const state = realRouteStates[dayKey];
    if (!state) {
      return;
    }
    state.requestToken += 1;
    state.loading = false;
    state.error = '';
    state.emptyReason = '';
    state.stale = state.bestOrderKeys.length > 0;
  });
}

function invalidateAllRealRoutes() {
  invalidateRealRouteByDayKeys(form.trip_days.map((day) => day.localKey));
}

function getItemDay(dayItem) {
  if (!dayItem?.localKey) {
    return null;
  }
  return (
    form.trip_days.find((day) =>
      day.items?.some((item) => item.localKey === dayItem.localKey)
    ) || null
  );
}

function getRealRouteSummaryItems(day) {
  const state = getRealRouteState(day?.localKey);
  if (state.bestItems.length > 0) {
    return state.bestItems;
  }
  const itemMap = new Map((day?.items || []).map((item) => [item.localKey, item]));
  return state.bestOrderKeys.map((itemKey) => itemMap.get(itemKey)).filter(Boolean);
}

function getRealRouteEmptyReason(day) {
  const state = getRealRouteState(day?.localKey);
  const routeableCount = getDayMappableCount(day);
  if (routeableCount < 2) {
    return routeableCount === 0
      ? '当前 Day 暂无可参与真实路线重算的条目'
      : '至少需要 2 个可路由条目才能开始真实路线重算';
  }
  if (routeableCount > MAX_REAL_ROUTE_POINTS) {
    return `当前 Day 可路由条目数超过 ${MAX_REAL_ROUTE_POINTS} 个，超出当前路线能力上限`;
  }
  if (state.emptyReason) {
    return state.emptyReason;
  }
  if (!state.bestOrderKeys.length) {
    return '点击“开始重算”后，将串行评估当前 Day 的真实道路优先方案';
  }
  return '';
}

const activeResourceDay = computed(() => form.trip_days[resourcePicker.dayIndex] || null);

const activeResourceItem = computed(() => {
  if (resourcePicker.mode !== 'replace') {
    return null;
  }
  return activeResourceDay.value?.items?.[resourcePicker.itemIndex] || null;
});

const resourcePickerTitle = computed(() => {
  if (!resourcePicker.isOpen) {
    return '资源库';
  }
  if (resourcePicker.mode === 'replace' && activeResourceItem.value) {
    return `替换条目：${activeResourceItem.value.title_snapshot || '未命名条目'}`;
  }
  return `Day ${resourcePicker.dayIndex + 1} 从资源库添加`;
});

const resourcePickerHint = computed(() => {
  if (!resourcePicker.isOpen) {
    return '';
  }
  if (resourcePicker.mode === 'replace') {
    return '选中资源后会覆盖类型与快照字段，保留时间、交通方式和备注。';
  }
  return '选中资源后会在当前 Day 末尾新增一个条目，时间与备注默认留空。';
});

function nextDayKey() {
  daySeed += 1;
  return `day-local-${daySeed}`;
}

function nextItemKey() {
  itemSeed += 1;
  return `item-local-${itemSeed}`;
}

function normalizeText(value) {
  if (value == null) {
    return '';
  }
  return String(value).trim();
}

function normalizeBudgetLevel(value) {
  if (value === '' || value == null) {
    return null;
  }

  const numericValue = Number(value);
  return Number.isInteger(numericValue) ? numericValue : value;
}

function normalizeRefId(value) {
  if (value === '' || value == null) {
    return null;
  }

  const numericValue = Number(value);
  return Number.isInteger(numericValue) ? numericValue : null;
}

function normalizeResourceType(value) {
  return SUPPORTED_RESOURCE_TYPES.includes(value) ? value : 'scenic_spot';
}

function formatDateByOffset(startDate, offset) {
  if (!startDate) {
    return '';
  }

  const baseDate = new Date(`${startDate}T00:00:00`);
  if (Number.isNaN(baseDate.getTime())) {
    return '';
  }

  baseDate.setDate(baseDate.getDate() + offset);
  const year = baseDate.getFullYear();
  const month = String(baseDate.getMonth() + 1).padStart(2, '0');
  const day = String(baseDate.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatDayDate(day, dayIndex) {
  if (form.start_date) {
    return formatDateByOffset(form.start_date, dayIndex) || '未设置日期';
  }
  return day.date || '未设置日期';
}

function getResourceTypeLabel(resourceType) {
  return RESOURCE_TYPE_LABELS[resourceType] || resourceType;
}

function formatResourceSummary(resourceType, resource) {
  const parts = [];
  if (resourceType === 'scenic_spot') {
    if (resource.type) {
      parts.push(`分类：${resource.type}`);
    }
    if (resource.ticket_price != null) {
      parts.push(`票价：¥${resource.ticket_price}`);
    }
  } else if (resourceType === 'food_place') {
    if (resource.cuisine_type) {
      parts.push(`菜系：${resource.cuisine_type}`);
    }
    if (resource.avg_price != null) {
      parts.push(`人均：¥${resource.avg_price}`);
    }
  } else if (resourceType === 'hotel') {
    if (resource.star_level) {
      parts.push(`星级：${resource.star_level}`);
    }
    if (resource.avg_price != null) {
      parts.push(`均价：¥${resource.avg_price}`);
    }
  }

  if (resource.rating_avg != null) {
    parts.push(`评分：${resource.rating_avg}`);
  }

  return parts.join(' · ') || '暂无更多信息';
}

function renumberItems(items) {
  return items.map((item, index) => ({
    ...item,
    item_index: index + 1,
  }));
}

function renumberDays(days) {
  return days.map((day, index) => ({
    ...day,
    day_index: index + 1,
    items: renumberItems(day.items || []),
  }));
}

function findDayIndexByLocalKey(dayKey) {
  return form.trip_days.findIndex((day) => day.localKey === dayKey);
}

function destroySortableInstances() {
  sortableInstances.forEach((instance) => instance.destroy());
  sortableInstances.clear();
}

function resolveSortableIndex(evt) {
  if (Number.isInteger(evt?.newDraggableIndex)) {
    return evt.newDraggableIndex;
  }
  if (Number.isInteger(evt?.newIndex)) {
    return evt.newIndex;
  }
  return null;
}

function handleSortableEnd(evt) {
  const sourceDayKey = evt?.from?.dataset?.dayKey;
  const targetDayKey = evt?.to?.dataset?.dayKey;
  const movedItemKey = evt?.item?.dataset?.itemKey;
  if (!sourceDayKey || !targetDayKey || !movedItemKey) {
    return;
  }

  const sourceDayIndex = findDayIndexByLocalKey(sourceDayKey);
  const targetDayIndex = findDayIndexByLocalKey(targetDayKey);
  if (sourceDayIndex < 0 || targetDayIndex < 0) {
    return;
  }

  const sourceDay = form.trip_days[sourceDayIndex];
  const targetDay = form.trip_days[targetDayIndex];
  const sourceItems = [...(sourceDay?.items || [])];
  const sourceItemIndex = sourceItems.findIndex((item) => item.localKey === movedItemKey);
  if (sourceItemIndex < 0) {
    return;
  }

  const [movedItem] = sourceItems.splice(sourceItemIndex, 1);
  const targetInsertIndexRaw = resolveSortableIndex(evt);
  const targetInsertIndex = Math.max(
    0,
    Math.min(
      Number.isInteger(targetInsertIndexRaw) ? targetInsertIndexRaw : targetDay.items.length,
      sourceDayIndex === targetDayIndex ? sourceItems.length : targetDay.items.length
    )
  );

  closeResourcePicker();

  if (sourceDayIndex === targetDayIndex) {
    sourceItems.splice(targetInsertIndex, 0, movedItem);
    sourceDay.items = renumberItems(sourceItems);
    invalidateRealRouteByDayKeys([sourceDayKey]);
    return;
  }

  const targetItems = [...(targetDay?.items || [])];
  targetItems.splice(targetInsertIndex, 0, movedItem);
  sourceDay.items = renumberItems(sourceItems);
  targetDay.items = renumberItems(targetItems);
  invalidateRealRouteByDayKeys([sourceDayKey, targetDayKey]);
}

function syncItemSortables() {
  if (!dayListRef.value) {
    return;
  }

  const currentDayKeys = new Set();
  const itemLists = dayListRef.value.querySelectorAll('[data-testid="trip-item-list"]');
  itemLists.forEach((itemList) => {
    const dayKey = itemList.dataset.dayKey;
    if (!dayKey) {
      return;
    }
    currentDayKeys.add(dayKey);
    if (sortableInstances.has(dayKey)) {
      return;
    }

    const sortable = Sortable.create(itemList, {
      animation: 150,
      forceFallback: true,
      fallbackOnBody: true,
      fallbackTolerance: 3,
      emptyInsertThreshold: 16,
      draggable: '.item-card',
      handle: '[data-testid="trip-drag-handle"]',
      ghostClass: 'item-card-ghost',
      chosenClass: 'item-card-chosen',
      dragClass: 'item-card-drag',
      group: {
        name: 'trip-day-items',
        pull: true,
        put: true,
      },
      onStart() {
        closeResourcePicker();
      },
      onEnd: handleSortableEnd,
    });

    sortableInstances.set(dayKey, sortable);
  });

  [...sortableInstances.keys()].forEach((dayKey) => {
    if (currentDayKeys.has(dayKey)) {
      return;
    }
    sortableInstances.get(dayKey)?.destroy();
    sortableInstances.delete(dayKey);
  });
}

function createEmptyDay(dayIndex = 1) {
  return {
    localKey: nextDayKey(),
    day_index: dayIndex,
    date: null,
    note: '',
    items: [],
  };
}

function createEmptyItem() {
  return {
    localKey: nextItemKey(),
    item_index: 1,
    item_type: 'custom',
    ref_id: null,
    title_snapshot: '',
    city_snapshot: form.origin_city || '',
    address_snapshot: '',
    start_time: '',
    end_time: '',
    transport_mode: '',
    note: '',
    longitude: null,
    latitude: null,
  };
}

function normalizeItem(item, index) {
  return {
    localKey: item.id ? `item-${item.id}` : nextItemKey(),
    item_index: index + 1,
    item_type: item.item_type || 'custom',
    ref_id: item.ref_id ?? null,
    title_snapshot: item.title_snapshot || '',
    city_snapshot: item.city_snapshot || '',
    address_snapshot: item.address_snapshot || '',
    start_time: item.start_time || '',
    end_time: item.end_time || '',
    transport_mode: item.transport_mode || '',
    note: item.note || '',
    longitude: normalizeCoordinate(item.longitude),
    latitude: normalizeCoordinate(item.latitude),
  };
}

function normalizeDay(day) {
  return {
    localKey: day.id ? `day-${day.id}` : nextDayKey(),
    day_index: day.day_index || 1,
    date: day.date || null,
    note: day.note || '',
    items: renumberItems((day.items || []).map((item, index) => normalizeItem(item, index))),
  };
}

function syncSelectedMapDay(days, preferCurrent = true) {
  if (!Array.isArray(days) || days.length === 0) {
    selectedMapDayIndex.value = 0;
    return;
  }

  if (preferCurrent && selectedMapDayIndex.value >= 0 && selectedMapDayIndex.value < days.length) {
    return;
  }

  const firstMappableDayIndex = days.findIndex((day) => getDayMappableCount(day) > 0);
  selectedMapDayIndex.value = firstMappableDayIndex >= 0 ? firstMappableDayIndex : 0;
}

function closeResourcePicker() {
  resourcePicker.isOpen = false;
  resourcePicker.mode = 'add';
  resourcePicker.dayIndex = -1;
  resourcePicker.itemIndex = -1;
  resourcePicker.resourceType = 'scenic_spot';
  resourcePicker.city = '';
  resourcePicker.keyword = '';
  resourcePicker.loading = false;
  resourcePicker.error = '';
  resourcePicker.results = [];
  resourcePicker.requestToken += 1;
}

function setFormFromTrip(trip) {
  closeResourcePicker();
  const tripDays = Array.isArray(trip.trip_days)
    ? [...trip.trip_days].sort((a, b) => (a.day_index || 0) - (b.day_index || 0))
    : [];
  const normalizedDays = renumberDays(tripDays.map((day) => normalizeDay(day)));

  form.title = trip.title || '';
  form.origin_city = trip.origin_city || '';
  form.start_date = trip.start_date || '';
  form.budget_level = trip.budget_level ?? null;
  form.travel_style = trip.travel_style || '';
  form.trip_days = normalizedDays.length ? normalizedDays : [createEmptyDay(1)];
  syncRealRouteStates(form.trip_days, true);
  syncSelectedMapDay(form.trip_days, false);
}

async function loadTripDetail() {
  if (!currentUser?.id) {
    return;
  }

  if (Number.isNaN(tripId)) {
    error.value = '无效的行程 ID';
    return;
  }

  loading.value = true;
  error.value = '';
  try {
    const resp = await getTrip(tripId, currentUser.id);
    setFormFromTrip(resp.data.trip || {});
  } catch (e) {
    const msg = e.response?.data?.error || '加载行程详情失败';
    error.value = msg;
    toast.error(msg);
  } finally {
    loading.value = false;
  }
}

function addDay() {
  if (form.trip_days.length >= MAX_TRIP_DAYS) {
    toast.error(`最多支持 ${MAX_TRIP_DAYS} 天`);
    return;
  }

  form.trip_days = renumberDays([
    ...form.trip_days,
    createEmptyDay(form.trip_days.length + 1),
  ]);
  syncRealRouteStates(form.trip_days);
  invalidateAllRealRoutes();
}

function removeDay(dayIndex) {
  if (form.trip_days.length === 1) {
    toast.error('至少保留 1 天');
    return;
  }

  closeResourcePicker();
  form.trip_days = renumberDays(
    form.trip_days.filter((_, index) => index !== dayIndex)
  );
  syncRealRouteStates(form.trip_days);
  invalidateAllRealRoutes();
}

function addItem(dayIndex) {
  const day = form.trip_days[dayIndex];
  if (!day) {
    return;
  }

  day.items = renumberItems([...day.items, createEmptyItem()]);
  invalidateRealRouteByDayKeys([day.localKey]);
}

function removeItem(dayIndex, itemIndex) {
  const day = form.trip_days[dayIndex];
  if (!day) {
    return;
  }

  closeResourcePicker();
  day.items = renumberItems(day.items.filter((_, index) => index !== itemIndex));
  invalidateRealRouteByDayKeys([day.localKey]);
}

function moveItem(dayIndex, itemIndex, offset) {
  const day = form.trip_days[dayIndex];
  if (!day) {
    return;
  }

  const targetIndex = itemIndex + offset;
  if (targetIndex < 0 || targetIndex >= day.items.length) {
    return;
  }

  const items = [...day.items];
  const [movedItem] = items.splice(itemIndex, 1);
  items.splice(targetIndex, 0, movedItem);
  day.items = renumberItems(items);
  invalidateRealRouteByDayKeys([day.localKey]);
}

function moveItemToAdjacentDay(dayIndex, itemIndex, offset) {
  const sourceDay = form.trip_days[dayIndex];
  const targetDay = form.trip_days[dayIndex + offset];
  if (!sourceDay || !targetDay) {
    return;
  }

  const sourceItems = [...sourceDay.items];
  const [movedItem] = sourceItems.splice(itemIndex, 1);
  if (!movedItem) {
    return;
  }

  closeResourcePicker();
  sourceDay.items = renumberItems(sourceItems);
  targetDay.items = renumberItems([...targetDay.items, movedItem]);
  invalidateRealRouteByDayKeys([sourceDay.localKey, targetDay.localKey]);
}

function applyDayRecommendation(dayIndex) {
  const day = form.trip_days[dayIndex];
  if (!day) {
    return;
  }

  const recommendation = buildDayRouteRecommendation(day.items || []);
  if (!recommendation.canApply) {
    return;
  }

  closeResourcePicker();
  day.items = renumberItems([...(recommendation.recommendedItems || [])]);
  invalidateRealRouteByDayKeys([day.localKey]);
  toast.success(`Day ${dayIndex + 1} 已应用路线建议顺序`);
}

async function recalculateRealRoute(dayIndex) {
  const day = form.trip_days[dayIndex];
  if (!day) {
    return;
  }

  closeResourcePicker();

  const dayKey = day.localKey;
  const state = getRealRouteState(dayKey);
  const requestToken = state.requestToken + 1;
  state.requestToken = requestToken;
  state.loading = true;
  state.stale = false;
  state.error = '';
  state.emptyReason = '';
  state.routeableCount = getDayMappableCount(day);
  state.skippedCount = Math.max(0, day.items.length - state.routeableCount);
  state.bestOrderKeys = [];
  state.bestItems = [];
  state.bestOption = null;

  const result = await evaluateTripRealRoute(day.items || [], (payload) => routeOptions(payload));
  const latestState = realRouteStates[dayKey];
  if (!latestState || latestState.requestToken !== requestToken) {
    return;
  }

  latestState.loading = false;
  latestState.routeableCount = result.routeableCount || 0;
  latestState.skippedCount = result.skippedCount || 0;

  if (result.status === 'success' && result.bestEvaluation) {
    latestState.bestOrderKeys = [...result.bestEvaluation.candidate.orderKeys];
    latestState.bestItems = [...result.bestEvaluation.candidate.orderedItems];
    latestState.bestOption = { ...result.bestEvaluation.option };
    latestState.lastEvaluatedSignature = createTripRealRouteSignature(day.items || []);
    latestState.emptyReason = '';
    latestState.error = '';
    latestState.stale = false;
    return;
  }

  latestState.lastEvaluatedSignature = '';
  latestState.bestOrderKeys = [];
  latestState.bestItems = [];
  latestState.bestOption = null;
  latestState.stale = false;

  if (result.status === 'error') {
    latestState.error = result.error || '真实路线重算失败';
    latestState.emptyReason = '';
    return;
  }

  latestState.error = '';
  latestState.emptyReason = result.reason || '当前 Day 暂无可用的真实路线方案';
}

function applyRealRoute(dayIndex) {
  const day = form.trip_days[dayIndex];
  if (!day) {
    return;
  }

  const state = getRealRouteState(day.localKey);
  if (state.loading || state.stale || state.bestOrderKeys.length === 0) {
    return;
  }

  closeResourcePicker();
  day.items = renumberItems(applyTripRealRouteOrder(day.items || [], state.bestOrderKeys));
  state.bestItems = getRealRouteSummaryItems(day);
  state.lastEvaluatedSignature = createTripRealRouteSignature(day.items || []);
  state.stale = false;
  state.error = '';
  state.emptyReason = '';
  toast.success(`Day ${dayIndex + 1} 已应用真实路线顺序`);
}

function openResourcePicker(mode, dayIndex, itemIndex = -1) {
  const day = form.trip_days[dayIndex];
  if (!day) {
    return;
  }

  const targetItem = mode === 'replace' ? day.items[itemIndex] : null;
  resourcePicker.isOpen = true;
  resourcePicker.mode = mode;
  resourcePicker.dayIndex = dayIndex;
  resourcePicker.itemIndex = mode === 'replace' ? itemIndex : -1;
  resourcePicker.resourceType = normalizeResourceType(targetItem?.item_type);
  resourcePicker.city = normalizeText(form.origin_city);
  resourcePicker.keyword = '';
  resourcePicker.loading = false;
  resourcePicker.error = '';
  resourcePicker.results = [];
  void searchResourceOptions();
}

async function searchResourceOptions() {
  if (!resourcePicker.isOpen) {
    return;
  }

  const requestToken = resourcePicker.requestToken + 1;
  resourcePicker.requestToken = requestToken;
  resourcePicker.loading = true;
  resourcePicker.error = '';
  const params = {
    page: 1,
    page_size: 10,
  };
  const city = normalizeText(resourcePicker.city);
  const keyword = normalizeText(resourcePicker.keyword);
  if (city) {
    params.city = city;
  }
  if (keyword) {
    params.keyword = keyword;
  }

  try {
    const resp = await searchTripResources(normalizeResourceType(resourcePicker.resourceType), params);
    if (resourcePicker.requestToken !== requestToken) {
      return;
    }
    resourcePicker.results = Array.isArray(resp.data?.items) ? resp.data.items : [];
  } catch (e) {
    if (resourcePicker.requestToken !== requestToken) {
      return;
    }
    resourcePicker.results = [];
    resourcePicker.error = e.response?.data?.error || '搜索资源失败';
  } finally {
    if (resourcePicker.requestToken === requestToken) {
      resourcePicker.loading = false;
    }
  }
}

function handleResourceTypeChange() {
  resourcePicker.resourceType = normalizeResourceType(resourcePicker.resourceType);
  void searchResourceOptions();
}

function handleItemTypeInput(item) {
  if (!isSupportedResourceType(item?.item_type)) {
    item.longitude = null;
    item.latitude = null;
  }
  const day = getItemDay(item);
  if (day?.localKey) {
    invalidateRealRouteByDayKeys([day.localKey]);
  }
}

function mapResourceToItem(resourceType, resource, currentItem = null) {
  const baseItem = currentItem ? { ...currentItem } : createEmptyItem();
  return {
    ...baseItem,
    item_type: resourceType,
    ref_id: normalizeRefId(resource.id),
    title_snapshot: normalizeText(resource.name),
    city_snapshot: normalizeText(resource.city) || form.origin_city || '',
    address_snapshot: normalizeText(resource.address),
    longitude: normalizeCoordinate(resource.longitude),
    latitude: normalizeCoordinate(resource.latitude),
  };
}

function applyResourceSelection(resource) {
  const day = form.trip_days[resourcePicker.dayIndex];
  if (!day) {
    return;
  }

  const resourceType = normalizeResourceType(resourcePicker.resourceType);

  if (resourcePicker.mode === 'replace') {
    const existingItem = day.items[resourcePicker.itemIndex];
    if (!existingItem) {
      return;
    }

    day.items = renumberItems(
      day.items.map((item, index) =>
        index === resourcePicker.itemIndex
          ? mapResourceToItem(resourceType, resource, existingItem)
          : item
      )
    );
    toast.success('条目资源已更新');
  } else {
    day.items = renumberItems([
      ...day.items,
      mapResourceToItem(resourceType, resource),
    ]);
    toast.success('资源条目已添加');
  }

  invalidateRealRouteByDayKeys([day.localKey]);
  closeResourcePicker();
}

function validateForm() {
  if (!normalizeText(form.title)) {
    toast.error('请输入行程标题');
    return false;
  }

  if (!normalizeText(form.origin_city)) {
    toast.error('请输入出发城市');
    return false;
  }

  if (form.trip_days.length < 1 || form.trip_days.length > MAX_TRIP_DAYS) {
    toast.error(`行程天数需要在 1 到 ${MAX_TRIP_DAYS} 天之间`);
    return false;
  }

  for (let dayIndex = 0; dayIndex < form.trip_days.length; dayIndex += 1) {
    const day = form.trip_days[dayIndex];
    for (let itemIndex = 0; itemIndex < day.items.length; itemIndex += 1) {
      const item = day.items[itemIndex];
      if (!normalizeText(item.item_type)) {
        toast.error(`请填写 Day ${dayIndex + 1} 第 ${itemIndex + 1} 个条目的类型`);
        return false;
      }
      if (!normalizeText(item.title_snapshot)) {
        toast.error(`请填写 Day ${dayIndex + 1} 第 ${itemIndex + 1} 个条目的标题`);
        return false;
      }
    }
  }

  return true;
}

function buildPayload() {
  const startDate = form.start_date || null;

  return {
    user_id: currentUser.id,
    title: normalizeText(form.title),
    start_date: startDate,
    origin_city: normalizeText(form.origin_city),
    budget_level: normalizeBudgetLevel(form.budget_level),
    travel_style: normalizeText(form.travel_style) || null,
    trip_days: form.trip_days.map((day, dayIndex) => ({
      day_index: dayIndex + 1,
      note: normalizeText(day.note) || null,
      items: day.items.map((item, itemIndex) => ({
        item_index: itemIndex + 1,
        item_type: normalizeText(item.item_type) || 'custom',
        ref_id: normalizeRefId(item.ref_id),
        title_snapshot: normalizeText(item.title_snapshot),
        city_snapshot: normalizeText(item.city_snapshot) || null,
        address_snapshot: normalizeText(item.address_snapshot) || null,
        start_time: normalizeText(item.start_time) || null,
        end_time: normalizeText(item.end_time) || null,
        transport_mode: normalizeText(item.transport_mode) || null,
        note: normalizeText(item.note) || null,
      })),
    })),
  };
}

async function handleSave() {
  if (!currentUser?.id || Number.isNaN(tripId) || !validateForm()) {
    return;
  }

  saving.value = true;
  try {
    const resp = await updateTrip(tripId, buildPayload());
    setFormFromTrip(resp.data.trip || {});
    toast.success('行程已保存');
  } catch (e) {
    const msg = e.response?.data?.error || '保存行程失败';
    toast.error(msg);
  } finally {
    saving.value = false;
  }
}

async function handleDelete() {
  if (!currentUser?.id || Number.isNaN(tripId)) {
    return;
  }

  if (!confirm('确定要删除这个行程吗？')) {
    return;
  }

  try {
    await deleteTrip(tripId, currentUser.id);
    toast.success('行程已删除');
    router.push('/trips');
  } catch (e) {
    const msg = e.response?.data?.error || '删除行程失败';
    toast.error(msg);
  }
}

watch(
  () => form.trip_days.length,
  () => {
    syncSelectedMapDay(form.trip_days, true);
  }
);

watch(
  [() => loading.value, () => form.trip_days.map((day) => day.localKey).join('|')],
  async ([isLoading]) => {
    if (isLoading) {
      return;
    }
    syncRealRouteStates(form.trip_days);
    await nextTick();
    syncItemSortables();
  },
  { flush: 'post' }
);

onMounted(() => {
  loadTripDetail();
});

onBeforeUnmount(() => {
  destroySortableInstances();
});
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.detail-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.block {
  padding: 16px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
}

.section-header,
.day-header,
.item-header,
.page-actions,
.resource-panel-header,
.resource-panel-actions,
.route-recommendation-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.compact-grid {
  margin-top: 12px;
}

.trip-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.trip-summary span,
.map-summary {
  padding: 6px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 13px;
}

.map-summary {
  font-weight: 600;
}

.map-day-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.map-day-tab {
  background: #dbeafe;
  color: #1d4ed8;
}

.map-day-tab.active {
  background: #2563eb;
  color: #ffffff;
}

.day-list {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}

.day-card {
  padding: 16px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
}

.day-actions,
.item-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.route-recommendation {
  margin-top: 12px;
  padding: 14px;
  border-radius: 10px;
  border: 1px solid #bfdbfe;
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
}

.route-recommendation-header h5 {
  margin: 0;
  font-size: 15px;
}

.route-recommendation-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.route-recommendation-real {
  border-color: #99f6e4;
  background: linear-gradient(180deg, #ecfeff 0%, #ffffff 100%);
}

.route-recommendation-body {
  margin-top: 12px;
}

.route-recommendation-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.route-recommendation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid #dbeafe;
}

.route-recommendation-order {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #2563eb;
  color: #ffffff;
  font-size: 12px;
  font-weight: 600;
}

.route-recommendation-title {
  flex: 1;
  font-weight: 600;
}

.route-recommendation-badge {
  padding: 4px 8px;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
  font-size: 12px;
}

.route-recommendation-badge.muted {
  background: #f1f5f9;
  color: #64748b;
}

.real-route-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.real-route-metric {
  padding: 6px 10px;
  border-radius: 999px;
  background: #ccfbf1;
  color: #115e59;
  font-size: 13px;
  font-weight: 600;
}

.real-route-stale {
  color: #b45309;
  margin-bottom: 12px;
}

.route-recommendation-empty {
  margin-top: 12px;
}

.resource-panel {
  margin-top: 12px;
  padding: 14px;
  border-radius: 10px;
  border: 1px solid #fdba74;
  background: linear-gradient(180deg, #fff7ed 0%, #ffffff 100%);
}

.resource-panel-header h5 {
  margin: 0;
  font-size: 15px;
}

.resource-panel-actions {
  margin-top: 12px;
  flex-wrap: wrap;
}

.resource-result-list,
.item-list {
  list-style: none;
  margin: 16px 0 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

.item-list[data-empty='true'] {
  min-height: 96px;
}

.resource-result,
.item-card {
  padding: 14px;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
}

.resource-result {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.resource-result-main {
  flex: 1;
}

.item-summary {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.item-title {
  font-weight: 600;
}

.item-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

.drag-handle {
  min-width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px dashed #94a3b8;
  background: #f8fafc;
  color: #334155;
  font-weight: 700;
  letter-spacing: 1px;
  cursor: grab;
  user-select: none;
}

.drag-handle:active {
  cursor: grabbing;
}

.item-card-ghost {
  opacity: 0.45;
}

.item-card-chosen {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}

.item-card-drag {
  opacity: 0.9;
}

.empty-items {
  margin-top: 12px;
  padding: 14px;
  border-radius: 8px;
  border: 1px dashed #cbd5e1;
  color: #64748b;
  font-size: 14px;
  background: #ffffff;
}

.block-field {
  margin-top: 12px;
}

.hint {
  color: #6b7280;
  font-size: 14px;
  margin: 4px 0 0;
}

.error {
  color: #b91c1c;
}

.empty-state {
  padding: 24px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
}

input,
select,
textarea {
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  background: #ffffff;
}

textarea {
  min-height: 88px;
  resize: vertical;
}

button,
.link-button {
  padding: 8px 12px;
  border-radius: 6px;
  border: none;
  background: #2563eb;
  color: #ffffff;
  cursor: pointer;
  text-decoration: none;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

button.danger {
  background: #dc2626;
}

.ghost-danger {
  background: #fee2e2;
  color: #b91c1c;
}

.button-secondary,
.link-button.secondary {
  background: #6b7280;
}

.link-like {
  background: transparent;
  color: #92400e;
  padding: 0;
}

@media (max-width: 768px) {
  .page-header,
  .section-header,
  .day-header,
  .item-header,
  .page-actions,
  .resource-panel-header,
  .resource-panel-actions,
  .resource-result,
  .route-recommendation-header,
  .route-recommendation-actions,
  .item-summary {
    flex-direction: column;
  }
}
</style>
