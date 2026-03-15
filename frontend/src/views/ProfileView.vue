<template>
  <div class="page">
    <div class="header">
      <div class="title">
        <h2>??????</h2>
        <p class="subtitle">??????????????????????????</p>
      </div>
      <button class="ghost" type="button" @click="resetChat" :disabled="sending">????</button>
    </div>

    <div v-if="!userId" class="notice">
      ?????????? Agent ?????????????????
    </div>

    <div class="layout">
      <section class="chat">
        <div ref="chatWindowRef" class="chat-window">
          <div v-if="showSuggestions" class="suggestions">
            <div class="suggestions-title">???????</div>
            <div class="suggestions-actions">
              <button
                type="button"
                class="chip"
                @click="sendSuggestion('?????????3????3000???')"
              >
                ?????? 3 ?
              </button>
              <button
                type="button"
                class="chip"
                @click="sendSuggestion('??????4????????????5000')"
              >
                ???? 4 ?
              </button>
              <button
                type="button"
                class="chip"
                @click="sendSuggestion('??????2??????????')"
              >
                ???? 2 ?
              </button>
            </div>
          </div>

          <div v-for="(m, idx) in chatMessages" :key="idx" class="msg" :class="m.role">
            <div class="bubble">
              <div class="meta">{{ m.role === 'user' ? '?' : '??' }}</div>
              <div class="content">{{ m.content }}</div>
            </div>
          </div>

          <div v-if="sending" class="msg assistant">
            <div class="bubble">
              <div class="meta">??</div>
              <div class="content">???...</div>
            </div>
          </div>
        </div>

        <form class="composer" data-testid="agent-form" @submit.prevent="handleSendChat">
          <input
            v-model="chatInput"
            data-testid="agent-input"
            type="text"
            :disabled="sending"
            placeholder="?????????2?????????3000???"
          />
          <button
            type="submit"
            data-testid="agent-send"
            :disabled="sending || !chatInput.trim()"
          >
            ??
          </button>
        </form>

        <p v-if="chatError" class="error">{{ chatError }}</p>
      </section>

      <aside class="side">
        <div class="card">
          <h3>?????Slots?</h3>
          <div v-if="!hasSlots" class="muted">??</div>
          <div v-else class="kv">
            <div class="row">
              <span class="k">???</span>
              <span class="v">{{ slots.destination || '???' }}</span>
            </div>
            <div class="row">
              <span class="k">??</span>
              <span class="v">{{ slots.days == null ? '???' : slots.days }}</span>
            </div>
            <div class="row">
              <span class="k">??</span>
              <span class="v">{{ budgetLabel(slots) }}</span>
            </div>
            <div class="row">
              <span class="k">????</span>
              <span class="v">{{ transportLabel(slots.transport_mode) }}</span>
            </div>
            <div class="row">
              <span class="k">??</span>
              <span class="v">{{ interestsLabel(slots.interests) }}</span>
            </div>
            <div class="row">
              <span class="k">??</span>
              <span class="v">{{ travelStyleLabel(slots.travel_style) }}</span>
            </div>
          </div>
          <details v-if="hasSlots" class="raw">
            <summary>???? JSON</summary>
            <pre>{{ JSON.stringify(slots, null, 2) }}</pre>
          </details>
        </div>

        <div class="card">
          <h3>?????Profile?</h3>
          <div v-if="!userId" class="muted">????????????</div>
          <div v-else class="kv">
            <div class="row">
              <span class="k">????</span>
              <span class="v">{{ travelStyleLabel(form.travel_style) }}</span>
            </div>
            <div class="row">
              <span class="k">????</span>
              <span class="v">{{ budgetLevelLabel(form.budget_level) }}</span>
            </div>
            <div class="row">
              <span class="k">??????</span>
              <span class="v">{{ form.prefer_scenic_types || '???' }}</span>
            </div>
            <div class="row">
              <span class="k">??????</span>
              <span class="v">{{ form.prefer_food_types || '???' }}</span>
            </div>
          </div>

          <details v-if="userId" class="edit">
            <summary>???????</summary>
            <form class="mini-form" @submit.prevent="handleSubmit">
              <label>
                ????
                <select v-model="form.travel_style">
                  <option value="">???</option>
                  <option value="relax">????</option>
                  <option value="adventure">????</option>
                  <option value="family">????</option>
                  <option value="culture">????</option>
                  <option value="photography">????</option>
                </select>
              </label>

              <label>
                ????
                <select v-model.number="form.budget_level">
                  <option :value="null">???</option>
                  <option :value="1">??</option>
                  <option :value="2">??</option>
                  <option :value="3">???</option>
                </select>
              </label>

              <label>
                ??????
                <input
                  v-model="form.prefer_scenic_types"
                  type="text"
                  placeholder="?????, ??, ???"
                />
              </label>

              <label>
                ??????
                <input
                  v-model="form.prefer_food_types"
                  type="text"
                  placeholder="?????, ??, ??"
                />
              </label>

              <div class="mini-actions">
                <button type="submit" :disabled="submitting">
                  {{ submitting ? '???...' : '????' }}
                </button>
              </div>
              <p v-if="error" class="error">{{ error }}</p>
              <p v-if="success" class="success">{{ success }}</p>
            </form>
          </details>
        </div>

        <div class="card">
          <h3>?????Itinerary?</h3>
          <div v-if="!itinerary" class="muted">
            ??????????Agent ?????????????
          </div>
          <div v-else class="itinerary" data-testid="agent-itinerary">
            <div class="it-summary">
              <span>???{{ itinerary.city || '??' }}</span>
              <span>???{{ itinerary.days ? itinerary.days.length : 0 }}</span>
            </div>
            <div v-for="day in itinerary.days" :key="day.day_index" class="it-day">
              <div class="it-day-title">Day {{ day.day_index }}</div>
              <div class="it-items">
                <div v-for="(item, idx) in day.items" :key="idx" class="it-item">
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
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue';
import { getCurrentUser } from '../utils/user';
import { fetchUserProfile, saveUserProfile } from '../api/profile';
import { chatAgent } from '../api/agent';

const user = getCurrentUser();
const userId = user?.id ?? null;

const assistantGreeting =
  '??????????????????????????????????????????????????';

const chatMessages = ref([{ role: 'assistant', content: assistantGreeting }]);
const chatInput = ref('');
const sending = ref(false);
const chatError = ref('');
const chatWindowRef = ref(null);

const slots = ref({});
const actions = ref([]);
const itinerary = ref(null);

const hasSlots = computed(() => Object.keys(slots.value || {}).length > 0);
const showSuggestions = computed(
  () => chatMessages.value.length === 1 && chatMessages.value[0]?.role === 'assistant'
);

const form = reactive({
  travel_style: '',
  budget_level: null,
  prefer_scenic_types: '',
  prefer_food_types: '',
});

const submitting = ref(false);
const error = ref('');
const success = ref('');

function travelStyleLabel(value) {
  const v = value || '';
  if (v === 'relax') return '????';
  if (v === 'adventure') return '????';
  if (v === 'family') return '????';
  if (v === 'culture') return '????';
  if (v === 'photography') return '????';
  return v || '???';
}

function budgetLevelLabel(value) {
  if (value === 1) return '??';
  if (value === 2) return '??';
  if (value === 3) return '???';
  return '???';
}

function transportLabel(mode) {
  if (mode === 'drive') return '??';
  if (mode === 'transit') return '????';
  if (mode === 'walk') return '??';
  return mode || '???';
}

function interestsLabel(value) {
  if (Array.isArray(value) && value.length) return value.join('?');
  return '???';
}

function budgetLabel(s) {
  const amount = s?.budget_amount;
  const level = s?.budget_level;
  const levelText = budgetLevelLabel(level);
  if (amount != null && String(amount) !== '') {
    return `${String(amount)} (${levelText})`;
  }
  return levelText;
}

function itineraryItemTitle(item) {
  if (!item) return '?????';
  if (item.name) return item.name;
  const typeLabel =
    item.type === 'scenic_spot'
      ? '??'
      : item.type === 'food_place'
      ? '??'
      : item.type || '??';
  return `${typeLabel} #${item.id}`;
}

async function scrollChatToBottom() {
  await nextTick();
  const el = chatWindowRef.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

function resetChat() {
  chatMessages.value = [{ role: 'assistant', content: assistantGreeting }];
  chatInput.value = '';
  chatError.value = '';
  slots.value = {};
  actions.value = [];
  itinerary.value = null;
}

function applyProfileToForm(profile) {
  if (!profile) return;
  form.travel_style = profile.travel_style || '';
  form.budget_level = profile.budget_level ?? null;
  form.prefer_scenic_types = profile.prefer_scenic_types || '';
  form.prefer_food_types = profile.prefer_food_types || '';
}

async function sendChatText(text) {
  const t = (text || '').trim();
  if (!t || sending.value) return;

  chatError.value = '';
  chatMessages.value.push({ role: 'user', content: t });
  chatInput.value = '';
  sending.value = true;
  await scrollChatToBottom();

  try {
    const payload = {
      user_id: userId,
      text: t,
      messages: chatMessages.value.map((m) => ({ role: m.role, content: m.content })),
    };
    const resp = await chatAgent(payload);
    const data = resp.data || {};
    if (data.reply) {
      chatMessages.value.push({ role: 'assistant', content: data.reply });
    }
    slots.value = data.slots || {};
    actions.value = data.actions || [];
    itinerary.value = data.itinerary || null;
    if (data.profile) applyProfileToForm(data.profile);
  } catch (e) {
    chatError.value = e.response?.data?.error || '??????????';
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
    if (!profile) return;
    applyProfileToForm(profile);
  } catch (e) {
    console.error('????????', e);
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
    };
    await saveUserProfile(payload);
    success.value = '???????????????????';
  } catch (e) {
    error.value = e.response?.data?.error || '??????????';
  } finally {
    submitting.value = false;
  }
}

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

.notice {
  padding: 8px 12px;
  border-radius: 4px;
  background: #fef3c7;
  color: #92400e;
  font-size: 14px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 12px;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
}

h3 {
  margin: 0;
  font-size: 16px;
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

button {
  align-self: flex-start;
  margin-top: 8px;
  padding: 8px 12px;
  border-radius: 4px;
  border: none;
  background: #2563eb;
  color: #ffffff;
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
  margin-top: 0;
}

.composer button {
  margin-top: 0;
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
</style>

