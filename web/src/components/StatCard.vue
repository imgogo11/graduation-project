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
  border: 1px solid rgba(24, 50, 47, 0.08);
  background: var(--panel-strong);
  box-shadow: var(--shadow-card);
}

.stat-card__label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
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
  background: linear-gradient(180deg, rgba(11, 143, 140, 0.1), rgba(255, 255, 255, 0.9));
}

.stat-card--orange {
  background: linear-gradient(180deg, rgba(242, 140, 40, 0.12), rgba(255, 255, 255, 0.9));
}

.stat-card--berry {
  background: linear-gradient(180deg, rgba(185, 82, 79, 0.12), rgba(255, 255, 255, 0.9));
}
</style>
