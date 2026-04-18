<script setup lang="ts">
defineProps<{
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "teal" | "orange" | "berry";
}>();
</script>

<template>
  <article class="stat-card" :class="`stat-card--${tone || 'neutral'}`">
    <div class="stat-card__label">{{ label }}</div>
    <div class="stat-card__value">{{ value }}</div>
    <div v-if="hint" class="stat-card__hint">{{ hint }}</div>
  </article>
</template>

<style scoped>
.stat-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 20px;
  border-radius: 22px;
  border: 1px solid var(--panel-border);
  background: var(--panel-strong);
  box-shadow: var(--shadow-card);
}

.stat-card__label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--text-soft);
  font-weight: 700;
}

.stat-card__value {
  font-size: clamp(28px, 4vw, 34px);
  font-weight: 700;
  line-height: 1;
}

.stat-card__hint {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.stat-card--teal {
  background: linear-gradient(180deg, rgba(47, 111, 237, 0.07), rgba(255, 255, 255, 0.96));
}

.stat-card--orange {
  background: linear-gradient(180deg, rgba(240, 90, 40, 0.09), rgba(255, 255, 255, 0.96));
}

.stat-card--berry {
  background: linear-gradient(180deg, rgba(208, 48, 80, 0.08), rgba(255, 255, 255, 0.96));
}
</style>
