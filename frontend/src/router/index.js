import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import LoginView from '../views/LoginView.vue';
import RegisterView from '../views/RegisterView.vue';
import BrowseView from '../views/BrowseView.vue';
import ProfileView from '../views/ProfileView.vue';
import RouteView from '../views/RouteView.vue';
import TripsView from '../views/TripsView.vue';
import TripCreateView from '../views/TripCreateView.vue';
import TripDetailView from '../views/TripDetailView.vue';
import MonitorView from '../views/MonitorView.vue';

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView,
  },
  {
    path: '/register',
    name: 'register',
    component: RegisterView,
  },
  {
    path: '/browse',
    name: 'browse',
    component: BrowseView,
  },
  {
    path: '/profile',
    name: 'profile',
    component: ProfileView,
  },
  {
    path: '/route',
    name: 'route',
    component: RouteView,
  },
  {
    path: '/trips',
    name: 'trips',
    component: TripsView,
  },
  {
    path: '/trips/new',
    name: 'trip-create',
    component: TripCreateView,
  },
  {
    path: '/trips/:id',
    name: 'trip-detail',
    component: TripDetailView,
  },
  {
    path: '/monitor',
    name: 'monitor',
    component: MonitorView,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
