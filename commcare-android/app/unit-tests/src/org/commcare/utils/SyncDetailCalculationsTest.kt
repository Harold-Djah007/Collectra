package org.commcare.utils

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncDetailCalculationsTest {
    @Test
    fun `long offline thresholds are not capped at twenty five days`() {
        val day = 86400000L
        assertFalse(SyncDetailCalculations.timeLimitExceeded(day, 30 * day, "30"))
        assertFalse(SyncDetailCalculations.timeLimitExceeded(day, 31 * day, "30"))
        assertTrue(SyncDetailCalculations.timeLimitExceeded(day, 31 * day + 1, "30"))
    }

    @Test
    fun `invalid profile thresholds fall back to five`() {
        for (value in listOf(null, "", "invalid", "-1", "NaN", "Infinity", "-Infinity")) {
            assertEquals(5.0, SyncDetailCalculations.parseWarningLimit(value), 0.0)
        }
    }

    @Test
    fun `fractional days and zero thresholds are preserved`() {
        assertEquals(0.0, SyncDetailCalculations.parseWarningLimit("0"), 0.0)
        assertFalse(SyncDetailCalculations.timeLimitExceeded(1, 43200001L, "0.5"))
        assertTrue(SyncDetailCalculations.timeLimitExceeded(1, 43200002L, "0.5"))
        assertFalse(SyncDetailCalculations.timeLimitExceeded(100, 99, "0"))
    }
}
