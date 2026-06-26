<template>
  <div class="page">
    <div class="header">
      <div class="title">
        <h2>我的偏好</h2>
        <p class="subtitle">通过对话生成偏好槽位、更新画像，并预览多日行程草案。</p>
      </div>
      <button class="ghost" type="button" @click="resetChat" :disabled="sending">
        清空对话
      </button>
    </div>

    <div v-if="!userId" class="notice">
      未登录时也可以和 Agent 对话并预览行程草案，但不会写入画像，也不能保存为我的行程。
    </div>

    <div class="layout">
      <section class="chat">
        <div ref="chatWindowRef" class="chat-window">
          <div v-if="showSuggestions" class="suggestions">
            <div class="suggestions-title">可以这样开始：</div>
            <div class="suggestions-actions">
              <button
                type="button"
                class="chip"
                @click="sendSuggestion('想自驾去呼伦贝尔玩3天，预算3000，亲子')"
              >
                呼伦贝尔 3 天
              </button>
              <button
                type="button"
                class="chip"
                @click="sendSuggestion('去呼和浩特玩4天，喜欢人文历史和美食，预算5000')"
              >
                呼和浩特 4 天
              </button>
              <button
                type="button"
                class="chip"
                @click="sendSuggestion('想去包头玩2天，轻松一点，想吃本地特色')"
              >
                包头 2 天
              </button>
            </div>
          </div>

          <div v-for="(message, index) in chatMessages" :key="index" class="msg" :class="message.role">
            <div class="bubble">
              <div class="meta">{{ message.role === 'user' ? '我' : 'Agent' }}</div>
              <div class="content">{{ message.content }}</div>
            </div>
          </div>

          <div v-if="sending" class="msg assistant">
            <div class="bubble">
              <div class="meta">Agent</div>
              <div class="content">正在思考中...</div>
            </div>
          </div>
        </div>

        <form class="composer" data-testid="agent-form" @submit.prevent="handleSendChat">
          <input
            v-model="chatInput"
            data-testid="agent-input"
            type="text"
            :disabled="sending"
            placeholder="例如：想自驾去呼伦贝尔玩3天，预算3000，亲子"
          />
          <button
            type="submit"
            data-testid="agent-send"
            :disabled="sending || !chatInput.trim()"
          >
            发送
          </button>
        </form>

        <p v-if="chatError" class="error">{{ chatError }}</p>
      </section>

      <aside class="side">
        <div class="card">
          <h3>识别结果（Slots）</h3>
          <div v-if="!hasSlots" class="muted">还没有识别到槽位。</div>
          <div v-else class="kv">
            <div class="row">
              <span class="k">目的地</span>
              <span class="v">{{ slots.destination || '未识别' }}</span>
            </div>
            <div class="row">
              <span class="k">天数</span>
              <span class="v">{{ slots.days == null ? '未识别' : slots.days }}</span>
            </div>
            <div class="row">
              <span class="k">预算</span>
              <span class="v">{{ budgetLabel(slots) }}</span>
            </div>
            <div class="row">
              <span class="k">交通方式</span>
              <span class="v">{{ transportLabel(slots.transport_mode) }}</span>
            </div>
            <div class="row">
              <span class="k">兴趣</span>
              <span class="v">{{ interestsLabel(slots.interests) }}</span>
            </div>
            <div class="row">
              <span class="k">出游风格</span>
              <span class="v">{{ travelStyleLabel(slots.travel_style) }}</span>
            </div>
          </div>

          <details v-if="hasSlots" class="raw">
            <summary>查看原始 JSON</summary>
            <pre>{{ JSON.stringify(slots, null, 2) }}</pre>
          </details>
        </div>

        <div class="card">
          <h3>当前画像</h3>
          <div v-if="!userId" class="muted">登录后才会保存画像。</div>
          <div v-else class="kv">
            <div class="row">
              <span class="k">性别</span>
              <span class="v">{{ genderLabel(form.gender) }}</span>
            </div>
            <div class="row">
              <span class="k">年龄</span>
              <span class="v">{{ form.age === '' || form.age === null ? '未设置' : form.age }}</span>
            </div>
            <div class="row">
              <span class="k">常住地/籍贯</span>
              <span class="v">{{ form.home_region || '未设置' }}</span>
            </div>
            <div class="row">
              <span class="k">出游风格</span>
              <span class="v">{{ travelStyleLabel(form.travel_style) }}</span>
            </div>
            <div class="row">
              <span class="k">预算等级</span>
              <span class="v">{{ budgetLevelLabel(form.budget_level) }}</span>
            </div>
            <div class="row">
              <span class="k">偏好景点</span>
              <span class="v">{{ form.prefer_scenic_types || '未设置' }}</span>
            </div>
            <div class="row">
              <span class="k">偏好美食</span>
              <span class="v">{{ form.prefer_food_types || '未设置' }}</span>
            </div>
          </div>

          <details v-if="userId" class="edit">
            <summary>手动编辑画像</summary>
            <form class="mini-form" @submit.prevent="handleSubmit">
              <label>
                性别
                <select v-model="form.gender">
                  <option value="">不愿透露</option>
                  <option value="male">男</option>
                  <option value="female">女</option>
                </select>
              </label>

              <label>
                年龄
                <input
                  v-model="form.age"
                  type="number"
                  min="1"
                  max="120"
                  placeholder="例如：28"
                />
              </label>

              <label>
                常住地 / 籍贯
                <input
                  v-model="form.home_region"
                  type="text"
                  placeholder="例如：湖南、内蒙古"
                />
              </label>

              <label>
                出游风格
                <select v-model="form.travel_style">
                  <option value="">未设置</option>
                  <option value="relax">轻松</option>
                  <option value="adventure">探索</option>
                  <option value="family">亲子</option>
                  <option value="culture">人文</option>
                  <option value="photography">摄影</option>
                </select>
              </label>

              <label>
                预算等级
                <select v-model.number="form.budget_level">
                  <option :value="null">未设置</option>
                  <option :value="1">低</option>
                  <option :value="2">中</option>
                  <option :value="3">高</option>
                </select>
              </label>

              <label>
                偏好景点类型
                <input
                  v-model="form.prefer_scenic_types"
                  type="text"
                  placeholder="例如：草原, 湖泊, 博物馆"
                />
              </label>

              <label>
                偏好美食类型
                <input
                  v-model="form.prefer_food_types"
                  type="text"
                  placeholder="例如：锅茶, 手把肉, 奶茶"
                />
              </label>

              <div class="mini-actions">
                <button type="submit" :disabled="submitting">
                  {{ submitting ? '保存中...' : '保存画像' }}
                </button>
              </div>
              <p v-if="error" class="error">{{ error }}</p>
              <p v-if="success" class="success">{{ success }}</p>
            </form>
          </details>
        </div>

        <div class="card">
          <h3>行程草案</h3>
          <div v-if="!hasItineraryDays" class="muted">
            继续和 Agent 对话，当识别到目的地后，这里会生成多日草案。
          </div>

          <div v-else class="itinerary" data-testid="agent-itinerary">
            <div class="it-summary">
              <span>城市：{{ itinerary.city || '未识别' }}</span>
              <span>天数：{{ itinerary.days.length }}</span>
            </div>

            <div v-for="day in itinerary.days" :key="day.day_index" class="it-day">
              <div class="it-day-title">Day {{ day.day_index }}</div>
              <div class="it-items">
                <div v-for="(item, index) in day.items" :key="index" class="it-item">
                  <div class="it-time">{{ item.start_time }} - {{ item.end_time }}</div>
                  <div class="it-main">
                    <div class="it-name">{{ itineraryItemTitle(item) }}</div>
                    <div v-if="item.address" class="it-addr">{{ item.address }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="hasItineraryDays && userId"
          class="card"
          data-testid="agent-save-section"
        >
          <h3>保存为多日行程</h3>
          <label>
            行程标题
            <input
              v-model="saveForm.title"
              data-testid="agent-save-title-input"
              type="text"
              placeholder="请输入行程标题"
            />
          </label>

          <label>
            出发日期
            <input
              v-model="saveForm.start_date"
              data-testid="agent-save-date-input"
              type="date"
            />
          </label>

          <p class="muted">保存后会跳转到“我的行程”详情页，可继续补充天数和自定义条目。</p>

          <button
            type="button"
            data-testid="agent-save-btn"
            :disabled="savingTrip"
            @click="handleSaveItinerary"
          >
            {{ savingTrip ? '保存中...' : '保存为行程' }}
          </button>
        </div>

        <div
          v-else-if="hasItineraryDays"
          class="card"
          data-testid="agent-save-login-hint"
        >
          <h3>保存为多日行程</h3>
          <p class="muted">登录后即可把这份 Agent 草案保存到“我的行程”。</p>
          <router-link to="/login" class="link-button">前往登录</router-link>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { chatAgent } from '../api/agent';
import { fetchUserProfile, saveUserProfile } from '../api/profile';
import { createTrip } from '../api/trips';
import { toast } from '../utils/toast';
import { getCurrentUser } from '../utils/user';

const router = useRouter();
const user = getCurrentUser();
const userId = user?.id ?? null;

const assistantGreeting =
  '你好，我可以帮你整理出行偏好并生成多日行程草案。你可以告诉我目的地、天数、预算、交通方式和兴趣。';

const chatMessages = ref([{ role: 'assistant', content: assistantGreeting }]);
const chatInput = ref('');
const sending = ref(false);
const chatError = ref('');
const chatWindowRef = ref(null);

const slots = ref({});
const actions = ref([]);
const itinerary = ref(null);

const saveForm = reactive({
  title: '',
  start_date: '',
});
const savingTrip = ref(false);

const hasSlots = computed(() => Object.keys(slots.value || {}).length > 0);
const hasItineraryDays = computed(
  () => Array.isArray(itinerary.value?.days) && itinerary.value.days.length > 0
);
const showSuggestions = computed(
  () => chatMessages.value.length === 1 && chatMessages.value[0]?.role === 'assistant'
);

const form = reactive({
  travel_style: '',
  budget_level: null,
  prefer_scenic_types: '',
  prefer_food_types: '',
  gender: '',
  age: '',
  home_region: '',
});

const submitting = ref(false);
const error = ref('');
const success = ref('');

function travelStyleLabel(value) {
  const normalizedValue = value || '';
  if (normalizedValue === 'relax') return '轻松';
  if (normalizedValue === 'adventure') return '探索';
  if (normalizedValue === 'family') return '亲子';
  if (normalizedValue === 'culture') return '人文';
  if (normalizedValue === 'photography') return '摄影';
  return normalizedValue || '未设置';
}

function budgetLevelLabel(value) {
  if (value === 1) return '低';
  if (value === 2) return '中';
  if (value === 3) return '高';
  return '未设置';
}

function transportLabel(mode) {
  if (mode === 'drive') return '自驾';
  if (mode === 'transit') return '公共交通';
  if (mode === 'walk') return '步行';
  return mode || '未设置';
}

function interestsLabel(value) {
  if (Array.isArray(value) && value.length) {
    return value.join('、');
  }
  return '未识别';
}

function budgetLabel(slotValue) {
  const amount = slotValue?.budget_amount;
  const levelText = budgetLevelLabel(slotValue?.budget_level);
  if (amount != null && String(amount) !== '') {
    return `${String(amount)} (${levelText})`;
  }
  return levelText;
}

function itineraryItemTitle(item) {
  if (!item) return '未命名条目';
  if (item.name) return item.name;
  if (item.title_snapshot) return item.title_snapshot;
  if (item.type === 'scenic_spot') return `景点 #${item.id ?? '-'}`;
  if (item.type === 'food_place') return `美食 #${item.id ?? '-'}`;
  return item.type || '自定义条目';
}

function getTripOriginCity() {
  return itinerary.value?.city || slots.value?.destination || '';
}

function resetSaveForm() {
  const city = getTripOriginCity();
  saveForm.title = city ? `${city}多日行程` : '多日行程';
  saveForm.start_date = '';
}

function normalizeRefId(value) {
  if (value == null || value === '') {
    return null;
  }

  const numericValue = Number(value);
  return Number.isInteger(numericValue) ? numericValue : null;
}

function buildTripPayloadFromItinerary() {
  const originCity = getTripOriginCity().trim();
  if (!originCity) {
    return null;
  }

  return {
    user_id: userId,
    title: saveForm.title.trim() || `${originCity}多日行程`,
    start_date: saveForm.start_date || null,
    origin_city: originCity,
    created_by: 'agent_planner',
    trip_days: itinerary.value.days.map((day, dayIndex) => ({
      day_index: day.day_index || dayIndex + 1,
      note: day.note || null,
      items: (day.items || []).map((item, itemIndex) => ({
        item_index: item.item_index || itemIndex + 1,
        item_type: item.type || item.item_type || 'custom',
        ref_id: normalizeRefId(item.id ?? item.ref_id),
        title_snapshot: item.name || item.title_snapshot || itineraryItemTitle(item),
        city_snapshot: originCity,
        address_snapshot: item.address || item.address_snapshot || null,
        start_time: item.start_time || null,
        end_time: item.end_time || null,
        transport_mode: item.transport_mode || null,
        note: item.note || null,
      })),
    })),
  };
}

async function scrollChatToBottom() {
  await nextTick();
  const element = chatWindowRef.value;
  if (!element) return;
  element.scrollTop = element.scrollHeight;
}

function resetChat() {
  chatMessages.value = [{ role: 'assistant', content: assistantGreeting }];
  chatInput.value = '';
  chatError.value = '';
  slots.value = {};
  actions.value = [];
  itinerary.value = null;
  resetSaveForm();
}

function applyProfileToForm(profile) {
  if (!profile) return;
  form.travel_style = profile.travel_style || '';
  form.budget_level = profile.budget_level ?? null;
  form.prefer_scenic_types = profile.prefer_scenic_types || '';
  form.prefer_food_types = profile.prefer_food_types || '';
  if ('gender' in profile) {
    form.gender = profile.gender && profile.gender !== 'unknown' ? profile.gender : '';
  }
  if ('age' in profile) {
    form.age = profile.age ?? '';
  }
  if ('home_region' in profile) {
    form.home_region = profile.home_region || '';
  }
}

function genderLabel(value) {
  if (value === 'male') return '男';
  if (value === 'female') return '女';
  return '未设置';
}

async function sendChatText(text) {
  const trimmedText = (text || '').trim();
  if (!trimmedText || sending.value) return;

  chatError.value = '';
  chatMessages.value.push({ role: 'user', content: trimmedText });
  chatInput.value = '';
  sending.value = true;
  await scrollChatToBottom();

  try {
    const payload = {
      user_id: userId,
      text: trimmedText,
      messages: chatMessages.value.map((message) => ({
        role: message.role,
        content: message.content,
      })),
    };
    const resp = await chatAgent(payload);
    const data = resp.data || {};
    if (data.reply) {
      chatMessages.value.push({ role: 'assistant', content: data.reply });
    }
    slots.value = data.slots || {};
    actions.value = data.actions || [];
    itinerary.value = data.itinerary || null;
    if (data.profile) {
      applyProfileToForm(data.profile);
    }
  } catch (e) {
    chatError.value = e.response?.data?.error || '生成行程草案失败';
  } finally {
    sending.value = false;
    await scrollChatToBottom();
  }
}

async function handleSendChat() {
  await sendChatText(chatInput.value);
}

async function sendSuggestion(text) {
  await sendChatText(text);
}

async function loadProfile() {
  if (!userId) return;

  try {
    const resp = await fetchUserProfile(userId);
    const profile = resp.data?.profile;
    if (profile) {
      applyProfileToForm(profile);
    }
  } catch (e) {
    console.error('加载画像失败', e);
  }
}

async function handleSubmit() {
  if (!userId) return;

  submitting.value = true;
  error.value = '';
  success.value = '';
  try {
    const payload = {
      user_id: userId,
      travel_style: form.travel_style || null,
      budget_level: form.budget_level ?? null,
      prefer_scenic_types: form.prefer_scenic_types || null,
      prefer_food_types: form.prefer_food_types || null,
      gender: form.gender || 'unknown',
      age: form.age === '' || form.age === null ? null : Number(form.age),
      home_region: form.home_region ? form.home_region.trim() : null,
    };
    await saveUserProfile(payload);
    success.value = '画像已保存';
  } catch (e) {
    error.value = e.response?.data?.error || '保存画像失败';
  } finally {
    submitting.value = false;
  }
}

async function handleSaveItinerary() {
  if (!userId || !hasItineraryDays.value) {
    return;
  }

  const payload = buildTripPayloadFromItinerary();
  if (!payload) {
    toast.error('无法识别出发城市，请继续补充目的地信息');
    return;
  }

  savingTrip.value = true;
  try {
    const resp = await createTrip(payload);
    const tripId = resp.data?.trip?.id;
    toast.success('多日行程已保存');
    if (tripId) {
      router.push(`/trips/${tripId}`);
    } else {
      router.push('/trips');
    }
  } catch (e) {
    const message = e.response?.data?.error || '保存多日行程失败';
    toast.error(message);
  } finally {
    savingTrip.value = false;
  }
}

watch(
  () => itinerary.value,
  () => {
    resetSaveForm();
  }
);

onMounted(() => {
  resetChat();
  loadProfile();
});
</script>

<style scoped>
.page {
  max-width: 1100px;
  margin: 24px auto;
  padding: 16px;
  background: #ffffff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.title h2 {
  margin: 0;
}

.subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: #6b7280;
}

.notice {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #fef3c7;
  color: #92400e;
  font-size: 14px;
}

.ghost {
  margin-top: 0;
  background: transparent;
  color: #2563eb;
  border: 1px solid #bfdbfe;
}

.layout {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 16px;
  margin-top: 12px;
}

.chat {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-window {
  height: 520px;
  overflow-y: auto;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
}

.suggestions {
  margin-bottom: 12px;
}

.suggestions-title {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}

.suggestions-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  margin-top: 0;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  color: #111827;
  padding: 8px 10px;
  border-radius: 999px;
  font-size: 13px;
}

.msg {
  display: flex;
  margin-bottom: 10px;
}

.msg.user {
  justify-content: flex-end;
}

.msg.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 84%;
  border-radius: 10px;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
}

.msg.user .bubble {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.meta {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.content {
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-word;
}

.composer {
  display: flex;
  gap: 8px;
}

.composer input {
  flex: 1;
}

.side {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  background: #ffffff;
}

.card h3 {
  margin: 0 0 10px;
  font-size: 16px;
}

.muted {
  color: #6b7280;
  font-size: 13px;
}

.kv {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
}

.k {
  color: #6b7280;
}

.v {
  color: #111827;
  text-align: right;
}

.raw {
  margin-top: 10px;
}

.raw pre {
  margin: 8px 0 0;
  padding: 8px;
  background: #f3f4f6;
  border-radius: 6px;
  overflow: auto;
  font-size: 12px;
}

.edit {
  margin-top: 10px;
}

.mini-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}

.mini-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.itinerary {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.it-summary {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #374151;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
}

.it-day-title {
  font-weight: 600;
  font-size: 13px;
  margin-top: 8px;
}

.it-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.it-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.it-time {
  width: 110px;
  flex-shrink: 0;
  font-size: 12px;
  color: #6b7280;
}

.it-main {
  flex: 1;
}

.it-name {
  font-size: 13px;
  color: #111827;
}

.it-addr {
  font-size: 12px;
  color: #6b7280;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
}

input,
select,
button,
.link-button {
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  background: #ffffff;
  font-size: 14px;
}

button,
.link-button {
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

.error {
  margin-top: 4px;
  color: #b91c1c;
  font-size: 13px;
}

.success {
  margin-top: 4px;
  color: #047857;
  font-size: 13px;
}

@media (max-width: 960px) {
  .layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .header,
  .composer,
  .row,
  .it-summary,
  .it-item {
    flex-direction: column;
  }

  .it-time {
    width: auto;
  }
}
</style>
