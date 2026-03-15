import api from './http';

export function login(payload) {
  return api.post('/auth/login', payload);
}

export function register(payload) {
  return api.post('/auth/register', payload);
}
