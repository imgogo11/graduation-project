<script setup lang="ts">
defineProps<{
  title: string;
  description: string;
}>();
</script>

<template>
  <div class="empty-state">
    <div class="empty-state__orb" />
    <h3 class="empty-state__title">{{ title }}</h3>
    <p class="empty-state__description">{{ description }}</p>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 10px;
  padding: 36px 18px;
  border-radius: 20px;
  border: 1px dashed var(--panel-border-strong);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.92), rgba(255, 255, 255, 0.92));
}

.empty-state__orb {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--accent-primary), var(--accent-blue));
  box-shadow: 0 0 0 12px rgba(240, 90, 40, 0.08);
}

.empty-state__title {
  margin: 0;
  font-size: 18px;
}

.empty-state__description {
  margin: 0;
  max-width: 460px;
  color: var(--text-secondary);
  line-height: 1.7;
  font-size: 14px;
}
</style>
