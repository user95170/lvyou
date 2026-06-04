import api from './http';

export function getScenicSpots(params) {
  return api.get('/scenic-spots', { params });
}

export function getHotels(params) {
  return api.get('/hotels', { params });
}

export function getFoods(params) {
  return api.get('/foods', { params });
}

export function createRating(payload) {
  return api.post('/ratings', payload);
}

export function createBehavior(payload) {
  return api.post('/behaviors', payload);
}

export function searchTripResources(resourceType, params) {
  if (resourceType === 'scenic_spot') {
    return getScenicSpots(params);
  }
  if (resourceType === 'food_place') {
    return getFoods(params);
  }
  if (resourceType === 'hotel') {
    return getHotels(params);
  }

  return Promise.reject(new Error(`unsupported resource type: ${resourceType}`));
}
