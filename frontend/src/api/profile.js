import api from './http';

export function fetchUserProfile(userId) {
  return api.get(`/user/profile/${userId}`);
}

export function saveUserProfile(payload) {
  return api.post('/user/profile', payload);
}
