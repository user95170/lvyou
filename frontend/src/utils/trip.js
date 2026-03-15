/**
 * 行程规划待选景点管理工具
 * 使用 localStorage 存储用户从推荐页面加入行程的景点
 */

const STORAGE_KEY = 'trip_pending_spots';

/**
 * 获取待规划景点列表
 * @returns {Array} 景点对象数组
 */
export function getPendingSpots() {
  try {
    const data = localStorage.getItem(STORAGE_KEY);
    return data ? JSON.parse(data) : [];
  } catch (e) {
    console.error('读取待规划景点失败', e);
    return [];
  }
}

/**
 * 添加景点到待规划列表
 * @param {Object} spot - 景点对象
 * @returns {boolean} 是否成功添加
 */
export function addPendingSpot(spot) {
  try {
    const spots = getPendingSpots();
    // 检查是否已存在
    if (spots.some(s => s.id === spot.id)) {
      return false;
    }
    spots.push({
      id: spot.id,
      name: spot.name,
      city: spot.city,
      description: spot.description,
      tags: spot.tags
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(spots));
    return true;
  } catch (e) {
    console.error('添加待规划景点失败', e);
    return false;
  }
}

/**
 * 从待规划列表中移除景点
 * @param {number} spotId - 景点ID
 */
export function removePendingSpot(spotId) {
  try {
    const spots = getPendingSpots();
    const filtered = spots.filter(s => s.id !== spotId);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
  } catch (e) {
    console.error('移除待规划景点失败', e);
  }
}

/**
 * 清空待规划列表
 */
export function clearPendingSpots() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (e) {
    console.error('清空待规划景点失败', e);
  }
}

/**
 * 获取待规划景点数量
 * @returns {number}
 */
export function getPendingSpotsCount() {
  return getPendingSpots().length;
}
