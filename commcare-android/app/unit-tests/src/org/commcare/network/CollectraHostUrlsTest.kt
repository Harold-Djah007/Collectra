package org.commcare.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.net.URI

class CollectraHostUrlsTest {
    @Test
    fun `blank build config is treated as unconfigured`() {
        // Unit tests compile with an empty COLLECTRA_HQ_BASE_URL by default.
        assertFalse(CollectraHostUrls.isConfigured())
        assertNull(CollectraHostUrls.getConfiguredHost())
        assertTrue(CollectraHostUrls.getServerUpUrl().endsWith("/serverup.txt"))
    }

    @Test
    fun `host is parsed from absolute base URLs`() {
        assertEquals(
            "collectra.example.com",
            URI("https://collectra.example.com").host,
        )
        assertEquals(
            "192.168.1.195",
            URI("http://192.168.1.195:8000").host,
        )
    }
}
