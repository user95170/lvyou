import api from './http';

/**
 * 记录用户行为日志
 * @param {Object} data - 行为数据
 * @param {number} data.user_id - 用户ID（可选）
 * @param {string} data.target_type - 目标类型，如 'scenic_spot'
 * @param {number} data.target_id - 目标ID
 * @param {string} data.behavior_type - 行为类型，如 'view', 'click'
 * @param {number} data.behavior_value - 行为数值（可选）
 * @param {string} data.device - 设备类型（可选）
 */
export function logBehavior(data) {
  return api.post('/behaviors', data);
}
