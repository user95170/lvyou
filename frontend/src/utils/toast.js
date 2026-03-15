import { createApp, h } from 'vue';
import Toast from '../components/Toast.vue';

/**
 * Toast 提示工具类
 * 用于在应用中显示全局提示消息
 */

let toastInstance = null;
let container = null;

const createToast = (options) => {
  // 移除已有的 toast
  if (toastInstance) {
    toastInstance.unmount();
    if (container && container.parentNode) {
      container.parentNode.removeChild(container);
    }
  }

  // 创建容器
  container = document.createElement('div');
  document.body.appendChild(container);

  // 创建 Toast 实例
  toastInstance = createApp({
    render() {
      return h(Toast, {
        ...options,
        onClose: () => {
          if (toastInstance) {
            toastInstance.unmount();
            if (container && container.parentNode) {
              container.parentNode.removeChild(container);
            }
            toastInstance = null;
            container = null;
          }
          if (options.onClose) {
            options.onClose();
          }
        }
      });
    }
  });

  toastInstance.mount(container);

  return {
    close: () => {
      if (toastInstance) {
        toastInstance.unmount();
        if (container && container.parentNode) {
          container.parentNode.removeChild(container);
        }
        toastInstance = null;
        container = null;
      }
    }
  };
};

export const toast = {
  show(message, type = 'info', duration = 3000) {
    return createToast({ message, type, duration });
  },

  info(message, duration = 3000) {
    return createToast({ message, type: 'info', duration });
  },

  success(message, duration = 3000) {
    return createToast({ message, type: 'success', duration });
  },

  warning(message, duration = 3000) {
    return createToast({ message, type: 'warning', duration });
  },

  error(message, duration = 4000) {
    return createToast({ message, type: 'error', duration });
  }
};

export default toast;
