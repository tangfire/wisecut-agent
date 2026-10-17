<script setup lang="ts">
import { onMounted } from "vue";
import { useAuthStore } from "./stores/auth";
import { useRouter } from "vue-router";

const auth = useAuthStore();
const router = useRouter();

onMounted(() => {
  if (auth.isAuthenticated) {
    auth.fetchUser();
  }
});

function handleLogout() {
  auth.logout();
  router.push("/login");
}
</script>

<template>
  <div id="app-root">
    <nav v-if="auth.isAuthenticated" class="topnav">
      <div class="topnav-inner">
        <div class="topnav-brand">
          <router-link to="/projects">Agent Film</router-link>
        </div>
        <div class="topnav-links">
          <router-link to="/projects">Projects</router-link>
          <router-link to="/settings">Settings</router-link>
          <span class="topnav-user">{{ auth.user?.display_name }}</span>
          <button @click="handleLogout" class="btn-logout">Logout</button>
        </div>
      </div>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
#app-root { min-height: 100vh; display: flex; flex-direction: column; }
.topnav { background: #fff; border-bottom: 1px solid #e0e0e0; position: sticky; top: 0; z-index: 100; }
.topnav-inner { max-width: 1200px; margin: 0 auto; padding: 0 24px; display: flex; justify-content: space-between; align-items: center; height: 56px; }
.topnav-brand a { font-size: 18px; font-weight: 700; color: #1a1a1a; text-decoration: none; }
.topnav-links { display: flex; gap: 16px; align-items: center; }
.topnav-links a { text-decoration: none; color: #555; font-size: 14px; }
.topnav-links a.router-link-active { color: #1a73e8; font-weight: 600; }
.topnav-user { font-size: 13px; color: #888; }
.btn-logout { background: none; border: 1px solid #ddd; border-radius: 6px; padding: 6px 12px; cursor: pointer; font-size: 13px; color: #555; }
.btn-logout:hover { background: #f0f0f0; }
.main-content { flex: 1; max-width: 1200px; width: 100%; margin: 0 auto; padding: 24px; }

/* Mobile responsive */
@media (max-width: 640px) {
  .topnav-inner { padding: 0 16px; }
  .topnav-links { gap: 12px; }
  .topnav-user { display: none; }
  .main-content { padding: 16px; }
}
</style>
