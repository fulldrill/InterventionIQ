/**
 * Application-wide constants.
 * Proficiency threshold should match backend PROFICIENCY_THRESHOLD env var.
 */

// 70% proficiency threshold (school-configurable, default is 70%)
export const PROFICIENCY_THRESHOLD_PCT = 70;

// Intervention tier thresholds (percentage)
export const TIER_1_MIN_PCT = 85; // Enrichment
export const TIER_2_MIN_PCT = 60; // Strategic
// Below TIER_2_MIN_PCT = Tier 3 (Intensive)

// Small group suppression (must match backend SMALL_GROUP_SUPPRESSION_THRESHOLD)
export const SUPPRESSION_THRESHOLD = 5;

// Chart color palette (consistent across all charts)
export const CHART_COLORS = {
  proficient:   "#10B981", // Green
  approaching:  "#F59E0B", // Amber
  below:        "#EF4444", // Red
  suppressed:   "#D1D5DB", // Gray
  tier1:        "#10B981",
  tier2:        "#F59E0B",
  tier3:        "#EF4444",
  primary:      "#1E3A5F",
  accent:       "#2E86AB",
};
