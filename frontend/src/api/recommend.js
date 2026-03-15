import api from './http';

export function getScenicRecommendations(params) {
  return api.get('/recommend/scenic-spots', { params });
}

export function getHotelRecommendations(params) {
  return api.get('/recommend/hotels', { params });
}

export function getFoodRecommendations(params) {
  return api.get('/recommend/foods', { params });
}

export function getSimilarScenicSpots(spotId, params) {
  return api.get(`/recommend/scenic-spots/${spotId}/similar`, { params });
}

export function getRecommendMetrics() {
  return api.get('/recommend/metrics');
}
