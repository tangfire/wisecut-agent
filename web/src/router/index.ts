/**
 * Vue Router configuration.
 */
import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("../views/LoginView.vue"),
      meta: { requiresAuth: false },
    },
    {
      path: "/register",
      name: "register",
      component: () => import("../views/RegisterView.vue"),
      meta: { requiresAuth: false },
    },
    {
      path: "/",
      redirect: "/projects",
    },
    {
      path: "/projects",
      name: "projects",
      component: () => import("../views/projects/ProjectListView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/projects/:projectId",
      name: "project-detail",
      component: () => import("../views/projects/ProjectDetailView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/workbench/:projectId",
      name: "workbench",
      component: () => import("../views/workbench/WorkbenchView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("../views/settings/SettingsView.vue"),
      meta: { requiresAuth: true },
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: "login" };
  }
});

export default router;
