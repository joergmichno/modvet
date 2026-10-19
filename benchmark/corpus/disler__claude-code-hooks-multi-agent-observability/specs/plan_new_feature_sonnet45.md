# Implementation Plan: UI Themes, 10-Minute Time Span, and Regex Search Bar

**Created:** 2025-10-17
**Run Name:** sonnet45
**Status:** Planning Phase

---

## 1. Problem Statement and Objectives

### Requirements
The user has requested three distinct feature additions to the Claude Code Multi-Agent Observability system:

1. **Add 3 new UI themes** to expand the visual customization options
2. **Add a 10-minute live activity pulse time span** to allow users to view longer periods of agent activity
3. **Add a regex-enabled frontend search bar** for filtering the agent event stream, positioned full-width directly below the agent/app tags

### Success Criteria
- Three new, visually distinct and accessible themes are available in the theme manager
- Users can select "10m" as a time range option in the Live Activity Pulse chart
- Users can filter events in real-time using regex patterns via a search bar positioned below agent tags
- All features work seamlessly with existing functionality
- No performance degradation in the event stream or chart rendering
- Regex search validation prevents invalid patterns from crashing the UI

---

## 2. Technical Approach and Architecture

### Current Architecture Overview

**Theme System:**
- Uses CSS custom properties defined in `apps/client/src/styles/themes.css`
- Theme definitions in `apps/client/src/composables/useThemes.ts` (PREDEFINED_THEMES object)
- Type definitions in `apps/client/src/types/theme.ts`
- Currently supports 9 themes: light, dark, modern, earth, glass, high-contrast, dark-blue, colorblind-friendly, ocean
- Each theme includes 24+ color properties covering primary, background, text, border, accent, shadow, and interactive states

**Time Range System:**
- Implemented in `apps/client/src/components/LivePulseChart.vue`
- Current time ranges: ['1m', '3m', '5m']
- Uses `useChartData` composable for data aggregation
- TimeRange type defined in types file

**Event Stream:**
- Located in `apps/client/src/components/EventTimeline.vue`
- Agent/app tags displayed at lines 9-30
- Currently uses basic filter system via FilterPanel.vue
- No text search capability exists

### Architecture Decisions

#### Feature 1: Three New UI Themes
**Decision:** Add "sunset", "cyberpunk", and "forest" themes following existing pattern

**Rationale:**
- **Sunset Theme**: Warm gradient palette (orange/pink/purple) for a calming, creative atmosphere
- **Cyberpunk Theme**: High-contrast neon colors (purple/cyan/magenta) on dark backgrounds for futuristic aesthetic
- **Forest Theme**: Natural green palette with earthy accents for a nature-inspired look

**Design Considerations:**
- Ensure WCAG 2.1 Level AA contrast ratios (4.5:1 for text, 3:1 for UI components)
- Maintain consistency with existing theme structure (all 24+ color properties)
- Test with existing components to ensure visual harmony

#### Feature 2: 10-Minute Time Span
**Decision:** Add '10m' to the existing time range array

**Rationale:**
- Simple addition that follows existing pattern
- Useful for monitoring longer-running agent sessions
- No changes to underlying data structure needed
- Chart rendering already handles variable time windows

**Implementation Notes:**
- Update timeRanges array in LivePulseChart.vue
- Adjust aria-label text to include "10 minutes" option
- Verify bucket/aggregation logic handles 10-minute window correctly
- May need to adjust chart bar width/spacing for increased data points

#### Feature 3: Regex-Enabled Search Bar
**Decision:** Create new SearchBar component with regex validation and error handling

**Component Location:** `apps/client/src/components/EventSearchBar.vue`

**Architecture:**
- Frontend-only filtering (no backend changes)
- Real-time filtering as user types (with debouncing)
- Regex validation to catch syntax errors
- Search across multiple event fields: source_app, session_id, hook_event_type, and event data
- Visual error indication for invalid regex patterns
- Clear button to reset search
- Position: Full width, between agent tags row and event list

**Data Flow:**
```
User Input → Debounce (300ms) → Regex Validation →
  Valid: Apply Filter to Events → Update Display
  Invalid: Show Error Message, Disable Filtering
```

**Search Fields:**
- `source_app`: Source application name
- `session_id`: Session identifier
- `hook_event_type`: Event type (e.g., tool_use, request_start)
- Event data: Stringified JSON for deep searching

---

## 3. Step-by-Step Implementation Guide

### Phase 1: Add Three New UI Themes

#### Step 1.1: Update Type Definitions
**File:** `apps/client/src/types/theme.ts`

**Action:** Update the `ThemeName` type to include new themes
```typescript
// Line 3 - Update ThemeName type
export type ThemeName = 'light' | 'dark' | 'modern' | 'earth' | 'glass' |
  'high-contrast' | 'dark-blue' | 'colorblind-friendly' | 'ocean' |
  'sunset' | 'cyberpunk' | 'forest';
```

**Action:** Update PREDEFINED_THEME_NAMES array
```typescript
// Line 179 - Add new theme names to array
export const PREDEFINED_THEME_NAMES: ThemeName[] = [
  'light', 'dark', 'modern', 'earth', 'glass', 'high-contrast',
  'dark-blue', 'colorblind-friendly', 'ocean',
  'sunset', 'cyberpunk', 'forest'
];
```

**Action:** Add metadata for new themes (optional but recommended for consistency)
```typescript
// After line 245, add metadata for new themes
sunset: {
  name: 'sunset' as ThemeName,
  displayName: 'Sunset',
  description: 'Warm gradient theme with orange, pink, and purple tones',
  cssClass: 'theme-sunset',
  category: 'vibrant',
  accessibility: 'standard',
},
// ... similar for cyberpunk and forest
```

#### Step 1.2: Define Theme Colors
**File:** `apps/client/src/composables/useThemes.ts`

**Action:** Add theme definitions to PREDEFINED_THEMES object (after line 314)

**Sunset Theme Colors:**
```typescript
sunset: {
  name: 'sunset',
  displayName: 'Sunset',
  description: 'Warm gradient theme with orange, pink, and purple tones',
  cssClass: 'theme-sunset',
  preview: { primary: '#fff5f0', secondary: '#ffd4a3', accent: '#ff6b35' },
  colors: {
    primary: '#ff6b35',           // Bright orange
    primaryHover: '#ff5722',      // Deeper orange
    primaryLight: '#ffccbc',      // Light peachy
    primaryDark: '#e64a19',       // Dark orange
    bgPrimary: '#fff5f0',         // Very light peach
    bgSecondary: '#ffe8d6',       // Light peach
    bgTertiary: '#ffd4a3',        // Peachy gold
    bgQuaternary: '#ffb88c',      // Light coral
    textPrimary: '#4a2c2a',       // Dark brown
    textSecondary: '#6d4c41',     // Medium brown
    textTertiary: '#8d6e63',      // Light brown
    textQuaternary: '#a1887f',    // Very light brown
    borderPrimary: '#ffd4a3',     // Peachy gold
    borderSecondary: '#ffb88c',   // Light coral
    borderTertiary: '#ff9966',    // Coral
    accentSuccess: '#66bb6a',     // Green
    accentWarning: '#ffa726',     // Amber
    accentError: '#e53935',       // Red
    accentInfo: '#ff6b35',        // Orange
    shadow: 'rgba(255, 107, 53, 0.15)',
    shadowLg: 'rgba(255, 107, 53, 0.3)',
    hoverBg: 'rgba(255, 107, 53, 0.08)',
    activeBg: 'rgba(255, 107, 53, 0.15)',
    focusRing: '#ff6b35'
  }
}
```

**Cyberpunk Theme Colors:**
```typescript
cyberpunk: {
  name: 'cyberpunk',
  displayName: 'Cyberpunk',
  description: 'Futuristic neon theme with purple, cyan, and magenta',
  cssClass: 'theme-cyberpunk',
  preview: { primary: '#0d0221', secondary: '#1a0b2e', accent: '#7b2cbf' },
  colors: {
    primary: '#7b2cbf',           // Neon purple
    primaryHover: '#9d4edd',      // Light purple
    primaryLight: '#c77dff',      // Very light purple
    primaryDark: '#5a189a',       // Dark purple
    bgPrimary: '#0d0221',         // Almost black
    bgSecondary: '#1a0b2e',       // Very dark purple
    bgTertiary: '#2d1b4e',        // Dark purple
    bgQuaternary: '#3c2a6d',      // Purple
    textPrimary: '#e0aaff',       // Light purple
    textSecondary: '#c77dff',     // Purple
    textTertiary: '#9d4edd',      // Medium purple
    textQuaternary: '#7b2cbf',    // Deep purple
    borderPrimary: '#3c2a6d',     // Purple
    borderSecondary: '#5a189a',   // Dark purple
    borderTertiary: '#7b2cbf',    // Neon purple
    accentSuccess: '#00f5d4',     // Neon cyan
    accentWarning: '#ffd60a',     // Neon yellow
    accentError: '#ff006e',       // Neon pink
    accentInfo: '#00b4d8',        // Cyan
    shadow: 'rgba(123, 44, 191, 0.5)',
    shadowLg: 'rgba(123, 44, 191, 0.8)',
    hoverBg: 'rgba(123, 44, 191, 0.2)',
    activeBg: 'rgba(123, 44, 191, 0.3)',
    focusRing: '#7b2cbf'
  }
}
```

**Forest Theme Colors:**
```typescript
forest: {
  name: 'forest',
  displayName: 'Forest',
  description: 'Natural theme with deep greens and earthy tones',
  cssClass: 'theme-forest',
  preview: { primary: '#f1f8f4', secondary: '#d4edda', accent: '#2d5016' },
  colors: {
    primary: '#2d5016',           // Dark forest green
    primaryHover: '#3d6b1f',      // Medium forest green
    primaryLight: '#a8d5ba',      // Light sage
    primaryDark: '#1a3409',       // Very dark green
    bgPrimary: '#f1f8f4',         // Very light mint
    bgSecondary: '#e8f5e9',       // Light mint
    bgTertiary: '#d4edda',        // Mint
    bgQuaternary: '#c3e6cb',      // Green tint
    textPrimary: '#1b3409',       // Very dark green
    textSecondary: '#2d5016',     // Dark green
    textTertiary: '#4a7c2c',      // Medium green
    textQuaternary: '#6b9e4d',    // Light green
    borderPrimary: '#c3e6cb',     // Green tint
    borderSecondary: '#a8d5ba',   // Light sage
    borderTertiary: '#81c784',    // Sage
    accentSuccess: '#4caf50',     // Green
    accentWarning: '#ff9800',     // Orange
    accentError: '#d32f2f',       // Red
    accentInfo: '#2d5016',        // Forest green
    shadow: 'rgba(45, 80, 22, 0.15)',
    shadowLg: 'rgba(45, 80, 22, 0.3)',
    hoverBg: 'rgba(45, 80, 22, 0.08)',
    activeBg: 'rgba(45, 80, 22, 0.15)',
    focusRing: '#2d5016'
  }
}
```

#### Step 1.3: Add CSS Theme Classes
**File:** `apps/client/src/styles/themes.css`

**Action:** Add CSS custom property definitions for each new theme (after line 374)

**Sunset Theme CSS:**
```css
/* Sunset theme - Warm gradient with orange, pink, and purple tones */
.theme-sunset {
  /* Primary colors */
  --theme-primary: #ff6b35;
  --theme-primary-hover: #ff5722;
  --theme-primary-light: #ffccbc;
  --theme-primary-dark: #e64a19;

  /* Background colors */
  --theme-bg-primary: #fff5f0;
  --theme-bg-secondary: #ffe8d6;
  --theme-bg-tertiary: #ffd4a3;
  --theme-bg-quaternary: #ffb88c;

  /* Text colors */
  --theme-text-primary: #4a2c2a;
  --theme-text-secondary: #6d4c41;
  --theme-text-tertiary: #8d6e63;
  --theme-text-quaternary: #a1887f;

  /* Border colors */
  --theme-border-primary: #ffd4a3;
  --theme-border-secondary: #ffb88c;
  --theme-border-tertiary: #ff9966;

  /* Accent colors */
  --theme-accent-success: #66bb6a;
  --theme-accent-warning: #ffa726;
  --theme-accent-error: #e53935;
  --theme-accent-info: #ff6b35;

  /* Shadow colors */
  --theme-shadow: rgba(255, 107, 53, 0.15);
  --theme-shadow-lg: rgba(255, 107, 53, 0.3);

  /* Interactive states */
  --theme-hover-bg: rgba(255, 107, 53, 0.08);
  --theme-active-bg: rgba(255, 107, 53, 0.15);
  --theme-focus-ring: #ff6b35;
}
```

**Cyberpunk Theme CSS:**
```css
/* Cyberpunk theme - Futuristic neon with purple, cyan, and magenta */
.theme-cyberpunk {
  /* Primary colors */
  --theme-primary: #7b2cbf;
  --theme-primary-hover: #9d4edd;
  --theme-primary-light: #c77dff;
  --theme-primary-dark: #5a189a;

  /* Background colors */
  --theme-bg-primary: #0d0221;
  --theme-bg-secondary: #1a0b2e;
  --theme-bg-tertiary: #2d1b4e;
  --theme-bg-quaternary: #3c2a6d;

  /* Text colors */
  --theme-text-primary: #e0aaff;
  --theme-text-secondary: #c77dff;
  --theme-text-tertiary: #9d4edd;
  --theme-text-quaternary: #7b2cbf;

  /* Border colors */
  --theme-border-primary: #3c2a6d;
  --theme-border-secondary: #5a189a;
  --theme-border-tertiary: #7b2cbf;

  /* Accent colors */
  --theme-accent-success: #00f5d4;
  --theme-accent-warning: #ffd60a;
  --theme-accent-error: #ff006e;
  --theme-accent-info: #00b4d8;

  /* Shadow colors */
  --theme-shadow: rgba(123, 44, 191, 0.5);
  --theme-shadow-lg: rgba(123, 44, 191, 0.8);

  /* Interactive states */
  --theme-hover-bg: rgba(123, 44, 191, 0.2);
  --theme-active-bg: rgba(123, 44, 191, 0.3);
  --theme-focus-ring: #7b2cbf;
}
```

**Forest Theme CSS:**
```css
/* Forest theme - Natural deep greens and earthy tones */
.theme-forest {
  /* Primary colors */
  --theme-primary: #2d5016;
  --theme-primary-hover: #3d6b1f;
  --theme-primary-light: #a8d5ba;
  --theme-primary-dark: #1a3409;

  /* Background colors */
  --theme-bg-primary: #f1f8f4;
  --theme-bg-secondary: #e8f5e9;
  --theme-bg-tertiary: #d4edda;
  --theme-bg-quaternary: #c3e6cb;

  /* Text colors */
  --theme-text-primary: #1b3409;
  --theme-text-secondary: #2d5016;
  --theme-text-tertiary: #4a7c2c;
  --theme-text-quaternary: #6b9e4d;

  /* Border colors */
  --theme-border-primary: #c3e6cb;
  --theme-border-secondary: #a8d5ba;
  --theme-border-tertiary: #81c784;

  /* Accent colors */
  --theme-accent-success: #4caf50;
  --theme-accent-warning: #ff9800;
  --theme-accent-error: #d32f2f;
  --theme-accent-info: #2d5016;

  /* Shadow colors */
  --theme-shadow: rgba(45, 80, 22, 0.15);
  --theme-shadow-lg: rgba(45, 80, 22, 0.3);

  /* Interactive states */
  --theme-hover-bg: rgba(45, 80, 22, 0.08);
  --theme-active-bg: rgba(45, 80, 22, 0.15);
  --theme-focus-ring: #2d5016;
}
```

#### Step 1.4: Verification Steps
1. Open theme manager in the app
2. Verify all three new themes appear in the theme list
3. Switch to each theme and verify:
   - All UI components update correctly
   - Text remains readable against backgrounds
   - Hover states work properly
   - Buttons and interactive elements are visible
4. Test theme persistence (refresh page, theme should remain)
5. Verify theme export/import functionality works with new themes

---

### Phase 2: Add 10-Minute Time Span

#### Step 2.1: Update Time Range Type (if needed)
**File:** `apps/client/src/types/index.ts` or similar types file

**Action:** Verify TimeRange type includes '10m' option
```typescript
export type TimeRange = '1m' | '3m' | '5m' | '10m';
```

#### Step 2.2: Update LivePulseChart Component
**File:** `apps/client/src/components/LivePulseChart.vue`

**Action:** Update timeRanges array (around line 123)
```typescript
const timeRanges: TimeRange[] = ['1m', '3m', '5m', '10m'];
```

**Action:** Update aria-label text (around line 20, 28, 36, 58)
- Add "10 minutes" option to conditional text
- Example: `timeRange === '10m' ? '10 minutes' : ...`

**Action:** Update tooltip text (around line 179)
```typescript
const chartAriaLabel = computed(() => {
  const rangeText = timeRange.value === '1m' ? '1 minute'
    : timeRange.value === '3m' ? '3 minutes'
    : timeRange.value === '5m' ? '5 minutes'
    : '10 minutes';
  return `Activity chart showing ${totalEventCount.value} events over the last ${rangeText}`;
});
```

#### Step 2.3: Verify Chart Data Handling
**File:** `apps/client/src/composables/useChartData.ts`

**Action:** Review the time window calculation logic
- Ensure bucket size calculations handle 10-minute window
- Verify data point aggregation works correctly
- May need to adjust `maxDataPoints` or bucket duration for 10m range

**Potential Changes:**
```typescript
// Adjust bucket size based on time range
const getBucketDuration = (timeRange: TimeRange): number => {
  switch (timeRange) {
    case '1m': return 1000; // 1 second buckets
    case '3m': return 3000; // 3 second buckets
    case '5m': return 5000; // 5 second buckets
    case '10m': return 10000; // 10 second buckets
    default: return 1000;
  }
};
```

#### Step 2.4: Verification Steps
1. Open the app and navigate to Live Activity Pulse chart
2. Verify "10m" button appears in time range selector
3. Click "10m" button and verify:
   - Chart updates to show 10-minute window
   - All metrics (agent count, event count, tool calls, avg gap) calculate correctly
   - Chart bars render properly (not too compressed or spaced)
   - Tooltips show correct time range text
4. Test switching between all time ranges (1m, 3m, 5m, 10m)
5. Verify chart performance remains smooth with 10-minute data window

---

### Phase 3: Add Regex-Enabled Search Bar

#### Step 3.1: Create Search Bar Component
**File:** `apps/client/src/components/EventSearchBar.vue`

**Component Structure:**
```vue
<template>
  <div class="w-full bg-gradient-to-r from-[var(--theme-bg-primary)] to-[var(--theme-bg-secondary)] px-3 py-3 mobile:px-2 mobile:py-2 border-t border-b border-[var(--theme-border-primary)] shadow-md">
    <div class="flex items-center gap-2 w-full">
      <!-- Search Icon -->
      <span class="text-2xl mobile:text-xl">🔍</span>

      <!-- Input Field -->
      <div class="flex-1 relative">
        <input
          v-model="searchQuery"
          @input="handleInput"
          type="text"
          placeholder="Search events (supports regex: e.g., 'tool.*use' or 'session_.*')"
          class="w-full px-4 py-2 mobile:px-3 mobile:py-1.5 text-base mobile:text-sm border rounded-lg transition-all duration-200"
          :class="[
            hasError
              ? 'border-[var(--theme-accent-error)] focus:ring-[var(--theme-accent-error)]/30 bg-red-50 dark:bg-red-900/20'
              : 'border-[var(--theme-primary)] focus:ring-[var(--theme-primary)]/30 bg-[var(--theme-bg-primary)]',
            'text-[var(--theme-text-primary)] focus:ring-2 focus:outline-none'
          ]"
          :aria-invalid="hasError"
          :aria-describedby="hasError ? 'search-error' : undefined"
        />

        <!-- Clear Button -->
        <button
          v-if="searchQuery"
          @click="clearSearch"
          class="absolute right-2 top-1/2 transform -translate-y-1/2 p-1 hover:bg-[var(--theme-hover-bg)] rounded transition-colors"
          title="Clear search"
          aria-label="Clear search"
        >
          <span class="text-lg">✕</span>
        </button>
      </div>

      <!-- Regex Toggle -->
      <button
        @click="toggleRegexMode"
        :class="[
          'px-3 py-2 mobile:px-2 mobile:py-1.5 rounded-lg font-bold text-sm mobile:text-xs transition-all duration-200 border shadow-md hover:shadow-lg',
          regexEnabled
            ? 'bg-[var(--theme-primary)] text-white border-[var(--theme-primary-dark)]'
            : 'bg-[var(--theme-bg-tertiary)] text-[var(--theme-text-primary)] border-[var(--theme-border-primary)]'
        ]"
        :title="regexEnabled ? 'Regex mode enabled' : 'Regex mode disabled (plain text search)'"
      >
        .*
      </button>

      <!-- Match Count Badge -->
      <div
        v-if="searchQuery && !hasError"
        class="px-3 py-2 mobile:px-2 mobile:py-1.5 bg-[var(--theme-primary)]/10 border border-[var(--theme-primary)]/30 rounded-lg text-sm mobile:text-xs font-bold text-[var(--theme-primary)]"
        :title="`${matchCount} events match your search`"
      >
        {{ matchCount }} match{{ matchCount !== 1 ? 'es' : '' }}
      </div>
    </div>

    <!-- Error Message -->
    <div
      v-if="hasError"
      id="search-error"
      class="mt-2 text-sm mobile:text-xs text-[var(--theme-accent-error)] font-medium"
      role="alert"
    >
      {{ errorMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { HookEvent } from '../types';

const props = defineProps<{
  events: HookEvent[];
  modelValue: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: string];
  'update:filteredEvents': [events: HookEvent[]];
}>();

// Component state
const searchQuery = ref(props.modelValue || '');
const regexEnabled = ref(true);
const hasError = ref(false);
const errorMessage = ref('');
const debounceTimer = ref<number | null>(null);

// Computed match count
const matchCount = computed(() => {
  if (!searchQuery.value || hasError.value) return 0;
  return filterEvents().length;
});

// Handle input with debouncing
const handleInput = () => {
  // Clear previous timer
  if (debounceTimer.value !== null) {
    clearTimeout(debounceTimer.value);
  }

  // Debounce search by 300ms
  debounceTimer.value = window.setTimeout(() => {
    validateAndFilter();
    emit('update:modelValue', searchQuery.value);
  }, 300);
};

// Validate regex pattern
const validateRegex = (pattern: string): { valid: boolean; error?: string } => {
  if (!pattern || !regexEnabled.value) {
    return { valid: true };
  }

  try {
    new RegExp(pattern, 'i'); // Case-insensitive by default
    return { valid: true };
  } catch (e) {
    return {
      valid: false,
      error: `Invalid regex pattern: ${(e as Error).message}`
    };
  }
};

// Filter events based on search query
const filterEvents = (): HookEvent[] => {
  if (!searchQuery.value) {
    return props.events;
  }

  try {
    if (regexEnabled.value) {
      const regex = new RegExp(searchQuery.value, 'i');
      return props.events.filter(event => {
        // Search across multiple fields
        const searchableText = [
          event.source_app,
          event.session_id,
          event.hook_event_type,
          JSON.stringify(event.hook_event_data || {})
        ].join(' ');

        return regex.test(searchableText);
      });
    } else {
      // Plain text search (case-insensitive)
      const query = searchQuery.value.toLowerCase();
      return props.events.filter(event => {
        const searchableText = [
          event.source_app,
          event.session_id,
          event.hook_event_type,
          JSON.stringify(event.hook_event_data || {})
        ].join(' ').toLowerCase();

        return searchableText.includes(query);
      });
    }
  } catch (e) {
    return props.events;
  }
};

// Validate and filter events
const validateAndFilter = () => {
  if (!searchQuery.value) {
    hasError.value = false;
    errorMessage.value = '';
    emit('update:filteredEvents', props.events);
    return;
  }

  const validation = validateRegex(searchQuery.value);

  if (!validation.valid) {
    hasError.value = true;
    errorMessage.value = validation.error || 'Invalid search pattern';
    // Don't filter when there's an error
    emit('update:filteredEvents', props.events);
  } else {
    hasError.value = false;
    errorMessage.value = '';
    const filtered = filterEvents();
    emit('update:filteredEvents', filtered);
  }
};

// Clear search
const clearSearch = () => {
  searchQuery.value = '';
  hasError.value = false;
  errorMessage.value = '';
  emit('update:modelValue', '');
  emit('update:filteredEvents', props.events);
};

// Toggle regex mode
const toggleRegexMode = () => {
  regexEnabled.value = !regexEnabled.value;
  validateAndFilter();
};

// Watch for external changes to modelValue
watch(() => props.modelValue, (newValue) => {
  if (newValue !== searchQuery.value) {
    searchQuery.value = newValue;
    validateAndFilter();
  }
});

// Watch for events changes (re-filter when events update)
watch(() => props.events, () => {
  if (searchQuery.value) {
    validateAndFilter();
  }
}, { deep: true });
</script>
```

#### Step 3.2: Integrate Search Bar into EventTimeline
**File:** `apps/client/src/components/EventTimeline.vue`

**Action:** Add import for EventSearchBar component (after line 68)
```typescript
import EventSearchBar from './EventSearchBar.vue';
```

**Action:** Add search state variables (after line 88)
```typescript
const searchQuery = ref('');
const searchFilteredEvents = ref<HookEvent[]>([]);
```

**Action:** Update filteredEvents computed property to include search filtering (around line 106)
```typescript
const filteredEvents = computed(() => {
  // First apply regular filters (source app, session, event type)
  const regularFiltered = props.events.filter(event => {
    if (props.filters.sourceApp && event.source_app !== props.filters.sourceApp) {
      return false;
    }
    if (props.filters.sessionId && event.session_id !== props.filters.sessionId) {
      return false;
    }
    if (props.filters.eventType && event.hook_event_type !== props.filters.eventType) {
      return false;
    }
    return true;
  });

  // Then apply search filter if search query exists
  if (searchQuery.value && searchFilteredEvents.value.length >= 0) {
    return searchFilteredEvents.value.filter(event => {
      // Ensure event passes regular filters too
      if (props.filters.sourceApp && event.source_app !== props.filters.sourceApp) {
        return false;
      }
      if (props.filters.sessionId && event.session_id !== props.filters.sessionId) {
        return false;
      }
      if (props.filters.eventType && event.hook_event_type !== props.filters.eventType) {
        return false;
      }
      return true;
    });
  }

  return regularFiltered;
});
```

**Action:** Add search bar component to template (after agent tags row, around line 31)
```vue
<!-- Search Bar (below Agent/App Tags) -->
<EventSearchBar
  v-model="searchQuery"
  :events="props.events"
  @update:filtered-events="searchFilteredEvents = $event"
  class="w-full"
/>
```

#### Step 3.3: Add Search Functionality to App.vue (Optional)
If you want to make the search state available at the app level for persistence or other features:

**File:** `apps/client/src/App.vue`

**Action:** Add search query state (around line 169)
```typescript
const searchQuery = ref('');
```

**Action:** Pass search query to EventTimeline (around line 97)
```vue
<EventTimeline
  :events="events"
  :filters="filters"
  :unique-app-names="uniqueAppNames"
  :all-app-names="allAppNames"
  v-model:stick-to-bottom="stickToBottom"
  v-model:search-query="searchQuery"
  @select-agent="toggleAgentLane"
/>
```

#### Step 3.4: Verification Steps
1. Open the app and navigate to the event stream
2. Verify search bar appears full-width below agent/app tags
3. Test plain text search:
   - Toggle regex mode off
   - Type "tool" and verify only events with "tool" in any field appear
   - Verify match count updates correctly
4. Test regex search:
   - Toggle regex mode on
   - Test pattern: `tool.*use` (should match "tool_use")
   - Test pattern: `session_[a-z]+` (should match session IDs with letters)
   - Test pattern: `(request|response)` (should match either word)
5. Test error handling:
   - Enter invalid regex: `[invalid`
   - Verify error message appears
   - Verify events are not filtered when error is shown
6. Test search with existing filters:
   - Set source app filter
   - Apply search query
   - Verify both filters work together correctly
7. Test clear button:
   - Enter search query
   - Click clear button
   - Verify all events reappear and input is cleared
8. Test search performance:
   - Load 1000+ events
   - Type rapidly in search box
   - Verify debouncing prevents excessive filtering
   - Verify no UI lag or freezing

---

## 4. Potential Challenges and Solutions

### Challenge 1: Theme Contrast and Accessibility
**Problem:** New themes may not meet WCAG contrast requirements.

**Solution:**
- Use contrast checker tools (e.g., WebAIM Contrast Checker) during color selection
- Test all text/background combinations
- Adjust colors if contrast ratio falls below 4.5:1 (text) or 3:1 (UI components)
- Add high-contrast variants if needed

### Challenge 2: Chart Performance with 10-Minute Window
**Problem:** 10-minute window may contain significantly more data points, potentially impacting rendering performance.

**Solution:**
- Implement adaptive bucket sizing (larger buckets for longer time ranges)
- Consider reducing maxDataPoints for 10m range
- Monitor frame rate during chart rendering
- Implement canvas optimization techniques (e.g., requestAnimationFrame throttling)

### Challenge 3: Regex Search Performance
**Problem:** Complex regex patterns on large event sets (1000+ events) may cause UI lag.

**Solution:**
- Implement debouncing (300ms delay) to reduce filter frequency
- Consider Web Workers for regex processing if performance issues persist
- Add maximum complexity check for regex patterns
- Provide user feedback when filtering large datasets ("Searching..." indicator)

### Challenge 4: Regex Error Messages
**Problem:** JavaScript regex error messages may not be user-friendly.

**Solution:**
- Parse common regex errors and provide clearer messages:
  - "Nothing to repeat" → "Invalid use of *, +, or ? operator"
  - "Unterminated character class" → "Missing closing bracket ]"
  - "Unmatched (" → "Missing closing parenthesis )"
- Provide example patterns in placeholder text
- Add help icon with regex syntax reference

### Challenge 5: Search Bar Layout on Mobile
**Problem:** Full-width search bar with multiple controls may be cramped on mobile devices.

**Solution:**
- Stack controls vertically on mobile (using mobile: breakpoint classes)
- Reduce padding and font sizes on mobile
- Consider hiding regex toggle on very small screens (show in overflow menu)
- Test on devices with screen width < 400px

### Challenge 6: Search Bar State Persistence
**Problem:** Search query resets when navigating away or refreshing.

**Solution:**
- Store search query in localStorage
- Restore query on component mount
- Add "Clear all filters and search" button for easy reset
- Consider adding search history (last 5 queries)

---

## 5. Testing Strategy

### Unit Tests

#### Theme Tests
**File:** `apps/client/src/composables/__tests__/useThemes.spec.ts`

**Test Cases:**
```typescript
describe('useThemes - New Themes', () => {
  it('should include sunset, cyberpunk, and forest in predefined themes', () => {
    const { predefinedThemes } = useThemes();
    const themeNames = predefinedThemes.value.map(t => t.name);
    expect(themeNames).toContain('sunset');
    expect(themeNames).toContain('cyberpunk');
    expect(themeNames).toContain('forest');
  });

  it('should apply sunset theme correctly', () => {
    const { setTheme } = useThemes();
    setTheme('sunset');
    expect(document.documentElement.classList.contains('theme-sunset')).toBe(true);
  });

  it('should have all required color properties for new themes', () => {
    const { predefinedThemes } = useThemes();
    const newThemes = predefinedThemes.value.filter(t =>
      ['sunset', 'cyberpunk', 'forest'].includes(t.name)
    );

    newThemes.forEach(theme => {
      expect(theme.colors).toHaveProperty('primary');
      expect(theme.colors).toHaveProperty('bgPrimary');
      expect(theme.colors).toHaveProperty('textPrimary');
      // ... check all required properties
    });
  });
});
```

#### Time Range Tests
**File:** `apps/client/src/composables/__tests__/useChartData.spec.ts`

**Test Cases:**
```typescript
describe('useChartData - 10 Minute Range', () => {
  it('should handle 10m time range', () => {
    const { setTimeRange, timeRange } = useChartData();
    setTimeRange('10m');
    expect(timeRange.value).toBe('10m');
  });

  it('should calculate correct bucket duration for 10m', () => {
    const { setTimeRange, getBucketDuration } = useChartData();
    setTimeRange('10m');
    const duration = getBucketDuration();
    expect(duration).toBe(10000); // 10 seconds
  });

  it('should aggregate data correctly over 10 minute window', () => {
    const { setTimeRange, addEvent, getChartData } = useChartData();
    setTimeRange('10m');

    // Add events spanning 10 minutes
    const now = Date.now();
    for (let i = 0; i < 10; i++) {
      addEvent(createMockEvent({ timestamp: now - (i * 60000) }));
    }

    const data = getChartData();
    expect(data.length).toBeGreaterThan(0);
    // Verify all events are captured
  });
});
```

#### Search Bar Tests
**File:** `apps/client/src/components/__tests__/EventSearchBar.spec.ts`

**Test Cases:**
```typescript
describe('EventSearchBar', () => {
  it('should filter events with plain text search', async () => {
    const wrapper = mount(EventSearchBar, {
      props: {
        events: mockEvents,
        modelValue: ''
      }
    });

    await wrapper.find('input').setValue('tool_use');
    await wrapper.vm.$nextTick();

    // Wait for debounce
    await new Promise(resolve => setTimeout(resolve, 400));

    const emitted = wrapper.emitted('update:filteredEvents');
    expect(emitted).toBeTruthy();
    expect(emitted![0][0].length).toBeLessThan(mockEvents.length);
  });

  it('should validate regex patterns', () => {
    const wrapper = mount(EventSearchBar, {
      props: { events: mockEvents, modelValue: '' }
    });

    const invalidPattern = '[invalid';
    wrapper.vm.searchQuery = invalidPattern;
    wrapper.vm.validateAndFilter();

    expect(wrapper.vm.hasError).toBe(true);
    expect(wrapper.vm.errorMessage).toContain('Invalid');
  });

  it('should handle regex mode toggle', async () => {
    const wrapper = mount(EventSearchBar, {
      props: { events: mockEvents, modelValue: '' }
    });

    expect(wrapper.vm.regexEnabled).toBe(true);

    await wrapper.find('[title*="Regex mode"]').trigger('click');
    expect(wrapper.vm.regexEnabled).toBe(false);
  });

  it('should clear search when clear button clicked', async () => {
    const wrapper = mount(EventSearchBar, {
      props: { events: mockEvents, modelValue: 'test' }
    });

    await wrapper.find('[aria-label="Clear search"]').trigger('click');

    expect(wrapper.vm.searchQuery).toBe('');
    expect(wrapper.emitted('update:modelValue')).toEqual([['']]);
  });
});
```

### Integration Tests

**Test Cases:**
1. **Theme Switching with Event Stream**
   - Load events → Switch themes → Verify all components update colors correctly

2. **10-Minute Chart with Live Data**
   - Set time range to 10m → Stream events for 10+ minutes → Verify chart scrolls and aggregates correctly

3. **Search + Filter Combination**
   - Apply source app filter → Apply search query → Verify both filters work together
   - Clear filters → Verify search still works independently

### Manual Testing Checklist

#### New Themes
- [ ] Sunset theme displays correctly on all components
- [ ] Cyberpunk theme displays correctly on all components
- [ ] Forest theme displays correctly on all components
- [ ] Text is readable on all backgrounds (check contrast)
- [ ] Hover states work on all interactive elements
- [ ] Theme persists after page refresh
- [ ] Theme export/import works with new themes
- [ ] Theme preview in ThemeManager shows correct colors

#### 10-Minute Time Span
- [ ] "10m" button appears in time range selector
- [ ] Chart displays 10 minutes of data correctly
- [ ] All metrics calculate correctly for 10m window
- [ ] Chart rendering performance is acceptable
- [ ] Switching between time ranges works smoothly
- [ ] Aria-labels include "10 minutes" text
- [ ] Tooltips show correct time range

#### Regex Search Bar
- [ ] Search bar appears full-width below agent tags
- [ ] Plain text search works (regex mode off)
- [ ] Regex search works (regex mode on)
- [ ] Match count displays correctly
- [ ] Error message appears for invalid regex
- [ ] Clear button removes search query
- [ ] Regex toggle button changes state
- [ ] Debouncing prevents excessive filtering
- [ ] Search works with existing filters
- [ ] Search bar is responsive on mobile
- [ ] Keyboard navigation works (tab, enter, escape)
- [ ] Screen reader announces errors and match counts

### Performance Testing

**Metrics to Monitor:**
1. **Theme Switching Performance**
   - Time to apply new theme: < 100ms
   - No visual flash or layout shift

2. **10-Minute Chart Performance**
   - Frame rate during rendering: ≥ 30 FPS
   - Memory usage: No significant increase compared to 5m

3. **Search Performance**
   - Time to filter 1000 events: < 200ms
   - Time to filter 10000 events: < 500ms
   - Debounce delay: 300ms (configurable)

**Load Testing:**
```typescript
// Generate large event dataset for testing
function generateMockEvents(count: number): HookEvent[] {
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    source_app: `app_${i % 10}`,
    session_id: `session_${i % 100}`,
    hook_event_type: 'tool_use',
    hook_event_data: { tool_name: `tool_${i % 20}` },
    timestamp: Date.now() - (i * 1000)
  }));
}

// Test search performance
console.time('Search 10k events');
const results = filterEvents(generateMockEvents(10000), /tool_use/);
console.timeEnd('Search 10k events');
// Expected: < 500ms
```

---

## 6. Success Criteria

### Feature 1: Three New UI Themes ✅
- [ ] Sunset, Cyberpunk, and Forest themes are available in ThemeManager
- [ ] All themes follow the existing 24+ color property structure
- [ ] Themes apply correctly to all UI components
- [ ] All text meets WCAG 2.1 Level AA contrast requirements (4.5:1)
- [ ] Theme switching is smooth with no visual glitches
- [ ] Themes persist across page refreshes
- [ ] Export/import functionality works with new themes

### Feature 2: 10-Minute Time Span ✅
- [ ] "10m" option appears in time range selector buttons
- [ ] Chart correctly displays 10 minutes of agent activity
- [ ] All metrics (agent count, events, tools, avg gap) calculate correctly for 10m window
- [ ] Chart rendering performance remains smooth (≥30 FPS)
- [ ] Time range labels and tooltips include "10 minutes" text
- [ ] Switching between time ranges (1m, 3m, 5m, 10m) works seamlessly

### Feature 3: Regex-Enabled Search Bar ✅
- [ ] Search bar appears full-width directly below agent/app tags
- [ ] Plain text search filters events correctly (regex mode off)
- [ ] Regex search filters events correctly (regex mode on)
- [ ] Invalid regex patterns show clear error messages
- [ ] Match count displays and updates in real-time
- [ ] Clear button removes search query and resets filter
- [ ] Regex mode toggle works and re-filters events
- [ ] Search works in combination with existing filters (source app, session, event type)
- [ ] Debouncing prevents excessive filtering (300ms delay)
- [ ] Search performance is acceptable with 1000+ events (< 500ms)
- [ ] Search bar is responsive and usable on mobile devices
- [ ] Keyboard navigation and screen reader support work correctly

### Overall Quality Criteria
- [ ] No console errors or warnings
- [ ] No breaking changes to existing functionality
- [ ] Code follows project conventions and style guide
- [ ] All files are properly typed (TypeScript)
- [ ] Documentation is updated (if applicable)
- [ ] No performance regressions in existing features

---

## 7. Implementation Timeline Estimate

**Phase 1: Three New UI Themes**
- Step 1.1 (Type definitions): 15 minutes
- Step 1.2 (Theme colors in composable): 45 minutes
- Step 1.3 (CSS theme classes): 45 minutes
- Step 1.4 (Testing and verification): 30 minutes
- **Phase 1 Total: ~2 hours**

**Phase 2: 10-Minute Time Span**
- Step 2.1 (Type updates): 5 minutes
- Step 2.2 (LivePulseChart updates): 20 minutes
- Step 2.3 (Chart data handling verification): 30 minutes
- Step 2.4 (Testing and verification): 20 minutes
- **Phase 2 Total: ~1.25 hours**

**Phase 3: Regex-Enabled Search Bar**
- Step 3.1 (Create EventSearchBar component): 2 hours
- Step 3.2 (Integrate into EventTimeline): 45 minutes
- Step 3.3 (Optional App.vue integration): 15 minutes
- Step 3.4 (Testing and verification): 1 hour
- **Phase 3 Total: ~4 hours**

**Testing and Refinement**
- Unit tests: 2 hours
- Integration tests: 1 hour
- Manual testing: 1 hour
- Performance testing and optimization: 1 hour
- **Testing Total: ~5 hours**

**Grand Total: ~12.25 hours**

---

## 8. Future Enhancements (Out of Scope)

These enhancements would further improve the features but are not required for the current implementation:

### Theme Enhancements
- Theme categories/tags for easier browsing
- Theme color customization UI (color picker for each property)
- Theme rating/favorites system
- Community theme sharing platform
- Dynamic theme generation based on uploaded image
- Automatic theme switching based on time of day

### Time Range Enhancements
- Custom time range input (e.g., "15m", "30m", "1h")
- Time range presets for different use cases
- Playback controls (pause, rewind, fast-forward)
- Time range bookmarks for specific periods

### Search Bar Enhancements
- Search history dropdown (last 10 searches)
- Saved search patterns (bookmarks)
- Search syntax highlighting in input field
- Advanced search options (case sensitivity, whole word, field-specific)
- Search result highlighting in event rows
- Export filtered events to JSON/CSV
- Search performance metrics display
- Multi-field search (separate queries for different fields)

---

## 9. Dependencies and Requirements

### Required Dependencies
All required dependencies are already present in the project:
- Vue 3.x (composition API)
- TypeScript 4.x+
- CSS custom properties support
- Canvas API support (for charts)
- ES6 RegExp support

### Browser Compatibility
- Modern browsers (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
- Mobile browsers (iOS Safari 14+, Chrome Mobile 90+)
- No IE11 support required

### Development Tools
- Vue DevTools (for debugging)
- Contrast checker (for accessibility testing)
- Browser DevTools performance profiler

---

## 10. Code Examples and Pseudo-Code

### Example: Regex Search Algorithm
```typescript
// Pseudo-code for regex search filtering
function filterEventsWithRegex(
  events: HookEvent[],
  pattern: string,
  regexEnabled: boolean
): HookEvent[] {
  // Early return if no search pattern
  if (!pattern) return events;

  try {
    if (regexEnabled) {
      // Create case-insensitive regex
      const regex = new RegExp(pattern, 'i');

      return events.filter(event => {
        // Concatenate all searchable fields
        const searchText = [
          event.source_app,
          event.session_id,
          event.hook_event_type,
          JSON.stringify(event.hook_event_data || {})
        ].join(' ');

        // Test regex against concatenated text
        return regex.test(searchText);
      });
    } else {
      // Plain text search (case-insensitive)
      const query = pattern.toLowerCase();

      return events.filter(event => {
        const searchText = [
          event.source_app,
          event.session_id,
          event.hook_event_type,
          JSON.stringify(event.hook_event_data || {})
        ].join(' ').toLowerCase();

        return searchText.includes(query);
      });
    }
  } catch (error) {
    // If regex compilation fails, return unfiltered events
    console.error('Regex error:', error);
    return events;
  }
}
```

### Example: Theme Color Contrast Check
```typescript
// Pseudo-code for checking color contrast
function checkContrast(textColor: string, bgColor: string): boolean {
  // Convert hex to RGB
  const textRGB = hexToRGB(textColor);
  const bgRGB = hexToRGB(bgColor);

  // Calculate relative luminance
  const textLuminance = calculateLuminance(textRGB);
  const bgLuminance = calculateLuminance(bgRGB);

  // Calculate contrast ratio
  const contrastRatio = (Math.max(textLuminance, bgLuminance) + 0.05) /
                        (Math.min(textLuminance, bgLuminance) + 0.05);

  // Check against WCAG AA standard (4.5:1 for normal text)
  return contrastRatio >= 4.5;
}
```

### Example: 10-Minute Bucket Calculation
```typescript
// Pseudo-code for calculating time buckets
function calculateBuckets(timeRange: TimeRange, maxBuckets: number = 60) {
  // Map time range to milliseconds
  const timeWindows = {
    '1m': 60 * 1000,
    '3m': 180 * 1000,
    '5m': 300 * 1000,
    '10m': 600 * 1000
  };

  const windowMs = timeWindows[timeRange];

  // Calculate bucket duration to fit maxBuckets
  const bucketDuration = windowMs / maxBuckets;

  // Create buckets
  const now = Date.now();
  const buckets = Array.from({ length: maxBuckets }, (_, i) => ({
    timestamp: now - ((maxBuckets - i) * bucketDuration),
    count: 0,
    events: []
  }));

  return { buckets, bucketDuration };
}
```

---

## 11. Documentation Updates

### Files to Update
1. **README.md** - Add screenshots of new themes and search feature
2. **CHANGELOG.md** - Document new features in version notes
3. **User Guide** (if exists) - Add sections for:
   - How to use new themes
   - How to use 10-minute time range
   - How to use regex search (with examples)

### Example Documentation Content

**README.md Addition:**
```markdown
## New Features (v1.2.0)

### Extended Theme Collection
We've added three new beautiful themes to our collection:
- **Sunset**: Warm gradient theme with orange, pink, and purple tones
- **Cyberpunk**: Futuristic neon theme with purple, cyan, and magenta
- **Forest**: Natural theme with deep greens and earthy tones

### 10-Minute Activity Window
You can now view up to 10 minutes of agent activity in the Live Pulse Chart,
perfect for monitoring longer-running agent sessions.

### Regex-Enabled Event Search
Filter events using powerful regex patterns or simple text search. The search
bar supports searching across all event fields including source app, session ID,
event type, and event data.

**Example Searches:**
- `tool_use` - Find all tool use events
- `session_[a-z]+` - Find sessions with letter-based IDs
- `(error|warning)` - Find events containing either error or warning
```

---

## End of Implementation Plan

This plan provides a comprehensive blueprint for implementing all three requested features. Each section can be followed independently, though it's recommended to implement in the order presented to ensure a logical progression and easier testing.

**Next Steps:**
1. Review this plan with the team
2. Create GitHub issues/tickets for each phase
3. Begin implementation with Phase 1 (Themes)
4. Conduct testing after each phase
5. Deploy features incrementally or as a bundled release

**Questions or Concerns:**
- Contact the development team for clarification
- Refer to existing codebase patterns and conventions
- Test early and often to catch issues
