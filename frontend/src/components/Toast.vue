<template>
  <Transition name="toast">
    <div v-if="visible" :class="['toast', `toast-${type}`]" data-testid="toast">
      <span class="toast-icon">{{ iconMap[type] }}</span>
      <span class="toast-message" data-testid="toast-message">{{ message }}</span>
      <button v-if="closable" class="toast-close" @click="close">×</button>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';

const props = defineProps({
  message: {
    type: String,
    required: true
  },
  type: {
    type: String,
    default: 'info', // info | success | warning | error
    validator: (value) => ['info', 'success', 'warning', 'error'].includes(value)
  },
  duration: {
    type: Number,
    default: 3000 // 毫秒，0表示不自动关闭
  },
  closable: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['close']);

const visible = ref(false);
let timer = null;

const iconMap = {
  info: 'ℹ️',
  success: '✅',
  warning: '⚠️',
  error: '❌'
};

const close = () => {
  visible.value = false;
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
  emit('close');
};

const show = () => {
  visible.value = true;
  if (props.duration > 0) {
    timer = setTimeout(() => {
      close();
    }, props.duration);
  }
};

// 监听 message 变化，自动显示
watch(() => props.message, (newVal) => {
  if (newVal) {
    show();
  }
}, { immediate: true });

onMounted(() => {
  show();
});
</script>

<style scoped>
.toast {
  position: fixed;
  top: 20px;
  right: 20px;
  min-width: 280px;
  max-width: 400px;
  padding: 12px 16px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  gap: 10px;
  z-index: 9999;
  font-size: 14px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
}

.toast-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.toast-message {
  flex: 1;
  line-height: 1.5;
}

.toast-close {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  flex-shrink: 0;
}

.toast-close:hover {
  color: #1f2937;
}

.toast-info {
  border-left: 4px solid #3b82f6;
}

.toast-success {
  border-left: 4px solid #10b981;
}

.toast-warning {
  border-left: 4px solid #f59e0b;
}

.toast-error {
  border-left: 4px solid #ef4444;
}

/* 过渡动画 */
.toast-enter-active {
  animation: toast-in 0.3s ease-out;
}

.toast-leave-active {
  animation: toast-out 0.3s ease-in;
}

@keyframes toast-in {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes toast-out {
  from {
    transform: translateX(0);
    opacity: 1;
  }
  to {
    transform: translateX(100%);
    opacity: 0;
  }
}
</style>
