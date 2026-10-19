# Implementation Plan: UI Themes, Live Activity Pulse, and Regex Search

## Problem Statement & Objectives

The observability dashboard requires three enhancements:

1. **Add 3 new UI themes** to expand visual customization options beyond the current 9 predefined themes
2. **Add 10-minute live activity pulse time span** to support longer observation windows while maintaining performance
3. **Add regex-enabled frontend search bar** for the agent event stream with full-width placement below agent/app tags to enable powerful event filtering

## Technical Approach & Architecture Decisions

### 1. New UI Themes

**Location**: `/apps/client/src/composables/useThemes.ts` and `/apps/client/src/types/theme.ts`

**Architecture Decision**:
- Add 3 new themes following the existing pattern (predefined color sets)
- Maintain consistency with current 24-color property structure (ThemeColors interface)
- Ensure accessibility standards (sufficient contrast ratios, colorblind-friendly considerations)
- Themes proposed:
  - **Midnight Purple**: Deep purples with neon accents (modern, low-light friendly)
  - **Sunset Orange**: Warm oranges and warm neutrals (high contrast, distinctive)
  - **Mint Fresh**: Cool mint greens with slate neutrals (calming, professional)

**Key Colors to Define**:
- Primary colors (4): base, hover, light, dark
- Backgrounds (4): primary, secondary, tertiary, quaternary
- Text (4): primary, secondary, tertiary, quaternary
- Borders (3): primary, secondary, tertiary
- Accents (4): success, warning, error, info
- Effects (4): shadow, shadowLg, hoverBg, activeBg
- Focus ring: 1
- **Total**: 24 properties per theme

**Implementation Steps**:
1. Define color palettes using hex values that meet WCAG AA contrast standards
2. Add to `PREDEFINED_THEMES` object in `useThemes.ts` with keys: `'midnight-purple'`, `'sunset-orange'`, `'mint-fresh'`
3. Ensure Tailwind safelist includes new theme class names
4. Update theme selector component to display new options
5. Test theme switching and persistence in localStorage

---

### 2. 10-Minute Live Activity Pulse Time Span

**Location**: `/apps/client/src/composables/useChartData.ts`

**Architecture Decision**:
- Add `'10m'` entry to `timeRangeConfig` object
- Use 10-second bucket size (consistent with granularity: 60 buckets × 10s = 600s)
- Implement dynamic button generation to support future time ranges
- Maintain backward compatibility with existing 1m, 3m, 5m ranges

**Performance Considerations**:
- 10-minute range = 60 data buckets (same as 1m with 1s buckets)
- WebSocket will maintain rolling 10-minute window in memory
- Chart canvas rendering remains efficient with fixed 60-point maximum

**Implementation Steps**:
1. Add to `timeRangeConfig`:
   ```typescript
   '10m': { duration: 10 * 60 * 1000, bucketSize: 10000, maxPoints: 60 }
   ```
2. Add button in `LivePulseChart.vue` component (line 50-60)
3. Update time range labels/descriptions for 10-minute display
4. Test data aggregation accuracy for 10-second buckets
5. Verify WebSocket memory usage doesn't spike with longer window

---

### 3. Regex-Enabled Frontend Search Bar

**Location**: `/apps/client/src/components/EventTimeline.vue` + new composable

**Architecture Decision**:
- Create new composable `useEventSearch.ts` for regex matching logic
- Add search input component as full-width bar below agent/app tags (line 31, after current tags section)
- Implement real-time filtering on client-side (no server roundtrip)
- Use Vue computed properties for reactive filtering
- Add regex validation and error display

**Search Scope** (what gets matched):
- Event type (tool call name)
- Tool command/arguments
- File paths
- Event summary text
- Session ID
- Source app name
- Model name

**User Experience**:
- Placeholder: `"Search events (regex enabled)..."`
- Visual feedback: highlight matching terms or show match count
- Error state: Display regex error message in red if pattern is invalid
- Clear button (X icon) to reset search
- Keyboard: Enter/Escape to focus/unfocus

**Implementation Steps**:
1. Create `useEventSearch.ts` composable:
   - `validateRegex(pattern: string): { valid: boolean, error?: string }`
   - `matchesPattern(event: HookEvent, pattern: string): boolean`
   - `searchEvents(events: HookEvent[], pattern: string): HookEvent[]`

2. Add to EventTimeline.vue:
   - New data properties: `searchPattern`, `searchError`, `showSearchError`
   - Computed: `filteredEvents` (combines existing filters + regex search)
   - Template: Insert search bar after agent tags section (full-width input)

3. Update event filtering logic:
   - Apply regex filter in addition to existing app/session/type filters
   - Order: existing filters first, then regex search (for performance)

4. Add styling:
   - Full-width container with appropriate padding/margins
   - Input styling matching theme system
   - Error message styling (red text, small font)
   - Focus state and transitions

5. Testing:
   - Test valid regex patterns (simple and complex)
   - Test invalid regex patterns (display error gracefully)
   - Test performance with large event streams
   - Test special characters and escaping

---

## Step-by-Step Implementation Guide

### Phase 1: Add New Themes (30 minutes)

**Step 1.1**: Define color palettes
- Research WCAG AA contrast requirements (4.5:1 for text, 3:1 for UI components)
- Define hex values for 3 new themes × 24 properties = 72 colors total

**Step 1.2**: Update `useThemes.ts`
- Add 3 theme definitions to `PREDEFINED_THEMES` object
- Ensure `applyPredefinedTheme()` function works with new themes
- Test localStorage persistence

**Step 1.3**: Update `tailwind.config.js`
- Add 3 new theme class names to safelist if not already included

**Step 1.4**: Update `ThemeManager.vue`
- Add 3 new themes to dropdown/selector (if dropdown exists)
- Display theme previews

**Step 1.5**: Test & validate
- Switch between all 12 themes (9 existing + 3 new)
- Verify colors render correctly
- Check accessibility with contrast checker

---

### Phase 2: Add 10-Minute Time Span (15 minutes)

**Step 2.1**: Update `useChartData.ts`
- Add `'10m'` to `timeRangeConfig` with 10-second bucket size

**Step 2.2**: Update `LivePulseChart.vue`
- Add button for `10m` time range
- Ensure button styling matches existing 1m, 3m, 5m buttons
- Update button styling/positioning if needed for 4 buttons

**Step 2.3**: Test & validate
- Click 10m button and verify events aggregate properly
- Check that 60 data points are maintained (10s × 60 = 10m)
- Monitor memory usage in browser DevTools

---

### Phase 3: Add Regex Search (60 minutes)

**Step 3.1**: Create `useEventSearch.ts`
```typescript
// Location: /apps/client/src/composables/useEventSearch.ts
export function useEventSearch() {
  // validateRegex(pattern): { valid, error? }
  // matchesPattern(event, pattern): boolean
  // searchEvents(events, pattern): HookEvent[]
}
```

**Step 3.2**: Update `EventTimeline.vue`
- Add data: `{ searchPattern: '', searchError: '' }`
- Add computed: `filteredEvents` that applies regex filter
- Add methods: `updateSearch()`, `clearSearch()`
- Import and use `useEventSearch()`

**Step 3.3**: Add search bar UI
- Insert full-width input below agent/app tags section
- Style with theme colors
- Add error message display
- Add clear (X) button

**Step 3.4**: Connect filtering logic
- Modify `computedEvents` or create new computed property
- Apply regex search after existing filters
- Handle regex compilation errors gracefully

**Step 3.5**: Test & validate
- Test simple patterns: `"tool"`, `"error"`, `"\.py$"`
- Test complex patterns: `"(tool|command)"`, `"[a-z]{3,}"`
- Test invalid patterns and verify error handling
- Test performance with 1000+ events
- Test clearing search
- Test across different themes

---

## Potential Challenges & Solutions

### Challenge 1: Regex Performance at Scale
**Problem**: Large event streams + complex regex patterns could cause UI lag
**Solution**:
- Debounce regex search by 300ms to avoid excessive recomputation
- Add computed property caching
- Consider limiting search scope to recent 1000 events if performance degrades
- Show "searching..." indicator during complex pattern matching

### Challenge 2: Theme Color Consistency
**Problem**: New themes might not work well with existing component styles
**Solution**:
- Use design system approach: validate all 24 color properties work together
- Test each theme with all component types (buttons, inputs, cards, tags, etc.)
- Create visual regression tests or screenshot comparisons

### Challenge 3: Regex Learning Curve
**Problem**: Users may not be familiar with regex syntax
**Solution**:
- Add placeholder hints: `"e.g., 'tool.*error' or '^GET'"`
- Show error messages with helpful context: `"Invalid regex at position X: ..."`
- Consider adding preset filters alongside regex (e.g., "Errors only", "Tool calls only")
- Add documentation/help text link

### Challenge 4: Accessibility for New Themes
**Problem**: New themes might have insufficient contrast
**Solution**:
- Use WCAG Color Contrast Checker during development
- Test with accessibility audits (axe, Lighthouse)
- Ensure all 4 text colors meet 4.5:1 contrast ratio minimum

### Challenge 5: WebSocket Memory with Longer Time Range
**Problem**: 10-minute buffer might consume more memory
**Solution**:
- Monitor memory usage during development
- Implement data pruning strategy if needed
- Use rolling window that discards events older than 10 minutes

---

## Testing Strategy

### Unit Tests

**Theme System**:
- `useThemes.ts`: Test `applyPredefinedTheme()` with all 12 themes
- Test `applyCustomTheme()` with new themes
- Test localStorage persistence

**Chart Data**:
- `useChartData.ts`: Test time range bucketing for '10m'
- Verify bucket size = 10000ms, max points = 60

**Search Composable**:
- `useEventSearch.ts`: Test `validateRegex()` with valid/invalid patterns
- Test `matchesPattern()` with various event types
- Test edge cases: empty patterns, special characters, escaped chars

### Integration Tests

**Theme Application**:
- Switch between themes
- Verify all UI components update colors
- Check persistence across page refresh

**Time Range**:
- Select 10m time range
- Generate events across full 10-minute window
- Verify chart displays all time buckets

**Search Filtering**:
- Enter regex pattern
- Verify events list updates immediately
- Clear search and verify all events return
- Test interaction with existing filters (app, type, etc.)

### E2E/Manual Tests

1. **Theme switching**:
   - Open app, switch to new theme
   - Reload page, verify theme persists
   - Check all colors render correctly
   - Test on mobile responsiveness

2. **Time range**:
   - Switch to 10m view
   - Monitor WebSocket connection (no errors)
   - Check chart memory usage reasonable

3. **Search functionality**:
   - Type simple pattern, verify filtering works
   - Type invalid regex, verify error displays
   - Type complex pattern, verify correct matches
   - Test with special characters (quotes, backslashes)
   - Test clearing search

---

## Success Criteria

✅ **Themes**:
- [ ] All 3 new themes render correctly
- [ ] Themes persist across page reloads
- [ ] All components styled properly with new colors
- [ ] WCAG AA contrast standards met
- [ ] No console errors when switching themes

✅ **10-Minute Time Span**:
- [ ] Button appears in LivePulseChart with other time ranges
- [ ] Data aggregates correctly with 10-second buckets
- [ ] Chart displays full 10-minute window
- [ ] Memory usage remains stable
- [ ] No performance degradation

✅ **Regex Search**:
- [ ] Search bar displays full-width below agent tags
- [ ] Valid regex patterns filter events correctly
- [ ] Invalid regex patterns show error message
- [ ] Clear button resets search
- [ ] Search works with existing filters (AND logic)
- [ ] Performance acceptable with 1000+ events
- [ ] Mobile-responsive layout

---

## Estimated Effort

| Component           | Effort          | Priority |
| ------------------- | --------------- | -------- |
| Add 3 themes        | 1-2 hours       | Medium   |
| 10-minute time span | 30 minutes      | Low      |
| Regex search bar    | 2-3 hours       | High     |
| **Total**           | **4-5.5 hours** | -        |

---

## Dependencies & Prerequisites

- Vue 3 composables knowledge
- Regex fundamentals
- Tailwind CSS variables system
- WebSocket data handling

## Files to Modify

1. `/apps/client/src/composables/useThemes.ts` - Add theme definitions
2. `/apps/client/src/types/theme.ts` - Update theme types if needed
3. `/apps/client/tailwind.config.js` - Update safelist if needed
4. `/apps/client/src/composables/useChartData.ts` - Add 10m config
5. `/apps/client/src/components/LivePulseChart.vue` - Add 10m button
6. `/apps/client/src/components/EventTimeline.vue` - Add search bar
7. **NEW**: `/apps/client/src/composables/useEventSearch.ts` - Create search logic

## Files to Create

- `/apps/client/src/composables/useEventSearch.ts` - Regex search composable
- Optionally: test files for new composable
