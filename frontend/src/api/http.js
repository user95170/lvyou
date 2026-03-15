import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 简单错误透传，后续如需统一处理可在此扩展
    return Promise.reject(error);
  }
);

export default api;
