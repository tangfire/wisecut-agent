<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();
const email = ref("");
const password = ref("");
const displayName = ref("");
const error = ref("");

async function handleRegister() {
  error.value = "";
  try {
    await auth.register(email.value, password.value, displayName.value);
    router.push("/projects");
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "Registration failed";
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <h1>Agent Film</h1>
      <h2>Create account</h2>
      <form @submit.prevent="handleRegister">
        <div class="field">
          <label for="displayName">Display Name</label>
          <input id="displayName" v-model="displayName" type="text" required placeholder="Your name" />
        </div>
        <div class="field">
          <label for="email">Email</label>
          <input id="email" v-model="email" type="email" required placeholder="you@example.com" />
        </div>
        <div class="field">
          <label for="password">Password</label>
          <input id="password" v-model="password" type="password" required minlength="8" placeholder="At least 8 characters" />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="auth.loading" class="btn-primary">
          {{ auth.loading ? "Creating..." : "Create account" }}
        </button>
      </form>
      <p class="switch-auth">
        Already have an account? <router-link to="/login">Sign in</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-page { display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #f5f5f5; }
.auth-card { background: #fff; border-radius: 12px; padding: 40px; width: 400px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
.auth-card h1 { font-size: 24px; margin-bottom: 4px; }
.auth-card h2 { font-size: 16px; color: #666; font-weight: 400; margin-bottom: 24px; }
.field { margin-bottom: 16px; }
.field label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #333; }
.field input { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
.field input:focus { outline: none; border-color: #1a73e8; }
.error { color: #d93025; font-size: 13px; margin-bottom: 12px; }
.btn-primary { width: 100%; padding: 10px; background: #1a73e8; color: #fff; border: none; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.switch-auth { text-align: center; margin-top: 16px; font-size: 13px; color: #666; }
.switch-auth a { color: #1a73e8; text-decoration: none; }
</style>
